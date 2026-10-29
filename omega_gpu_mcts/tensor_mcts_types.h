#ifndef OMEGA_TENSOR_MCTS_TYPES_H
#define OMEGA_TENSOR_MCTS_TYPES_H
#include "../hardware/cuda/rational_types.cuh"
namespace omega_gpu {
constexpr uint32_t MAX_AST_TOKENS=63,REWARD_SCALE=1048576,NO_NODE=UINT32_MAX;
// Each field is a separately allocated, fixed-capacity contiguous array.
// These are buffer views, never pointers linking individual AST/MCTS nodes.
struct TensorMCTS {
 uint32_t *parent_idx,*children_start;
 uint16_t *children_count;
 float *visit_count;
 Rational64 *total_value; // denominator stays REWARD_SCALE for atomic numerators
 uint16_t *edge_action_token,*prefix_tokens,*prefix_length,*pending_holes;
 uint32_t *expansion_state,*allocated;
 uint32_t forests,capacity,max_tokens;
};
struct SearchConfig {
 uint32_t forests,capacity,rollouts,iterations,max_tokens,examples,variables,constants,elites;
 uint64_t seed;
};
struct SearchStats {
 uint64_t candidates,nodes_evaluated,tier1_survivors;
 float elapsed_ms;
 uint32_t elite_count;
};
struct Elite {
 uint16_t tokens[MAX_AST_TOKENS];uint16_t length;uint16_t reserved;
 uint32_t reward,candidate_index;uint8_t tier1_admissible;uint8_t error;uint16_t padding;
};
}
#endif
