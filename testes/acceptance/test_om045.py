"""OM-045: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.inference import Rule,derive

def test_horn_inference_preserves_witnesses_and_does_not_invent_facts():
    facts,proof=derive(['P'],[Rule('pq',frozenset(['P']),'Q'),Rule('qr',frozenset(['Q']),'R'),Rule('zs',frozenset(['Z']),'S')])
    assert facts==frozenset(['P','Q','R']) and proof['R']==('qr',('Q',))
    with pytest.raises(ValueError):derive(['P'],[Rule('r',frozenset(['P']),'Q')],fuel=0)
