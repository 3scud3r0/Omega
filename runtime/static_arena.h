#ifndef OMEGA_STATIC_ARENA_H
#define OMEGA_STATIC_ARENA_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define OMEGA_STATIC_SLOTS 1024
typedef struct {uint32_t slot,generation,owner;} OmegaLinearHandle;
typedef struct {size_t offset,size;uint32_t generation,owner,borrows;uint8_t alive,retired;} OmegaLinearRegion;
typedef struct {unsigned char *memory;size_t capacity,used,peak;uint32_t depth,active[OMEGA_STATIC_SLOTS],borrow_depth,next_borrow,borrow_tokens[OMEGA_STATIC_SLOTS],borrow_slots[OMEGA_STATIC_SLOTS];OmegaLinearRegion regions[OMEGA_STATIC_SLOTS];} OmegaStaticArena;
static inline int omega_static_init(OmegaStaticArena *a,void *storage,size_t capacity){if(!a||!storage||!capacity)return -1;memset(a,0,sizeof *a);a->memory=storage;a->capacity=capacity;return 0;}
static inline OmegaLinearRegion *omega_static_region(OmegaStaticArena *a,OmegaLinearHandle h){if(!a||h.slot>=OMEGA_STATIC_SLOTS)return NULL;OmegaLinearRegion *r=&a->regions[h.slot];return r->alive&&r->generation==h.generation&&r->owner==h.owner?r:NULL;}
static inline int omega_static_allocate(OmegaStaticArena *a,size_t size,uint32_t owner,OmegaLinearHandle *out){
 if(!a||!out||!size||a->used>a->capacity||size>a->capacity-a->used||a->depth>=OMEGA_STATIC_SLOTS)return -1;
 uint32_t slot=0;while(slot<OMEGA_STATIC_SLOTS&&(a->regions[slot].alive||a->regions[slot].retired))slot++;if(slot==OMEGA_STATIC_SLOTS)return -2;
 OmegaLinearRegion *r=&a->regions[slot];if(r->generation>=UINT32_MAX-1){r->retired=1;return -3;}
 r->generation++;r->owner=owner;r->offset=a->used;r->size=size;r->alive=1;r->borrows=0;a->active[a->depth++]=slot;a->used+=size;if(a->used>a->peak)a->peak=a->used;
 *out=(OmegaLinearHandle){slot,r->generation,owner};return 0;
}
static inline int omega_static_move(OmegaStaticArena *a,OmegaLinearHandle old,uint32_t owner,OmegaLinearHandle *out){OmegaLinearRegion *r=omega_static_region(a,old);if(!r||!out||r->borrows||r->generation==UINT32_MAX)return -1;r->generation++;r->owner=owner;*out=(OmegaLinearHandle){old.slot,r->generation,owner};return 0;}
static inline int omega_static_write(OmegaStaticArena *a,OmegaLinearHandle h,size_t offset,const void *data,size_t count){OmegaLinearRegion *r=omega_static_region(a,h);if(!r||r->borrows||!data||offset>r->size||count>r->size-offset)return -1;memcpy(a->memory+r->offset+offset,data,count);return 0;}
static inline int omega_static_read(OmegaStaticArena *a,OmegaLinearHandle h,size_t offset,void *data,size_t count){OmegaLinearRegion *r=omega_static_region(a,h);if(!r||!data||offset>r->size||count>r->size-offset)return -1;memcpy(data,a->memory+r->offset+offset,count);return 0;}
static inline int omega_static_borrow(OmegaStaticArena *a,OmegaLinearHandle h,uint32_t *serial){OmegaLinearRegion *r=omega_static_region(a,h);if(!r||!serial||a->borrow_depth>=OMEGA_STATIC_SLOTS||a->next_borrow==UINT32_MAX)return -1;*serial=++a->next_borrow;a->borrow_tokens[a->borrow_depth]=*serial;a->borrow_slots[a->borrow_depth++]=h.slot;r->borrows++;return 0;}
static inline int omega_static_unborrow(OmegaStaticArena *a,OmegaLinearHandle h,uint32_t serial){OmegaLinearRegion *r=omega_static_region(a,h);if(!r||!serial||!r->borrows||!a->borrow_depth||serial!=a->borrow_tokens[a->borrow_depth-1]||h.slot!=a->borrow_slots[a->borrow_depth-1])return -1;a->borrow_depth--;r->borrows--;return 0;}
static inline int omega_static_release(OmegaStaticArena *a,OmegaLinearHandle h){OmegaLinearRegion *r=omega_static_region(a,h);if(!r||r->borrows||!a->depth||a->active[a->depth-1]!=h.slot)return -1;a->depth--;a->used=r->offset;r->alive=0;if(r->generation==UINT32_MAX)r->retired=1;else r->generation++;return 0;}
static inline int omega_static_finish(const OmegaStaticArena *a){return a&&a->depth==0&&a->used==0&&a->borrow_depth==0?0:-1;}
#endif
