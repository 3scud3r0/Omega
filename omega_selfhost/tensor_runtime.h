/* Native rational tensor operations and exact all-coordinate dual AD. */
#ifndef OMEGA_TENSOR_RUNTIME_H
#define OMEGA_TENSOR_RUNTIME_H
#include "polynomial.h"
#include "runtime.h"
typedef V (*OmegaGraph)(V, V, long);
static V t_pair(V a, V b) { return o_push(o_push(o_list(), a), b); }
static V t_zero(V a) {
  if (a->kind == 0)
    return o_int(0);
  if (a->kind != 2)
    o_die("Tensor required");
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_zero(a->a[i]));
  return r;
}
static V t_full(V shape, size_t at, V value) {
  if (at == shape->n)
    return value;
  long n = o_long(shape->a[at]);
  if (n < 1 || n > 2048)
    o_die("Invalid tensor dimension");
  V r = o_list();
  for (long i = 0; i < n; i++)
    o_push(r, t_full(shape, at + 1, value));
  return r;
}
static V t_read(V a) {
  if (a->kind == 1)
    return o_number(a);
  if (a->kind != 2)
    o_die("Serialized rational tensor required");
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_read(a->a[i]));
  return r;
}
static V t_serial(V a) {
  if (a->kind == 0)
    return o_text(a);
  if (a->kind != 2)
    o_die("Tensor required");
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_serial(a->a[i]));
  return r;
}
static V t_serial_state(V a) {
  V r = o_obj();
  for (size_t i = 0; i < a->n; i++)
    o_put(r, o_str(a->keys[i]), t_serial(a->a[i]));
  return r;
}
static V t_map2(V a, V b, V (*fn)(V, V), int broadcast) {
  if (a->kind == 0 && b->kind == 0)
    return fn(a, b);
  if (a->kind != 2 && b->kind != 2)
    o_die("Invalid tensor scalar");
  if (a->kind == 2 && b->kind == 2 && a->n != b->n)
    o_die("Tensor shape mismatch");
  if (!broadcast && (a->kind != 2 || b->kind != 2))
    o_die("Tensor shape mismatch");
  V r = o_list();
  size_t n = a->kind == 2 ? a->n : b->n;
  for (size_t i = 0; i < n; i++)
    o_push(r, t_map2(a->kind == 2 ? a->a[i] : a, b->kind == 2 ? b->a[i] : b, fn, broadcast));
  return r;
}
static V t_add(V a, V b) { return t_map2(a, b, o_add, 0); }
static V t_sub(V a, V b) { return t_map2(a, b, o_sub, 0); }
static V t_mul(V a, V b) {
  if (a->kind == 2 && b->kind == 2)
    o_die("Scalar multiplication required");
  return t_map2(a, b, o_mul, 1);
}
static V t_div(V a, V b) {
  if (b->kind != 0)
    o_die("Scalar divisor required");
  return t_map2(a, b, o_div, 1);
}
static V t_neg(V a) { return t_mul(a, o_int(-1)); }
static V t_sum(V a) {
  if (a->kind == 0)
    return a;
  V r = o_int(0);
  for (size_t i = 0; i < a->n; i++)
    r = o_add(r, t_sum(a->a[i]));
  return r;
}
static V t_relu(V a) {
  if (a->kind == 0)
    return o_cmp(a, o_int(0)) > 0 ? a : o_int(0);
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_relu(a->a[i]));
  return r;
}
static V t_relu_tangent(V a, V da) {
  if (a->kind == 0)
    return o_cmp(a, o_int(0)) > 0 ? da : o_int(0);
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_relu_tangent(a->a[i], da->a[i]));
  return r;
}
static V t_transpose(V a) {
  if (a->kind != 2 || !a->n || a->a[0]->kind != 2)
    o_die("Matrix required");
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
static V t_dot(V a, V b) {
  if (a->kind != 2 || b->kind != 2 || a->n != b->n)
    o_die("Equal vectors required");
  V r = o_int(0);
  for (size_t i = 0; i < a->n; i++)
    r = o_add(r, o_mul(a->a[i], b->a[i]));
  return r;
}
static V t_mm(V a, V b) {
  if (a->kind != 2 || b->kind != 2 || !a->n || !b->n || a->a[0]->kind != 2 || a->a[0]->n != b->n)
    o_die("Invalid matrix multiplication");
  V r = o_list();
  if (b->a[0]->kind == 0) {
    for (size_t i = 0; i < a->n; i++)
      o_push(r, t_dot(a->a[i], b));
    return r;
  }
  V bt = t_transpose(b);
  for (size_t i = 0; i < a->n; i++) {
    V row = o_list();
    for (size_t j = 0; j < bt->n; j++)
      o_push(row, t_dot(a->a[i], bt->a[j]));
    o_push(r, row);
  }
  return r;
}
static V t_pow(V a, long n) {
  if (a->kind || n < 0 || n > 20)
    o_die("Invalid scalar exponent");
  V r = o_int(1);
  for (long i = 0; i < n; i++)
    r = o_mul(r, a);
  return r;
}
static V d_num(V a) { return t_pair(a, o_int(0)); }
static V d_param(V state, V dirs, V name, V shape) {
  V a = o_truth(o_has(state, name)) ? o_get(state, name) : t_full(shape, 0, o_int(0));
  V da = o_truth(o_has(dirs, name)) ? o_get(dirs, name) : t_zero(a);
  return t_pair(a, da);
}
static V d_construct(V op, V shape) {
  V a = t_full(shape, 0, o_int(0));
  if (!strcmp(op->s, "identidade")) {
    if (shape->n != 2 || o_long(shape->a[0]) != o_long(shape->a[1]))
      o_die("Square identity required");
    for (size_t i = 0; i < a->n; i++)
      a->a[i]->a[i] = o_int(1);
  }
  return t_pair(a, t_zero(a));
}
static V d_stack(V args) {
  V a = o_list(), da = o_list();
  for (size_t i = 0; i < args->n; i++) {
    o_push(a, args->a[i]->a[0]);
    o_push(da, args->a[i]->a[1]);
  }
  return t_pair(a, da);
}
static V d_add(V a, V b) { return t_pair(t_add(a->a[0], b->a[0]), t_add(a->a[1], b->a[1])); }
static V d_sub(V a, V b) { return t_pair(t_sub(a->a[0], b->a[0]), t_sub(a->a[1], b->a[1])); }
static V d_neg(V a) { return t_pair(t_neg(a->a[0]), t_neg(a->a[1])); }
static V d_mul(V a, V b) {
  return t_pair(t_mul(a->a[0], b->a[0]), t_add(t_mul(a->a[1], b->a[0]), t_mul(a->a[0], b->a[1])));
}
static V d_div(V a, V b) {
  return t_pair(
      t_div(a->a[0], b->a[0]),
      t_sub(t_div(a->a[1], b->a[0]), t_div(t_mul(a->a[0], b->a[1]), o_mul(b->a[0], b->a[0]))));
}
static V d_pow(V a, V b) {
  long n = o_long(b->a[0]);
  return t_pair(t_pow(a->a[0], n),
                n ? t_mul(a->a[1], o_mul(o_int(n), t_pow(a->a[0], n - 1))) : o_int(0));
}
static V d_mm(V a, V b) {
  return t_pair(t_mm(a->a[0], b->a[0]), t_add(t_mm(a->a[1], b->a[0]), t_mm(a->a[0], b->a[1])));
}
static V d_dot(V a, V b) {
  return t_pair(t_dot(a->a[0], b->a[0]), o_add(t_dot(a->a[1], b->a[0]), t_dot(a->a[0], b->a[1])));
}
static V d_relu(V a) { return t_pair(t_relu(a->a[0]), t_relu_tangent(a->a[0], a->a[1])); }
static V d_sum(V a) { return t_pair(t_sum(a->a[0]), t_sum(a->a[1])); }
static V d_transpose(V a) { return t_pair(t_transpose(a->a[0]), t_transpose(a->a[1])); }
static size_t t_size(V a) {
  if (a->kind == 0)
    return 1;
  size_t n = 0;
  for (size_t i = 0; i < a->n; i++)
    n += t_size(a->a[i]);
  return n;
}
static V t_basis(V a, size_t target, size_t *index) {
  if (a->kind == 0)
    return o_int((*index)++ == target);
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_basis(a->a[i], target, index));
  return r;
}
static V t_unflatten(V shape, V values, size_t *index) {
  if (shape->kind == 0)
    return values->a[(*index)++];
  V r = o_list();
  for (size_t i = 0; i < shape->n; i++)
    o_push(r, t_unflatten(shape->a[i], values, index));
  return r;
}
static V t_grad(OmegaGraph graph, V ir, V state, V loss) {
  V grads = o_obj();
  long lid = o_long(o_get(o_get(ir, o_str("perdas")), loss));
  for (size_t pi = 0; pi < state->n; pi++) {
    V flat = o_list();
    size_t count = t_size(state->a[pi]);
    for (size_t c = 0; c < count; c++) {
      V dirs = o_obj();
      for (size_t j = 0; j < state->n; j++) {
        size_t index = 0;
        o_put(dirs, o_str(state->keys[j]),
              j == pi ? t_basis(state->a[j], c, &index) : t_zero(state->a[j]));
      }
      V vals = graph(state, dirs, -1);
      o_push(flat, vals->a[lid]->a[1]);
    }
    size_t index = 0;
    o_put(grads, o_str(state->keys[pi]), t_unflatten(state->a[pi], flat, &index));
  }
  return grads;
}
static V t_clone_obj(V a) {
  V b = o_obj();
  for (size_t i = 0; i < a->n; i++)
    o_put(b, o_str(a->keys[i]), a->a[i]);
  return b;
}
/* Python-compatible MT19937 integer seeding and getrandbits(2) rejection sampling. */
static uint32_t mt[624];
static size_t mt_at = 624;
static void mt_seed(uint32_t seed) {
  mt[0] = 19650218U;
  for (size_t i = 1; i < 624; i++)
    mt[i] = 1812433253U * (mt[i - 1] ^ (mt[i - 1] >> 30)) + (uint32_t)i;
  size_t i = 1, j = 0;
  for (size_t k = 624; k; k--) {
    mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525U)) + seed + (uint32_t)j;
    i++;
    j++;
    if (i >= 624) {
      mt[0] = mt[623];
      i = 1;
    }
    if (j >= 1)
      j = 0;
  }
  for (size_t k = 623; k; k--) {
    mt[i] = (mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941U)) - (uint32_t)i;
    i++;
    if (i >= 624) {
      mt[0] = mt[623];
      i = 1;
    }
  }
  mt[0] = 0x80000000U;
  mt_at = 624;
}
static uint32_t mt_next(void) {
  if (mt_at >= 624) {
    for (size_t i = 0; i < 624; i++) {
      uint32_t y = (mt[i] & 0x80000000U) | (mt[(i + 1) % 624] & 0x7fffffffU);
      mt[i] = mt[(i + 397) % 624] ^ (y >> 1) ^ ((y & 1) ? 0x9908b0dfU : 0);
    }
    mt_at = 0;
  }
  uint32_t y = mt[mt_at++];
  y ^= y >> 11;
  y ^= (y << 7) & 0x9d2c5680U;
  y ^= (y << 15) & 0xefc60000U;
  y ^= y >> 18;
  return y;
}
static V t_noise(V a, V rate) {
  if (a->kind == 0) {
    uint32_t n;
    do {
      n = mt_next() >> 30;
    } while (n >= 3);
    return o_mul(rate, o_div(o_int((long)n - 1), o_int(16)));
  }
  V r = o_list();
  for (size_t i = 0; i < a->n; i++)
    o_push(r, t_noise(a->a[i], rate));
  return r;
}
static V t_repr_inner(V a, int nested) {
  if (a->kind == 0) {
    V s = o_text(a);
    return nested ? o_add(o_add(o_str("'"), s), o_str("'")) : s;
  }
  V parts = o_list();
  o_push(parts, o_str(a->kind == 3 ? "{" : "["));
  for (size_t i = 0; i < a->n; i++) {
    if (i)
      o_push(parts, o_str(", "));
    if (a->kind == 3) {
      o_push(parts, o_add(o_add(o_str("'"), o_str(a->keys[i])), o_str("': ")));
    }
    o_push(parts, t_repr_inner(a->a[i], 1));
  }
  o_push(parts, o_str(a->kind == 3 ? "}" : "]"));
  return o_join(parts, o_str(""));
}
static V t_get(V a, const char *key) { return o_get(a, o_str(key)); }
static int omega_tensor_main(OmegaGraph graph, V ir) {
  V state = o_obj(), outputs = o_list(), certs = o_list(), theorems = o_obj();
  V params = t_get(ir, "parametros"), cmds = t_get(ir, "comandos");
  for (size_t i = 0; i < cmds->n; i++) {
    V c = cmds->a[i];
    if (!strcmp(t_get(c, "tipo")->s, "reescrever") && o_truth(o_has(c, o_str("left")))) {
      if (!p_equal(p_eval(t_get(c, "left")), p_eval(t_get(c, "right"))))
        o_die("Rewrite polynomial identity rejected");
      V proof = o_obj();
      o_put(proof, o_str("tipo"), o_str("identidade_nativa"));
      o_put(proof, o_str("left"), t_get(c, "left"));
      o_put(proof, o_str("right"), t_get(c, "right"));
      o_push(certs, proof);
    }
  }
  for (size_t i = 0; i < params->n; i++) {
    V p = params->a[i];
    long init = o_long(t_get(p, "inicial"));
    V vals = graph(state, o_obj(), init);
    o_put(state, t_get(p, "nome"), vals->a[init]->a[0]);
  }
  V initial_state = t_serial_state(state);
  for (size_t ci = 0; ci < cmds->n; ci++) {
    o_tick();
    V c = cmds->a[ci], kind = t_get(c, "tipo"), name = t_get(c, "nome");
    const char *op = kind->s;
    if (!strcmp(op, "declaracao")) {
      o_push(outputs, o_add(o_str("declarado: "), name));
      continue;
    }
    if (!strcmp(op, "reescrever")) {
      o_push(outputs, o_add(o_str("reescrita local certificável: "), name));
      continue;
    }
    if (!strcmp(op, "provar") || !strcmp(op, "teorema")) {
      V left = t_get(c, "left"), right = t_get(c, "right");
      if (!p_equal(p_eval(left), p_eval(right)))
        o_die("Polynomial identity rejected");
      V proof = o_obj();
      o_put(proof, o_str("tipo"), o_str("identidade_nativa"));
      o_put(proof, o_str("left"), left);
      o_put(proof, o_str("right"), right);
      o_push(certs, proof);
      if (!strcmp(op, "teorema")) {
        o_put(theorems, name, proof);
        o_push(outputs,
               o_add(o_add(o_str("TEOREMA "), name), o_str(": identidade exata demonstrada")));
      } else
        o_push(outputs, o_str("PROVADO: identidade exata"));
      continue;
    }
    if (!strcmp(op, "verificar")) {
      if (!o_truth(o_has(theorems, name)))
        o_die("Unknown theorem");
      o_push(outputs, o_add(o_str("VERIFICADO: teorema "), name));
      continue;
    }
    if (!strcmp(op, "mostrar_teorema")) {
      if (!o_truth(o_has(theorems, name)))
        o_die("Unknown theorem");
      o_push(outputs, o_add(name, o_str(" = teorema demonstrado")));
      continue;
    }
    V vals = graph(state, o_obj(), -1);
    if (!strcmp(op, "mostrar")) {
      long id = o_long(o_get(t_get(ir, "simbolos"), name));
      o_push(outputs, o_add(o_add(name, o_str(" = ")), t_repr_inner(vals->a[id]->a[0], 0)));
      continue;
    }
    V grads = t_grad(graph, ir, state, name), cert = o_obj();
    int step = !strncmp(op, "passo", 5);
    o_put(cert, o_str("tipo"), o_str(step ? "passo_ir" : "gradiente_ir"));
    o_put(cert, o_str("ir"), ir);
    o_put(cert, o_str("perda"), name);
    o_put(cert, o_str("estado_antes"), t_serial_state(state));
    o_put(cert, o_str("gradientes"), t_serial_state(grads));
    if (step) {
      V target = t_get(c, "parametro"), rate = vals->a[o_long(t_get(c, "taxa"))]->a[0];
      if (rate->kind || mpq_sgn(rate->q) <= 0)
        o_die("Positive learning rate required");
      V after = t_clone_obj(state),
        candidate = t_sub(o_get(state, target), t_mul(o_get(grads, target), rate));
      if (!strcmp(op, "passo_ruidoso")) {
        V seed = t_get(c, "semente");
        mt_seed((uint32_t)o_long(seed));
        candidate = t_add(candidate, t_noise(candidate, rate));
        o_put(cert, o_str("semente"), seed);
      }
      o_put(after, target, candidate);
      long lid = o_long(o_get(t_get(ir, "perdas"), name));
      V before = vals->a[lid]->a[0], next = graph(after, o_obj(), -1)->a[lid]->a[0];
      if (!strcmp(op, "passo") && o_cmp(next, before) > 0)
        o_die("Step rejected: loss would increase");
      o_put(cert, o_str("alvo"), target);
      o_put(cert, o_str("politica"), kind);
      o_put(cert, o_str("taxa"), o_text(rate));
      o_put(cert, o_str("estado_depois"), t_serial_state(after));
      o_put(cert, o_str("perda_antes"), o_text(before));
      o_put(cert, o_str("perda_depois"), o_text(next));
      V line =
          o_add(o_add(o_add(o_add(o_add(o_add(o_add(o_add(kind, o_str(" ")), target), o_str(": ")),
                                        o_text(before)),
                                  o_str(" -> ")),
                            o_text(next)),
                      o_str(" (taxa ")),
                o_add(o_text(rate), o_str(")")));
      o_push(outputs, line);
      state = after;
    } else if (!strcmp(op, "gradientes")) {
      o_push(outputs,
             o_add(o_add(o_str("gradientes "), name), o_add(o_str(": "), t_repr_inner(grads, 0))));
    } else if (!strcmp(op, "gradiente")) {
      V target = t_get(c, "parametro");
      o_push(outputs, o_add(o_add(o_str("gradiente "), target),
                            o_add(o_str(": "), t_repr_inner(o_get(grads, target), 0))));
    } else
      o_die("Unknown native command");
    o_push(certs, cert);
  }
  V observed = o_obj();
  V final_values = graph(state, o_obj(), -1);
  V symbols = t_get(ir, "simbolos");
  for (size_t i = 0; i < symbols->n; i++) {
    long idx = o_long(symbols->a[i]);
    o_put(observed, o_str(symbols->keys[i]), t_serial(final_values->a[idx]->a[0]));
  }
  V result = o_obj();
  o_put(result, o_str("format"), o_str("omega-native-result-2"));
  o_put(result, o_str("ir"), ir);
  o_put(result, o_str("initial_state"), initial_state);
  o_put(result, o_str("values"), observed);
  o_put(result, o_str("outputs"), outputs);
  o_put(result, o_str("state"), t_serial_state(state));
  o_put(result, o_str("certificates"), certs);
  puts(o_json(result)->s);
  return 0;
}
#endif
