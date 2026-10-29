#ifndef OMEGA_CUDA_API_H
#define OMEGA_CUDA_API_H
#include "grammar_masks.cuh"
#include "../omega_abstract_domain/interval_domain.cuh"
extern "C" {
int omega_cuda_available();
int omega_cuda_search(omega_gpu::SearchConfig config,omega_gpu::GrammarMasks grammar,
 const omega_gpu::Rational64 *constants,const omega_gpu::Rational64 *inputs,const omega_gpu::Rational64 *targets,
 const omega_gpu::RationalInterval *input_bounds,const omega_gpu::RationalInterval *output_bounds,
 omega_gpu::Elite *elites,omega_gpu::SearchStats *stats,char *message,uint32_t message_bytes);
}
#endif
