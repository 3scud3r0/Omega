"""OM-132: executable checks; source delivery, not a recorded pass."""
from threading import Event,Timer
import pytest
from omega_security.revocation import Revocations
from omega_platform.sandbox import run
from omega_platform.budget import Budget

def test_revocation_and_shutdown_invoke_registered_cancellations():
    revoked=Revocations();cancelled=Event();revoked.register('cap',cancelled.set)
    assert revoked.revoke('cap')==() and cancelled.is_set() and not revoked.active('cap')
    with pytest.raises(PermissionError):revoked.register('cap',lambda:None)
    other=Event();revoked.register('other',other.set);revoked.shutdown()
    assert other.is_set() and not revoked.active('new')

def test_running_sandbox_observes_cancel_event():
    event=Event();timer=Timer(1,event.set);timer.start()
    try:outcome=run(['/usr/bin/sleep','10'],budget=Budget(wall_seconds=15,cpu_seconds=2),cancel_event=event)
    finally:timer.cancel()
    assert outcome.limit=='revoked' and outcome.termination=='revoked' and not outcome.ok
