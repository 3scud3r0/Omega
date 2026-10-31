"""Finite native induction and independently checked improvement proposals."""

def run(operation, request):
    from .runtime import call
    return call(operation, request)
