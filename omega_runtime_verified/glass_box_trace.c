#include "proof_envelope.h"
#include <limits.h>
int omega_trace_init(OmegaTraceRing *ring,OmegaTraceEvent *storage,size_t capacity){
 if(!ring||!storage||!capacity||capacity>SIZE_MAX/sizeof(OmegaTraceEvent))return -1;
 *ring=(OmegaTraceRing){storage,capacity,0,0,0,0,0};return 0;
}
int omega_trace_record(OmegaTraceRing *ring,uint64_t cycle,uint32_t node,uint16_t operation,uint8_t branch,int64_t numerator,uint64_t denominator){
 if(!ring||!ring->events||!ring->capacity||!denominator||denominator>INT64_MAX||numerator==INT64_MIN||branch>1||ring->halted)return -1;
 if(ring->sequence==UINT64_MAX||ring->dropped==UINT64_MAX){ring->halted=1;return -2;}
 OmegaTraceEvent event={ring->sequence++,cycle,node,operation,branch,0,numerator,denominator};
 ring->events[ring->next]=event;ring->next=(ring->next+1)%ring->capacity;
 if(ring->count<ring->capacity)ring->count++;else ring->dropped++;
 return 0;
}
int omega_trace_get(const OmegaTraceRing *ring,size_t index,OmegaTraceEvent *event){
 if(!ring||!event||!ring->events||!ring->capacity||index>=ring->count)return -1;
 size_t start=ring->count==ring->capacity?ring->next:0;
 size_t position=index>=ring->capacity-start?index-(ring->capacity-start):start+index;
 *event=ring->events[position];return 0;
}
int omega_trace_relu(OmegaTraceRing *ring,uint64_t cycle,uint32_t node,int64_t numerator,uint64_t denominator,int64_t *output){
 if(!output)return -1;
 int status=omega_trace_record(ring,cycle,node,7,numerator>0,numerator,denominator);
 if(status)return status;
 *output=numerator>0?numerator:0;return 0;
}
