"""Bounded native logic, exact tensors and direct ELF compilation.

No import builds or executes candidate code. See kernel/README.md for the
supported theory, numeric domains and the independent verification boundary.
"""

__version__ = "0.1.0"


def verify(packet, *, reference=False):
    from .runtime import request
    return request("verify-omega" if reference else "verify", packet)


def tensor(packet, *, reference=False):
    from .runtime import request
    return request("tensor-reference" if reference else "tensor", packet)


def compile_source(source, architecture="x86_64"):
    from .runtime import request
    return request("compile-source", {"source": source, "architecture": architecture})
