"""OM-070: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.contracts import Tool,Contract
from omega_tools.capability_adapter import CapabilityAdapter
from omega_security.encoding import digest

def test_tool_adapter_uses_exact_subject_and_copies_arguments(signed_authority,events):
    verifier,mint=signed_authority;adapter=CapabilityAdapter(verifier,'agent',events,max_calls=1)
    def invoke(arguments):value=arguments['x'];arguments['x']=999;return {'y':value+1}
    adapter.register(Tool('inc','math.eval',Contract({'x':int},frozenset(['x'])),Contract({'y':int},frozenset(['y'])),invoke))
    args={'x':2};request=adapter.request('inc',args)
    assert adapter.call('inc',args,mint(['math.eval'],subject=digest(request)))=={'y':3} and args=={'x':2}
    with pytest.raises(ValueError):adapter.call('inc',args,mint(['math.eval']))
    assert events.events[-1]['status']=='completed'

def test_unknown_capability_cannot_invoke_registered_tool(signed_authority,events):
    verifier,mint=signed_authority;adapter=CapabilityAdapter(verifier,'agent',events)
    invoked=[];adapter.register(Tool('t','math.eval',Contract({},frozenset()),Contract({},frozenset()),lambda args:invoked.append(args) or {}))
    with pytest.raises(PermissionError):adapter.call('t',{},mint(['other']))
    assert invoked==[]
