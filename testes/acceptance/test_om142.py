"""OM-142: executable checks; source delivery, not a recorded pass."""
from omega_bench.telemetry import Snapshot,difference,snapshot

def test_telemetry_cost_per_solution_and_unavailable_energy_are_explicit():
    before=Snapshot(1,2,100,None,None);after=Snapshot(5,4,120,None,None)
    result=difference(before,after,correct=2)
    assert result['wall_seconds']==4 and result['cpu_seconds']==2 and result['seconds_per_correct']==2
    assert result['energy_joules'] is None and result['energy_per_correct'] is None
    assert snapshot().gpu_memory_bytes is None
