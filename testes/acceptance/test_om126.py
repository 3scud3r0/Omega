"""OM-126: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.integration import decode_proposal
from omega_tools.capability_adapter import CapabilityAdapter
from omega_tools.contracts import Tool,Contract

def test_candidate_cannot_attach_authority_or_register_it_after_execution(signed_authority,events):
    with pytest.raises(ValueError):decode_proposal({'kind':'tool_request','name':'publish','arguments':{},'capability':'invented'})
    verifier,mint=signed_authority;adapter=CapabilityAdapter(verifier,'agent',events)
    tool=Tool('noop','read',Contract({},frozenset()),Contract({},frozenset()),lambda _: {})
    adapter.register(tool);assert adapter.call('noop',{},mint(['read']))=={}
    with pytest.raises(ValueError):adapter.register(Tool('other','read',tool.arguments,tool.response,lambda _:{}))
