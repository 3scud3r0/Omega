"""OM-052: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_agent.experiments import Experiment,run

def test_experiment_records_seed_prediction_and_refutation():
    experiment=Experiment('x increases',10,2,'observe x',7)
    result=run(experiment,lambda intervention,seed:intervention+seed,lambda e,raw:{'status':'refuted' if raw!=e.prediction else 'supported'})
    assert result['seed']==7 and result['observation']==9 and result['interpretation']['status']=='refuted'
    with pytest.raises(ValueError):run(experiment,lambda *_:0,lambda *_:{'status':'proven'})
