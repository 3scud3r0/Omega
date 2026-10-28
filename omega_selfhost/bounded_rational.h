/* Fixed-storage exact rational arithmetic. Overflow is an error, never silent
   truncation. GCC/Clang __int128 is the explicitly required host primitive. */
#ifndef OMEGA_BOUNDED_RATIONAL_H
#define OMEGA_BOUNDED_RATIONAL_H
#include <stdint.h>
#include <limits.h>
typedef struct { int64_t numerator;uint64_t denominator; } omega_q64;
enum { OMEGA_Q_OK=0,OMEGA_Q_ZERO_DENOM=1,OMEGA_Q_OVERFLOW=2 };
static unsigned __int128 omega_abs128(__int128 value){return value<0?(unsigned __int128)(-(value+1))+1:(unsigned __int128)value;}
static unsigned __int128 omega_gcd128(unsigned __int128 a,unsigned __int128 b){while(b){unsigned __int128 r=a%b;a=b;b=r;}return a;}
static int omega_q64_make(omega_q64 *out,__int128 numerator,unsigned __int128 denominator){
 if(!out||!denominator)return OMEGA_Q_ZERO_DENOM;
 unsigned __int128 divisor=omega_gcd128(omega_abs128(numerator),denominator);
 if(!divisor){divisor=1;}
 unsigned __int128 magnitude=omega_abs128(numerator)/divisor;denominator/=divisor;
 if(magnitude>INT64_MAX||denominator>INT64_MAX)return OMEGA_Q_OVERFLOW;
 out->numerator=numerator<0?-(int64_t)magnitude:(int64_t)magnitude;
 out->denominator=(uint64_t)denominator;return OMEGA_Q_OK;
}
static int omega_q64_valid(omega_q64 q){return q.denominator>0&&q.denominator<=INT64_MAX&&q.numerator!=INT64_MIN;}
static int omega_q64_add(omega_q64 *out,omega_q64 a,omega_q64 b){
 if(!omega_q64_valid(a)||!omega_q64_valid(b))return OMEGA_Q_ZERO_DENOM;
 return omega_q64_make(out,(__int128)a.numerator*b.denominator+(__int128)b.numerator*a.denominator,(unsigned __int128)a.denominator*b.denominator);
}
static int omega_q64_mul(omega_q64 *out,omega_q64 a,omega_q64 b){
 if(!omega_q64_valid(a)||!omega_q64_valid(b))return OMEGA_Q_ZERO_DENOM;
 return omega_q64_make(out,(__int128)a.numerator*b.numerator,(unsigned __int128)a.denominator*b.denominator);
}
static int omega_q64_div(omega_q64 *out,omega_q64 a,omega_q64 b){
 if(!omega_q64_valid(a)||!omega_q64_valid(b)||!b.numerator)return OMEGA_Q_ZERO_DENOM;
 __int128 numerator=(__int128)a.numerator*b.denominator;if(b.numerator<0)numerator=-numerator;
 return omega_q64_make(out,numerator,(unsigned __int128)a.denominator*omega_abs128(b.numerator));
}
#endif
