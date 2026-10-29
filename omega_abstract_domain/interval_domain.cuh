#ifndef OMEGA_INTERVAL_DOMAIN_CUH
#define OMEGA_INTERVAL_DOMAIN_CUH
#include "../hardware/cuda/flat_ast_eval.cuh"
namespace omega_gpu {
struct RationalInterval { Rational64 lower,upper; };
struct IntervalResult { RationalInterval value;uint8_t error; };
OMEGA_HD bool valid_interval(RationalInterval x){return valid(x.lower)&&valid(x.upper)&&rat_compare(x.lower,x.upper)<=0;}
OMEGA_HD IntervalResult interval_failure(uint8_t e){return {{zero(),zero()},e};}
OMEGA_HD IntervalResult interval_add(RationalInterval a,RationalInterval b){
 if(!valid_interval(a)||!valid_interval(b))return interval_failure(INVALID);
 Checked lo=rat_add(a.lower,b.lower),hi=rat_add(a.upper,b.upper);
 return {{lo.value,hi.value},uint8_t(lo.error|hi.error)};
}
OMEGA_HD IntervalResult interval_neg(RationalInterval a){
 if(!valid_interval(a))return interval_failure(INVALID);
 return {{{-a.upper.num,a.upper.den},{-a.lower.num,a.lower.den}},OK};
}
OMEGA_HD IntervalResult interval_mul(RationalInterval a,RationalInterval b){
 if(!valid_interval(a)||!valid_interval(b))return interval_failure(INVALID);
 Checked products[4]={rat_mul(a.lower,b.lower),rat_mul(a.lower,b.upper),rat_mul(a.upper,b.lower),rat_mul(a.upper,b.upper)};
 Rational64 lo=products[0].value,hi=lo;
 for(unsigned i=0;i<4;i++){
  if(products[i].error)return interval_failure(products[i].error);
  if(rat_compare(products[i].value,lo)<0)lo=products[i].value;
  if(rat_compare(products[i].value,hi)>0)hi=products[i].value;
 }
 return {{lo,hi},OK};
}
OMEGA_HD IntervalResult interval_inverse(RationalInterval a){
 if(!valid_interval(a))return interval_failure(INVALID);
 if(a.lower.num<=0&&a.upper.num>=0)return interval_failure(ZERO_DIVISOR);
 Checked lo=rat_div({1,1},a.upper),hi=rat_div({1,1},a.lower);
 return {{lo.value,hi.value},uint8_t(lo.error|hi.error)};
}
OMEGA_HD IntervalResult interval_node(uint16_t op,RationalInterval a,RationalInterval b){
 if(!valid_interval(a))return interval_failure(INVALID);
 if(op==NEG)return interval_neg(a);
 if(op==RELU)return {{a.lower.num>0?a.lower:zero(),a.upper.num>0?a.upper:zero()},OK};
 if(op==ADD)return interval_add(a,b);
 if(op==MUL)return interval_mul(a,b);
 if(op==SUB){IntervalResult n=interval_neg(b);return n.error?n:interval_add(a,n.value);}
 if(op==DIV){IntervalResult n=interval_inverse(b);return n.error?n:interval_mul(a,n.value);}
 return interval_failure(INVALID);
}
OMEGA_HD uint8_t filter_candidate(const uint16_t *ops,const int32_t *left,const int32_t *right,
 const RationalInterval *inputs,const RationalInterval *limits,RationalInterval *scratch,
 const Rational64 *constants,const uint32_t *counts,const uint32_t *roots,EvalShape s,uint32_t candidate){
 if(!eval_shape_valid(s)||candidate>=s.candidates)return INVALID;
 uint32_t n=counts[candidate];if(!n||n>s.max_nodes)return INVALID;
 for(uint32_t i=0;i<n;i++){
  uint64_t index=(uint64_t)i*s.candidates+candidate;uint16_t op=ops[index];int32_t l=left[index],r=right[index];
  IntervalResult result=interval_failure(INVALID);
  if(op==LITERAL){if(l>=0&&uint32_t(l)<s.constants&&valid(constants[l]))result={{constants[l],constants[l]},OK};}
  else if(op==VARIABLE){if(l>=0&&uint32_t(l)<s.inputs&&valid_interval(inputs[l]))result={inputs[l],OK};}
  else if(l>=0&&uint32_t(l)<i&&(op==NEG||op==RELU||(r>=0&&uint32_t(r)<i))){
   result=interval_node(op,scratch[(uint64_t)l*s.candidates+candidate],op==NEG||op==RELU?RationalInterval{zero(),zero()}:scratch[(uint64_t)r*s.candidates+candidate]);
  }
  if(result.error)return result.error;scratch[(uint64_t)i*s.candidates+candidate]=result.value;
 }
 for(uint32_t k=0;k<s.outputs;k++){
  uint32_t ref=roots[(uint64_t)k*s.candidates+candidate];if(ref>=n||!valid_interval(limits[k]))return INVALID;
  RationalInterval x=scratch[(uint64_t)ref*s.candidates+candidate];
  if(rat_compare(x.lower,limits[k].lower)<0||rat_compare(x.upper,limits[k].upper)>0)return UNPROVED;
 }
 return OK;
}
#ifdef __CUDACC__
__global__ void verify_contract_invariants_kernel(const uint16_t *__restrict__ ast_nodes,
 const RationalInterval *__restrict__ precond_intervals,const RationalInterval *__restrict__ invariant_limits,
 uint8_t *__restrict__ is_admissible_mask,const int32_t *__restrict__ left,const int32_t *__restrict__ right,
 RationalInterval *__restrict__ scratch,const Rational64 *__restrict__ constants,
 const uint32_t *__restrict__ counts,const uint32_t *__restrict__ roots,uint8_t *__restrict__ errors,EvalShape shape);
#endif
}
#endif
