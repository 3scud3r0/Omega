// Executable host checks of the shared arithmetic/AST/interval algorithms.
// This library is never labelled a CUDA execution or a GPU performance result.
#include "flat_ast_eval.cuh"
#include "../../omega_abstract_domain/interval_domain.cuh"
using namespace omega_gpu;
extern "C" {
int omega_host_evaluate(const uint16_t *ops,const int32_t *left,const int32_t *right,
 const Rational64 *inputs,Rational64 *outputs,Rational64 *scratch,const Rational64 *constants,
 const uint32_t *counts,const uint32_t *roots,uint8_t *errors,EvalShape s){
 if(!eval_shape_valid(s))return INVALID;
 for(uint32_t job=0;job<s.count*s.examples;job++)errors[(s.first+job/s.examples)*s.examples+job%s.examples]=
   evaluate_job(ops,left,right,inputs,outputs,scratch,constants,counts,roots,s,job);
 return OK;
}
int omega_host_filter(const uint16_t *ops,const int32_t *left,const int32_t *right,
 const RationalInterval *inputs,const RationalInterval *limits,RationalInterval *scratch,
 const Rational64 *constants,const uint32_t *counts,const uint32_t *roots,uint8_t *mask,uint8_t *errors,EvalShape s){
 if(!eval_shape_valid(s))return INVALID;
 for(uint32_t c=s.first;c<s.first+s.count;c++){
  errors[c]=filter_candidate(ops,left,right,inputs,limits,scratch,constants,counts,roots,s,c);
  mask[c]=errors[c]==OK;
 }
 return OK;
}
}
