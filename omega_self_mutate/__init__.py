"""Proof-gated compiler evolution; raw source patches have no admission path."""
from .rules import discover_rule,validate_rule
from .bootstrap import evolve
from .activation import activate,deactivate,load_active
__all__=['discover_rule','validate_rule','evolve','activate','deactivate','load_active']
