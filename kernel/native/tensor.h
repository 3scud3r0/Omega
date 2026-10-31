#ifndef OMEGA_KERNEL_TENSOR_H
#define OMEGA_KERNEL_TENSOR_H

/* Exact structure-of-arrays batches. SIMD is used only after lane range checks.
 * Overflow is a per-lane result, never a wrapped value masquerading as Q.
 * Inputs/outputs are caller-owned, non-overlapping contiguous arrays.
 */
#include <stddef.h>
#include <stdint.h>
#include <limits.h>
#include "../../omega_selfhost/bounded_rational.h"

#if defined(__x86_64__) && defined(__GNUC__)
#include <immintrin.h>
#define OKQ_X86_SIMD 1
#else
#define OKQ_X86_SIMD 0
#endif

#if defined(__aarch64__) && defined(__ARM_NEON)
#include <arm_neon.h>
#define OKQ_ARM_SIMD 1
#else
#define OKQ_ARM_SIMD 0
#endif

enum {
    OKQ_AUTO,
    OKQ_SCALAR,
    OKQ_AVX2,
    OKQ_AVX512,
    OKQ_NEON
};

enum {
    OKQ_ADD,
    OKQ_MULTIPLY
};

enum {
    OKQ_SUCCESS,
    OKQ_BAD_ARGUMENT,
    OKQ_UNSUPPORTED,
    OKQ_ARITHMETIC_OVERFLOW,
    OKQ_BAD_RATIONAL
};

typedef struct {
    const int64_t *numerators;
    const uint64_t *denominators;
    size_t length;
} okq_view;

typedef struct {
    int64_t *numerators;
    uint64_t *denominators;
    uint8_t *status;
    size_t capacity;
} okq_output;

typedef struct {
    unsigned backend;
    size_t simd_lanes;
    size_t scalar_lanes;
    size_t failed_lanes;
} okq_statistics;

static inline int okq_available(unsigned backend)
{
    if (backend == OKQ_AUTO || backend == OKQ_SCALAR) {
        return 1;
    }
#if OKQ_X86_SIMD
    __builtin_cpu_init();
    if (backend == OKQ_AVX2) {
        return !!__builtin_cpu_supports("avx2");
    }
    if (backend == OKQ_AVX512) {
        return __builtin_cpu_supports("avx512f") &&
               __builtin_cpu_supports("avx512dq") &&
               __builtin_cpu_supports("avx512bw");
    }
#endif
#if OKQ_ARM_SIMD
    if (backend == OKQ_NEON) {
        return 1;
    }
#endif
    return 0;
}

static inline unsigned okq_choose(unsigned requested)
{
    if (requested != OKQ_AUTO) {
        return okq_available(requested) ? requested : UINT_MAX;
    }
    if (okq_available(OKQ_AVX512)) {
        return OKQ_AVX512;
    }
    if (okq_available(OKQ_AVX2)) {
        return OKQ_AVX2;
    }
    if (okq_available(OKQ_NEON)) {
        return OKQ_NEON;
    }
    return OKQ_SCALAR;
}

static inline int okq_small_lane(okq_view a, okq_view b, size_t i)
{
    return a.numerators[i] >= INT32_MIN && a.numerators[i] <= INT32_MAX &&
           b.numerators[i] >= INT32_MIN && b.numerators[i] <= INT32_MAX &&
           a.denominators[i] > 0 && a.denominators[i] <= INT32_MAX &&
           b.denominators[i] > 0 && b.denominators[i] <= INT32_MAX;
}

static inline int okq_block_eligible(okq_view a, okq_view b, size_t start, size_t width)
{
    if (width > a.length - start) {
        return 0;
    }
    for (size_t i = 0; i < width; ++i) {
        if (!okq_small_lane(a,b,start+i)) {
            return 0;
        }
    }
    return 1;
}

#if OKQ_X86_SIMD
__attribute__((target("avx2")))
static void okq_avx2_products(okq_view a, okq_view b, size_t start, unsigned operation,
                              int64_t numerator[4], uint64_t denominator[4])
{
    __m256i an = _mm256_loadu_si256((const __m256i *)(const void *)(a.numerators+start));
    __m256i ad = _mm256_loadu_si256((const __m256i *)(const void *)(a.denominators+start));
    __m256i bn = _mm256_loadu_si256((const __m256i *)(const void *)(b.numerators+start));
    __m256i bd = _mm256_loadu_si256((const __m256i *)(const void *)(b.denominators+start));
    __m256i n;
    if (operation == OKQ_ADD) {
        n = _mm256_add_epi64(_mm256_mul_epi32(an,bd),_mm256_mul_epi32(bn,ad));
    } else {
        n = _mm256_mul_epi32(an,bn);
    }
    __m256i d = _mm256_mul_epu32(ad,bd);
    _mm256_storeu_si256((__m256i *)(void *)numerator,n);
    _mm256_storeu_si256((__m256i *)(void *)denominator,d);
}

__attribute__((target("avx512f,avx512dq,avx512bw")))
static void okq_avx512_products(okq_view a, okq_view b, size_t start, unsigned operation,
                                int64_t numerator[8], uint64_t denominator[8])
{
    __m512i an = _mm512_loadu_si512((const void *)(a.numerators+start));
    __m512i ad = _mm512_loadu_si512((const void *)(a.denominators+start));
    __m512i bn = _mm512_loadu_si512((const void *)(b.numerators+start));
    __m512i bd = _mm512_loadu_si512((const void *)(b.denominators+start));
    __m512i n;
    if (operation == OKQ_ADD) {
        n = _mm512_add_epi64(_mm512_mul_epi32(an,bd),_mm512_mul_epi32(bn,ad));
    } else {
        n = _mm512_mul_epi32(an,bn);
    }
    __m512i d = _mm512_mul_epu32(ad,bd);
    _mm512_storeu_si512((void *)numerator,n);
    _mm512_storeu_si512((void *)denominator,d);
}

__attribute__((target("avx2")))
static int64_t okq_avx2_dot16(const int16_t *a, const int16_t *b, size_t n)
{
    __m256i low = _mm256_setzero_si256();
    __m256i high = _mm256_setzero_si256();
    size_t i = 0;
    for (; i+16 <= n; i+=16) {
        __m256i x = _mm256_loadu_si256((const __m256i *)(const void *)(a+i));
        __m256i y = _mm256_loadu_si256((const __m256i *)(const void *)(b+i));
        __m256i p = _mm256_madd_epi16(x,y);
        low = _mm256_add_epi64(low,_mm256_cvtepi32_epi64(_mm256_castsi256_si128(p)));
        high = _mm256_add_epi64(high,_mm256_cvtepi32_epi64(_mm256_extracti128_si256(p,1)));
    }
    int64_t lanes[4];
    _mm256_storeu_si256((__m256i *)(void *)lanes,_mm256_add_epi64(low,high));
    int64_t sum = lanes[0]+lanes[1]+lanes[2]+lanes[3];
    for (; i<n; ++i) {
        sum += (int64_t)a[i]*b[i];
    }
    return sum;
}

__attribute__((target("avx512f,avx512dq,avx512bw")))
static int64_t okq_avx512_dot16(const int16_t *a, const int16_t *b, size_t n)
{
    __m512i low = _mm512_setzero_si512();
    __m512i high = _mm512_setzero_si512();
    size_t i = 0;
    for (; i+32<=n; i+=32) {
        __m512i x = _mm512_loadu_si512((const void *)(a+i));
        __m512i y = _mm512_loadu_si512((const void *)(b+i));
        __m512i p = _mm512_madd_epi16(x,y);
        low = _mm512_add_epi64(low,_mm512_cvtepi32_epi64(_mm512_castsi512_si256(p)));
        high = _mm512_add_epi64(high,_mm512_cvtepi32_epi64(_mm512_extracti64x4_epi64(p,1)));
    }
    int64_t lanes[8];
    _mm512_storeu_si512((void *)lanes,_mm512_add_epi64(low,high));
    int64_t sum = 0;
    for (unsigned k=0;k<8;++k) {
        sum += lanes[k];
    }
    for (;i<n;++i) {
        sum += (int64_t)a[i]*b[i];
    }
    return sum;
}
#endif

#if OKQ_ARM_SIMD
static void okq_neon_products(okq_view a, okq_view b, size_t start, unsigned operation,
                               int64_t numerator[2], uint64_t denominator[2])
{
    int32_t an[2] = {(int32_t)a.numerators[start],(int32_t)a.numerators[start+1]};
    int32_t bn[2] = {(int32_t)b.numerators[start],(int32_t)b.numerators[start+1]};
    int32_t ad[2] = {(int32_t)a.denominators[start],(int32_t)a.denominators[start+1]};
    int32_t bd[2] = {(int32_t)b.denominators[start],(int32_t)b.denominators[start+1]};
    int64x2_t n;
    if (operation == OKQ_ADD) {
        n = vaddq_s64(vmull_s32(vld1_s32(an),vld1_s32(bd)),
                       vmull_s32(vld1_s32(bn),vld1_s32(ad)));
    } else {
        n = vmull_s32(vld1_s32(an),vld1_s32(bn));
    }
    int64x2_t d = vmull_s32(vld1_s32(ad),vld1_s32(bd));
    vst1q_s64(numerator,n);
    vst1q_u64(denominator,vreinterpretq_u64_s64(d));
}

static int64_t okq_neon_dot16(const int16_t *a, const int16_t *b, size_t n)
{
    int64x2_t sum = vdupq_n_s64(0);
    size_t i=0;
    for (;i+8<=n;i+=8) {
        int16x8_t x=vld1q_s16(a+i);
        int16x8_t y=vld1q_s16(b+i);
        sum=vpadalq_s32(sum,vmull_s16(vget_low_s16(x),vget_low_s16(y)));
        sum=vpadalq_s32(sum,vmull_s16(vget_high_s16(x),vget_high_s16(y)));
    }
    int64_t result=vgetq_lane_s64(sum,0)+vgetq_lane_s64(sum,1);
    for (;i<n;++i) {
        result+=(int64_t)a[i]*b[i];
    }
    return result;
}
#endif

static inline int64_t okq_dot16(const int16_t *a, const int16_t *b, size_t n,
                                unsigned backend)
{
    /* Caller proves |a[i]|,|b[i]|<=32767 and n<=4096 before dispatch. */
#if OKQ_X86_SIMD
    if (backend==OKQ_AVX512) {
        return okq_avx512_dot16(a,b,n);
    }
    if (backend==OKQ_AVX2) {
        return okq_avx2_dot16(a,b,n);
    }
#endif
#if OKQ_ARM_SIMD
    if (backend==OKQ_NEON) {
        return okq_neon_dot16(a,b,n);
    }
#endif
    int64_t result=0;
    for (size_t i=0;i<n;++i) {
        result+=(int64_t)a[i]*b[i];
    }
    return result;
}

static inline void okq_store(okq_output out, size_t index, int status,
                              omega_q64 value, okq_statistics *statistics)
{
    if (status != OMEGA_Q_OK) {
        out.numerators[index]=0;
        out.denominators[index]=1;
        out.status[index]=status==OMEGA_Q_OVERFLOW ?
            OKQ_ARITHMETIC_OVERFLOW : OKQ_BAD_RATIONAL;
        statistics->failed_lanes++;
    } else {
        out.numerators[index]=value.numerator;
        out.denominators[index]=value.denominator;
        out.status[index]=OKQ_SUCCESS;
    }
}

static inline int okq_batch(okq_view a, okq_view b, okq_output out,
                            unsigned operation, unsigned requested,
                            okq_statistics *statistics)
{
    if (!statistics || !a.numerators || !a.denominators || !b.numerators ||
        !b.denominators || !out.numerators || !out.denominators || !out.status ||
        a.length != b.length || a.length > out.capacity || a.length>1048576 ||
        operation>OKQ_MULTIPLY || requested>OKQ_NEON) {
        return OKQ_BAD_ARGUMENT;
    }
    statistics->backend=okq_choose(requested);
    statistics->simd_lanes=0;
    statistics->scalar_lanes=0;
    statistics->failed_lanes=0;
    if (statistics->backend==UINT_MAX) {
        return OKQ_UNSUPPORTED;
    }
    unsigned width=1;
    if (statistics->backend==OKQ_AVX512) {
        width=8;
    } else if (statistics->backend==OKQ_AVX2) {
        width=4;
    } else if (statistics->backend==OKQ_NEON) {
        width=2;
    }
    size_t i=0;
    while (i<a.length) {
        if (width>1 && okq_block_eligible(a,b,i,width)) {
            int64_t numerators[8];
            uint64_t denominators[8];
#if OKQ_X86_SIMD
            if (statistics->backend==OKQ_AVX512) {
                okq_avx512_products(a,b,i,operation,numerators,denominators);
            } else if (statistics->backend==OKQ_AVX2) {
                okq_avx2_products(a,b,i,operation,numerators,denominators);
            }
#endif
#if OKQ_ARM_SIMD
            if (statistics->backend==OKQ_NEON) {
                okq_neon_products(a,b,i,operation,numerators,denominators);
            }
#endif
            for (unsigned j=0;j<width;++j) {
                omega_q64 value={0,1};
                int status=omega_q64_make(&value,numerators[j],denominators[j]);
                okq_store(out,i+j,status,value,statistics);
            }
            statistics->simd_lanes+=width;
            i+=width;
            continue;
        }
        omega_q64 x={a.numerators[i],a.denominators[i]};
        omega_q64 y={b.numerators[i],b.denominators[i]};
        omega_q64 value={0,1};
        int status=operation==OKQ_ADD ? omega_q64_add(&value,x,y) :
                                       omega_q64_mul(&value,x,y);
        okq_store(out,i,status,value,statistics);
        statistics->scalar_lanes++;
        i++;
    }
    return OKQ_SUCCESS;
}

static inline int okq_gemm64(okq_view a, okq_view b, okq_output out,
                              size_t rows, size_t inner, size_t columns)
{
    if (!rows || !inner || !columns || rows>1024 || inner>4096 || columns>1024 ||
        a.length!=rows*inner || b.length!=inner*columns ||
        out.capacity<rows*columns || !a.numerators || !a.denominators ||
        !b.numerators || !b.denominators || !out.numerators ||
        !out.denominators || !out.status) {
        return OKQ_BAD_ARGUMENT;
    }
    for (size_t i=0;i<rows;++i) {
        for (size_t j=0;j<columns;++j) {
            omega_q64 accumulator={0,1};
            int status=OMEGA_Q_OK;
            for (size_t k=0;k<inner;++k) {
                omega_q64 x={a.numerators[i*inner+k],a.denominators[i*inner+k]};
                omega_q64 y={b.numerators[k*columns+j],b.denominators[k*columns+j]};
                omega_q64 product;
                status=omega_q64_mul(&product,x,y);
                if (status!=OMEGA_Q_OK) {
                    break;
                }
                status=omega_q64_add(&accumulator,accumulator,product);
                if (status!=OMEGA_Q_OK) {
                    break;
                }
            }
            size_t index=i*columns+j;
            out.status[index]=status==OMEGA_Q_OK ? OKQ_SUCCESS :
                status==OMEGA_Q_OVERFLOW ? OKQ_ARITHMETIC_OVERFLOW : OKQ_BAD_RATIONAL;
            out.numerators[index]=status==OMEGA_Q_OK ? accumulator.numerator : 0;
            out.denominators[index]=status==OMEGA_Q_OK ? accumulator.denominator : 1;
        }
    }
    return OKQ_SUCCESS;
}

#endif
