"""OM-118: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.documents import extract
from omega_security.untrusted_data import UntrustedDocument
from omega_platform.sandbox import ExecutionFailure

def test_document_worker_extracts_text_with_origin_and_rejects_malformed_json():
    document=UntrustedDocument('fixture://doc','Ômega\nline two'.encode(),'2026-10-25T00:00:00Z')
    result=extract(document,'text')
    assert result['pages']==[{'page':1,'text':'Ômega\nline two'}] and result['sha256']==document.digest and result['authority'] is False
    with pytest.raises(ExecutionFailure):extract(UntrustedDocument('fixture://bad',b'{','now'),'json')
