"""OM-145: executable checks; source delivery, not a recorded pass."""
from omega_bench.dashboard import summarize,render

def test_maturity_counts_only_accepted_tasks_not_source_files_or_lines():
    progress={'tasks':[{'id':'a','status':'source_written_pending_validation'},{'id':'b','status':'accepted'}]}
    result=summarize(progress,{'observed_accuracy':.5})
    assert result['accepted']==1 and result['accepted_fraction']==.5 and result['line_count_is_acceptance'] is False
    assert 'Accepted: 1/2' in render(result)
