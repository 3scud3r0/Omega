/* Bounded lifetime arena. Destroy only after all values using it are dead.
 * GMP limbs have their own allocator: clear mpq values before arena reset. */
#ifndef OMEGA_MEMORY_H
#define OMEGA_MEMORY_H
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
typedef enum { OM_MEMORY_OK, OM_MEMORY_LIMIT, OM_MEMORY_SYSTEM } OmegaMemoryError;
typedef struct OmegaAllocation {
  struct OmegaAllocation *next;
  _Alignas(max_align_t) unsigned char data[];
} OmegaAllocation;
typedef struct {
  OmegaAllocation *head;
  size_t used, peak, allocations, quota;
  OmegaMemoryError error;
} OmegaArena;
static void omega_arena_init(OmegaArena *a, size_t quota) {
  *a = (OmegaArena){ .quota = quota };
}
static void *omega_arena_alloc(OmegaArena *a, size_t n) {
  if (!n) n = 1;
  if (n > SIZE_MAX - sizeof(OmegaAllocation)) {a->error=OM_MEMORY_LIMIT;return NULL;}
  size_t total=sizeof(OmegaAllocation)+n;
  if (total>a->quota || a->used>a->quota-total) {a->error=OM_MEMORY_LIMIT;return NULL;}
  OmegaAllocation *block=calloc(1,total);
  if (!block) {a->error=OM_MEMORY_SYSTEM;return NULL;}
  block->next=a->head;a->head=block;a->used+=total;a->allocations++;
  if(a->used>a->peak)a->peak=a->used;
  a->error=OM_MEMORY_OK;return block->data;
}
static void omega_arena_reset(OmegaArena *a) {
  while(a->head){OmegaAllocation *next=a->head->next;free(a->head);a->head=next;}
  a->used=0;a->allocations=0;a->error=OM_MEMORY_OK;
}
#endif
