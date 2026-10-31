#ifndef OMEGA_EMBEDDED_LOGIC_H
#define OMEGA_EMBEDDED_LOGIC_H

/* Predicative intensional dependent type checker, not a Lean/Coq importer.
 * No axioms, unification, tactics, general recursion, proof irrelevance or eta.
 * The caller owns all arenas. Exhaustion is UNKNOWN, never successful checking.
 * Conversion: beta, delta, zeta, projections, Nat recursion and bounded exact Q.
 */
#include <stddef.h>
#include <stdint.h>
#include <limits.h>
#include "../../omega_selfhost/bounded_rational.h"

#define OK_NONE UINT32_MAX
#define OK_CONTEXT_MAX 256u
#define OK_DEFINITIONS_MAX 256u
#define OK_LEVEL_MAX 31u

typedef enum {
    OK_SORT,
    OK_VAR,
    OK_PI,
    OK_LAMBDA,
    OK_APP,
    OK_LET,
    OK_ANNOTATION,
    OK_SIGMA,
    OK_PAIR,
    OK_FIRST,
    OK_SECOND,
    OK_NAT,
    OK_ZERO,
    OK_SUCCESSOR,
    OK_NAT_LITERAL,
    OK_NAT_ADD,
    OK_NAT_MUL,
    OK_NAT_REC,
    OK_EQUALITY,
    OK_REFL,
    OK_TRANSPORT,
    OK_UNIT,
    OK_UNIT_VALUE,
    OK_EMPTY,
    OK_ABSURD,
    OK_CONSTANT,
    OK_RAT,
    OK_RAT_LITERAL,
    OK_RAT_ADD,
    OK_RAT_MUL,
    OK_RAT_NEG,
    OK_TAG_COUNT
} ok_tag;

typedef enum {
    OK_SUCCESS,
    OK_BAD_NODE,
    OK_BAD_SCOPE,
    OK_TYPE_MISMATCH,
    OK_NOT_A_TYPE,
    OK_NOT_A_FUNCTION,
    OK_NOT_A_PAIR,
    OK_BAD_CONSTANT,
    OK_ARENA_LIMIT,
    OK_FUEL_LIMIT,
    OK_DEPTH_LIMIT,
    OK_CONTEXT_LIMIT,
    OK_UNIVERSE_LIMIT,
    OK_ARITHMETIC_LIMIT
} ok_error;

typedef struct {
    uint32_t child[4];
    int64_t data[2];
    uint8_t tag;
} ok_term;

typedef struct {
    uint32_t type;
    uint32_t body;
} ok_definition;

typedef struct {
    ok_term *terms;
    size_t count;
    size_t capacity;
    uint64_t fuel;
    uint64_t initial_fuel;
    uint32_t depth_limit;
    uint32_t context[OK_CONTEXT_MAX];
    size_t context_size;
    ok_definition definitions[OK_DEFINITIONS_MAX];
    size_t definition_count;
    ok_error error;
    uint32_t error_node;
    uint32_t peak_depth;
} ok_checker;

static inline uint32_t ok_fail(ok_checker *s, ok_error error, uint32_t node)
{
    if (s && s->error == OK_SUCCESS) {
        s->error = error;
        s->error_node = node;
    }
    return OK_NONE;
}

static inline int ok_tick(ok_checker *s, uint32_t node, uint32_t depth)
{
    if (!s || s->error != OK_SUCCESS) {
        return 0;
    }
    if (depth > s->depth_limit) {
        ok_fail(s, OK_DEPTH_LIMIT, node);
        return 0;
    }
    if (depth > s->peak_depth) {
        s->peak_depth = depth;
    }
    if (s->fuel == 0) {
        ok_fail(s, OK_FUEL_LIMIT, node);
        return 0;
    }
    s->fuel--;
    return 1;
}

static inline int ok_init(ok_checker *s, ok_term *arena, size_t capacity,
                          uint64_t fuel, uint32_t depth)
{
    if (!s || !arena || capacity < 16 || capacity > 65536 ||
        fuel == 0 || fuel > 10000000 || depth < 8 || depth > 256) {
        return 0;
    }
    s->terms = arena;
    s->capacity = capacity;
    s->count = 0;
    s->fuel = fuel;
    s->initial_fuel = fuel;
    s->depth_limit = depth;
    s->context_size = 0;
    s->definition_count = 0;
    s->error = OK_SUCCESS;
    s->error_node = OK_NONE;
    s->peak_depth = 0;
    return 1;
}

static inline unsigned ok_arity(unsigned tag)
{
    switch (tag) {
    case OK_PI:
    case OK_LAMBDA:
    case OK_APP:
    case OK_SIGMA:
    case OK_ANNOTATION:
    case OK_REFL:
    case OK_ABSURD:
    case OK_NAT_ADD:
    case OK_NAT_MUL:
    case OK_RAT_ADD:
    case OK_RAT_MUL:
        return 2;
    case OK_LET:
    case OK_PAIR:
    case OK_EQUALITY:
    case OK_TRANSPORT:
        return 3;
    case OK_FIRST:
    case OK_SECOND:
    case OK_SUCCESSOR:
    case OK_RAT_NEG:
        return 1;
    case OK_NAT_REC:
        return 4;
    default:
        return 0;
    }
}

static inline unsigned ok_data_arity(unsigned tag)
{
    if (tag == OK_RAT_LITERAL) {
        return 2;
    }
    if (tag == OK_SORT || tag == OK_VAR || tag == OK_CONSTANT ||
        tag == OK_NAT_LITERAL) {
        return 1;
    }
    return 0;
}

static inline const ok_term *ok_get(ok_checker *s, uint32_t id)
{
    if (!s || id >= s->count) {
        ok_fail(s, OK_BAD_NODE, id);
        return NULL;
    }
    return &s->terms[id];
}

static inline uint32_t ok_new(ok_checker *s, unsigned tag,
                            uint32_t a, uint32_t b, uint32_t c, uint32_t d,
                            int64_t x, int64_t y)
{
    if (!s || s->error != OK_SUCCESS || tag >= OK_TAG_COUNT) {
        return ok_fail(s, OK_BAD_NODE, OK_NONE);
    }
    if (s->count >= s->capacity) {
        return ok_fail(s, OK_ARENA_LIMIT, OK_NONE);
    }
    /* Keep shifts safe even when callers bypass the JSON wire decoder. */
    if ((tag == OK_SORT && (x < 0 || x > OK_LEVEL_MAX + 1)) ||
        ((tag == OK_VAR || tag == OK_CONSTANT) && (x < 0 || x >= 256)) ||
        (tag == OK_NAT_LITERAL && x < 0) ||
        (tag == OK_RAT_LITERAL && (x == INT64_MIN || y <= 0))) {
        return ok_fail(s, OK_BAD_NODE, OK_NONE);
    }
    uint32_t children[4] = {a, b, c, d};
    for (unsigned i = 0; i < ok_arity(tag); ++i) {
        if (children[i] >= s->count) {
            return ok_fail(s, OK_BAD_NODE, children[i]);
        }
    }
    uint32_t id = (uint32_t)s->count++;
    ok_term *term = &s->terms[id];
    term->tag = (uint8_t)tag;
    for (unsigned i = 0; i < 4; ++i) {
        term->child[i] = children[i];
    }
    term->data[0] = x;
    term->data[1] = y;
    return id;
}

static inline uint32_t ok_atom(ok_checker *s, unsigned tag)
{
    return ok_new(s, tag, 0, 0, 0, 0, 0, 0);
}

static inline uint32_t ok_unary(ok_checker *s, unsigned tag, uint32_t a)
{
    return ok_new(s, tag, a, 0, 0, 0, 0, 0);
}

static inline uint32_t ok_binary(ok_checker *s, unsigned tag, uint32_t a, uint32_t b)
{
    return ok_new(s, tag, a, b, 0, 0, 0, 0);
}

static inline uint32_t ok_sort(ok_checker *s, int64_t level)
{
    if (level < 0 || level > OK_LEVEL_MAX + 1) {
        return ok_fail(s, OK_UNIVERSE_LIMIT, OK_NONE);
    }
    return ok_new(s, OK_SORT, 0, 0, 0, 0, level, 0);
}

static inline uint32_t ok_variable(ok_checker *s, int64_t index)
{
    if (index < 0 || index >= OK_CONTEXT_MAX) {
        return ok_fail(s, OK_BAD_SCOPE, OK_NONE);
    }
    return ok_new(s, OK_VAR, 0, 0, 0, 0, index, 0);
}

static inline uint32_t ok_nat_literal(ok_checker *s, int64_t n)
{
    if (n < 0) {
        return ok_fail(s, OK_BAD_NODE, OK_NONE);
    }
    return ok_new(s, OK_NAT_LITERAL, 0, 0, 0, 0, n, 0);
}

static inline unsigned ok_binder_child(unsigned tag, unsigned child)
{
    return ((tag == OK_PI || tag == OK_LAMBDA || tag == OK_SIGMA) && child == 1) ||
           (tag == OK_LET && child == 2);
}

static uint32_t ok_shift(ok_checker *, uint32_t, int32_t, uint32_t, uint32_t);
static uint32_t ok_substitute(ok_checker *, uint32_t, uint32_t, uint32_t, uint32_t);
static uint32_t ok_whnf(ok_checker *, uint32_t, uint32_t);
static uint32_t ok_infer(ok_checker *, uint32_t, uint32_t);
static int ok_convert(ok_checker *, uint32_t, uint32_t, uint32_t);
static int ok_check(ok_checker *, uint32_t, uint32_t, uint32_t);

static uint32_t ok_shift(ok_checker *s, uint32_t id, int32_t amount,
                         uint32_t cutoff, uint32_t depth)
{
    if (!ok_tick(s, id, depth)) {
        return OK_NONE;
    }
    const ok_term *source = ok_get(s, id);
    if (!source) {
        return OK_NONE;
    }
    ok_term term = *source;
    if (term.tag == OK_VAR && term.data[0] >= cutoff) {
        int64_t index = term.data[0] + amount;
        return ok_variable(s, index);
    }
    unsigned arity = ok_arity(term.tag);
    int changed = 0;
    for (unsigned i = 0; i < arity; ++i) {
        uint32_t next = ok_shift(s, term.child[i], amount,
                                 cutoff + ok_binder_child(term.tag, i), depth + 1);
        if (next == OK_NONE) {
            return OK_NONE;
        }
        changed |= next != term.child[i];
        term.child[i] = next;
    }
    if (!changed) {
        return id;
    }
    return ok_new(s, term.tag, term.child[0], term.child[1], term.child[2],
                   term.child[3], term.data[0], term.data[1]);
}

static uint32_t ok_substitute(ok_checker *s, uint32_t id, uint32_t index,
                              uint32_t value, uint32_t depth)
{
    if (!ok_tick(s, id, depth)) {
        return OK_NONE;
    }
    const ok_term *source = ok_get(s, id);
    if (!source) {
        return OK_NONE;
    }
    ok_term term = *source;
    if (term.tag == OK_VAR && term.data[0] == index) {
        return value;
    }
    unsigned arity = ok_arity(term.tag);
    int changed = 0;
    for (unsigned i = 0; i < arity; ++i) {
        uint32_t replacement = value;
        uint32_t binder = ok_binder_child(term.tag, i);
        if (binder) {
            replacement = ok_shift(s, value, 1, 0, depth + 1);
        }
        uint32_t next = ok_substitute(s, term.child[i], index + binder,
                                      replacement, depth + 1);
        if (next == OK_NONE) {
            return OK_NONE;
        }
        changed |= next != term.child[i];
        term.child[i] = next;
    }
    if (!changed) {
        return id;
    }
    return ok_new(s, term.tag, term.child[0], term.child[1], term.child[2],
                   term.child[3], term.data[0], term.data[1]);
}

static inline uint32_t ok_instantiate(ok_checker *s, uint32_t body,
                                     uint32_t argument, uint32_t depth)
{
    uint32_t lifted = ok_shift(s, argument, 1, 0, depth + 1);
    uint32_t replaced = ok_substitute(s, body, 0, lifted, depth + 1);
    return ok_shift(s, replaced, -1, 0, depth + 1);
}

static inline int ok_natural_value(ok_checker *s, uint32_t id, int64_t *out)
{
    const ok_term *term = ok_get(s, id);
    if (!term) {
        return 0;
    }
    if (term->tag == OK_ZERO) {
        *out = 0;
        return 1;
    }
    if (term->tag == OK_NAT_LITERAL && term->data[0] >= 0) {
        *out = term->data[0];
        return 1;
    }
    return 0;
}

static inline uint32_t ok_q_literal(ok_checker *s, omega_q64 q)
{
    return ok_new(s, OK_RAT_LITERAL, 0, 0, 0, 0,
                   q.numerator, (int64_t)q.denominator);
}

static uint32_t ok_whnf(ok_checker *s, uint32_t id, uint32_t depth)
{
    for (;;) {
        if (!ok_tick(s, id, depth)) {
            return OK_NONE;
        }
        const ok_term *source = ok_get(s, id);
        if (!source) {
            return OK_NONE;
        }
        ok_term term = *source;
        if (term.tag == OK_CONSTANT) {
            if (term.data[0] < 0 || (uint64_t)term.data[0] >= s->definition_count) {
                return ok_fail(s, OK_BAD_CONSTANT, id);
            }
            id = s->definitions[term.data[0]].body;
            continue;
        }
        if (term.tag == OK_ANNOTATION) {
            id = term.child[0];
            continue;
        }
        if (term.tag == OK_LET) {
            id = ok_instantiate(s, term.child[2], term.child[1], depth + 1);
            continue;
        }
        if (term.tag == OK_APP) {
            uint32_t function = ok_whnf(s, term.child[0], depth + 1);
            const ok_term *fn = ok_get(s, function);
            if (!fn) {
                return OK_NONE;
            }
            if (fn->tag == OK_LAMBDA) {
                id = ok_instantiate(s, fn->child[1], term.child[1], depth + 1);
                continue;
            }
            return function == term.child[0] ? id :
                ok_binary(s, OK_APP, function, term.child[1]);
        }
        if (term.tag == OK_FIRST || term.tag == OK_SECOND) {
            uint32_t pair = ok_whnf(s, term.child[0], depth + 1);
            const ok_term *p = ok_get(s, pair);
            if (!p) {
                return OK_NONE;
            }
            if (p->tag == OK_PAIR) {
                id = p->child[term.tag == OK_FIRST ? 1 : 2];
                continue;
            }
            return pair == term.child[0] ? id : ok_unary(s, term.tag, pair);
        }
        if (term.tag == OK_ZERO) {
            return ok_nat_literal(s, 0);
        }
        if (term.tag == OK_SUCCESSOR) {
            uint32_t child = ok_whnf(s, term.child[0], depth + 1);
            int64_t value;
            if (ok_natural_value(s, child, &value)) {
                if (value == INT64_MAX) {
                    return ok_fail(s, OK_ARITHMETIC_LIMIT, id);
                }
                return ok_nat_literal(s, value + 1);
            }
            return child == term.child[0] ? id : ok_unary(s, OK_SUCCESSOR, child);
        }
        if (term.tag == OK_NAT_ADD || term.tag == OK_NAT_MUL) {
            uint32_t left = ok_whnf(s, term.child[0], depth + 1);
            uint32_t right = ok_whnf(s, term.child[1], depth + 1);
            int64_t a;
            int64_t b;
            int left_numeric = ok_natural_value(s, left, &a);
            int right_numeric = ok_natural_value(s, right, &b);
            if (s->error != OK_SUCCESS) {
                return OK_NONE;
            }
            if (left_numeric && right_numeric) {
                __int128 value = term.tag == OK_NAT_ADD ?
                    (__int128)a + b : (__int128)a * b;
                if (value > INT64_MAX) {
                    return ok_fail(s, OK_ARITHMETIC_LIMIT, id);
                }
                return ok_nat_literal(s, (int64_t)value);
            }
            if (left_numeric && a == 0) {
                return term.tag == OK_NAT_ADD ? right : ok_nat_literal(s, 0);
            }
            const ok_term *lhs = ok_get(s, left);
            uint32_t predecessor = OK_NONE;
            if (left_numeric && a > 0) {
                predecessor = ok_nat_literal(s, a - 1);
            } else if (lhs && lhs->tag == OK_SUCCESSOR) {
                predecessor = lhs->child[0];
            }
            if (predecessor != OK_NONE) {
                uint32_t tail = ok_binary(s, term.tag, predecessor, right);
                id = term.tag == OK_NAT_ADD ?
                    ok_unary(s, OK_SUCCESSOR, tail) :
                    ok_binary(s, OK_NAT_ADD, right, tail);
                continue;
            }
            return left == term.child[0] && right == term.child[1] ? id :
                ok_binary(s, term.tag, left, right);
        }
        if (term.tag == OK_NAT_REC) {
            uint32_t n = ok_whnf(s, term.child[3], depth + 1);
            int64_t value;
            uint32_t predecessor = OK_NONE;
            if (ok_natural_value(s, n, &value)) {
                if (value == 0) {
                    id = term.child[1];
                    continue;
                }
                predecessor = ok_nat_literal(s, value - 1);
            } else {
                const ok_term *natural = ok_get(s, n);
                if (natural && natural->tag == OK_SUCCESSOR) {
                    predecessor = natural->child[0];
                }
            }
            if (predecessor != OK_NONE) {
                uint32_t rec = ok_new(s, OK_NAT_REC, term.child[0], term.child[1],
                                      term.child[2], predecessor, 0, 0);
                uint32_t applied = ok_binary(s, OK_APP, term.child[2], predecessor);
                id = ok_binary(s, OK_APP, applied, rec);
                continue;
            }
            return n == term.child[3] ? id :
                ok_new(s, OK_NAT_REC, term.child[0], term.child[1], term.child[2], n, 0, 0);
        }
        if (term.tag == OK_TRANSPORT) {
            uint32_t equality = ok_whnf(s, term.child[1], depth + 1);
            const ok_term *proof = ok_get(s, equality);
            if (proof && proof->tag == OK_REFL) {
                id = term.child[2];
                continue;
            }
            return equality == term.child[1] ? id :
                ok_new(s, OK_TRANSPORT, term.child[0], equality, term.child[2], 0, 0, 0);
        }
        if (term.tag == OK_RAT_LITERAL) {
            if (term.data[0] == INT64_MIN || term.data[1] <= 0) {
                return ok_fail(s, OK_BAD_NODE, id);
            }
            omega_q64 q;
            if (omega_q64_make(&q, term.data[0], (uint64_t)term.data[1]) != OMEGA_Q_OK) {
                return ok_fail(s, OK_ARITHMETIC_LIMIT, id);
            }
            if (q.numerator == term.data[0] && q.denominator == (uint64_t)term.data[1]) {
                return id;
            }
            return ok_q_literal(s, q);
        }
        if (term.tag == OK_RAT_ADD || term.tag == OK_RAT_MUL || term.tag == OK_RAT_NEG) {
            uint32_t left = ok_whnf(s, term.child[0], depth + 1);
            uint32_t right = term.tag == OK_RAT_NEG ? left :
                ok_whnf(s, term.child[1], depth + 1);
            const ok_term *a = ok_get(s, left);
            const ok_term *b = ok_get(s, right);
            if (!a || !b) {
                return OK_NONE;
            }
            if (a->tag == OK_RAT_LITERAL && b->tag == OK_RAT_LITERAL) {
                omega_q64 x = {a->data[0], (uint64_t)a->data[1]};
                omega_q64 y = {b->data[0], (uint64_t)b->data[1]};
                omega_q64 q;
                int status;
                if (term.tag == OK_RAT_NEG) {
                    status = omega_q64_make(&q, -(__int128)x.numerator, x.denominator);
                } else if (term.tag == OK_RAT_ADD) {
                    status = omega_q64_add(&q, x, y);
                } else {
                    status = omega_q64_mul(&q, x, y);
                }
                if (status != OMEGA_Q_OK) {
                    return ok_fail(s, OK_ARITHMETIC_LIMIT, id);
                }
                return ok_q_literal(s, q);
            }
            if (left == term.child[0] && (term.tag == OK_RAT_NEG || right == term.child[1])) {
                return id;
            }
            return term.tag == OK_RAT_NEG ? ok_unary(s, OK_RAT_NEG, left) :
                ok_binary(s, term.tag, left, right);
        }
        return id;
    }
}

static int ok_convert(ok_checker *s, uint32_t left, uint32_t right, uint32_t depth)
{
    if (!ok_tick(s, left, depth)) {
        return 0;
    }
    if (left == right && left < s->count) {
        return 1;
    }
    left = ok_whnf(s, left, depth + 1);
    right = ok_whnf(s, right, depth + 1);
    const ok_term *a = ok_get(s, left);
    const ok_term *b = ok_get(s, right);
    if (!a || !b || s->error != OK_SUCCESS) {
        return 0;
    }
    if (left == right) {
        return 1;
    }
    if (a->tag != b->tag || a->data[0] != b->data[0] || a->data[1] != b->data[1]) {
        return 0;
    }
    ok_term x = *a;
    ok_term y = *b;
    for (unsigned i = 0; i < ok_arity(x.tag); ++i) {
        if (!ok_convert(s, x.child[i], y.child[i], depth + 1)) {
            return 0;
        }
    }
    return 1;
}

static inline int ok_push(ok_checker *s, uint32_t type, uint32_t node)
{
    if (s->context_size >= OK_CONTEXT_MAX) {
        ok_fail(s, OK_CONTEXT_LIMIT, node);
        return 0;
    }
    s->context[s->context_size++] = type;
    return 1;
}

static inline int64_t ok_type_level(ok_checker *s, uint32_t type, uint32_t depth)
{
    uint32_t inferred = ok_infer(s, type, depth + 1);
    uint32_t reduced = ok_whnf(s, inferred, depth + 1);
    const ok_term *sort = ok_get(s, reduced);
    if (!sort || sort->tag != OK_SORT) {
        ok_fail(s, OK_NOT_A_TYPE, type);
        return -1;
    }
    return sort->data[0];
}

static uint32_t ok_infer(ok_checker *s, uint32_t id, uint32_t depth)
{
    if (!ok_tick(s, id, depth)) {
        return OK_NONE;
    }
    const ok_term *source = ok_get(s, id);
    if (!source) {
        return OK_NONE;
    }
    ok_term term = *source;
    switch (term.tag) {
    case OK_SORT:
        if (term.data[0] < 0 || term.data[0] > OK_LEVEL_MAX) {
            return ok_fail(s, OK_UNIVERSE_LIMIT, id);
        }
        return ok_sort(s, term.data[0] + 1);
    case OK_VAR:
        if (term.data[0] < 0 || (uint64_t)term.data[0] >= s->context_size) {
            return ok_fail(s, OK_BAD_SCOPE, id);
        }
        return ok_shift(s, s->context[s->context_size - 1 - term.data[0]],
                         (int32_t)term.data[0] + 1, 0, depth + 1);
    case OK_PI:
    case OK_SIGMA: {
        int64_t domain_level = ok_type_level(s, term.child[0], depth + 1);
        if (domain_level < 0 || !ok_push(s, term.child[0], id)) {
            return OK_NONE;
        }
        int64_t codomain_level = ok_type_level(s, term.child[1], depth + 1);
        s->context_size--;
        if (codomain_level < 0) {
            return OK_NONE;
        }
        return ok_sort(s, domain_level > codomain_level ? domain_level : codomain_level);
    }
    case OK_LAMBDA: {
        if (ok_type_level(s, term.child[0], depth + 1) < 0 ||
            !ok_push(s, term.child[0], id)) {
            return OK_NONE;
        }
        uint32_t body_type = ok_infer(s, term.child[1], depth + 1);
        s->context_size--;
        return ok_binary(s, OK_PI, term.child[0], body_type);
    }
    case OK_APP: {
        uint32_t function_type = ok_whnf(s, ok_infer(s, term.child[0], depth + 1), depth + 1);
        const ok_term *type = ok_get(s, function_type);
        if (!type || type->tag != OK_PI) {
            return ok_fail(s, OK_NOT_A_FUNCTION, id);
        }
        uint32_t domain = type->child[0];
        uint32_t codomain = type->child[1];
        if (!ok_check(s, term.child[1], domain, depth + 1)) {
            return OK_NONE;
        }
        return ok_instantiate(s, codomain, term.child[1], depth + 1);
    }
    case OK_LET: {
        if (ok_type_level(s, term.child[0], depth + 1) < 0 ||
            !ok_check(s, term.child[1], term.child[0], depth + 1) ||
            !ok_push(s, term.child[0], id)) {
            return OK_NONE;
        }
        uint32_t body_type = ok_infer(s, term.child[2], depth + 1);
        s->context_size--;
        return ok_instantiate(s, body_type, term.child[1], depth + 1);
    }
    case OK_ANNOTATION:
        if (ok_type_level(s, term.child[1], depth + 1) < 0 ||
            !ok_check(s, term.child[0], term.child[1], depth + 1)) {
            return OK_NONE;
        }
        return term.child[1];
    case OK_PAIR: {
        if (ok_type_level(s, term.child[0], depth + 1) < 0) {
            return OK_NONE;
        }
        uint32_t sigma = ok_whnf(s, term.child[0], depth + 1);
        const ok_term *type = ok_get(s, sigma);
        if (!type || type->tag != OK_SIGMA) {
            return ok_fail(s, OK_NOT_A_PAIR, id);
        }
        uint32_t domain = type->child[0];
        uint32_t codomain = type->child[1];
        if (!ok_check(s, term.child[1], domain, depth + 1)) {
            return OK_NONE;
        }
        uint32_t second_type = ok_instantiate(s, codomain, term.child[1], depth + 1);
        if (!ok_check(s, term.child[2], second_type, depth + 1)) {
            return OK_NONE;
        }
        return term.child[0];
    }
    case OK_FIRST:
    case OK_SECOND: {
        uint32_t sigma = ok_whnf(s, ok_infer(s, term.child[0], depth + 1), depth + 1);
        const ok_term *type = ok_get(s, sigma);
        if (!type || type->tag != OK_SIGMA) {
            return ok_fail(s, OK_NOT_A_PAIR, id);
        }
        if (term.tag == OK_FIRST) {
            return type->child[0];
        }
        uint32_t codomain = type->child[1];
        return ok_instantiate(s, codomain, ok_unary(s, OK_FIRST, term.child[0]), depth + 1);
    }
    case OK_NAT:
    case OK_RAT:
    case OK_UNIT:
    case OK_EMPTY:
        return ok_sort(s, 0);
    case OK_UNIT_VALUE:
        return ok_atom(s, OK_UNIT);
    case OK_ZERO:
        return ok_atom(s, OK_NAT);
    case OK_NAT_LITERAL:
        if (term.data[0] < 0) {
            return ok_fail(s, OK_BAD_NODE, id);
        }
        return ok_atom(s, OK_NAT);
    case OK_SUCCESSOR:
    case OK_NAT_ADD:
    case OK_NAT_MUL: {
        uint32_t natural = ok_atom(s, OK_NAT);
        for (unsigned i = 0; i < ok_arity(term.tag); ++i) {
            if (!ok_check(s, term.child[i], natural, depth + 1)) {
                return OK_NONE;
            }
        }
        return natural;
    }
    case OK_NAT_REC: {
        uint32_t motive_type = ok_whnf(s, ok_infer(s, term.child[0], depth + 1), depth + 1);
        const ok_term *motive = ok_get(s, motive_type);
        if (!motive || motive->tag != OK_PI) {
            return ok_fail(s, OK_NOT_A_FUNCTION, id);
        }
        uint32_t domain = motive->child[0];
        uint32_t codomain = motive->child[1];
        uint32_t natural = ok_atom(s, OK_NAT);
        const ok_term *result_sort = ok_get(s, ok_whnf(s, codomain, depth + 1));
        if (!ok_convert(s, domain, natural, depth + 1) ||
            !result_sort || result_sort->tag != OK_SORT) {
            return ok_fail(s, OK_NOT_A_TYPE, id);
        }
        uint32_t zero_type = ok_binary(s, OK_APP, term.child[0], ok_nat_literal(s, 0));
        if (!ok_check(s, term.child[1], zero_type, depth + 1)) {
            return OK_NONE;
        }
        uint32_t shifted_motive = ok_shift(s, term.child[0], 1, 0, depth + 1);
        uint32_t induction_type = ok_binary(s, OK_APP, shifted_motive, ok_variable(s, 0));
        uint32_t motive_two = ok_shift(s, term.child[0], 2, 0, depth + 1);
        uint32_t successor = ok_unary(s, OK_SUCCESSOR, ok_variable(s, 1));
        uint32_t conclusion = ok_binary(s, OK_APP, motive_two, successor);
        uint32_t step_type = ok_binary(s, OK_PI, natural,
                                      ok_binary(s, OK_PI, induction_type, conclusion));
        if (!ok_check(s, term.child[2], step_type, depth + 1) ||
            !ok_check(s, term.child[3], natural, depth + 1)) {
            return OK_NONE;
        }
        return ok_binary(s, OK_APP, term.child[0], term.child[3]);
    }
    case OK_EQUALITY: {
        int64_t level = ok_type_level(s, term.child[0], depth + 1);
        if (level < 0 || !ok_check(s, term.child[1], term.child[0], depth + 1) ||
            !ok_check(s, term.child[2], term.child[0], depth + 1)) {
            return OK_NONE;
        }
        return ok_sort(s, level);
    }
    case OK_REFL:
        if (ok_type_level(s, term.child[0], depth + 1) < 0 ||
            !ok_check(s, term.child[1], term.child[0], depth + 1)) {
            return OK_NONE;
        }
        return ok_new(s, OK_EQUALITY, term.child[0], term.child[1], term.child[1], 0, 0, 0);
    case OK_TRANSPORT: {
        uint32_t equality = ok_whnf(s, ok_infer(s, term.child[1], depth + 1), depth + 1);
        const ok_term *eq = ok_get(s, equality);
        if (!eq || eq->tag != OK_EQUALITY) {
            return ok_fail(s, OK_TYPE_MISMATCH, id);
        }
        uint32_t base = eq->child[0];
        uint32_t left = eq->child[1];
        uint32_t right = eq->child[2];
        uint32_t motive_type = ok_whnf(s, ok_infer(s, term.child[0], depth + 1), depth + 1);
        const ok_term *motive = ok_get(s, motive_type);
        if (!motive || motive->tag != OK_PI) {
            return ok_fail(s, OK_NOT_A_FUNCTION, id);
        }
        uint32_t domain = motive->child[0];
        uint32_t codomain = motive->child[1];
        const ok_term *sort = ok_get(s, ok_whnf(s, codomain, depth + 1));
        if (!ok_convert(s, domain, base, depth + 1) || !sort || sort->tag != OK_SORT) {
            return ok_fail(s, OK_NOT_A_TYPE, id);
        }
        if (!ok_check(s, term.child[2], ok_binary(s, OK_APP, term.child[0], left), depth + 1)) {
            return OK_NONE;
        }
        return ok_binary(s, OK_APP, term.child[0], right);
    }
    case OK_ABSURD:
        if (ok_type_level(s, term.child[0], depth + 1) < 0 ||
            !ok_check(s, term.child[1], ok_atom(s, OK_EMPTY), depth + 1)) {
            return OK_NONE;
        }
        return term.child[0];
    case OK_CONSTANT:
        if (term.data[0] < 0 || (uint64_t)term.data[0] >= s->definition_count) {
            return ok_fail(s, OK_BAD_CONSTANT, id);
        }
        return s->definitions[term.data[0]].type;
    case OK_RAT_LITERAL:
        if (term.data[0] == INT64_MIN || term.data[1] <= 0) {
            return ok_fail(s, OK_BAD_NODE, id);
        }
        return ok_atom(s, OK_RAT);
    case OK_RAT_ADD:
    case OK_RAT_MUL:
    case OK_RAT_NEG: {
        uint32_t rational = ok_atom(s, OK_RAT);
        for (unsigned i = 0; i < ok_arity(term.tag); ++i) {
            if (!ok_check(s, term.child[i], rational, depth + 1)) {
                return OK_NONE;
            }
        }
        return rational;
    }
    default:
        return ok_fail(s, OK_BAD_NODE, id);
    }
}

static int ok_check(ok_checker *s, uint32_t term, uint32_t expected, uint32_t depth)
{
    uint32_t inferred = ok_infer(s, term, depth + 1);
    if (inferred == OK_NONE || !ok_convert(s, inferred, expected, depth + 1)) {
        ok_fail(s, OK_TYPE_MISMATCH, term);
        return 0;
    }
    return s->error == OK_SUCCESS;
}

static inline int ok_define(ok_checker *s, uint32_t type, uint32_t body)
{
    if (!s || s->context_size != 0 || s->definition_count >= OK_DEFINITIONS_MAX) {
        ok_fail(s, OK_BAD_CONSTANT, body);
        return 0;
    }
    if (ok_type_level(s, type, 0) < 0 || !ok_check(s, body, type, 0)) {
        return 0;
    }
    s->definitions[s->definition_count].type = type;
    s->definitions[s->definition_count].body = body;
    s->definition_count++;
    return 1;
}

static inline int ok_verify(ok_checker *s, uint32_t proof, uint32_t expected)
{
    if (!s || s->context_size != 0 || s->error != OK_SUCCESS) {
        return 0;
    }
    if (ok_type_level(s, expected, 0) < 0) {
        return 0;
    }
    return ok_check(s, proof, expected, 0) && s->error == OK_SUCCESS;
}

static inline int ok_is_resource_error(ok_error error)
{
    return error == OK_ARENA_LIMIT || error == OK_FUEL_LIMIT ||
           error == OK_DEPTH_LIMIT || error == OK_CONTEXT_LIMIT ||
           error == OK_UNIVERSE_LIMIT || error == OK_ARITHMETIC_LIMIT;
}

#endif
