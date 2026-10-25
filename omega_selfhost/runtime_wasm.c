/* Checked i64 subset only: this is not a replacement for exact GMP rationals. */
#include <stdint.h>
#include <limits.h>
static void trap(void){__builtin_trap();}
int64_t omega_add(int64_t a,int64_t b){int64_t r;if(__builtin_add_overflow(a,b,&r))trap();return r;}
int64_t omega_sub(int64_t a,int64_t b){int64_t r;if(__builtin_sub_overflow(a,b,&r))trap();return r;}
int64_t omega_mul(int64_t a,int64_t b){int64_t r;if(__builtin_mul_overflow(a,b,&r))trap();return r;}
int64_t omega_div(int64_t a,int64_t b){if(!b || (a==INT64_MIN && b==-1) || a%b)trap();return a/b;}
int64_t omega_relu(int64_t a){return a>0?a:0;}
