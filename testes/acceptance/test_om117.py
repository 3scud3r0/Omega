"""OM-117: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_tools.web import Retrieval

def test_web_retrieval_scope_and_provenance_without_live_network(signed_authority,monkeypatch):
    verifier,mint=signed_authority;retrieval=Retrieval(verifier,'agent',mint(['network:example.test']))
    class Response:
        url='https://example.test/doc'
        def read(self,count):return b'evidence'
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class Opener:
        def open(self,*args,**kwargs):return Response()
    monkeypatch.setattr('urllib.request.build_opener',lambda *handlers:Opener())
    document=retrieval.get('https://example.test/doc')
    assert document.source=='https://example.test/doc' and document.content==b'evidence' and document.observed_at
    with pytest.raises(PermissionError):retrieval.require('https://other.test/doc')
    with pytest.raises(PermissionError):retrieval.require('http://example.test/doc')
