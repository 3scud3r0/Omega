#ifndef OMEGA_POLYNOMIAL_H
#define OMEGA_POLYNOMIAL_H
#include "runtime.h"
/* Sparse multivariate polynomials: sorted repeated variable names -> Q. */
static V p_constant(V q) {
  V p = o_obj();
  o_put(p, o_str(""), q);
  return p;
}
static V p_variable(V name) {
  V p = o_obj();
  o_put(p, name, o_int(1));
  return p;
}
static V p_coefficient(V p, V key) { return o_truth(o_has(p, key)) ? o_get(p, key) : o_int(0); }
static V p_add(V a, V b) {
  V p = o_obj();
  for (size_t i = 0; i < a->n; i++)
    o_put(p, o_str(a->keys[i]), a->a[i]);
  for (size_t i = 0; i < b->n; i++) {
    V k = o_str(b->keys[i]);
    o_put(p, k, o_add(p_coefficient(p, k), b->a[i]));
  }
  return p;
}
static V p_neg(V a) {
  V p = o_obj();
  for (size_t i = 0; i < a->n; i++)
    o_put(p, o_str(a->keys[i]), o_neg(a->a[i]));
  return p;
}
static V p_sub(V a, V b) { return p_add(a, p_neg(b)); }
static int p_strcmp(const void *a, const void *b) {
  return strcmp(*(char *const *)a, *(char *const *)b);
}
static V p_monomial(const char *a, const char *b) {
  if (!*a)
    return o_str(b);
  if (!*b)
    return o_str(a);
  char *s = o_add(o_add(o_str(a), o_str("*")), o_str(b))->s;
  size_t n = 1;
  for (char *q = s; *q; q++)
    if (*q == '*')
      n++;
  char **parts = o_alloc(n * sizeof(char *));
  size_t i = 0;
  parts[i++] = s;
  for (char *q = s; *q; q++)
    if (*q == '*') {
      *q = 0;
      parts[i++] = q + 1;
    }
  qsort(parts, n, sizeof(char *), p_strcmp);
  V seq = o_list();
  for (i = 0; i < n; i++)
    o_push(seq, o_str(parts[i]));
  return o_join(seq, o_str("*"));
}
static V p_mul(V a, V b) {
  V p = o_obj();
  for (size_t i = 0; i < a->n; i++)
    for (size_t j = 0; j < b->n; j++) {
      o_tick();
      V k = p_monomial(a->keys[i], b->keys[j]);
      o_put(p, k, o_add(p_coefficient(p, k), o_mul(a->a[i], b->a[j])));
      if (p->n > 100000)
        o_die("Polynomial budget exceeded");
    }
  return p;
}
static V p_div(V a, V b) {
  for (size_t i = 0; i < b->n; i++)
    if (*b->keys[i] && mpq_sgn(b->a[i]->q))
      o_die("Nonconstant polynomial divisor");
  V q = p_coefficient(b, o_str(""));
  V p = o_obj();
  for (size_t i = 0; i < a->n; i++)
    o_put(p, o_str(a->keys[i]), o_div(a->a[i], q));
  return p;
}
static V p_power(V a, long n) {
  if (a->kind != 3)
    o_die("Scalar polynomial power required");
  if (n < 0 || n > 20)
    o_die("Polynomial exponent outside 0..20");
  V p = p_constant(o_int(1));
  for (long i = 0; i < n; i++)
    p = p_mul(p, a);
  return p;
}
static int p_equal(V a, V b) {
  if (a->kind == 2 || b->kind == 2) {
    if (a->kind != 2 || b->kind != 2 || a->n != b->n)
      return 0;
    for (size_t i = 0; i < a->n; i++)
      if (!p_equal(a->a[i], b->a[i]))
        return 0;
    return 1;
  }
  if (a->kind != 3 || b->kind != 3)
    o_die("Polynomial required");
  for (size_t i = 0; i < a->n; i++)
    if (!o_equal(a->a[i], p_coefficient(b, o_str(a->keys[i]))))
      return 0;
  for (size_t i = 0; i < b->n; i++)
    if (!o_equal(b->a[i], p_coefficient(a, o_str(b->keys[i]))))
      return 0;
  return 1;
}
static V p_element(V a, V b, V (*fn)(V, V), int broadcast) {
  if (a->kind == 3 && b->kind == 3)
    return fn(a, b);
  if (a->kind != 2 && b->kind != 2)
    o_die("Polynomial tensor required");
  if (a->kind == 2 && b->kind == 2 && a->n != b->n)
    o_die("Polynomial tensor shapes differ");
  if (!broadcast && (a->kind != 2 || b->kind != 2))
    o_die("Polynomial tensor shapes differ");
  V r = o_list();
  size_t n = a->kind == 2 ? a->n : b->n;
  for (size_t i = 0; i < n; i++)
    o_push(r, p_element(a->kind == 2 ? a->a[i] : a, b->kind == 2 ? b->a[i] : b, fn, broadcast));
  return r;
}
static V p_tadd(V a, V b) { return p_element(a, b, p_add, 0); }
static V p_tsub(V a, V b) { return p_element(a, b, p_sub, 0); }
static V p_tmul(V a, V b) {
  if (a->kind == 2 && b->kind == 2)
    o_die("Scalar polynomial factor required");
  return p_element(a, b, p_mul, 1);
}
static V p_tdiv(V a, V b) {
  if (b->kind != 3)
    o_die("Scalar polynomial divisor required");
  return p_element(a, b, p_div, 1);
}
static V p_transpose(V a) {
  if (a->kind != 2 || !a->n || a->a[0]->kind != 2)
    o_die("Polynomial matrix required");
  V r = o_list();
  for (size_t j = 0; j < a->a[0]->n; j++) {
    V row = o_list();
    for (size_t i = 0; i < a->n; i++) {
      if (a->a[i]->kind != 2 || a->a[i]->n != a->a[0]->n)
        o_die("Irregular matrix");
      o_push(row, a->a[i]->a[j]);
    }
    o_push(r, row);
  }
  return r;
}
static V p_dot(V a, V b) {
  if (a->kind != 2 || b->kind != 2 || a->n != b->n)
    o_die("Polynomial vectors required");
  V p = p_constant(o_int(0));
  for (size_t i = 0; i < a->n; i++)
    p = p_add(p, p_mul(a->a[i], b->a[i]));
  return p;
}
static V p_mm(V a, V b) {
  if (a->kind != 2 || b->kind != 2 || !a->n || !b->n || a->a[0]->kind != 2 || a->a[0]->n != b->n)
    o_die("Invalid polynomial matrix product");
  V r = o_list();
  if (b->a[0]->kind == 3) {
    for (size_t i = 0; i < a->n; i++)
      o_push(r, p_dot(a->a[i], b));
    return r;
  }
  V bt = p_transpose(b);
  for (size_t i = 0; i < a->n; i++) {
    V row = o_list();
    for (size_t j = 0; j < bt->n; j++)
      o_push(row, p_dot(a->a[i], bt->a[j]));
    o_push(r, row);
  }
  return r;
}
static V p_sum(V a) {
  if (a->kind == 3)
    return a;
  V p = p_constant(o_int(0));
  for (size_t i = 0; i < a->n; i++)
    p = p_add(p, p_sum(a->a[i]));
  return p;
}
static V p_eval(V ast) {
  o_tick();
  const char *kind = ast->a[0]->s;
  if (!strcmp(kind, "n"))
    return p_constant(o_number(ast->a[1]));
  if (!strcmp(kind, "v"))
    return p_variable(ast->a[1]);
  if (!strcmp(kind, "list")) {
    V r = o_list();
    for (size_t i = 0; i < ast->a[1]->n; i++)
      o_push(r, p_eval(ast->a[1]->a[i]));
    return r;
  }
  if (!strcmp(kind, "un"))
    return p_tmul(p_eval(ast->a[2]), p_constant(o_int(-1)));
  if (!strcmp(kind, "bin")) {
    const char *op = ast->a[1]->s;
    V a = p_eval(ast->a[2]), b = p_eval(ast->a[3]);
    if (!strcmp(op, "+"))
      return p_tadd(a, b);
    if (!strcmp(op, "-"))
      return p_tsub(a, b);
    if (!strcmp(op, "*"))
      return p_tmul(a, b);
    if (!strcmp(op, "/"))
      return p_tdiv(a, b);
    if (!strcmp(op, "@"))
      return p_mm(a, b);
    if (!strcmp(op, "^")) {
      for (size_t i = 0; i < b->n; i++)
        if (*b->keys[i] && mpq_sgn(b->a[i]->q))
          o_die("Variable exponent not supported");
      return p_power(a, o_long(p_coefficient(b, o_str(""))));
    }
    o_die("Unknown polynomial operation");
  }
  if (!strcmp(kind, "call")) {
    const char *op = ast->a[1]->s;
    V args = ast->a[2];
    if (!strcmp(op, "dot") && args->n == 2)
      return p_dot(p_eval(args->a[0]), p_eval(args->a[1]));
    if (!strcmp(op, "transposta") && args->n == 1)
      return p_transpose(p_eval(args->a[0]));
    if (!strcmp(op, "soma") && args->n == 1)
      return p_sum(p_eval(args->a[0]));
  }
  o_die("Unsupported polynomial expression");
  return NULL;
}
#endif
