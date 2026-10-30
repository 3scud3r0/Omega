#ifndef OMEGA_CELLULAR_MICRO_ARENA_H
#define OMEGA_CELLULAR_MICRO_ARENA_H
/* Allocation-free, stackless, single-thread cooperative microactors.
 * Caller owns storage and immutable bytecode. Exact bounded rationals use
 * checked 128-bit intermediates. No GMP, OS, threads, callbacks or I/O here. */
#include <stdint.h>
#include <stddef.h>
#include <limits.h>
#ifndef __SIZEOF_INT128__
#error "This bounded rational backend requires compiler 128-bit integer support"
#endif

typedef struct { int64_t n; uint64_t d; } OmegaMicroQ;
enum { OMEGA_MICRO_SET, OMEGA_MICRO_ADD, OMEGA_MICRO_MUL,
       OMEGA_MICRO_ASSERT, OMEGA_MICRO_SEND, OMEGA_MICRO_RECV,
       OMEGA_MICRO_JUMP, OMEGA_MICRO_JNZ, OMEGA_MICRO_YIELD, OMEGA_MICRO_HALT };
enum { OMEGA_MICRO_READY, OMEGA_MICRO_BLOCKED_SEND,
       OMEGA_MICRO_BLOCKED_RECEIVE, OMEGA_MICRO_HALTED };
typedef struct {
    uint32_t op, reg, target;
    OmegaMicroQ value;
} OmegaMicroInstruction;
typedef struct {
    uint32_t pc, head, tail, count, halted, status;
    uint64_t executed;
    OmegaMicroQ registers[16], mailbox[64];
} OmegaMicroCell;
typedef struct {
    unsigned char *storage;
    size_t storage_bytes, stride, code_length;
    uint32_t actors, registers, mailbox_capacity, quantum, completed, deadlock;
    uint64_t turns, instructions, messages, mailbox_peak, idle_turns;
    const OmegaMicroInstruction *code;
} OmegaMicroRuntime;
_Static_assert(sizeof(OmegaMicroRuntime) <= 256, "Update shared runtime reservation");
_Static_assert(sizeof(OmegaMicroInstruction) <= 64, "Update shared instruction reservation");

static inline OmegaMicroCell *omega_micro_cell(OmegaMicroRuntime *r, uint32_t id) {
    return (OmegaMicroCell *)(void *)(r->storage + (size_t)id * r->stride);
}
static inline unsigned __int128 omega_micro_gcd(unsigned __int128 a, unsigned __int128 b) {
    while (b) { unsigned __int128 t = a % b; a = b; b = t; }
    return a;
}
static inline int omega_micro_normalize(__int128 n, unsigned __int128 d, OmegaMicroQ *out) {
    if (!d || !out) return -1;
    unsigned __int128 magnitude = n < 0 ? (unsigned __int128)(-(n + 1)) + 1 : (unsigned __int128)n;
    unsigned __int128 g = omega_micro_gcd(magnitude, d);
    magnitude /= g; d /= g;
    if (magnitude > INT64_MAX || d > INT64_MAX) return -1;
    out->n = n < 0 ? -(int64_t)magnitude : (int64_t)magnitude;
    out->d = (uint64_t)d;
    return 0;
}
static inline int omega_micro_arithmetic(OmegaMicroQ a, OmegaMicroQ b, uint32_t op, OmegaMicroQ *out) {
    if (!a.d || !b.d || a.d > INT64_MAX || b.d > INT64_MAX || a.n == INT64_MIN || b.n == INT64_MIN) return -1;
    __int128 numerator;
    if (op == OMEGA_MICRO_ADD) numerator = (__int128)a.n * b.d + (__int128)b.n * a.d;
    else if (op == OMEGA_MICRO_MUL) numerator = (__int128)a.n * b.n;
    else return -1;
    return omega_micro_normalize(numerator, (unsigned __int128)a.d * b.d, out);
}
static inline int omega_micro_init(OmegaMicroRuntime *r, void *storage, size_t bytes,
        size_t stride, uint32_t actors, uint32_t registers, uint32_t mailbox_capacity,
        uint32_t quantum, const OmegaMicroInstruction *code, size_t code_length) {
    if (!r || !storage || !code || !actors || actors > 256 || !registers || registers > 16 ||
        !mailbox_capacity || mailbox_capacity > 64 || !quantum || quantum > 64 ||
        !code_length || code_length > 128 || stride < 4096 || stride > 524288 ||
        stride < sizeof(OmegaMicroCell) || (uintptr_t)storage % _Alignof(OmegaMicroCell) ||
        stride % _Alignof(OmegaMicroCell) || actors > SIZE_MAX / stride || bytes < actors * stride) return -1;
    for (size_t i = 0; i < code_length; ++i) {
        const OmegaMicroInstruction *c = &code[i];
        if (c->op > OMEGA_MICRO_HALT) return -2;
        if (c->op <= OMEGA_MICRO_RECV || c->op == OMEGA_MICRO_JNZ) {
            if (c->reg >= registers) return -2;
        }
        if (c->op == OMEGA_MICRO_SEND && c->target >= actors) return -2;
        if ((c->op == OMEGA_MICRO_JUMP || c->op == OMEGA_MICRO_JNZ) && c->target >= code_length) return -2;
        if (c->op <= OMEGA_MICRO_ASSERT && (!c->value.d || c->value.d > INT64_MAX || c->value.n == INT64_MIN)) return -2;
    }
    *r = (OmegaMicroRuntime){0}; r->storage = storage; r->storage_bytes = bytes;
    r->stride = stride; r->actors = actors; r->registers = registers;
    r->mailbox_capacity = mailbox_capacity; r->quantum = quantum;
    r->code = code; r->code_length = code_length;
    for (size_t i = 0; i < (size_t)actors * stride; ++i) r->storage[i] = 0;
    for (uint32_t i = 0; i < actors; ++i) {
        OmegaMicroCell *cell = omega_micro_cell(r, i);
        for (uint32_t j = 0; j < registers; ++j) cell->registers[j] = (OmegaMicroQ){0, 1};
        cell->registers[0].n = i;
    }
    return 0;
}
/* One bounded quantum; 0=blocked/inactive, 1=progress, negative=typed fault. */
static inline int omega_micro_quantum(OmegaMicroRuntime *r, uint32_t id) {
    OmegaMicroCell *cell = omega_micro_cell(r, id);
    if (cell->halted) return 0;
    int progress = 0;
    for (uint32_t used = 0; used < r->quantum; ++used) {
        if (cell->pc >= r->code_length) return -3;
        const OmegaMicroInstruction *c = &r->code[cell->pc];
        uint32_t next = cell->pc + 1;
        switch (c->op) {
        case OMEGA_MICRO_SET: cell->registers[c->reg] = c->value; break;
        case OMEGA_MICRO_ADD: case OMEGA_MICRO_MUL:
            if (omega_micro_arithmetic(cell->registers[c->reg], c->value, c->op, &cell->registers[c->reg])) return -4;
            break;
        case OMEGA_MICRO_ASSERT:
            if ((__int128)cell->registers[c->reg].n * c->value.d != (__int128)c->value.n * cell->registers[c->reg].d) return -5;
            break;
        case OMEGA_MICRO_SEND: {
            OmegaMicroCell *recipient = omega_micro_cell(r, c->target);
            if (recipient->count == r->mailbox_capacity) { cell->status = OMEGA_MICRO_BLOCKED_SEND; return progress; }
            recipient->mailbox[recipient->tail] = cell->registers[c->reg];
            recipient->tail = (recipient->tail + 1) % r->mailbox_capacity; recipient->count++; r->messages++;
            if (recipient->count > r->mailbox_peak) r->mailbox_peak = recipient->count;
            break;
        }
        case OMEGA_MICRO_RECV:
            if (!cell->count) { cell->status = OMEGA_MICRO_BLOCKED_RECEIVE; return progress; }
            cell->registers[c->reg] = cell->mailbox[cell->head]; cell->mailbox[cell->head] = (OmegaMicroQ){0, 1};
            cell->head = (cell->head + 1) % r->mailbox_capacity; cell->count--; break;
        case OMEGA_MICRO_JUMP: next = c->target; break;
        case OMEGA_MICRO_JNZ: if (cell->registers[c->reg].n) next = c->target; break;
        case OMEGA_MICRO_YIELD: case OMEGA_MICRO_HALT: break;
        default: return -2;
        }
        cell->pc = next; cell->executed++; r->instructions++; progress = 1; cell->status = OMEGA_MICRO_READY;
        if (c->op == OMEGA_MICRO_HALT) { cell->halted = 1; cell->status = OMEGA_MICRO_HALTED; r->completed++; return progress; }
        if (c->op == OMEGA_MICRO_YIELD) return progress;
    }
    return progress;
}
static inline int omega_micro_run(OmegaMicroRuntime *r, uint64_t max_turns) {
    if (!r || !max_turns || max_turns > 100000) return -1;
    while (r->turns < max_turns && r->completed < r->actors && !r->deadlock) {
        int progress = omega_micro_quantum(r, (uint32_t)(r->turns % r->actors));
        if (progress < 0) return progress;
        r->idle_turns = progress ? 0 : r->idle_turns + 1;
        if (r->idle_turns >= r->actors && r->completed < r->actors) r->deadlock = 1;
        r->turns++;
    }
    return 0;
}
#endif
