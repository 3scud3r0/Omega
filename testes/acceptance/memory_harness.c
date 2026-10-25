#include "memory.h"
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
int main(void) {
  OmegaArena arena; omega_arena_init(&arena,4096);
  unsigned char *p=omega_arena_alloc(&arena,128);
  assert(p && arena.allocations==1);
  for(size_t i=0;i<128;i++) assert(p[i]==0);
  assert(((uintptr_t)p % _Alignof(max_align_t))==0);
  size_t used=arena.used;
  assert(omega_arena_alloc(&arena,SIZE_MAX)==NULL);
  assert(arena.error==OM_MEMORY_LIMIT && arena.used==used && p[0]==0);
  p[127]=7;
  omega_arena_reset(&arena);
  assert(arena.used==0 && arena.head==NULL && arena.allocations==0);
  for(int n=0;n<100;n++) { assert(omega_arena_alloc(&arena,64)); omega_arena_reset(&arena); }
  puts("arena-ok"); return 0;
}
