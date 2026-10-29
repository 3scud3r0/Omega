#include "flat_ast_eval.cuh"
using namespace omega_gpu;
extern "C" {
uint64_t omega_host_gcd(uint64_t a,uint64_t b){return binary_gcd_stein(a,b);}
int omega_host_rational(int op,Rational64 a,Rational64 b,Rational64 *out){
 if(!out)return INVALID;Checked x=eval_node(uint16_t(op),a,b);*out=x.value;return x.error;
}
int omega_host_prune(Rational64 a,uint64_t cap,Rational64 *out,uint64_t *error_words){
 if(!out||!error_words)return INVALID;Pruned x=stern_brocot_prune(a,cap);*out=x.value;
 unsigned __int128 n=magnitude128(x.absolute_error.num);
 error_words[0]=uint64_t(n);error_words[1]=uint64_t(n>>64);
 error_words[2]=uint64_t(x.absolute_error.den);error_words[3]=uint64_t(x.absolute_error.den>>64);return x.error;
}
}
