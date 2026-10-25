"""OM-097: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
from omega_nextorch.inference_metrics import measure

def test_inference_metrics_preserve_training_mode_and_missing_energy():
    model=nn.Linear(2,1);model.train()
    result=measure(model,torch.ones(1,2),repetitions=2)
    assert result['repetitions']==2 and result['median_seconds']>=0
    assert result['energy_joules'] is None and result['cuda_allocated_bytes'] is None and model.training
