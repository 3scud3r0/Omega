#include <cuda_runtime.h>
#include "mcts_kernel.cuh"
namespace omega_gpu {
__global__ void initialize_tree(TensorMCTS tree){
 uint32_t i=blockIdx.x*blockDim.x+threadIdx.x,total=tree.forests*tree.capacity;
 if(i>=total)return;tree.parent_idx[i]=NO_NODE;tree.children_start[i]=0;tree.children_count[i]=0;
 tree.visit_count[i]=0;tree.total_value[i]={0,REWARD_SCALE};tree.edge_action_token[i]=UINT16_MAX;
 tree.prefix_length[i]=0;tree.pending_holes[i]=1;tree.expansion_state[i]=0;
 if(i%tree.capacity==0)tree.allocated[i/tree.capacity]=1;
}
__device__ uint32_t integer_sqrt(uint32_t n){uint32_t root=0;for(uint32_t bit=1u<<15;bit;bit>>=1){uint32_t x=root|bit;if((uint64_t)x*x<=n)root=x;}return root;}
__device__ Checked puct(TensorMCTS t,GrammarMasks g,uint32_t parent,uint32_t child){
 uint32_t visits=uint32_t(t.visit_count[child]),pv=uint32_t(t.visit_count[parent]);
 Checked exploit=rat_div(t.total_value[child],{int64_t(visits?visits:1),1});
 uint32_t prior=g.priors[t.edge_action_token[child]];
 Checked explore=rat_div({int64_t((uint64_t)prior*integer_sqrt(pv+1)),g.prior_sum},{int64_t(visits+1),1});
 if(exploit.error||explore.error)return failure(OVERFLOW);
 return rat_add(exploit.value,explore.value);
}
__global__ void select_puct(TensorMCTS t,GrammarMasks g,uint32_t *selected,uint32_t rollouts){
 uint32_t lane=threadIdx.x&31,warp=(blockIdx.x*blockDim.x+threadIdx.x)/32;
 if(warp>=rollouts)return;uint32_t current=(warp%t.forests)*t.capacity;
 for(uint32_t depth=0;depth<t.max_tokens;depth++){
  uint32_t count=t.children_count[current];if(!count||t.expansion_state[current]!=2)break;
  uint32_t best=NO_NODE;Rational64 score=zero();
  for(uint32_t i=lane;i<count;i+=32){uint32_t child=t.children_start[current]+i;Checked q=puct(t,g,current,child);
   if(!q.error&&(best==NO_NODE||rat_compare(q.value,score)>0||(rat_compare(q.value,score)==0&&child<best))){best=child;score=q.value;}}
  for(uint32_t offset=16;offset;offset>>=1){
   uint32_t other=__shfl_down_sync(0xffffffff,best,offset);
   Rational64 q={__shfl_down_sync(0xffffffff,(long long)score.num,offset),__shfl_down_sync(0xffffffff,(unsigned long long)score.den,offset)};
   if(lane+offset<32&&other!=NO_NODE&&(best==NO_NODE||rat_compare(q,score)>0||(rat_compare(q,score)==0&&other<best))){best=other;score=q;}
  }
  best=__shfl_sync(0xffffffff,best,0);if(best==NO_NODE)break;current=best;
 }
 if(lane==0)selected[warp]=current;
}
__device__ uint32_t reserve(uint32_t *allocated,uint32_t count,uint32_t capacity){
 uint32_t old=atomicAdd(allocated,0);
 while(old<=capacity&&count<=capacity-old){uint32_t observed=atomicCAS(allocated,old,old+count);if(observed==old)return old;old=observed;}
 return NO_NODE;
}
__global__ void expand_nodes(TensorMCTS t,GrammarMasks g,const uint32_t *selected,uint32_t rollouts){
 uint32_t job=blockIdx.x*blockDim.x+threadIdx.x;if(job>=rollouts)return;
 uint32_t node=selected[job];if(!t.pending_holes[node]||atomicCAS(&t.expansion_state[node],0,1)!=0)return;
 uint64_t mask=grammar_mask(g,t.pending_holes[node],t.prefix_length[node],t.max_tokens);uint32_t count=__popcll(mask);
 uint32_t forest=node/t.capacity,start=reserve(&t.allocated[forest],count,t.capacity);
 if(!count||start==NO_NODE){atomicExch(&t.expansion_state[node],0);return;}
 start+=forest*t.capacity;uint32_t index=0;
 for(uint16_t token=0;token<64;token++)if(mask&(uint64_t(1)<<token)){
  uint32_t child=start+index++;t.parent_idx[child]=node;t.edge_action_token[child]=token;
  uint32_t length=t.prefix_length[node];t.prefix_length[child]=length+1;t.pending_holes[child]=t.pending_holes[node]-1+arity(token);
  for(uint32_t i=0;i<length;i++)t.prefix_tokens[(uint64_t)i*t.forests*t.capacity+child]=t.prefix_tokens[(uint64_t)i*t.forests*t.capacity+node];
  t.prefix_tokens[(uint64_t)length*t.forests*t.capacity+child]=token;
 }
 t.children_start[node]=start;t.children_count[node]=uint16_t(count);__threadfence();atomicExch(&t.expansion_state[node],2);
}
__global__ void generate_rollouts(TensorMCTS t,GrammarMasks g,uint32_t *selected,uint32_t rollouts,uint32_t iteration,
 uint64_t seed,uint16_t *ops,int32_t *left,int32_t *right,uint32_t *counts,uint32_t *roots,uint32_t candidates,uint8_t *errors,
 uint16_t *candidate_tokens,uint16_t *candidate_lengths){
 uint32_t job=blockIdx.x*blockDim.x+threadIdx.x;if(job>=rollouts)return;
 uint32_t c=iteration*rollouts+job,node=selected[job];uint64_t random=seed^((uint64_t)c*0xd1342543de82ef95ULL);
 if(t.expansion_state[node]==2&&t.children_count[node])node=t.children_start[node]+random_step(random)%t.children_count[node];
 selected[job]=node;uint16_t tokens[MAX_AST_TOKENS];uint32_t length=t.prefix_length[node];
 for(uint32_t i=0;i<length;i++)tokens[i]=t.prefix_tokens[(uint64_t)i*t.forests*t.capacity+node];
 uint8_t error=complete_prefix(tokens,length,t.pending_holes[node],g,t.max_tokens,random);
 if(!error)error=lower_prefix(tokens,length,c,candidates,ops,left,right,counts,roots);
 if(error)counts[c]=0;candidate_lengths[c]=uint16_t(error?0:length);errors[c]=error;
 for(uint32_t i=0;i<length&&!error;i++)candidate_tokens[(uint64_t)i*candidates+c]=tokens[i];
}
__global__ void reward_backprop(TensorMCTS t,const uint32_t *selected,uint32_t rollouts,uint32_t iteration,
 const Rational64 *values,const Rational64 *targets,const uint8_t *errors,uint32_t examples,uint32_t *rewards){
 uint32_t job=blockIdx.x*blockDim.x+threadIdx.x;if(job>=rollouts)return;uint32_t c=iteration*rollouts+job;Checked loss={zero(),OK};
 for(uint32_t e=0;e<examples;e++){
  if(errors[(uint64_t)c*examples+e]){loss.error=INVALID;break;}
  Checked d=rat_sub(values[(uint64_t)c*examples+e],targets[e]);if(d.error){loss.error=d.error;break;}
  d=rat_abs(d.value);loss=rat_add(loss.value,d.value);if(loss.error)break;
 }
 uint32_t reward=0;
 if(!loss.error){unsigned __int128 n=(unsigned __int128)loss.value.den*REWARD_SCALE;
  unsigned __int128 d=(unsigned __int128)loss.value.den+uint64_t(loss.value.num);reward=uint32_t(n/d);}
 rewards[c]=reward;
 for(uint32_t node=selected[job],depth=0;node!=NO_NODE&&depth<=t.max_tokens;node=t.parent_idx[node],depth++){
  atomicAdd(&t.visit_count[node],1.0f);
  // Fixed denominator and bounded nonnegative rewards make the numerator an
  // exact integer atomic reduction. A pair of independent rational writes
  // would be unsound. Host limits keep totals below INT64_MAX and visits 2^24.
  atomicAdd(reinterpret_cast<unsigned long long*>(&t.total_value[node].num),(unsigned long long)reward);
 }
}
__global__ void select_elites(const uint8_t *admissible,const uint8_t *errors,const uint32_t *rewards,
 const uint16_t *tokens,const uint16_t *lengths,uint32_t candidates,uint32_t requested,Elite *out,uint32_t *count,uint64_t *survivors){
 if(blockIdx.x||threadIdx.x)return;*count=0;*survivors=0;
 for(uint32_t c=0;c<candidates;c++)if(admissible[c]&&!errors[c]&&lengths[c]){
  (*survivors)++;uint32_t rank=*count;
  if(rank==requested){if(rewards[c]<=out[rank-1].reward)continue;rank--;}
  while(rank&&rewards[c]>out[rank-1].reward){if(rank<requested)out[rank]=out[rank-1];rank--;}
  Elite entry={};entry.length=lengths[c];entry.reward=rewards[c];entry.candidate_index=c;entry.tier1_admissible=1;
  for(uint32_t i=0;i<entry.length;i++)entry.tokens[i]=tokens[(uint64_t)i*candidates+c];out[rank]=entry;
  if(*count<requested)(*count)++;
 }
}
}
