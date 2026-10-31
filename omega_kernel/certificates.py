"""Source-bound finite exact matrix certificates for the embedded calculus.

The trusted verifier reconstructs the statement from the supplied matrix
request/result. A producer cannot substitute an unrelated true proposition.
These certify particular arithmetic results, not the algorithm for all inputs,
not a physical law, and not the correctness of the C compiler or processor.
"""
from __future__ import annotations

from fractions import Fraction

from omega_security.encoding import canonical, snapshot

from .protocol import matrix_values, plain, sha256


class ProofBuilder:
    def __init__(self):
        self.nodes = []
        self.interned = {}
        self.definitions = []

    def node(self, op, *args, data=()):
        key = (op, tuple(args), tuple(data))
        if key in self.interned:
            return self.interned[key]
        if len(self.nodes) >= 4096 or any(type(i) is not int or not 0 <= i < len(self.nodes) for i in args):
            raise ValueError("Proof node/edge budget")
        index = len(self.nodes)
        self.nodes.append({"op": op, "args": list(args), "data": list(data)})
        self.interned[key] = index
        return index

    def rational(self, value):
        value = Fraction(value)
        if abs(value.numerator) > (1 << 63) - 1 or value.denominator > (1 << 63) - 1:
            raise ValueError("Native proof rational exceeds the declared finite domain")
        return self.node("rat-literal", data=(value.numerator, value.denominator))

    def packet(self, proof, expected, *, fuel=1000000, nodes=16384, depth=128):
        return {"format": "omega-kernel-proof-1", "nodes": self.nodes,
                "definitions": self.definitions, "proof": proof, "expected": expected,
                "limits": {"fuel": fuel, "nodes": nodes, "depth": depth}}

    def bundle(self, equations):
        """Closed Sigma products of arithmetic equalities, terminated by Unit."""
        expected = self.node("unit")
        proof = self.node("unit-value")
        rational_type = self.node("rat")
        for left, right in reversed(equations):
            equality = self.node("equality", rational_type, left, right)
            reflexivity = self.node("refl", rational_type, left)
            # The second component is closed, so entering one binder does not
            # require a shift. No free term variables occur in these packets.
            expected = self.node("sigma", equality, expected)
            proof = self.node("pair", expected, reflexivity, proof)
        return self.packet(proof, expected)


def _matrix(value, builder):
    if set(value) != {"rows", "columns", "values"}:
        raise ValueError("Certificate matrix exact fields")
    rows = value["rows"]
    columns = value["columns"]
    if type(rows) is not int or type(columns) is not int or not 1 <= rows <= 16 or not 1 <= columns <= 16:
        raise ValueError("Certificate matrix dimensions 1..16")
    values = value["values"]
    if len(values) != rows * columns:
        raise ValueError("Certificate matrix size")
    return rows, columns, [builder.rational(x) for x in values]


def tensor_statement(request, result):
    request = plain(request)
    if not result.get("accepted") or result.get("operation") != "tensor":
        raise ValueError("Successful tensor result required")
    builder = ProofBuilder()
    rows, columns, a = _matrix(request["a"], builder)
    operation = request["operation"]
    expressions = []
    if operation in {"gemm", "add", "sub", "hadamard"}:
        br, bc, b = _matrix(request["b"], builder)
        if operation == "gemm":
            if columns != br:
                raise ValueError("Certificate GEMM shape")
            for i in range(rows):
                for j in range(bc):
                    term = builder.rational(0)
                    for k in range(columns):
                        product = builder.node("rat-mul", a[i * columns + k], b[k * bc + j])
                        term = builder.node("rat-add", term, product)
                    expressions.append(term)
            columns = bc
        else:
            if (br, bc) != (rows, columns):
                raise ValueError("Certificate elementwise shape")
            for left, right in zip(a, b):
                if operation == "sub":
                    right = builder.node("rat-neg", right)
                expressions.append(builder.node("rat-mul" if operation == "hadamard" else "rat-add", left, right))
    elif operation == "transpose":
        expressions = [a[j * columns + i] for i in range(columns) for j in range(rows)]
        rows, columns = columns, rows
    elif operation in {"sum", "sum-squares"}:
        term = builder.rational(0)
        for item in a:
            if operation == "sum-squares":
                item = builder.node("rat-mul", item, item)
            term = builder.node("rat-add", term, item)
        expressions = [term]
        rows, columns = 1, 1
    else:
        raise ValueError("No arithmetic certificate rule for this tensor operation")
    if len(expressions) > 32:
        raise ValueError("At most 32 result cells per finite proof certificate")
    matrix = result["matrix"]
    if (matrix["rows"], matrix["columns"]) != (rows, columns):
        raise ValueError("Tensor result shape does not match the requested statement")
    observed = matrix_values(matrix)
    return builder.bundle([(expression, builder.rational(value))
                           for expression, value in zip(expressions, observed)])


def create_tensor_certificate(request, result):
    # Raw execution records are not proofs. The kernel must still check the
    # reconstructed arithmetic statement, including its expected result.
    statement = tensor_statement(request, result)
    return {"format": "omega-tensor-certificate-1", "request": plain(request),
            "result": snapshot(result, max_bytes=4*1024**2, max_nodes=100000),
            "proof": statement, "axioms": [],
            "scope": "particular exact matrix arithmetic; no universal refinement theorem"}


def verify_tensor_certificate(certificate, *, reference=False):
    if type(certificate) is not dict or set(certificate) != {
            "format", "request", "result", "proof", "axioms", "scope"}:
        raise ValueError("Tensor certificate exact fields")
    if certificate["format"] != "omega-tensor-certificate-1" or certificate["axioms"] != []:
        raise ValueError("Unsupported tensor certificate or unauthorized axioms")
    expected = create_tensor_certificate(certificate["request"], certificate["result"])
    encode = lambda x: canonical(x, max_bytes=4*1024**2, max_nodes=100000)
    if encode(expected) != encode(certificate):
        raise ValueError("Certificate is not bound to this exact tensor statement")
    from .runtime import request
    outcome = request("verify-omega" if reference else "verify", expected["proof"])
    return {"accepted": bool(outcome["accepted"]), "verified": bool(outcome["verified"]),
            "certificate_sha256": sha256(encode(certificate)),
            "checker": "native-omega" if reference else "native-c", "kernel": outcome,
            "scope": expected["scope"]}
