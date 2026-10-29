#ifndef OMEGA_PROOF_ENVELOPE_H
#define OMEGA_PROOF_ENVELOPE_H
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct {
 const void* output_tensor;
 size_t tensor_bytes;
 uint8_t proof_hash_sha256[32];
 const char* lean_certificate_uri;
 uint64_t inference_cycle_count;
} OmegaProofEnvelope;
/* Hash and URI identify a proof artifact. This struct alone does not validate
   its signature, statements, output binding or a physical clock measurement. */
typedef struct {
 uint64_t sequence,inference_cycle;
 uint32_t node;
 uint16_t operation;
 uint8_t branch,reserved;
 int64_t numerator;
 uint64_t denominator;
} OmegaTraceEvent;
typedef struct {
 OmegaTraceEvent *events;
 size_t capacity,count,next;
 uint64_t sequence,dropped;
 uint8_t halted;
} OmegaTraceRing;
int omega_trace_init(OmegaTraceRing*,OmegaTraceEvent*,size_t);
int omega_trace_record(OmegaTraceRing*,uint64_t,uint32_t,uint16_t,uint8_t,int64_t,uint64_t);
int omega_trace_get(const OmegaTraceRing*,size_t,OmegaTraceEvent*);
int omega_trace_relu(OmegaTraceRing*,uint64_t,uint32_t,int64_t,uint64_t,int64_t*);
#ifdef __cplusplus
}
#endif
#endif
