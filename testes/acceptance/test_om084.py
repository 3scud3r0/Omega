"""OM-084: executable checks; source delivery, not a recorded pass."""
import torch
from torch import nn
import pytest
from omega_learning.versioning import Checkpoints

def test_checkpoint_recovers_weights_and_detects_tampering(tmp_path):
    model=nn.Linear(2,1);store=Checkpoints(tmp_path);expected=model(torch.ones(1,2)).detach()
    record=store.save('step1',model,{'seed':7,'dataset_sha256':'a'*64})
    restored=nn.Linear(2,1);assert store.load('step1',restored)==record
    torch.testing.assert_close(restored(torch.ones(1,2)),expected)
    (tmp_path/'step1.pt').write_bytes(b'corrupt')
    with pytest.raises(ValueError):store.load('step1',restored)
