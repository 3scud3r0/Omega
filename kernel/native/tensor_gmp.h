#ifndef OMEGA_KERNEL_TENSOR_GMP_H
#define OMEGA_KERNEL_TENSOR_GMP_H

/* A matrix is an integer grid over one positive common denominator. Matrix
 * products normalize once per output matrix, not once per multiply-accumulate.
 * A compact int16 representation activates checked SIMD dot products. General
 * inputs retain GMP precision; no denominator is truncated to make them fit.
 */
#include <gmp.h>
#include <stdlib.h>
#include <stdint.h>
#include <stddef.h>
#include "tensor.h"

_Static_assert(sizeof(long) >= 8, "GMP compact dot path requires a 64-bit long");

enum {
    OKG_SUCCESS,
    OKG_ARGUMENT,
    OKG_ALLOCATION,
    OKG_BUDGET,
    OKG_INPUT,
    OKG_SHAPE
};

typedef struct {
    size_t limit;
    size_t charged;
    size_t peak;
    unsigned bits;
} okg_budget;

typedef struct {
    size_t rows;
    size_t columns;
    size_t count;
    mpz_t *numerators;
    mpz_t denominator;
    okg_budget *budget;
    size_t charge;
    unsigned initialized;
    unsigned backend;
    size_t simd_products;
} okg_matrix;

typedef int (*okg_reader)(void *, size_t, mpq_t);

static inline int okg_budget_init(okg_budget *b, size_t limit, unsigned bits)
{
    if (!b || limit<4096 || limit>1073741824 || bits<64 || bits>8192) {
        return 0;
    }
    b->limit=limit;
    b->charged=0;
    b->peak=0;
    b->bits=bits;
    return 1;
}

static inline int okg_reserve(okg_budget *b, size_t bytes)
{
    if (!b || b->charged>b->limit || bytes>b->limit-b->charged) {
        return 0;
    }
    b->charged+=bytes;
    if (b->charged>b->peak) {
        b->peak=b->charged;
    }
    return 1;
}

static inline void okg_release(okg_budget *b, size_t bytes)
{
    if (b && bytes<=b->charged) {
        b->charged-=bytes;
    }
}

static inline int okg_allocate(okg_matrix *out, size_t rows, size_t columns,
                               okg_budget *budget)
{
    if (!out || out->initialized || !budget || !rows || !columns ||
        rows>1024 || columns>1024 || rows>1048576/columns) {
        return OKG_ARGUMENT;
    }
    size_t count=rows*columns;
    size_t per_cell=(budget->bits+7)/8+sizeof(mpz_t)+32;
    if (count>(SIZE_MAX-128)/per_cell) {
        return OKG_BUDGET;
    }
    size_t charge=count*per_cell+128;
    if (!okg_reserve(budget,charge)) {
        return OKG_BUDGET;
    }
    mpz_t *cells=calloc(count,sizeof(mpz_t));
    if (!cells) {
        okg_release(budget,charge);
        return OKG_ALLOCATION;
    }
    for (size_t i=0;i<count;++i) {
        mpz_init2(cells[i],64);
    }
    mpz_init_set_ui(out->denominator,1);
    out->rows=rows;
    out->columns=columns;
    out->count=count;
    out->numerators=cells;
    out->budget=budget;
    out->charge=charge;
    out->initialized=1;
    out->backend=OKQ_SCALAR;
    out->simd_products=0;
    return OKG_SUCCESS;
}

static inline void okg_clear(okg_matrix *matrix)
{
    if (!matrix || !matrix->initialized) {
        return;
    }
    for (size_t i=0;i<matrix->count;++i) {
        mpz_clear(matrix->numerators[i]);
    }
    free(matrix->numerators);
    mpz_clear(matrix->denominator);
    okg_release(matrix->budget,matrix->charge);
    matrix->initialized=0;
    matrix->numerators=NULL;
    matrix->rows=0;
    matrix->columns=0;
    matrix->count=0;
}

static inline int okg_within(const okg_matrix *matrix, const mpz_t value)
{
    return matrix && matrix->initialized &&
           mpz_sizeinbase(value,2)<=matrix->budget->bits;
}

static inline int okg_normalize(okg_matrix *matrix)
{
    if (!matrix || !matrix->initialized || mpz_sgn(matrix->denominator)<=0) {
        return OKG_ARGUMENT;
    }
    mpz_t common;
    mpz_init_set(common,matrix->denominator);
    for (size_t i=0;i<matrix->count;++i) {
        if (!okg_within(matrix,matrix->numerators[i])) {
            mpz_clear(common);
            return OKG_BUDGET;
        }
        if (mpz_cmp_ui(common,1)!=0) {
            mpz_gcd(common,common,matrix->numerators[i]);
        }
    }
    if (!okg_within(matrix,matrix->denominator)) {
        mpz_clear(common);
        return OKG_BUDGET;
    }
    if (mpz_cmp_ui(common,1)>0) {
        mpz_divexact(matrix->denominator,matrix->denominator,common);
        for (size_t i=0;i<matrix->count;++i) {
            mpz_divexact(matrix->numerators[i],matrix->numerators[i],common);
        }
    }
    mpz_clear(common);
    return OKG_SUCCESS;
}

static int okg_from_reader(okg_matrix *out, size_t rows, size_t columns,
                            okg_budget *budget, okg_reader reader, void *context)
{
    if (!reader) {
        return OKG_ARGUMENT;
    }
    int status=okg_allocate(out,rows,columns,budget);
    if (status) {
        return status;
    }
    mpq_t q;
    mpz_t divisor;
    mpz_t multiplier;
    mpq_init(q);
    mpz_init(divisor);
    mpz_init(multiplier);
    for (size_t i=0;i<out->count;++i) {
        if (!reader(context,i,q) || mpz_sgn(mpq_denref(q))<=0 ||
            !okg_within(out,mpq_numref(q)) || !okg_within(out,mpq_denref(q))) {
            status=OKG_INPUT;
            break;
        }
        mpz_gcd(divisor,out->denominator,mpq_denref(q));
        mpz_divexact(multiplier,out->denominator,divisor);
        mpz_mul(out->denominator,multiplier,mpq_denref(q));
        if (!okg_within(out,out->denominator)) {
            status=OKG_BUDGET;
            break;
        }
    }
    for (size_t i=0;!status && i<out->count;++i) {
        if (!reader(context,i,q) || mpz_sgn(mpq_denref(q))<=0 ||
            !mpz_divisible_p(out->denominator,mpq_denref(q))) {
            status=OKG_INPUT;
            break;
        }
        mpz_divexact(multiplier,out->denominator,mpq_denref(q));
        mpz_mul(out->numerators[i],mpq_numref(q),multiplier);
        if (!okg_within(out,out->numerators[i])) {
            status=OKG_BUDGET;
        }
    }
    if (!status) {
        status=okg_normalize(out);
    }
    mpq_clear(q);
    mpz_clear(divisor);
    mpz_clear(multiplier);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_clone(okg_matrix *out, const okg_matrix *source)
{
    if (!source || !source->initialized || out==source) {
        return OKG_ARGUMENT;
    }
    int status=okg_allocate(out,source->rows,source->columns,source->budget);
    if (status) {
        return status;
    }
    mpz_set(out->denominator,source->denominator);
    for (size_t i=0;i<source->count;++i) {
        mpz_set(out->numerators[i],source->numerators[i]);
    }
    return OKG_SUCCESS;
}

static inline int okg_transpose(okg_matrix *out, const okg_matrix *source)
{
    if (!source || !source->initialized || out==source) {
        return OKG_ARGUMENT;
    }
    int status=okg_allocate(out,source->columns,source->rows,source->budget);
    if (status) {
        return status;
    }
    mpz_set(out->denominator,source->denominator);
    for (size_t i=0;i<source->rows;++i) {
        for (size_t j=0;j<source->columns;++j) {
            mpz_set(out->numerators[j*out->columns+i],source->numerators[i*source->columns+j]);
        }
    }
    return OKG_SUCCESS;
}

static inline int okg_add(okg_matrix *out, const okg_matrix *a,
                           const okg_matrix *b, int subtract)
{
    if (!a || !b || !a->initialized || !b->initialized ||
        a->rows!=b->rows || a->columns!=b->columns || a->budget!=b->budget ||
        out==a || out==b || (subtract!=0 && subtract!=1)) {
        return OKG_SHAPE;
    }
    int status=okg_allocate(out,a->rows,a->columns,a->budget);
    if (status) {
        return status;
    }
    mpz_t common;
    mpz_t scale_a;
    mpz_t scale_b;
    mpz_t term;
    mpz_init(common);
    mpz_init(scale_a);
    mpz_init(scale_b);
    mpz_init(term);
    mpz_gcd(common,a->denominator,b->denominator);
    mpz_divexact(scale_a,b->denominator,common);
    mpz_divexact(scale_b,a->denominator,common);
    mpz_mul(out->denominator,a->denominator,scale_a);
    if (!okg_within(out,out->denominator)) {
        status=OKG_BUDGET;
    }
    for (size_t i=0;!status && i<a->count;++i) {
        mpz_mul(out->numerators[i],a->numerators[i],scale_a);
        mpz_mul(term,b->numerators[i],scale_b);
        if (subtract) {
            mpz_sub(out->numerators[i],out->numerators[i],term);
        } else {
            mpz_add(out->numerators[i],out->numerators[i],term);
        }
        if (!okg_within(out,out->numerators[i])) {
            status=OKG_BUDGET;
        }
    }
    if (!status) {
        status=okg_normalize(out);
    }
    mpz_clear(common);
    mpz_clear(scale_a);
    mpz_clear(scale_b);
    mpz_clear(term);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_hadamard(okg_matrix *out, const okg_matrix *a, const okg_matrix *b)
{
    if (!a || !b || !a->initialized || !b->initialized ||
        a->rows!=b->rows || a->columns!=b->columns || a->budget!=b->budget ||
        out==a || out==b) {
        return OKG_SHAPE;
    }
    int status=okg_allocate(out,a->rows,a->columns,a->budget);
    if (status) {
        return status;
    }
    mpz_mul(out->denominator,a->denominator,b->denominator);
    if (!okg_within(out,out->denominator)) {
        status=OKG_BUDGET;
    }
    for (size_t i=0;!status && i<a->count;++i) {
        mpz_mul(out->numerators[i],a->numerators[i],b->numerators[i]);
        if (!okg_within(out,out->numerators[i])) {
            status=OKG_BUDGET;
        }
    }
    if (!status) {
        status=okg_normalize(out);
    }
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_small_grid(const okg_matrix *a)
{
    for (size_t i=0;i<a->count;++i) {
        if (mpz_cmp_si(a->numerators[i],-32767)<0 || mpz_cmp_si(a->numerators[i],32767)>0) {
            return 0;
        }
    }
    return 1;
}

static int okg_gemm(okg_matrix *out, const okg_matrix *a,
                     const okg_matrix *b, unsigned requested)
{
    if (!a || !b || !a->initialized || !b->initialized ||
        a->columns!=b->rows || a->budget!=b->budget || out==a || out==b) {
        return OKG_SHAPE;
    }
    unsigned backend=okq_choose(requested);
    if (backend==UINT_MAX) {
        return OKG_ARGUMENT;
    }
    int status=okg_allocate(out,a->rows,b->columns,a->budget);
    if (status) {
        return status;
    }
    mpz_mul(out->denominator,a->denominator,b->denominator);
    if (!okg_within(out,out->denominator)) {
        okg_clear(out);
        return OKG_BUDGET;
    }
    int small=a->columns<=4096 && okg_small_grid(a) && okg_small_grid(b);
    size_t packed_bytes=(a->count+b->count)*sizeof(int16_t);
    if (small && okg_reserve(a->budget,packed_bytes)) {
        int16_t *left=malloc(a->count*sizeof(int16_t));
        int16_t *right=malloc(b->count*sizeof(int16_t));
        if (!left || !right) {
            free(left);
            free(right);
            okg_release(a->budget,packed_bytes);
            okg_clear(out);
            return OKG_ALLOCATION;
        }
        for (size_t i=0;i<a->count;++i) {
            left[i]=(int16_t)mpz_get_si(a->numerators[i]);
        }
        for (size_t i=0;i<b->rows;++i) {
            for (size_t j=0;j<b->columns;++j) {
                right[j*b->rows+i]=(int16_t)mpz_get_si(b->numerators[i*b->columns+j]);
            }
        }
        for (size_t i=0;i<a->rows;++i) {
            for (size_t j=0;j<b->columns;++j) {
                int64_t value=okq_dot16(left+i*a->columns,right+j*b->rows,a->columns,backend);
                mpz_set_si(out->numerators[i*out->columns+j],(long)value);
            }
        }
        out->backend=backend;
        out->simd_products=backend==OKQ_SCALAR ? 0 : a->rows*b->columns*a->columns;
        free(left);
        free(right);
        okg_release(a->budget,packed_bytes);
    } else {
        /* i-k-j tile order reuses A and traverses B/C rows contiguously. */
        size_t max_a=1;
        size_t max_b=1;
        for (size_t i=0;i<a->count;++i) {
            size_t bits=mpz_sizeinbase(a->numerators[i],2);
            if (bits>max_a) {
                max_a=bits;
            }
        }
        for (size_t i=0;i<b->count;++i) {
            size_t bits=mpz_sizeinbase(b->numerators[i],2);
            if (bits>max_b) {
                max_b=bits;
            }
        }
        size_t reserve_bits=max_a+max_b+16;
        if (reserve_bits>out->budget->bits+16) {
            okg_clear(out);
            return OKG_BUDGET;
        }
        for (size_t i=0;i<out->count;++i) {
            mpz_realloc2(out->numerators[i],reserve_bits);
        }
        const size_t tile=16;
        for (size_t ii=0;ii<a->rows;ii+=tile) {
            size_t ie=ii+tile<a->rows ? ii+tile : a->rows;
            for (size_t kk=0;kk<a->columns;kk+=tile) {
                size_t ke=kk+tile<a->columns ? kk+tile : a->columns;
                for (size_t jj=0;jj<b->columns;jj+=tile) {
                    size_t je=jj+tile<b->columns ? jj+tile : b->columns;
                    for (size_t i=ii;i<ie;++i) {
                        for (size_t k=kk;k<ke;++k) {
                            for (size_t j=jj;j<je;++j) {
                                mpz_addmul(out->numerators[i*out->columns+j],
                                           a->numerators[i*a->columns+k],
                                           b->numerators[k*b->columns+j]);
                            }
                        }
                    }
                }
            }
        }
    }
    status=okg_normalize(out);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_scale(okg_matrix *out, const okg_matrix *source, const mpq_t factor)
{
    if (!source || !source->initialized || mpz_sgn(mpq_denref(factor))<=0) {
        return OKG_ARGUMENT;
    }
    int status=okg_allocate(out,source->rows,source->columns,source->budget);
    if (status) {
        return status;
    }
    mpz_mul(out->denominator,source->denominator,mpq_denref(factor));
    for (size_t i=0;i<source->count;++i) {
        mpz_mul(out->numerators[i],source->numerators[i],mpq_numref(factor));
    }
    status=okg_normalize(out);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_reduce(okg_matrix *out, const okg_matrix *source, int square)
{
    if (!source || !source->initialized || (square!=0 && square!=1)) {
        return OKG_ARGUMENT;
    }
    int status=okg_allocate(out,1,1,source->budget);
    if (status) {
        return status;
    }
    mpz_set(out->denominator,source->denominator);
    if (square) {
        mpz_mul(out->denominator,out->denominator,out->denominator);
    }
    for (size_t i=0;i<source->count;++i) {
        if (square) {
            mpz_addmul(out->numerators[0],source->numerators[i],source->numerators[i]);
        } else {
            mpz_add(out->numerators[0],out->numerators[0],source->numerators[i]);
        }
        if (!okg_within(out,out->numerators[0])) {
            status=OKG_BUDGET;
            break;
        }
    }
    if (!status) {
        status=okg_normalize(out);
    }
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_relu(okg_matrix *out, const okg_matrix *source)
{
    int status=okg_clone(out,source);
    if (status) {
        return status;
    }
    for (size_t i=0;i<out->count;++i) {
        if (mpz_sgn(out->numerators[i])<0) {
            mpz_set_ui(out->numerators[i],0);
        }
    }
    status=okg_normalize(out);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_relu_pullback(okg_matrix *out, const okg_matrix *source,
                                    const okg_matrix *gradient)
{
    if (!source || !gradient || !source->initialized || !gradient->initialized ||
        source->rows!=gradient->rows || source->columns!=gradient->columns) {
        return OKG_SHAPE;
    }
    int status=okg_clone(out,gradient);
    if (status) {
        return status;
    }
    for (size_t i=0;i<out->count;++i) {
        /* Declared subgradient at zero is zero. */
        if (mpz_sgn(source->numerators[i])<=0) {
            mpz_set_ui(out->numerators[i],0);
        }
    }
    status=okg_normalize(out);
    if (status) {
        okg_clear(out);
    }
    return status;
}

static inline int okg_equal(const okg_matrix *a, const okg_matrix *b)
{
    if (!a || !b || !a->initialized || !b->initialized ||
        a->rows!=b->rows || a->columns!=b->columns) {
        return 0;
    }
    mpz_t left;
    mpz_t right;
    mpz_init(left);
    mpz_init(right);
    int equal=1;
    for (size_t i=0;i<a->count;++i) {
        mpz_mul(left,a->numerators[i],b->denominator);
        mpz_mul(right,b->numerators[i],a->denominator);
        if (mpz_cmp(left,right)!=0) {
            equal=0;
            break;
        }
    }
    mpz_clear(left);
    mpz_clear(right);
    return equal;
}

static inline int okg_accumulate(okg_matrix *target, okg_matrix *contribution)
{
    if (!target || !contribution || !contribution->initialized || target==contribution) {
        return OKG_ARGUMENT;
    }
    if (!target->initialized) {
        *target=*contribution;
        contribution->initialized=0;
        contribution->numerators=NULL;
        return OKG_SUCCESS;
    }
    okg_matrix sum={0};
    int status=okg_add(&sum,target,contribution,0);
    if (status) {
        return status;
    }
    okg_clear(target);
    *target=sum;
    sum.initialized=0;
    return OKG_SUCCESS;
}

#endif
