#ifndef OMEGA_MCTS_KERNEL_CUH
#define OMEGA_MCTS_KERNEL_CUH
#include "grammar_masks.cuh"
namespace omega_gpu {
#ifdef __CUDACC__
__global__ void initialize_tree(TensorMCTS tree);
__global__ void select_puct(TensorMCTS tree,GrammarMasks grammar,uint32_t *selected,uint32_t rollouts);
__global__ void expand_nodes(TensorMCTS tree,GrammarMasks grammar,const uint32_t *selected,uint32_t rollouts);
__global__ void generate_rollouts(TensorMCTS tree,GrammarMasks grammar,uint32_t *selected,uint32_t rollouts,uint32_t iteration,
 uint64_t seed,uint16_t *ops,int32_t *left,int32_t *right,uint32_t *counts,uint32_t *roots,uint32_t candidates,uint8_t *errors,
 uint16_t *candidate_tokens,uint16_t *candidate_lengths);
__global__ void reward_backprop(TensorMCTS tree,const uint32_t *selected,uint32_t rollouts,uint32_t iteration,
 const Rational64 *values,const Rational64 *targets,const uint8_t *errors,uint32_t examples,uint32_t *rewards);
__global__ void select_elites(const uint8_t *admissible,const uint8_t *errors,const uint32_t *rewards,
 const uint16_t *tokens,const uint16_t *lengths,uint32_t candidates,uint32_t requested,Elite *out,uint32_t *count,uint64_t *survivors);
#endif
}
#endif
