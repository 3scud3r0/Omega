"""Refinement contracts and fail-closed Lean admission for Omega programs."""
from .contracts import verify_contract, check_program
from .compiler import build

__all__ = ['verify_contract', 'check_program', 'build']
