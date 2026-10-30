"""Small proof terms exercising binding and computation, not just tautologies."""
from omega_kernel.certificates import ProofBuilder


def examples():
    b = ProofBuilder()
    nat = b.node("nat")
    var0 = b.node("var", data=(0,))
    identity = b.node("lambda", nat, var0)
    zero = b.node("nat-literal", data=(0,))
    three = b.node("nat-literal", data=(3,))
    six = b.node("nat-literal", data=(6,))
    nine = b.node("nat-literal", data=(9,))
    applied = b.node("app", identity, nine)
    equality = b.node("equality", nat, applied, nine)
    refl = b.node("refl", nat, applied)
    yield "beta-under-identity", b.packet(refl, equality), True
    yield "forged-identity-result", b.packet(refl, b.node("equality", nat, applied, six)), False
    pi = b.node("pi", nat, nat)
    yield "simple-function", b.packet(identity, pi), True
    yield "function-is-not-a-natural", b.packet(identity, nat), False
    plus = b.node("nat-add", three, six)
    yield "natural-add", b.packet(b.node("refl", nat, plus), b.node("equality", nat, plus, nine)), True
    times = b.node("nat-mul", three, three)
    yield "natural-mul", b.packet(b.node("refl", nat, times), b.node("equality", nat, times, nine)), True
    motive = b.node("lambda", nat, nat)
    # lambda n. lambda acc. succ acc : Nat -> Nat -> Nat
    step = b.node("lambda", nat, b.node("lambda", nat, b.node("successor", var0)))
    rec = b.node("nat-rec", motive, zero, step, three)
    yield "nat-rec-computation", b.packet(b.node("refl", nat, rec), b.node("equality", nat, rec, three)), True
    sort = b.node("sort", data=(0,))
    yield "no-type-in-type", b.packet(sort, sort), False
    yield "universe-successor", b.packet(sort, b.node("sort", data=(1,))), True
    # Polymorphic identity: lambda A:Sort0. lambda x:A. x
    polymorphic = b.node("lambda", sort, b.node("lambda", var0, var0))
    poly_type = b.node("pi", sort, b.node("pi", var0, b.node("var", data=(1,))))
    yield "dependent-polymorphic-identity", b.packet(polymorphic, poly_type), True
    yield "free-variable-closed-check", b.packet(var0, nat), False
    sigma = b.node("sigma", nat, nat)
    pair = b.node("pair", sigma, three, six)
    first = b.node("first", pair)
    second = b.node("second", pair)
    yield "sigma-first", b.packet(b.node("refl", nat, first), b.node("equality", nat, first, three)), True
    yield "sigma-second", b.packet(b.node("refl", nat, second), b.node("equality", nat, second, six)), True
    let = b.node("let", nat, nine, var0)
    yield "zeta-let", b.packet(b.node("refl", nat, let), b.node("equality", nat, let, nine)), True
    proof_zero = b.node("refl", nat, zero)
    transported = b.node("transport", motive, proof_zero, three)
    yield "equality-transport", b.packet(transported, nat), True
    b.definitions.append({"type": pi, "body": identity})
    constant = b.node("constant", data=(0,))
    delta = b.node("app", constant, six)
    yield "checked-transparent-definition", b.packet(b.node("refl", nat, delta), b.node("equality", nat, delta, six)), True
    for i in range(1, 9):
        q = b.rational(f"{i}/3")
        r = b.rational(f"{-i}/7")
        left = b.node("rat-add", q, r)
        right = b.rational(f"{4*i}/21")
        yield f"rational-cancellation-{i}", b.bundle([(left, right)]), True


def arithmetic_cases():
    # Includes signed extremes, short circuit, nonintegral division, overflow,
    # branch-local declarations and failure propagation after eager lets.
    return [
        ("a+b", [3, 7], 0, 10),
        ("a+b", [(1<<63)-1, 1], 1, 0),
        ("a-b", [-(1<<63), 1], 1, 0),
        ("a*b", [-17, 31], 0, -527),
        ("a*b", [1<<62, 4], 1, 0),
        ("a/b", [-18, 3], 0, -6),
        ("a/b", [7, 3], 4, 0),
        ("a/b", [7, 0], 2, 0),
        ("a/b", [-(1<<63), -1], 1, 0),
        ("a%b", [-7, 3], 0, -1),
        ("a%b", [7, -3], 0, 1),
        ("a%b", [-(1<<63), -1], 1, 0),
        ("-a", [-(1<<63), 0], 1, 0),
        ("-a", [-123, 0], 0, 123),
        ("!a", [0, 9], 0, 1),
        ("a==b", [5, 5], 0, 1),
        ("a!=b", [5, 5], 0, 0),
        ("a<b", [-(1<<63), (1<<63)-1], 0, 1),
        ("a>b", [-(1<<63), (1<<63)-1], 0, 0),
        ("a<=b", [-1, -1], 0, 1),
        ("a>=b", [-2, -1], 0, 0),
        ("a&&(7/b)", [0, 0], 0, 0),
        ("a||(7/b)", [1, 0], 0, 1),
        ("a&&(7/b)", [1, 0], 2, 0),
        ("(a+b)*(a-b)", [11, 4], 0, 105),
    ]
