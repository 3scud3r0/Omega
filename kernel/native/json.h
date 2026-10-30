#ifndef OMEGA_KERNEL_JSON_H
#define OMEGA_KERNEL_JSON_H

/* Bounded, allocation-free JSON tokenizer. Exact protocol numbers are decimal
 * integers; strings used as keys/tags are unescaped ASCII by protocol design.
 * Duplicate object keys are rejected at parse time, not overwritten later.
 */
#include <stddef.h>
#include <stdint.h>
#include <limits.h>

enum {
    OKJ_OBJECT,
    OKJ_ARRAY,
    OKJ_STRING,
    OKJ_INTEGER,
    OKJ_TRUE,
    OKJ_FALSE,
    OKJ_NULL
};

typedef struct {
    uint32_t begin;
    uint32_t end;
    uint32_t next;
    uint32_t count;
    uint8_t tag;
} okj_token;

typedef struct {
    const unsigned char *text;
    size_t length;
    size_t position;
    okj_token *tokens;
    size_t capacity;
    size_t count;
    unsigned depth_limit;
    int error;
} okj_parser;

static inline int okj_space(unsigned char c)
{
    return c == ' ' || c == '\t' || c == '\n' || c == '\r';
}

static inline void okj_skip(okj_parser *p)
{
    while (p->position < p->length && okj_space(p->text[p->position])) {
        p->position++;
    }
}

static inline uint32_t okj_bad(okj_parser *p)
{
    p->error = 1;
    return UINT32_MAX;
}

static inline uint32_t okj_allocate(okj_parser *p, unsigned tag, size_t begin)
{
    if (p->count >= p->capacity || begin > UINT32_MAX) {
        return okj_bad(p);
    }
    uint32_t id = (uint32_t)p->count++;
    p->tokens[id].begin = (uint32_t)begin;
    p->tokens[id].end = (uint32_t)begin;
    p->tokens[id].next = id + 1;
    p->tokens[id].count = 0;
    p->tokens[id].tag = (uint8_t)tag;
    return id;
}

static inline int okj_equal_tokens(const okj_parser *p, uint32_t a, uint32_t b)
{
    if (a >= p->count || b >= p->count) {
        return 0;
    }
    const okj_token *x = &p->tokens[a];
    const okj_token *y = &p->tokens[b];
    if (x->tag != y->tag || x->end - x->begin != y->end - y->begin) {
        return 0;
    }
    for (uint32_t i = 0; i < x->end - x->begin; ++i) {
        if (p->text[x->begin + i] != p->text[y->begin + i]) {
            return 0;
        }
    }
    return 1;
}

static inline int okj_name(const okj_parser *p, uint32_t id, const char *name)
{
    if (id >= p->count || p->tokens[id].tag != OKJ_STRING) {
        return 0;
    }
    const okj_token *t = &p->tokens[id];
    size_t i = 0;
    while (name[i]) {
        if (t->begin + i >= t->end || p->text[t->begin + i] != (unsigned char)name[i]) {
            return 0;
        }
        i++;
    }
    return t->begin + i == t->end;
}

static uint32_t okj_value(okj_parser *, unsigned);

static uint32_t okj_string(okj_parser *p)
{
    if (p->position >= p->length || p->text[p->position++] != '"') {
        return okj_bad(p);
    }
    size_t begin = p->position;
    while (p->position < p->length && p->text[p->position] != '"') {
        unsigned char c = p->text[p->position++];
        /* Protocol strings are deliberately canonical ASCII. */
        if (c < 32 || c > 126 || c == '\\') {
            return okj_bad(p);
        }
    }
    if (p->position == p->length) {
        return okj_bad(p);
    }
    uint32_t id = okj_allocate(p, OKJ_STRING, begin);
    if (id == UINT32_MAX) {
        return id;
    }
    p->tokens[id].end = (uint32_t)p->position++;
    return id;
}

static uint32_t okj_integer_token(okj_parser *p)
{
    size_t begin = p->position;
    if (p->text[p->position] == '-') {
        p->position++;
    }
    if (p->position >= p->length || p->text[p->position] < '0' ||
        p->text[p->position] > '9') {
        return okj_bad(p);
    }
    if (p->text[p->position] == '0') {
        p->position++;
        if (p->position < p->length && p->text[p->position] >= '0' && p->text[p->position] <= '9') {
            return okj_bad(p);
        }
    } else {
        while (p->position < p->length && p->text[p->position] >= '0' && p->text[p->position] <= '9') {
            p->position++;
        }
    }
    if (p->position - begin > 21) {
        return okj_bad(p);
    }
    if (p->position < p->length && (p->text[p->position] == '.' ||
        p->text[p->position] == 'e' || p->text[p->position] == 'E')) {
        return okj_bad(p);
    }
    uint32_t id = okj_allocate(p, OKJ_INTEGER, begin);
    if (id != UINT32_MAX) {
        p->tokens[id].end = (uint32_t)p->position;
    }
    return id;
}

static inline int okj_literal(okj_parser *p, const char *literal)
{
    size_t start = p->position;
    size_t i = 0;
    while (literal[i]) {
        if (start + i >= p->length || p->text[start + i] != (unsigned char)literal[i]) {
            return 0;
        }
        i++;
    }
    p->position += i;
    return 1;
}

static uint32_t okj_value(okj_parser *p, unsigned depth)
{
    okj_skip(p);
    if (p->error || p->position >= p->length || depth > p->depth_limit) {
        return okj_bad(p);
    }
    unsigned char c = p->text[p->position];
    if (c == '"') {
        return okj_string(p);
    }
    if (c == '-' || (c >= '0' && c <= '9')) {
        return okj_integer_token(p);
    }
    if (c == '[' || c == '{') {
        int object = c == '{';
        uint32_t id = okj_allocate(p, object ? OKJ_OBJECT : OKJ_ARRAY, p->position++);
        if (id == UINT32_MAX) {
            return id;
        }
        okj_skip(p);
        unsigned char end = object ? '}' : ']';
        if (p->position < p->length && p->text[p->position] == end) {
            p->position++;
            p->tokens[id].end = (uint32_t)p->position;
            p->tokens[id].next = (uint32_t)p->count;
            return id;
        }
        for (;;) {
            if (object) {
                uint32_t key = okj_string(p);
                if (key == UINT32_MAX) {
                    return key;
                }
                uint32_t previous = id + 1;
                while (previous < key) {
                    if (okj_equal_tokens(p, previous, key)) {
                        return okj_bad(p);
                    }
                    uint32_t value = previous + 1;
                    if (value >= p->count || p->tokens[value].next <= previous) {
                        return okj_bad(p);
                    }
                    previous = p->tokens[value].next;
                }
                okj_skip(p);
                if (p->position >= p->length || p->text[p->position++] != ':') {
                    return okj_bad(p);
                }
            }
            if (okj_value(p, depth + 1) == UINT32_MAX) {
                return UINT32_MAX;
            }
            p->tokens[id].count++;
            okj_skip(p);
            if (p->position >= p->length) {
                return okj_bad(p);
            }
            c = p->text[p->position++];
            if (c == end) {
                break;
            }
            if (c != ',') {
                return okj_bad(p);
            }
            okj_skip(p);
        }
        p->tokens[id].end = (uint32_t)p->position;
        p->tokens[id].next = (uint32_t)p->count;
        return id;
    }
    size_t begin = p->position;
    unsigned tag;
    if (okj_literal(p, "true")) {
        tag = OKJ_TRUE;
    } else if (okj_literal(p, "false")) {
        tag = OKJ_FALSE;
    } else if (okj_literal(p, "null")) {
        tag = OKJ_NULL;
    } else {
        return okj_bad(p);
    }
    uint32_t id = okj_allocate(p, tag, begin);
    if (id != UINT32_MAX) {
        p->tokens[id].end = (uint32_t)p->position;
    }
    return id;
}

static inline int okj_parse(okj_parser *p, const unsigned char *text, size_t length,
                           okj_token *arena, size_t capacity)
{
    if (!p || !text || !arena || length > 4u * 1024u * 1024u || capacity < 8) {
        return 0;
    }
    p->text = text;
    p->length = length;
    p->position = 0;
    p->tokens = arena;
    p->capacity = capacity;
    p->count = 0;
    p->depth_limit = 32;
    p->error = 0;
    if (okj_value(p, 0) != 0) {
        return 0;
    }
    okj_skip(p);
    return !p->error && p->position == length;
}

static inline uint32_t okj_field(const okj_parser *p, uint32_t object, const char *key)
{
    if (object >= p->count || p->tokens[object].tag != OKJ_OBJECT) {
        return UINT32_MAX;
    }
    uint32_t cursor = object + 1;
    while (cursor < p->tokens[object].next) {
        uint32_t value = cursor + 1;
        if (value >= p->count) {
            return UINT32_MAX;
        }
        if (okj_name(p, cursor, key)) {
            return value;
        }
        cursor = p->tokens[value].next;
    }
    return UINT32_MAX;
}

static inline uint32_t okj_element(const okj_parser *p, uint32_t array, size_t index)
{
    if (array >= p->count || p->tokens[array].tag != OKJ_ARRAY || index >= p->tokens[array].count) {
        return UINT32_MAX;
    }
    uint32_t cursor = array + 1;
    for (size_t i = 0; i < index; ++i) {
        if (cursor >= p->count) {
            return UINT32_MAX;
        }
        cursor = p->tokens[cursor].next;
    }
    return cursor < p->count ? cursor : UINT32_MAX;
}

static inline int okj_i64(const okj_parser *p, uint32_t id, int64_t *out)
{
    if (id >= p->count || p->tokens[id].tag != OKJ_INTEGER || !out) {
        return 0;
    }
    size_t i = p->tokens[id].begin;
    size_t end = p->tokens[id].end;
    int negative = p->text[i] == '-';
    if (negative) {
        i++;
    }
    uint64_t value = 0;
    uint64_t limit = negative ? (uint64_t)INT64_MAX + 1 : INT64_MAX;
    for (; i < end; ++i) {
        unsigned digit = p->text[i] - '0';
        if (digit > 9 || value > (limit - digit) / 10) {
            return 0;
        }
        value = value * 10 + digit;
    }
    *out = negative ? -(int64_t)(value - (value != 0)) - (value != 0) : (int64_t)value;
    return 1;
}

static inline int okj_range(const okj_parser *p, uint32_t id, int64_t low,
                           int64_t high, int64_t *out)
{
    return okj_i64(p, id, out) && *out >= low && *out <= high;
}

static inline int okj_fields(const okj_parser *p, uint32_t object,
                             const char *const *allowed, size_t n)
{
    if (object >= p->count || p->tokens[object].tag != OKJ_OBJECT) {
        return 0;
    }
    uint32_t cursor = object + 1;
    while (cursor < p->tokens[object].next) {
        int known = 0;
        for (size_t i = 0; i < n; ++i) {
            known |= okj_name(p, cursor, allowed[i]);
        }
        if (!known || cursor + 1 >= p->count) {
            return 0;
        }
        cursor = p->tokens[cursor + 1].next;
    }
    return 1;
}

#endif
