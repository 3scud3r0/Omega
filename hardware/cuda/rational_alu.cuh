#ifndef OMEGA_CUDA_RATIONAL_ALU_CUH
#define OMEGA_CUDA_RATIONAL_ALU_CUH
#include "rational_types.cuh"
namespace omega_gpu {
OMEGA_HD unsigned trailing64(uint64_t x){
#ifdef __CUDA_ARCH__
 return x?63u-unsigned(__clzll(x&(~x+1))):0u;
#else
 return x?unsigned(__builtin_ctzll(x)):0u;
#endif
}
OMEGA_HD unsigned trailing128(unsigned __int128 x){
 const uint64_t low=uint64_t(x),high=uint64_t(x>>64);
 return low?trailing64(low):(high?64+trailing64(high):0);
}
// Fixed iteration count on device: all lanes execute 128 rounds. Conditional
// selections are masks; compiler-generated instruction scheduling is not proved.
OMEGA_HD uint64_t binary_gcd_stein(uint64_t a,uint64_t b){
 unsigned shift=trailing64(a|b);a>>=trailing64(a);b>>=trailing64(b);
 for(unsigned i=0;i<128;i++){
#ifndef __CUDA_ARCH__
  if(!a||!b)break;
#endif
  uint64_t active=uint64_t(0)-uint64_t(a!=0&&b!=0);
  uint64_t swap=uint64_t(0)-uint64_t(a>b);
  uint64_t lo=(a&~swap)|(b&swap),hi=(b&~swap)|(a&swap);
  uint64_t difference=hi-lo;difference>>=trailing64(difference);
  a=(a&~active)|(lo&active);b=(b&~active)|(difference&active);
 }
 return (a|b)<<shift;
}
OMEGA_HD unsigned __int128 gcd128(unsigned __int128 a,unsigned __int128 b){
 unsigned shift=trailing128(a|b);a>>=trailing128(a);b>>=trailing128(b);
 for(unsigned i=0;i<256;i++){
#ifndef __CUDA_ARCH__
  if(!a||!b)break;
#endif
  unsigned __int128 active=(unsigned __int128)0-(a!=0&&b!=0);
  unsigned __int128 swap=(unsigned __int128)0-(a>b);
  unsigned __int128 lo=(a&~swap)|(b&swap),hi=(b&~swap)|(a&swap);
  unsigned __int128 difference=hi-lo;difference>>=trailing128(difference);
  a=(a&~active)|(lo&active);b=(b&~active)|(difference&active);
 }
 return (a|b)<<shift;
}
OMEGA_HD Checked narrow(__int128 n,unsigned __int128 d){
 if(!d)return failure(ZERO_DIVISOR);
 unsigned __int128 divisor=gcd128(magnitude128(n),d);
 unsigned __int128 m=magnitude128(n)/divisor;d/=divisor;
 if(m>INT64_MAX||d>INT64_MAX)return failure(OVERFLOW);
 return {{n<0?-int64_t(m):int64_t(m),uint64_t(d)},OK};
}
OMEGA_HD Checked rat_add(Rational64 a,Rational64 b){
 if(!valid(a)||!valid(b))return failure(INVALID);
 const uint64_t g=binary_gcd_stein(a.den,b.den);
 // Symmetric int64 operands keep this sum strictly inside signed int128.
 return narrow((__int128)a.num*(b.den/g)+(__int128)b.num*(a.den/g),
               (unsigned __int128)(a.den/g)*b.den);
}
OMEGA_HD Checked rat_neg(Rational64 a){return valid(a)?Checked{{-a.num,a.den},OK}:failure(INVALID);}
OMEGA_HD Checked rat_sub(Rational64 a,Rational64 b){
 if(!valid(b))return failure(INVALID);
 return rat_add(a,{-b.num,b.den});
}
OMEGA_HD Checked rat_mul(Rational64 a,Rational64 b){
 if(!valid(a)||!valid(b))return failure(INVALID);
 const uint64_t g=binary_gcd_stein(magnitude(a.num),b.den),h=binary_gcd_stein(magnitude(b.num),a.den);
 return narrow((__int128)(a.num/int64_t(g))*(b.num/int64_t(h)),
               (unsigned __int128)(a.den/h)*(b.den/g));
}
OMEGA_HD Checked rat_div(Rational64 a,Rational64 b){
 if(!valid(a)||!valid(b))return failure(INVALID);
 if(!b.num)return failure(ZERO_DIVISOR);
 Rational64 reciprocal={b.num<0?-int64_t(b.den):int64_t(b.den),magnitude(b.num)};
 return rat_mul(a,reciprocal);
}
OMEGA_HD int rat_compare(Rational64 a,Rational64 b){
 __int128 x=(__int128)a.num*b.den,y=(__int128)b.num*a.den;
 return (x>y)-(x<y);
}
OMEGA_HD Checked rat_abs(Rational64 a){return valid(a)?Checked{{int64_t(magnitude(a.num)),a.den},OK}:failure(INVALID);}
OMEGA_HD bool positive_fraction_le(unsigned __int128 a,unsigned __int128 b,unsigned __int128 c,unsigned __int128 d){
 bool reverse=false;
 while(true){
  unsigned __int128 x=a/b,y=c/d;
  if(x!=y)return reverse?x>y:x<y;
  a%=b;c%=d;
  if(!a||!c)return reverse?(!c):(!a);
  unsigned __int128 t=a;a=b;b=t;t=c;c=d;d=t;reverse=!reverse;
 }
}
OMEGA_HD Pruned stern_brocot_prune(Rational64 q,uint64_t max_den){
 Pruned out={zero(),{0,1},INVALID};
 if(!valid(q)||!max_den||max_den>INT64_MAX)return out;
 Checked canonical=narrow(q.num,q.den);q=canonical.value;
 if(q.den<=max_den)return {q,{0,1},OK};
 unsigned __int128 n=magnitude(q.num),d=q.den,p0=0,p1=1,q0=1,q1=0;
 while(d){
  unsigned __int128 a=n/d,q2=q0+a*q1;
  if(q2>max_den)break;
  unsigned __int128 p2=p0+a*p1;p0=p1;p1=p2;q0=q1;q1=q2;
  unsigned __int128 remainder=n-a*d;n=d;d=remainder;
 }
 unsigned __int128 k=(max_den-q0)/q1,ap=p0+k*p1,aq=q0+k*q1;
 unsigned __int128 original=magnitude(q.num);
 unsigned __int128 e0=original*aq>ap*q.den?original*aq-ap*q.den:ap*q.den-original*aq;
 unsigned __int128 e1=original*q1>p1*q.den?original*q1-p1*q.den:p1*q.den-original*q1;
 // Multiplying error numerators by denominators could require 192 bits.
 // Compare positive rational errors by Euclidean quotients, without products.
 unsigned __int128 p=ap,den=aq,error=e0;
 bool le=positive_fraction_le(e1,q1,e0,aq),equal=le&&positive_fraction_le(e0,aq,e1,q1);
 bool tie_choice=q1<aq||(q1==aq&&(q.num<0?p1>ap:p1<ap));
 if(le&&(!equal||tie_choice)){p=p1;den=q1;error=e1;}
 if(p>INT64_MAX)return {zero(),{0,1},OVERFLOW};
 unsigned __int128 error_den=(unsigned __int128)q.den*den,g=gcd128(error,error_den);
 return {{q.num<0?-int64_t(p):int64_t(p),uint64_t(den)},
         {(__int128)(error/g),error_den/g},OK};
}
}
#endif
