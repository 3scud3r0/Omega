"""OM-024: executable checks; source delivery, not a recorded pass."""
import pytest
from omega.debugger import Debugger
from omega.trace import evaluate
from omega.profiler import profile

def test_debugger_replay_and_profiler_match_pure_trace(typed_graph):
    expected=evaluate(typed_graph,{'x':3});debugger=Debugger(typed_graph,{'x':3})
    first=debugger.step();debugger.seek(0)
    assert debugger.step()==first
    debugger.seek(0);assert debugger.resume()==expected
    record=profile(typed_graph,{'x':3},repetitions=2)
    assert record['nodes']==len(expected) and record['median_seconds']>=0

def test_debugger_rejects_outside_trace_breakpoint(typed_graph):
    with pytest.raises(ValueError):Debugger(typed_graph,{'x':3}).add_breakpoint(-1)
