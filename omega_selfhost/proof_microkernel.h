/* Freestanding resource core, not an OS privilege boundary or a device driver.
   A host must authenticate principals and proof tickets before invoking it. */
#ifndef OMEGA_PROOF_MICROKERNEL_H
#define OMEGA_PROOF_MICROKERNEL_H
#include <stdint.h>
#include <stddef.h>
#define OMEGA_KERNEL_REGIONS 64
typedef struct {uint32_t slot,generation,owner;} omega_handle;
typedef struct {size_t offset,size;uint32_t generation,owner;uint16_t readers;uint8_t writer,alive,retired;} omega_region;
typedef struct {unsigned char *memory;size_t capacity;omega_region regions[OMEGA_KERNEL_REGIONS];} omega_microkernel;
static void omega_kernel_init(omega_microkernel *k,unsigned char *memory,size_t capacity){
 k->memory=memory;k->capacity=capacity;for(unsigned i=0;i<OMEGA_KERNEL_REGIONS;i++)k->regions[i]=(omega_region){0};
}
static omega_region *omega_kernel_region(omega_microkernel*k,omega_handle h){
 if(!k||h.slot>=OMEGA_KERNEL_REGIONS){return NULL;}
 omega_region*r=&k->regions[h.slot];
 return r->alive&&r->generation==h.generation&&r->owner==h.owner?r:NULL;
}
static int omega_kernel_allocate(omega_microkernel*k,uint32_t owner,size_t size,omega_handle*out){
 if(!k||!out||!k->memory||!size||size>k->capacity)return -1;
 unsigned slot=OMEGA_KERNEL_REGIONS;for(unsigned i=0;i<OMEGA_KERNEL_REGIONS;i++)if(!k->regions[i].alive&&!k->regions[i].retired){slot=i;break;}
 if(slot==OMEGA_KERNEL_REGIONS)return -2;
 size_t offset=0;int moved;
 do{if(offset>k->capacity-size){return -3;}moved=0;for(unsigned i=0;i<OMEGA_KERNEL_REGIONS;i++){omega_region*r=&k->regions[i];if(r->alive&&offset<r->offset+r->size&&r->offset<offset+size){offset=r->offset+r->size;moved=1;break;}}}while(moved);
 omega_region*r=&k->regions[slot];if(r->generation==UINT32_MAX){r->retired=1;return -4;}
 r->generation++;r->offset=offset;r->size=size;r->owner=owner;r->readers=0;r->writer=0;r->alive=1;
 *out=(omega_handle){slot,r->generation,owner};return 0;
}
static int omega_kernel_borrow(omega_microkernel*k,omega_handle h,int mutable,void**pointer){
 omega_region*r=omega_kernel_region(k,h);if(!r||!pointer||r->writer||(mutable&&r->readers)||r->readers==UINT16_MAX)return -1;
 if(mutable)r->writer=1;else r->readers++;*pointer=k->memory+r->offset;return 0;
}
static int omega_kernel_unborrow(omega_microkernel*k,omega_handle h,int mutable){
 omega_region*r=omega_kernel_region(k,h);if(!r)return -1;
 if(mutable){if(!r->writer)return -2;r->writer=0;}else{if(!r->readers)return -2;r->readers--;}return 0;
}
static int omega_kernel_move(omega_microkernel*k,omega_handle old,uint32_t owner,omega_handle*out){
 omega_region*r=omega_kernel_region(k,old);if(!r||r->writer||r->readers||!out||r->generation==UINT32_MAX)return -1;
 r->owner=owner;r->generation++;*out=(omega_handle){old.slot,r->generation,owner};return 0;
}
static int omega_kernel_consume(omega_microkernel*k,omega_handle h){
 omega_region*r=omega_kernel_region(k,h);if(!r||r->writer||r->readers)return -1;
 r->alive=0;if(r->generation==UINT32_MAX)r->retired=1;else r->generation++;return 0;
}
#endif
