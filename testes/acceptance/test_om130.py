"""OM-130: executable checks; source delivery, not a recorded pass."""
import json
from omega_security.secrets import redact
from omega_security.audit import AuditLog

def test_secrets_are_redacted_recursively_before_audit_persistence(tmp_path):
    fake='fixture-secret-not-a-real-credential'
    result=redact({'api_key':fake,'nested':['password='+fake]})
    assert fake not in json.dumps(result)
    log=AuditLog(tmp_path/'audit.log');log.append({'authorization':fake,'status':'denied'})
    assert fake not in (tmp_path/'audit.log').read_text()
    assert log.read()[0]['payload']['status']=='denied'
