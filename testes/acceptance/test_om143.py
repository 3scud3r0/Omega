"""OM-143: executable checks; source delivery, not a recorded pass."""
from omega_bench.provenance import record

def test_experiment_provenance_binds_dataset_model_seed_and_configuration(tmp_path):
    dataset=tmp_path/'data';dataset.write_bytes(b'heldout');model=tmp_path/'model';model.write_bytes(b'weights')
    before=record(dataset,model,7,{'budget':10})
    assert before['seed']==7 and before['dataset_sha256']!=before['model_sha256']
    assert before['experiment_sha256']!=record(dataset,model,8,{'budget':10})['experiment_sha256']
    dataset.write_bytes(b'changed')
    assert before['dataset_sha256']!=record(dataset,model,7,{'budget':10})['dataset_sha256']
