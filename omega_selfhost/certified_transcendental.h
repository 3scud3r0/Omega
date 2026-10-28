/* Exact rational Taylor/interval primitives used by the static real-graph
   emitter. Mirrors omega/transcendental.py; no libm or floating arithmetic. */
#ifndef OMEGA_CERTIFIED_TRANSCENDENTAL_H
#define OMEGA_CERTIFIED_TRANSCENDENTAL_H
#include <gmp.h>

static void omega_dyadic_floor(mpq_t out, mpq_srcptr x, unsigned bits, int upper) {
  mpz_t scaled,rounded,den;mpz_inits(scaled,rounded,den,NULL);
  mpz_mul_2exp(scaled,mpq_numref(x),bits);
  if(upper)mpz_cdiv_q(rounded,scaled,mpq_denref(x));else mpz_fdiv_q(rounded,scaled,mpq_denref(x));
  mpz_set_ui(den,1);mpz_mul_2exp(den,den,bits);
  mpz_set(mpq_numref(out),rounded);mpz_set(mpq_denref(out),den);mpq_canonicalize(out);
  mpz_clears(scaled,rounded,den,NULL);
}

static void omega_dyadic_nearest(mpq_t out, mpq_srcptr x, unsigned bits) {
  mpz_t scaled,rounded,remainder,den;mpz_inits(scaled,rounded,remainder,den,NULL);
  mpz_mul_2exp(scaled,mpq_numref(x),bits);mpz_fdiv_qr(rounded,remainder,scaled,mpq_denref(x));
  mpz_mul_2exp(remainder,remainder,1);int compare=mpz_cmp(remainder,mpq_denref(x));
  if(compare>0||(compare==0&&mpz_odd_p(rounded)))mpz_add_ui(rounded,rounded,1);
  mpz_set_ui(den,1);mpz_mul_2exp(den,den,bits);
  mpz_set(mpq_numref(out),rounded);mpz_set(mpq_denref(out),den);mpq_canonicalize(out);
  mpz_clears(scaled,rounded,remainder,den,NULL);
}

static int omega_rational_exp(mpq_t out, mpq_srcptr x, unsigned bits) {
  if(bits<8||bits>128||mpz_sizeinbase(mpq_numref(x),2)>16384||mpz_sizeinbase(mpq_denref(x),2)>16384)return -1;
  mpq_t absolute,t,power,polynomial,tail,low,high,tmp,coefficient,tolerance;
  mpq_inits(absolute,t,power,polynomial,tail,low,high,tmp,coefficient,tolerance,NULL);
  mpq_abs(absolute,x);int status=-1;
  if(mpq_cmp_ui(absolute,32,1)>0)goto done;
  if(!mpq_sgn(x)){mpq_set_ui(out,1,1);status=0;goto done;}
  mpq_set(t,absolute);unsigned reductions=0;
  while(mpq_cmp_ui(t,1,1)>0){mpq_div_2exp(t,t,1);reductions++;}
  mpz_t ceiling;mpz_init(ceiling);mpz_cdiv_q(ceiling,mpq_numref(absolute),mpq_denref(absolute));
  unsigned work=bits+2*(unsigned)mpz_get_ui(ceiling)+24;mpz_clear(ceiling);
  mpq_set_ui(tolerance,1,1);mpq_div_2exp(tolerance,tolerance,bits);
  for(unsigned terms=12;terms<=64;terms+=4){
    mpq_set_ui(polynomial,0,1);mpq_set_ui(power,1,1);
    for(unsigned j=0;j<terms;j++){
      mpq_add(polynomial,polynomial,power);mpq_mul(power,power,t);
      mpq_set_ui(coefficient,j+1,1);mpq_div(power,power,coefficient);
    }
    mpq_set_ui(coefficient,terms+1,terms);mpq_mul(tail,power,coefficient);
    mpq_sub(low,polynomial,tail);mpq_add(high,polynomial,tail);
    if(mpq_sgn(low)<=0)continue;
    for(unsigned j=0;j<reductions;j++){
      mpq_mul(tmp,low,low);omega_dyadic_floor(low,tmp,work,0);
      mpq_mul(tmp,high,high);omega_dyadic_floor(high,tmp,work,1);
    }
    if(mpq_sgn(x)<0){mpq_inv(tmp,high);mpq_inv(high,low);mpq_set(low,tmp);}
    mpq_sub(tmp,high,low);
    if(mpq_cmp(tmp,tolerance)<=0){mpq_add(tmp,low,high);mpq_div_2exp(tmp,tmp,1);omega_dyadic_nearest(out,tmp,bits+8);if(!mpq_sgn(out)){mpq_set_ui(out,1,1);mpq_div_2exp(out,out,bits+8);}status=0;break;}
  }
done:
  mpq_clears(absolute,t,power,polynomial,tail,low,high,tmp,coefficient,tolerance,NULL);
  return status;
}

static int omega_rational_rsqrt(mpq_t out, mpq_srcptr x, unsigned bits) {
  if(bits<8||bits>128||mpq_sgn(x)<=0||mpz_sizeinbase(mpq_numref(x),2)>16384||mpz_sizeinbase(mpq_denref(x),2)>16384)return -1;
  mpz_t scaled,root,upper,scale;mpz_inits(scaled,root,upper,scale,NULL);
  mpq_t low,high,tmp;mpq_inits(low,high,tmp,NULL);int status=-1;
  for(unsigned precision=bits;precision<=256;precision+=8){
    mpz_mul_2exp(scaled,mpq_numref(x),2*precision);mpz_fdiv_q(scaled,scaled,mpq_denref(x));mpz_sqrt(root,scaled);
    if(!mpz_sgn(root))continue;
    mpz_add_ui(upper,root,1);mpz_set_ui(scale,1);mpz_mul_2exp(scale,scale,precision);
    mpz_set(mpq_numref(low),scale);mpz_set(mpq_denref(low),upper);mpq_canonicalize(low);
    mpz_set(mpq_numref(high),scale);mpz_set(mpq_denref(high),root);mpq_canonicalize(high);
    mpq_add(tmp,low,high);mpq_div_2exp(tmp,tmp,1);omega_dyadic_nearest(out,tmp,bits+8);if(!mpq_sgn(out)){mpq_set_ui(out,1,1);mpq_div_2exp(out,out,bits+8);}status=0;break;
  }
  mpz_clears(scaled,root,upper,scale,NULL);mpq_clears(low,high,tmp,NULL);return status;
}
#endif
