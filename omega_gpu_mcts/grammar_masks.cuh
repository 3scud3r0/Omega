#ifndef OMEGA_GRAMMAR_MASKS_CUH
#define OMEGA_GRAMMAR_MASKS_CUH
#include "tensor_mcts_types.h"
#include "../hardware/cuda/flat_ast_eval.cuh"
namespace omega_gpu {
constexpr uint16_t TOKEN_CONST=32,TOKEN_ADD=48,TOKEN_SUB=49,TOKEN_MUL=50,TOKEN_DIV=51,TOKEN_NEG=52,TOKEN_RELU=53;
struct GrammarMasks {
 uint64_t valid_next_token_mask[1]; // one non-terminal: a scalar rational
 uint64_t scope_mask;uint32_t priors[64];uint32_t prior_sum;
};
OMEGA_HD uint32_t arity(uint16_t token){return token>=TOKEN_ADD&&token<=TOKEN_DIV?2:token>=TOKEN_NEG&&token<=TOKEN_RELU?1:0;}
OMEGA_HD uint64_t grammar_mask(GrammarMasks g,uint32_t pending,uint32_t length,uint32_t maximum){
 if(!pending||length>=maximum)return 0;
 uint64_t mask=g.valid_next_token_mask[0]&g.scope_mask,result=0;
 for(uint32_t token=0;token<64;token++){
  uint32_t after=pending-1+arity(uint16_t(token));
  if((mask&(uint64_t(1)<<token))&&after<=maximum-length-1)result|=uint64_t(1)<<token;
 }
 return result;
}
OMEGA_HD uint64_t random_step(uint64_t &state){state+=0x9e3779b97f4a7c15ULL;uint64_t z=state;z=(z^(z>>30))*0xbf58476d1ce4e5b9ULL;z=(z^(z>>27))*0x94d049bb133111ebULL;return z^(z>>31);}
OMEGA_HD uint16_t choose_token(uint64_t mask,uint64_t &state){
 uint32_t count=0;for(unsigned t=0;t<64;t++)count+=bool(mask&(uint64_t(1)<<t));
 if(!count)return UINT16_MAX;uint32_t chosen=uint32_t(random_step(state)%count);
 for(uint16_t t=0;t<64;t++)if(mask&(uint64_t(1)<<t)){if(!chosen--)return t;}
 return UINT16_MAX;
}
OMEGA_HD uint8_t complete_prefix(uint16_t *tokens,uint32_t &length,uint32_t pending,GrammarMasks grammar,uint32_t maximum,uint64_t &random){
 while(pending){
  uint64_t mask=grammar_mask(grammar,pending,length,maximum);
  uint64_t atoms=mask&((uint64_t(1)<<TOKEN_ADD)-1);
  if(atoms&&(random_step(random)&3)!=0)mask=atoms;
  uint16_t token=choose_token(mask,random);if(token==UINT16_MAX)return INVALID;
  tokens[length++]=token;pending=pending-1+arity(token);
 }
 return OK;
}
// Prefix grammar is converted to a topologically ordered flat AST by indices.
OMEGA_HD uint8_t lower_prefix(const uint16_t *tokens,uint32_t length,uint32_t candidate,uint32_t stride,
 uint16_t *ops,int32_t *left,int32_t *right,uint32_t *counts,uint32_t *roots){
 if(!length||length>MAX_AST_TOKENS)return INVALID;
 uint32_t stack[MAX_AST_TOKENS],top=0,nodes=0;
 for(uint32_t j=length;j>0;j--){
  uint16_t token=tokens[j-1],op=0;int32_t l=-1,r=-1;uint32_t a=arity(token);
  if(token<32){op=VARIABLE;l=token;}
  else if(token<48){op=LITERAL;l=token-TOKEN_CONST;}
  else if(token<=TOKEN_RELU){
   if(top<a)return INVALID;l=int32_t(stack[--top]);if(a==2)r=int32_t(stack[--top]);
   op=token-TOKEN_ADD+ADD;
  }else return INVALID;
  uint64_t index=(uint64_t)nodes*stride+candidate;ops[index]=op;left[index]=l;right[index]=r;
  stack[top++]=nodes++;
 }
 if(top!=1)return INVALID;counts[candidate]=nodes;roots[candidate]=stack[0];return OK;
}
}
#endif
