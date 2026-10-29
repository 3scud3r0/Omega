#include "runtime/static_arena.h"
#include <assert.h>
static unsigned char storage[10*1024*1024];
static OmegaStaticArena arena;
int main(void){
 OmegaLinearHandle a,b,m;uint32_t first,second;unsigned value=42,observed=0;
 assert(!omega_static_init(&arena,storage,sizeof storage));
 assert(!omega_static_allocate(&arena,8,1,&a));assert(!omega_static_allocate(&arena,16,2,&b));
 assert(omega_static_release(&arena,a));assert(!omega_static_write(&arena,b,0,&value,sizeof value));
 assert(omega_static_write(&arena,b,15,&value,sizeof value));
 assert(!omega_static_borrow(&arena,b,&first));assert(omega_static_move(&arena,b,3,&m));assert(omega_static_write(&arena,b,0,&value,sizeof value));
 assert(!omega_static_unborrow(&arena,b,first));assert(!omega_static_borrow(&arena,b,&second));
 assert(first!=second);assert(omega_static_unborrow(&arena,b,first));assert(!omega_static_unborrow(&arena,b,second));
 assert(!omega_static_move(&arena,b,3,&m));assert(omega_static_read(&arena,b,0,&observed,sizeof observed));
 assert(!omega_static_read(&arena,m,0,&observed,sizeof observed));assert(observed==42);
 assert(!omega_static_release(&arena,m));assert(omega_static_release(&arena,m));assert(!omega_static_release(&arena,a));
 assert(!omega_static_finish(&arena));assert(!omega_static_allocate(&arena,sizeof storage,1,&a));assert(omega_static_allocate(&arena,1,1,&b));assert(!omega_static_release(&arena,a));
 assert(arena.peak==sizeof storage);assert(!omega_static_finish(&arena));return 0;
}
