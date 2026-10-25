"""OM-114: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_evolution.resource_limits import EvolutionResources

def test_evolution_lifetime_and_process_quotas_are_released_and_revoked():
    resources=EvolutionResources(cycles=1,cpu_seconds=3,proposals=2,processes=1)
    resources.begin_cycle(proposals=1,cpu_seconds=2)
    with resources.process():
        with pytest.raises(ValueError):
            with resources.process():pass
    with resources.process():pass
    with pytest.raises(ValueError):resources.begin_cycle(proposals=1,cpu_seconds=1)
    resources.stop()
    with pytest.raises(PermissionError):
        with resources.process():pass
