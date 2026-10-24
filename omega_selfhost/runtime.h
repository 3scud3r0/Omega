/* Omega native value runtime. GMP rationals; no Python or external interpreter. */
#ifndef OMEGA_RUNTIME_H
#define OMEGA_RUNTIME_H
#include <ctype.h>
#include <errno.h>
#include <gmp.h>
#include <limits.h>
#include <locale.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <wchar.h>
#include <wctype.h>
typedef struct OmegaValue *V;
struct OmegaValue {
  int kind;
  mpq_t q;
  char *s;
  size_t n, cap;
  V *a;
  char **keys;
  V qnext;
};
static int omega_argc;
static char **omega_argv;
static unsigned long long omega_ticks = 0, omega_fuel = 500000000ULL;
static size_t omega_allocated = 0;
static unsigned omega_depth = 0, omega_max_depth = 512;
struct OmegaBlock {
  struct OmegaBlock *next;
  _Alignas(max_align_t) unsigned char data[];
};
static struct OmegaBlock *omega_blocks = NULL;
static V omega_rationals = NULL;
static int omega_cleanup_registered = 0;
static void o_cleanup(void) {
  for (V q = omega_rationals; q; q = q->qnext)
    mpq_clear(q->q);
  omega_rationals = NULL;
  while (omega_blocks) {
    struct OmegaBlock *block = omega_blocks;
    omega_blocks = block->next;
    free(block);
  }
  omega_allocated = 0;
}
static void o_qinit(V v) {
  mpq_init(v->q);
  v->qnext = omega_rationals;
  omega_rationals = v;
}
static _Noreturn void o_die(const char *s) {
  fprintf(stderr, "Omega: %s\n", s);
  exit(1);
}
static void o_tick(void) {
  if (++omega_ticks > omega_fuel)
    o_die("Resource budget exceeded");
}
static void o_enter(void) {
  o_tick();
  if (++omega_depth > omega_max_depth)
    o_die("Recursion depth exceeded");
}
static V o_ret(V v) {
  if (!omega_depth)
    o_die("Invalid call stack");
  --omega_depth;
  return v;
}
static void *o_alloc(size_t n) {
  if (!n)
    n = 1;
  if (n > SIZE_MAX - sizeof(struct OmegaBlock))
    o_die("Allocation overflow");
  size_t total = sizeof(struct OmegaBlock) + n;
  if (total > 2147483648ULL || omega_allocated > 2147483648ULL - total)
    o_die("Memory budget exceeded");
  struct OmegaBlock *block = calloc(1, total);
  if (!block)
    o_die("Out of memory");
  block->next = omega_blocks;
  omega_blocks = block;
  omega_allocated += total;
  return block->data;
}
static char *o_copy(const char *s, size_t n) {
  char *p = o_alloc(n + 1);
  for (size_t i = 0; i < n; ++i)
    p[i] = s[i];
  return p;
}
static V o_new(int kind) {
  V v = o_alloc(sizeof(*v));
  v->kind = kind;
  return v;
}
static V o_str(const char *s) {
  V v = o_new(1);
  v->n = strlen(s);
  v->s = o_copy(s, v->n);
  return v;
}
static unsigned o_codepoint(const char *s, size_t *width) {
  const unsigned char *p = (const unsigned char *)s;
  unsigned c = p[0];
  *width = 1;
  if (c < 128)
    return c;
  unsigned need = c >= 0xf0 ? 4 : c >= 0xe0 ? 3 : c >= 0xc0 ? 2 : 0;
  if (!need)
    return 0xffffffffU;
  unsigned q = c & ((1U << (7 - need)) - 1);
  for (unsigned i = 1; i < need; i++) {
    if ((p[i] & 0xc0) != 0x80)
      return 0xffffffffU;
    q = (q << 6) | (p[i] & 63);
  }
  if ((need == 2 && q < 128) || (need == 3 && q < 2048) || (need == 4 && q < 65536) ||
      q > 0x10ffff || (q >= 0xd800 && q <= 0xdfff))
    return 0xffffffffU;
  *width = need;
  return q;
}
static int o_digit(unsigned cp) {
  static const unsigned blocks[] = {
      0x30,    0x660,   0x6f0,   0x7c0,   0x966,   0x9e6,   0xa66,   0xae6,   0xb66,   0xbe6,
      0xc66,   0xce6,   0xd66,   0xde6,   0xe50,   0xed0,   0xf20,   0x1040,  0x1090,  0x17e0,
      0x1810,  0x1946,  0x19d0,  0x1a80,  0x1a90,  0x1b50,  0x1bb0,  0x1c40,  0x1c50,  0xa620,
      0xa8d0,  0xa900,  0xa9d0,  0xa9f0,  0xaa50,  0xabf0,  0xff10,  0x104a0, 0x10d30, 0x11066,
      0x110f0, 0x11136, 0x111d0, 0x112f0, 0x11450, 0x114d0, 0x11650, 0x116c0, 0x11730, 0x118e0,
      0x11950, 0x11c50, 0x11d50, 0x11da0, 0x11f50, 0x16a60, 0x16ac0, 0x16b50, 0x1d7ce, 0x1d7d8,
      0x1d7e2, 0x1d7ec, 0x1d7f6, 0x1e140, 0x1e2f0, 0x1e4f0, 0x1e950, 0x1fbf0};
  for (size_t i = 0; i < sizeof(blocks) / sizeof(blocks[0]); i++)
    if (cp >= blocks[i] && cp < blocks[i] + 10)
      return (int)(cp - blocks[i]);
  return -1;
}
static const char *o_ascii_number(const char *s) {
  size_t n = strlen(s);
  char *out = o_alloc(n + 1);
  size_t j = 0;
  while (*s) {
    size_t w;
    unsigned cp = o_codepoint(s, &w);
    int d = o_digit(cp);
    if (d >= 0)
      out[j++] = (char)('0' + d);
    else if (cp < 128)
      out[j++] = (char)cp;
    else
      o_die("Invalid numeric character");
    s += w;
  }
  return out;
}
static V o_num(const char *s) {
  s = o_ascii_number(s);
  V v = o_new(0);
  o_qinit(v);
  char *buf = o_copy(s, strlen(s));
  char *dot = strchr(buf, '.');
  if (dot) {
    size_t decimals = strlen(dot + 1);
    memmove(dot, dot + 1, decimals + 1);
    if (mpz_set_str(mpq_numref(v->q), buf, 10))
      o_die("Invalid rational");
    mpz_ui_pow_ui(mpq_denref(v->q), 10, decimals);
  } else if (mpq_set_str(v->q, s, 10))
    o_die("Invalid rational");
  if (mpz_sgn(mpq_denref(v->q)) == 0)
    o_die("Zero denominator");
  mpq_canonicalize(v->q);
  return v;
}
static V o_int(long n) {
  V v = o_new(0);
  o_qinit(v);
  mpq_set_si(v->q, n, 1);
  return v;
}
static long o_long(V v) {
  if (!v || v->kind || mpz_cmp_ui(mpq_denref(v->q), 1) || !mpz_fits_slong_p(mpq_numref(v->q)))
    o_die("Integer required");
  return mpz_get_si(mpq_numref(v->q));
}
static V o_list(void) { return o_new(2); }
static V o_obj(void) { return o_new(3); }
static int o_truth(V v) { return v->kind == 0 ? mpq_sgn(v->q) != 0 : v->n != 0; }
static V o_bool(int b) { return o_int(b ? 1 : 0); }
static void o_grow(V v) {
  if (v->n == v->cap) {
    size_t c = v->cap ? v->cap * 2 : 8;
    V *a = o_alloc(c * sizeof(V));
    if (v->n)
      memcpy(a, v->a, v->n * sizeof(V));
    v->a = a;
    if (v->kind == 3) {
      char **k = o_alloc(c * sizeof(char *));
      if (v->n)
        memcpy(k, v->keys, v->n * sizeof(char *));
      v->keys = k;
    }
    v->cap = c;
  }
}
static V o_push(V a, V v) {
  if (a->kind != 2)
    o_die("List required");
  o_grow(a);
  a->a[a->n++] = v;
  return a;
}
static V o_len(V a) {
  if (a->kind != 1 && a->kind != 2 && a->kind != 3)
    o_die("Sequence or object required");
  return o_int((long)a->n);
}
static V o_get(V a, V key) {
  if (a->kind == 3) {
    if (key->kind != 1)
      o_die("Object key must be string");
    for (size_t i = 0; i < a->n; i++)
      if (!strcmp(a->keys[i], key->s))
        return a->a[i];
    o_die("Missing object key");
  }
  long i = o_long(key);
  if (i < 0 || (size_t)i >= a->n)
    o_die("Index out of bounds");
  if (a->kind == 2)
    return a->a[i];
  if (a->kind == 1)
    return o_str(o_copy(a->s + i, 1));
  o_die("Indexable value required");
  return NULL;
}
static V o_has(V a, V k) {
  if (a->kind != 3 || k->kind != 1)
    o_die("Object and string required");
  for (size_t i = 0; i < a->n; i++)
    if (!strcmp(a->keys[i], k->s))
      return o_bool(1);
  return o_bool(0);
}
static V o_put(V a, V k, V v) {
  if (a->kind == 2) {
    long i = o_long(k);
    if (i < 0 || (size_t)i >= a->n)
      o_die("Index out of bounds");
    a->a[i] = v;
    return a;
  }
  if (a->kind != 3 || k->kind != 1)
    o_die("Object key required");
  for (size_t i = 0; i < a->n; i++)
    if (!strcmp(a->keys[i], k->s)) {
      a->a[i] = v;
      return a;
    }
  o_grow(a);
  a->keys[a->n] = k->s;
  a->a[a->n++] = v;
  return a;
}
static V o_keys(V a) {
  if (a->kind != 3)
    o_die("Object required");
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, o_str(a->keys[i]));
  return r;
}
static int o_equal(V a, V b);
static int o_equal_inner(V a, V b) {
  if (a->kind != b->kind)
    return 0;
  if (a->kind == 0)
    return mpq_equal(a->q, b->q);
  if (a->kind == 1)
    return a->n == b->n && !strcmp(a->s, b->s);
  if (a->n != b->n)
    return 0;
  for (size_t i = 0; i < a->n; i++) {
    if (a->kind == 3) {
      V k = o_str(a->keys[i]);
      if (!o_truth(o_has(b, k)) || !o_equal(a->a[i], o_get(b, k)))
        return 0;
    } else if (!o_equal(a->a[i], b->a[i]))
      return 0;
  }
  return 1;
}
static int o_equal(V a, V b) {
  o_enter();
  int result = o_equal_inner(a, b);
  --omega_depth;
  return result;
}
static V o_eq(V a, V b) { return o_bool(o_equal(a, b)); }
static V o_ne(V a, V b) { return o_bool(!o_equal(a, b)); }
static int o_cmp(V a, V b) {
  if (a->kind == 1 && b->kind == 1)
    return strcmp(a->s, b->s);
  if (a->kind || b->kind)
    o_die("Rational comparison required");
  return mpq_cmp(a->q, b->q);
}
static V o_lt(V a, V b) { return o_bool(o_cmp(a, b) < 0); }
static V o_le(V a, V b) { return o_bool(o_cmp(a, b) <= 0); }
static V o_gt(V a, V b) { return o_bool(o_cmp(a, b) > 0); }
static V o_ge(V a, V b) { return o_bool(o_cmp(a, b) >= 0); }
static V o_add(V a, V b) {
  if (a->kind == 1 && b->kind == 1) {
    char *s = o_alloc(a->n + b->n + 1);
    memcpy(s, a->s, a->n);
    memcpy(s + a->n, b->s, b->n);
    return o_str(s);
  }
  if (a->kind || b->kind)
    o_die("Rationals required");
  V r = o_num("0");
  mpq_add(r->q, a->q, b->q);
  return r;
}
static V o_sub(V a, V b) {
  if (a->kind || b->kind)
    o_die("Rationals required");
  V r = o_num("0");
  mpq_sub(r->q, a->q, b->q);
  return r;
}
static V o_mul(V a, V b) {
  if (a->kind || b->kind)
    o_die("Rationals required");
  V r = o_num("0");
  mpq_mul(r->q, a->q, b->q);
  return r;
}
static V o_div(V a, V b) {
  if (a->kind || b->kind || !mpq_sgn(b->q))
    o_die("Invalid division");
  V r = o_num("0");
  mpq_div(r->q, a->q, b->q);
  return r;
}
static V o_mod(V a, V b) {
  long x = o_long(a), y = o_long(b);
  if (!y || (x == LONG_MIN && y == -1))
    o_die("Invalid modulo");
  return o_int(x % y);
}
static V o_neg(V a) { return o_sub(o_int(0), a); }
static V o_not(V a) { return o_bool(!o_truth(a)); }
static V o_text(V a) {
  if (a->kind == 1)
    return a;
  if (a->kind != 0)
    o_die("Scalar required");
  char *s = mpq_get_str(NULL, 10, a->q);
  V r = o_str(s);
  free(s);
  return r;
}
static V o_ident(V s) {
  if (s->kind != 1 || !s->n)
    return o_bool(0);
  const char *p = s->s;
  int first = 1;
  while (*p) {
    size_t n;
    unsigned cp = o_codepoint(p, &n);
    if (cp == 0xffffffffU || !(cp == '_' || (first ? iswalpha((wint_t)cp) : iswalnum((wint_t)cp))))
      return o_bool(0);
    first = 0;
    p += n;
  }
  return o_bool(1);
}
static V o_decimal(V s, V pos) {
  long i = o_long(pos);
  if (s->kind != 1 || i < 0 || (size_t)i >= s->n)
    return o_int(0);
  size_t n;
  unsigned cp = o_codepoint(s->s + i, &n);
  return o_int(o_digit(cp) >= 0 ? (long)n : 0);
}
static V o_number(V a) {
  if (a->kind == 0)
    return a;
  if (a->kind != 1)
    o_die("Numeric text required");
  return o_num(a->s);
}
static V o_isnum(V a) { return o_bool(a->kind == 0); }
static V o_isstr(V a) { return o_bool(a->kind == 1); }
static V o_islist(V a) { return o_bool(a->kind == 2); }
static V o_slice(V a, V first, V last) {
  long f = o_long(first), l = o_long(last);
  if (f < 0 || l < f || (size_t)l > a->n)
    o_die("Invalid slice");
  if (a->kind == 1)
    return o_str(o_copy(a->s + f, (size_t)(l - f)));
  if (a->kind == 2) {
    V r = o_list();
    for (long i = f; i < l; i++)
      o_push(r, a->a[i]);
    return r;
  }
  o_die("Slice requires sequence");
  return NULL;
}
static V o_join(V a, V sep) {
  if (a->kind != 2 || sep->kind != 1)
    o_die("Join requires strings");
  size_t n = 0;
  for (size_t i = 0; i < a->n; i++) {
    if (a->a[i]->kind != 1)
      o_die("Join requires strings");
    n += a->a[i]->n;
    if (i)
      n += sep->n;
  }
  char *s = o_alloc(n + 1), *p = s;
  for (size_t i = 0; i < a->n; i++) {
    if (i) {
      memcpy(p, sep->s, sep->n);
      p += sep->n;
    }
    memcpy(p, a->a[i]->s, a->a[i]->n);
    p += a->a[i]->n;
  }
  return o_str(s);
}
static V o_contains(V a, V b) {
  if (a->kind == 1 && b->kind == 1)
    return o_bool(strstr(a->s, b->s) != NULL);
  if (a->kind == 2) {
    for (size_t i = 0; i < a->n; i++)
      if (o_equal(a->a[i], b))
        return o_bool(1);
    return o_bool(0);
  }
  o_die("Sequence required");
  return NULL;
}
static V o_arg(V a) {
  long i = o_long(a);
  if (i < 0 || i >= omega_argc)
    o_die("Missing command argument");
  return o_str(omega_argv[i]);
}
static V o_argc(void) { return o_int(omega_argc); }
static V o_read(V p) {
  if (p->kind != 1)
    o_die("File path required");
  FILE *f = fopen(p->s, "rb");
  if (!f)
    o_die("Cannot read input file");
  if (fseek(f, 0, SEEK_END))
    o_die("Seek failed");
  long n = ftell(f);
  if (n < 0 || n > 64000000)
    o_die("Input exceeds 64 MB");
  rewind(f);
  char *s = o_alloc((size_t)n + 1);
  if (fread(s, 1, (size_t)n, f) != (size_t)n)
    o_die("Read failed");
  fclose(f);
  return o_str(s);
}
static V o_write(V p, V data) {
  if (p->kind != 1 || data->kind != 1)
    o_die("File path and text required");
  FILE *f = fopen(p->s, "wb");
  if (!f)
    o_die("Cannot write file");
  if (fwrite(data->s, 1, data->n, f) != data->n || fclose(f))
    o_die("Write failed");
  return o_int(0);
}
static V o_print(V a) {
  V s = o_text(a);
  if (puts(s->s) == EOF || fflush(stdout) == EOF)
    o_die("Print failed");
  return o_int(0);
}
static V o_fail(V a) {
  o_die(o_text(a)->s);
  return NULL;
}
/* JSON is a data codec, not a source-code evaluator. */
static void o_json_into(V a, V parts);
static void o_json_inner(V a, V parts) {
  if (a->kind == 0) {
    if (mpz_cmp_ui(mpq_denref(a->q), 1))
      o_die("JSON rationals require explicit text conversion");
    o_push(parts, o_text(a));
    return;
  }
  if (a->kind == 1) {
    o_push(parts, o_str("\""));
    for (size_t i = 0; i < a->n; i++) {
      unsigned char c = (unsigned char)a->s[i];
      if (c == '"')
        o_push(parts, o_str("\\\""));
      else if (c == '\\')
        o_push(parts, o_str("\\\\"));
      else if (c == '\n')
        o_push(parts, o_str("\\n"));
      else if (c == '\r')
        o_push(parts, o_str("\\r"));
      else if (c == '\t')
        o_push(parts, o_str("\\t"));
      else if (c < 32) {
        char buf[7];
        snprintf(buf, sizeof(buf), "\\u%04x", c);
        o_push(parts, o_str(buf));
      } else
        o_push(parts, o_str(o_copy(a->s + i, 1)));
    }
    o_push(parts, o_str("\""));
    return;
  }
  o_push(parts, o_str(a->kind == 2 ? "[" : "{"));
  for (size_t i = 0; i < a->n; i++) {
    if (i)
      o_push(parts, o_str(","));
    if (a->kind == 3) {
      o_json_into(o_str(a->keys[i]), parts);
      o_push(parts, o_str(":"));
    }
    o_json_into(a->a[i], parts);
  }
  o_push(parts, o_str(a->kind == 2 ? "]" : "}"));
}
static void o_json_into(V a, V parts) {
  o_enter();
  o_json_inner(a, parts);
  --omega_depth;
}
static V o_json(V a) {
  V p = o_list();
  o_json_into(a, p);
  return o_join(p, o_str(""));
}
static void o_ws(const char **p) {
  while (isspace((unsigned char)**p))
    ++*p;
}
static V o_parse_value(const char **p, int depth) {
  o_tick();
  if ((unsigned)depth > omega_max_depth)
    o_die("JSON nesting exceeded");
  o_ws(p);
  if (**p == '"') {
    ++*p;
    V chars = o_list();
    while (**p && **p != '"') {
      char c = *(*p)++;
      if ((unsigned char)c < 32)
        o_die("Unescaped JSON control character");
      if (c == '\\') {
        if (!**p)
          o_die("Truncated JSON escape");
        c = *(*p)++;
        if (c == 'n')
          c = '\n';
        else if (c == 'r')
          c = '\r';
        else if (c == 't')
          c = '\t';
        else if (c == 'b')
          c = '\b';
        else if (c == 'f')
          c = '\f';
        else if (c == 'u') {
          unsigned cp = 0;
          for (int k = 0; k < 4; k++) {
            unsigned char h = (unsigned char)*(*p)++;
            if (!isxdigit(h))
              o_die("Invalid Unicode escape");
            cp = cp * 16 + (unsigned)(isdigit(h) ? h - '0' : tolower(h) - 'a' + 10);
          }
          if (cp >= 0xd800 && cp <= 0xdbff) {
            if ((*p)[0] != '\\' || (*p)[1] != 'u')
              o_die("Missing low surrogate");
            *p += 2;
            unsigned low = 0;
            for (int k = 0; k < 4; k++) {
              unsigned char h = (unsigned char)*(*p)++;
              if (!isxdigit(h))
                o_die("Invalid low surrogate");
              low = low * 16 + (unsigned)(isdigit(h) ? h - '0' : tolower(h) - 'a' + 10);
            }
            if (low < 0xdc00 || low > 0xdfff)
              o_die("Invalid low surrogate");
            cp = 0x10000 + ((cp - 0xd800) << 10) + (low - 0xdc00);
          } else if (cp >= 0xdc00 && cp <= 0xdfff)
            o_die("Unpaired low surrogate");
          if (!cp)
            o_die("Embedded NUL is not supported");
          char utf[5] = {0};
          if (cp < 0x80)
            utf[0] = (char)cp;
          else if (cp < 0x800) {
            utf[0] = (char)(0xc0 | (cp >> 6));
            utf[1] = (char)(0x80 | (cp & 63));
          } else if (cp < 0x10000) {
            utf[0] = (char)(0xe0 | (cp >> 12));
            utf[1] = (char)(0x80 | ((cp >> 6) & 63));
            utf[2] = (char)(0x80 | (cp & 63));
          } else {
            utf[0] = (char)(0xf0 | (cp >> 18));
            utf[1] = (char)(0x80 | ((cp >> 12) & 63));
            utf[2] = (char)(0x80 | ((cp >> 6) & 63));
            utf[3] = (char)(0x80 | (cp & 63));
          }
          o_push(chars, o_str(utf));
          continue;
        } else if (c != '"' && c != '\\' && c != '/')
          o_die("Unsupported JSON escape");
      }
      char buf[2] = {c, 0};
      o_push(chars, o_str(buf));
    }
    if (*(*p)++ != '"')
      o_die("Unterminated JSON string");
    return o_join(chars, o_str(""));
  }
  if (**p == '[' || **p == '{') {
    int obj = **p == '{';
    char end = obj ? '}' : ']';
    ++*p;
    V r = obj ? o_obj() : o_list();
    o_ws(p);
    if (**p == end) {
      ++*p;
      return r;
    }
    while (1) {
      V key = NULL;
      if (obj) {
        key = o_parse_value(p, depth + 1);
        if (key->kind != 1)
          o_die("JSON key required");
        o_ws(p);
        if (*(*p)++ != ':')
          o_die("Expected colon");
      }
      V v = o_parse_value(p, depth + 1);
      if (obj) {
        if (o_truth(o_has(r, key)))
          o_die("Duplicate JSON key");
        o_put(r, key, v);
      } else
        o_push(r, v);
      o_ws(p);
      if (**p == end) {
        ++*p;
        return r;
      }
      if (*(*p)++ != ',')
        o_die("Invalid JSON delimiter");
    }
  }
  const char *start = *p;
  if (**p == '-')
    ++*p;
  if (!isdigit((unsigned char)**p))
    o_die("JSON digit required");
  if (**p == '0' && isdigit((unsigned char)(*p)[1]))
    o_die("Leading zero in JSON number");
  while (isdigit((unsigned char)**p))
    ++*p;
  if (**p == '.') {
    ++*p;
    if (!isdigit((unsigned char)**p))
      o_die("JSON fractional digit required");
    while (isdigit((unsigned char)**p))
      ++*p;
  }
  if (*p == start)
    o_die("Invalid JSON value");
  return o_num(o_copy(start, (size_t)(*p - start)));
}
static V o_parsejson(V s) {
  if (s->kind != 1)
    o_die("JSON text required");
  const char *p = s->s;
  V r = o_parse_value(&p, 0);
  o_ws(&p);
  if (*p)
    o_die("Trailing JSON data");
  return r;
}
static void o_init(int argc, char **argv) {
  omega_argc = argc;
  omega_argv = argv;
  if (!omega_cleanup_registered) {
    if (atexit(o_cleanup))
      o_die("Could not register cleanup");
    omega_cleanup_registered = 1;
  }
  const char *depth = getenv("OMEGA_DEPTH");
  if (depth) {
    char *end;
    errno = 0;
    unsigned long n = strtoul(depth, &end, 10);
    if (errno || *end || n < 1 || n > 512)
      o_die("Invalid OMEGA_DEPTH");
    omega_max_depth = (unsigned)n;
  }
  setlocale(LC_CTYPE, "C.UTF-8");
  const char *f = getenv("OMEGA_FUEL");
  if (f) {
    char *end;
    errno = 0;
    unsigned long long n = strtoull(f, &end, 10);
    if (errno || *end || !n || n > 500000000ULL)
      o_die("Invalid OMEGA_FUEL");
    omega_fuel = n;
  }
}
#endif
