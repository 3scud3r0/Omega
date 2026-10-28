/* Exact continued-fraction denominator limiting, including signed values.
   The caller owns out; aliasing out and value is supported. No floats are used. */
#ifndef OMEGA_RATIONAL_PRUNING_H
#define OMEGA_RATIONAL_PRUNING_H
#include <gmp.h>
static int omega_mpq_limit_denominator(mpq_t out, mpq_srcptr value, unsigned long limit) {
  if (!limit) return -1;
  if (mpz_cmp_ui(mpq_denref(value), limit) <= 0) { mpq_set(out, value); return 0; }
  mpz_t n,d,p0,q0,p1,q1,p2,q2,a,r,k,t;
  mpz_inits(n,d,p0,q0,p1,q1,p2,q2,a,r,k,t,NULL);
  mpz_set(n,mpq_numref(value)); mpz_set(d,mpq_denref(value));
  mpz_set_ui(p0,0);mpz_set_ui(q0,1);mpz_set_ui(p1,1);mpz_set_ui(q1,0);
  for (;;) {
    mpz_fdiv_qr(a,r,n,d);
    mpz_mul(q2,a,q1);mpz_add(q2,q2,q0);
    if (mpz_cmp_ui(q2,limit)>0) break;
    mpz_mul(p2,a,p1);mpz_add(p2,p2,p0);
    mpz_set(p0,p1);mpz_set(p1,p2);mpz_set(q0,q1);mpz_set(q1,q2);
    mpz_set(n,d);mpz_set(d,r);
    if (!mpz_sgn(d)) break;
  }
  mpq_t b1,b2,e1,e2,original;
  mpq_inits(b1,b2,e1,e2,original,NULL);mpq_set(original,value);
  if (!mpz_sgn(d)) {
    mpz_set(mpq_numref(b1),p1);mpz_set(mpq_denref(b1),q1);mpq_canonicalize(b1);
    mpq_set(out,b1);
  } else {
    mpz_ui_sub(k,limit,q0);mpz_fdiv_q(k,k,q1);
    mpz_mul(t,k,p1);mpz_add(mpq_numref(b1),p0,t);
    mpz_mul(t,k,q1);mpz_add(mpq_denref(b1),q0,t);mpq_canonicalize(b1);
    mpz_set(mpq_numref(b2),p1);mpz_set(mpq_denref(b2),q1);mpq_canonicalize(b2);
    mpq_sub(e1,b1,original);mpq_abs(e1,e1);mpq_sub(e2,b2,original);mpq_abs(e2,e2);
    mpq_set(out,mpq_cmp(e2,e1)<=0?b2:b1);
  }
  mpq_clears(b1,b2,e1,e2,original,NULL);
  mpz_clears(n,d,p0,q0,p1,q1,p2,q2,a,r,k,t,NULL);
  return 0;
}
#endif
