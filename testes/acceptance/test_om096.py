"""OM-096: executable checks; source delivery, not a recorded pass."""
import torch
import pytest
from omega_nextorch.devices import resolve,parity

def test_cpu_precision_policy_and_nonfinite_numerics():
    device,dtype=resolve('cpu','float32');assert device.type=='cpu' and dtype==torch.float32
    assert parity(torch.tensor([1.]),torch.tensor([1.]))['within_tolerance']
    assert not parity(torch.tensor([1.]),torch.tensor([float('nan')]))['within_tolerance']
    with pytest.raises(ValueError):resolve('cpu','float16')

def test_cuda_parity_when_hardware_is_present():
    if not torch.cuda.is_available():pytest.skip('CUDA hardware required; this acceptance remains pending')
    values=torch.tensor([1.,2.,3.]);actual=(values.cuda()*2).cpu()
    assert parity(values*2,actual)['within_tolerance']
