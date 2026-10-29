#ifndef OMEGA_FLAT_AST_EVAL_CUH
#define OMEGA_FLAT_AST_EVAL_CUH
#include "rational_alu.cuh"
namespace omega_gpu {
enum Op : uint16_t { LITERAL=0,VARIABLE=1,ADD=2,SUB=3,MUL=4,DIV=5,NEG=6,RELU=7 };
struct EvalShape {
 uint32_t candidates,max_nodes,inputs,outputs,constants,examples;
 uint32_t first,count;
};
// Every node field is node-major [node,candidate], coalesced across programs.
// Scratch is [node,job], where job=(candidate-first)*examples+example.
OMEGA_HD Checked eval_node(uint16_t op,Rational64 a,Rational64 b){
 switch(op){
  case ADD:return rat_add(a,b);case SUB:return rat_sub(a,b);
  case MUL:return rat_mul(a,b);case DIV:return rat_div(a,b);
  case NEG:return rat_neg(a);
  case RELU:return valid(a)?Checked{a.num>0?a:zero(),OK}:failure(INVALID);
  default:return failure(INVALID);
 }
}
OMEGA_HD bool eval_shape_valid(EvalShape s){
 return s.candidates&&s.max_nodes&&s.max_nodes<=4096&&s.inputs<=32&&s.outputs&&s.outputs<=32&&
        s.constants<=64&&s.examples&&s.examples<=64&&s.first<=s.candidates&&s.count<=s.candidates-s.first;
}
OMEGA_HD uint8_t evaluate_job(const uint16_t *ops,const int32_t *left,const int32_t *right,
 const Rational64 *inputs,Rational64 *outputs,Rational64 *scratch,const Rational64 *constants,
 const uint32_t *counts,const uint32_t *roots,EvalShape s,uint32_t job,uint32_t *executed=nullptr){
 const uint32_t jobs=s.count*s.examples;
 if(!eval_shape_valid(s)||job>=jobs)return INVALID;
 const uint32_t c=s.first+job/s.examples,example=job%s.examples,n=counts[c];
 if(!n||n>s.max_nodes)return INVALID;
 for(uint32_t i=0;i<n;i++){
  if(executed)*executed=i+1;
  const uint64_t index=(uint64_t)i*s.candidates+c;
  uint16_t op=ops[index];int32_t l=left[index],r=right[index];Checked result=failure(INVALID);
  if(op==LITERAL){if(l>=0&&uint32_t(l)<s.constants)result={constants[l],OK};}
  else if(op==VARIABLE){if(l>=0&&uint32_t(l)<s.inputs)result={inputs[(uint64_t)example*s.inputs+l],OK};}
  else if(l>=0&&uint32_t(l)<i&&(op==NEG||op==RELU||(r>=0&&uint32_t(r)<i))){
   result=eval_node(op,scratch[(uint64_t)l*jobs+job],op==NEG||op==RELU?zero():scratch[(uint64_t)r*jobs+job]);
  }
  if(!valid(result.value))result.error|=INVALID;
  if(result.error)return result.error;
  scratch[(uint64_t)i*jobs+job]=result.value;
 }
 for(uint32_t k=0;k<s.outputs;k++){
  uint32_t ref=roots[(uint64_t)k*s.candidates+c];if(ref>=n)return INVALID;
  outputs[((uint64_t)c*s.examples+example)*s.outputs+k]=scratch[(uint64_t)ref*jobs+job];
 }
 return OK;
}
#ifdef __CUDACC__
__global__ void evaluate_flat_asts_kernel(
 const uint16_t *__restrict__ op_codes,const int32_t *__restrict__ left_child,
 const int32_t *__restrict__ right_child,const Rational64 *__restrict__ inputs,
 Rational64 *__restrict__ outputs,uint8_t *__restrict__ error_flags,
 Rational64 *__restrict__ scratch,const Rational64 *__restrict__ constants,
 const uint32_t *__restrict__ node_counts,const uint32_t *__restrict__ output_refs,EvalShape shape,uint64_t *evaluated_nodes);
#endif
}
#endif
