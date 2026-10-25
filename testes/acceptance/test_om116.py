"""OM-116: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.contracts import Contract
from omega_tools.capability_adapter import CapabilityAdapter
from omega_tools.local_files import register_files
from omega_security.encoding import digest

def test_typed_contract_rejects_bool_as_int_and_undeclared_fields():
    schema=Contract({'count':int},frozenset(['count']))
    with pytest.raises(TypeError):schema.check({'count':True})
    with pytest.raises(ValueError):schema.check({'count':1,'extra':2})

def test_file_tool_requires_exact_approved_mutation(tmp_path,signed_authority,approval_authority,events):
    verifier,mint=signed_authority;gate,approve=approval_authority
    file=tmp_path/'a.txt';file.write_text('old')
    adapter=CapabilityAdapter(verifier,'agent',events,approval_gate=gate)
    register_files(adapter,tmp_path,writable=True)
    read=adapter.call('files.read_text',{'path':str(file)},mint(['file.read']))
    assert read['content']=='old' and read['authority'] is False
    arguments={'path':str(file),'content':'new','expected_sha256':read['sha256']}
    request=adapter.request('files.replace_text',arguments)
    with pytest.raises(PermissionError):adapter.call('files.replace_text',arguments,mint(['file.write']),approval=None)
    result=adapter.call('files.replace_text',arguments,mint(['file.write'],subject=digest(request)),approval=approve(request))
    assert result['bytes']==3 and file.read_text()=='new'
