#include <cuda_runtime.h>
#include <algorithm>
#include <cstdio>
#include <cstring>
#include <stdexcept>
#include <vector>
#include "cuda_api.h"
#include "mcts_kernel.cuh"
using namespace omega_gpu;
namespace {
void checked(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
struct Arena {
 std::vector<void*> arrays;cudaStream_t stream=nullptr;cudaEvent_t start=nullptr,end=nullptr;
 Arena(){checked(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));checked(cudaEventCreate(&start));checked(cudaEventCreate(&end));}
 ~Arena(){if(stream)cudaStreamSynchronize(stream);for(void *p:arrays)cudaFree(p);if(start)cudaEventDestroy(start);if(end)cudaEventDestroy(end);if(stream)cudaStreamDestroy(stream);}
 template<class T>T *allocate(size_t count){T *p=nullptr;checked(cudaMalloc(&p,std::max<size_t>(1,count)*sizeof(T)));arrays.push_back(p);checked(cudaMemsetAsync(p,0,std::max<size_t>(1,count)*sizeof(T),stream));return p;}
 template<class T>T *upload(const T *host,size_t count){T *p=allocate<T>(count);if(count)checked(cudaMemcpyAsync(p,host,count*sizeof(T),cudaMemcpyHostToDevice,stream));return p;}
};
struct Pinned {
 Elite *data=nullptr;explicit Pinned(uint32_t count){checked(cudaHostAlloc(&data,count*sizeof(Elite),cudaHostAllocDefault));}
 ~Pinned(){if(data)cudaFreeHost(data);}
};
__global__ void join_errors(uint8_t *mask,uint8_t *filter_errors,const uint8_t *evaluation_errors,uint32_t count,uint32_t examples){
 uint32_t c=blockIdx.x*blockDim.x+threadIdx.x;if(c>=count)return;
 uint8_t status=filter_errors[c];for(uint32_t e=0;e<examples;e++)status|=evaluation_errors[(uint64_t)c*examples+e];
 filter_errors[c]=status;mask[c]=status==OK;
}
}
extern "C" int omega_cuda_available(){int count=0;cudaError_t e=cudaGetDeviceCount(&count);if(e!=cudaSuccess){cudaGetLastError();return 0;}return count;}
extern "C" int omega_cuda_search(SearchConfig c,GrammarMasks grammar,const Rational64 *constants,const Rational64 *inputs,
 const Rational64 *targets,const RationalInterval *input_bounds,const RationalInterval *output_bounds,Elite *elites,SearchStats *stats,char *message,uint32_t message_bytes){
 try {
  const uint64_t candidates=(uint64_t)c.rollouts*c.iterations,nodes=(uint64_t)c.forests*c.capacity;
  if(!stats||!elites||!message||!message_bytes||!c.forests||c.forests>128||c.capacity<64||c.capacity>65536||
     !c.rollouts||c.rollouts>4096||!c.iterations||c.iterations>4096||!c.max_tokens||c.max_tokens>MAX_AST_TOKENS||
     !c.examples||c.examples>64||c.variables>32||c.constants>16||!c.elites||c.elites>64||
     !candidates||candidates>1000000||candidates>=(1u<<24)||c.elites>(candidates+999)/1000||!grammar.prior_sum)
     throw std::runtime_error("Invalid fixed-capacity CUDA search configuration");
  if(!omega_cuda_available()){std::snprintf(message,message_bytes,"CUDA device unavailable; no host substitution");return 77;}
  // Account for all major arrays before allocating; reserve driver/workspace room.
  uint64_t bytes=nodes*(64+c.max_tokens*2)+candidates*(c.max_tokens*44+32+c.examples*17)+
                 (uint64_t)c.max_tokens*c.rollouts*c.examples*sizeof(Rational64)+16*1024*1024;
  size_t free_bytes=0,total_bytes=0;checked(cudaMemGetInfo(&free_bytes,&total_bytes));
  if(bytes>2ULL*1024*1024*1024||bytes>free_bytes*3/4)throw std::runtime_error("VRAM budget exceeded before allocation");
  Arena a;TensorMCTS tree={};tree.forests=c.forests;tree.capacity=c.capacity;tree.max_tokens=c.max_tokens;
  tree.parent_idx=a.allocate<uint32_t>(nodes);tree.children_start=a.allocate<uint32_t>(nodes);tree.children_count=a.allocate<uint16_t>(nodes);
  tree.visit_count=a.allocate<float>(nodes);tree.total_value=a.allocate<Rational64>(nodes);tree.edge_action_token=a.allocate<uint16_t>(nodes);
  tree.prefix_tokens=a.allocate<uint16_t>(nodes*c.max_tokens);tree.prefix_length=a.allocate<uint16_t>(nodes);tree.pending_holes=a.allocate<uint16_t>(nodes);
  tree.expansion_state=a.allocate<uint32_t>(nodes);tree.allocated=a.allocate<uint32_t>(c.forests);
  auto d_constants=a.upload(constants,c.constants),d_inputs=a.upload(inputs,(uint64_t)c.examples*c.variables),d_targets=a.upload(targets,c.examples);
  auto bounds=a.upload(input_bounds,c.variables),limits=a.upload(output_bounds,1);
  auto ops=a.allocate<uint16_t>(candidates*c.max_tokens);auto left=a.allocate<int32_t>(candidates*c.max_tokens),right=a.allocate<int32_t>(candidates*c.max_tokens);
  auto counts=a.allocate<uint32_t>(candidates),roots=a.allocate<uint32_t>(candidates),selected=a.allocate<uint32_t>(c.rollouts),rewards=a.allocate<uint32_t>(candidates);
  auto tokens=a.allocate<uint16_t>(candidates*c.max_tokens),lengths=a.allocate<uint16_t>(candidates);
  auto generation_errors=a.allocate<uint8_t>(candidates),evaluation_errors=a.allocate<uint8_t>(candidates*c.examples);
  auto interval_errors=a.allocate<uint8_t>(candidates),mask=a.allocate<uint8_t>(candidates);
  auto values=a.allocate<Rational64>(candidates*c.examples),scratch=a.allocate<Rational64>((uint64_t)c.max_tokens*c.rollouts*c.examples);
  auto intervals=a.allocate<RationalInterval>(candidates*c.max_tokens);auto output=a.allocate<Elite>(c.elites);
  auto elite_count=a.allocate<uint32_t>(1);auto survivors=a.allocate<uint64_t>(1);auto evaluated_nodes=a.allocate<uint64_t>(1);
  initialize_tree<<<(nodes+255)/256,256,0,a.stream>>>(tree);checked(cudaGetLastError());
  checked(cudaEventRecord(a.start,a.stream));
  EvalShape shape={uint32_t(candidates),c.max_tokens,c.variables,1,c.constants,c.examples,0,c.rollouts};
  for(uint32_t iteration=0;iteration<c.iterations;iteration++){
   select_puct<<<(c.rollouts*32+127)/128,128,0,a.stream>>>(tree,grammar,selected,c.rollouts);
   expand_nodes<<<(c.rollouts+127)/128,128,0,a.stream>>>(tree,grammar,selected,c.rollouts);
   generate_rollouts<<<(c.rollouts+127)/128,128,0,a.stream>>>(tree,grammar,selected,c.rollouts,iteration,c.seed,
        ops,left,right,counts,roots,uint32_t(candidates),generation_errors,tokens,lengths);
   shape.first=iteration*c.rollouts;
   evaluate_flat_asts_kernel<<<(c.rollouts*c.examples+127)/128,128,0,a.stream>>>(ops,left,right,d_inputs,values,evaluation_errors,scratch,d_constants,counts,roots,shape,evaluated_nodes);
   reward_backprop<<<(c.rollouts+127)/128,128,0,a.stream>>>(tree,selected,c.rollouts,iteration,values,d_targets,evaluation_errors,c.examples,rewards);
   checked(cudaGetLastError());
  }
  shape.first=0;shape.count=uint32_t(candidates);
  verify_contract_invariants_kernel<<<(candidates+127)/128,128,0,a.stream>>>(ops,bounds,limits,mask,left,right,intervals,d_constants,counts,roots,interval_errors,shape);
  join_errors<<<(candidates+127)/128,128,0,a.stream>>>(mask,interval_errors,evaluation_errors,uint32_t(candidates),c.examples);
  select_elites<<<1,1,0,a.stream>>>(mask,interval_errors,rewards,tokens,lengths,uint32_t(candidates),c.elites,output,elite_count,survivors);
  checked(cudaGetLastError());checked(cudaEventRecord(a.end,a.stream));
  Pinned pinned(c.elites);checked(cudaMemcpyAsync(pinned.data,output,c.elites*sizeof(Elite),cudaMemcpyDeviceToHost,a.stream));
  checked(cudaMemcpyAsync(&stats->elite_count,elite_count,sizeof(uint32_t),cudaMemcpyDeviceToHost,a.stream));
  checked(cudaMemcpyAsync(&stats->tier1_survivors,survivors,sizeof(uint64_t),cudaMemcpyDeviceToHost,a.stream));
  checked(cudaMemcpyAsync(&stats->nodes_evaluated,evaluated_nodes,sizeof(uint64_t),cudaMemcpyDeviceToHost,a.stream));
  checked(cudaStreamSynchronize(a.stream));checked(cudaEventElapsedTime(&stats->elapsed_ms,a.start,a.end));
  std::memcpy(elites,pinned.data,c.elites*sizeof(Elite));stats->candidates=candidates;
  std::snprintf(message,message_bytes,"ok");return 0;
 }catch(const std::exception &error){if(message&&message_bytes)std::snprintf(message,message_bytes,"%s",error.what());return 1;}
}
