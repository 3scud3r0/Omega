"""OM-131: executable checks; source delivery, not a recorded pass."""
import json
import pytest
from omega_security.audit import AuditLog

def test_hash_chain_and_external_anchor_detect_tampered_decision(tmp_path):
    path=tmp_path/'audit';log=AuditLog(path);log.append({'decision':'deny'});anchor=log.append({'decision':'review'})
    assert len(AuditLog(path,anchor=anchor).read())==2
    lines=path.read_text().splitlines();item=json.loads(lines[0]);item['payload']['decision']='approve';lines[0]=json.dumps(item)
    path.write_text('\n'.join(lines)+'\n')
    with pytest.raises(ValueError):AuditLog(path,anchor=anchor).read()
