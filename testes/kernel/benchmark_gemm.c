/* Same-process arithmetic benchmark. Includes every output normalization and
 * allocation, excludes parsing/compilation, and verifies equality against mpq.
 * No result here is a claim about large networks or another CPU architecture. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdio.h>
#include <time.h>
#include "../../kernel/native/tensor_gmp.h"

static double now(void)
{
    struct timespec value;
    assert(!clock_gettime(CLOCK_MONOTONIC,&value));
    return (double)value.tv_sec+(double)value.tv_nsec/1e9;
}

static int sample(void *context, size_t index, mpq_t out)
{
    unsigned mode=*(const unsigned *)context;
    mpq_set_si(out,(long)(index%23)-11,(unsigned long)(1+index%7));
    if(mode) {
        static const unsigned primes[]={1009,1013,1019,1021,1031,1033,1039};
        mpz_mul_2exp(mpq_numref(out),mpq_numref(out),96);
        mpz_add_ui(mpq_numref(out),mpq_numref(out),index%5);
        mpz_set_ui(mpq_denref(out),primes[index%7]);
    }
    mpq_canonicalize(out);
    return 1;
}

static void measure(size_t n, unsigned mode)
{
    okg_budget budget;
    assert(okg_budget_init(&budget,268435456,4096));
    okg_matrix a={0},b={0},out={0};
    assert(!okg_from_reader(&a,n,n,&budget,sample,&mode));
    assert(!okg_from_reader(&b,n,n,&budget,sample,&mode));
    mpq_t *left=calloc(n*n,sizeof(mpq_t));
    mpq_t *right=calloc(n*n,sizeof(mpq_t));
    mpq_t *reference=calloc(n*n,sizeof(mpq_t));
    assert(left&&right&&reference);
    for(size_t i=0;i<n*n;++i) {
        mpq_init(left[i]);mpq_init(right[i]);mpq_init(reference[i]);
        assert(sample(&mode,i,left[i]));assert(sample(&mode,i,right[i]));
    }
    mpq_t temporary,observed;
    mpq_inits(temporary,observed,NULL);
    double start=now();
    for(size_t i=0;i<n;++i) {
        for(size_t j=0;j<n;++j) {
            for(size_t k=0;k<n;++k) {
                mpq_mul(temporary,left[i*n+k],right[k*n+j]);
                mpq_add(reference[i*n+j],reference[i*n+j],temporary);
            }
        }
    }
    double mpq_seconds=now()-start;
    start=now();
    assert(!okg_gemm(&out,&a,&b,OKQ_AUTO));
    double grid_seconds=now()-start;
    for(size_t i=0;i<n*n;++i) {
        mpz_set(mpq_numref(observed),out.numerators[i]);
        mpz_set(mpq_denref(observed),out.denominator);
        mpq_canonicalize(observed);
        assert(mpq_equal(observed,reference[i]));
        mpq_clear(left[i]);mpq_clear(right[i]);mpq_clear(reference[i]);
    }
    printf("{\"dimension\":%zu,\"regime\":\"%s\",\"mpq_seconds\":%.9f,\"grid_seconds\":%.9f,"
           "\"ratio\":%.6f,\"backend\":%u,\"simd_products\":%zu,\"equal\":true}\n",
           n,mode?"wide-gmp":"compact-simd",mpq_seconds,grid_seconds,mpq_seconds/grid_seconds,out.backend,out.simd_products);
    free(left);free(right);free(reference);
    mpq_clears(temporary,observed,NULL);
    okg_clear(&out);okg_clear(&b);okg_clear(&a);
    assert(!budget.charged);
}

int main(void)
{
    measure(8,0);
    for(unsigned repeat=0;repeat<3;++repeat) {
        measure(32,0);
        measure(64,0);
        measure(32,1);
        measure(64,1);
    }
    return 0;
}
