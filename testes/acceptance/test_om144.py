"""OM-144: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_bench.statistics import report,paired_versions

def test_statistical_report_preserves_errors_and_negative_outcomes():
    records=[{'id':'a','status':'correct','seconds':1},{'id':'b','status':'error','seconds':3,'error_type':'TimeoutError'}]
    summary=report(records)
    assert summary['median_seconds']==2 and summary['statuses']=={'correct':1,'error':1}
    assert summary['failures'][0]['error_type']=='TimeoutError'
    with pytest.raises(ValueError):paired_versions(records,list(reversed(records)))
