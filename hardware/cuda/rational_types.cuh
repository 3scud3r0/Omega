#ifndef OMEGA_CUDA_RATIONAL_TYPES_CUH
#define OMEGA_CUDA_RATIONAL_TYPES_CUH
#include <stdint.h>
#include <limits.h>
#ifdef __CUDACC__
#define OMEGA_HD __host__ __device__ __forceinline__
#define OMEGA_ALIGN(n) __align__(n)
#else
#define OMEGA_HD inline
#define OMEGA_ALIGN(n) alignas(n)
#endif

namespace omega_gpu {
// Alignment is an ABI property, not a guarantee of a particular LDG instruction.
struct OMEGA_ALIGN(16) Rational64 { int64_t num; uint64_t den; };
struct OMEGA_ALIGN(32) Rational128 { __int128_t num; unsigned __int128 den; };
static_assert(sizeof(Rational64)==16 && alignof(Rational64)==16,"Rational64 ABI");
static_assert(sizeof(Rational128)==32 && alignof(Rational128)==32,"Rational128 ABI");
enum Status : uint8_t {
 OK=0, ZERO_DIVISOR=1, OVERFLOW=2, INVALID=4, CAPACITY=8, UNPROVED=16
};
struct Checked { Rational64 value; uint8_t error; };
struct Pruned { Rational64 value; Rational128 absolute_error; uint8_t error; };
OMEGA_HD Rational64 zero(){return {0,1};}
OMEGA_HD Checked failure(uint8_t code){return {zero(),code};}
OMEGA_HD bool valid(Rational64 x){return x.den>0 && x.den<=INT64_MAX && x.num!=INT64_MIN;}
OMEGA_HD uint64_t magnitude(int64_t x){return x<0?uint64_t(-(x+1))+1:uint64_t(x);}
OMEGA_HD unsigned __int128 magnitude128(__int128 x){return x<0?(unsigned __int128)(-(x+1))+1:(unsigned __int128)x;}
}
#endif
