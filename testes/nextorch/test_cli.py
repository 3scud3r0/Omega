import json

import pytest

from nextorch.__main__ import main
from nextorch.evolution import CertifiedReplayBuffer, NextorchEngine


def test_demo_writes_reloadable_real_artifacts(tmp_path):
    assert (
        main(
            ["demo", "--cycles", "1", "--problems", "2", "--width", "8", "--output", str(tmp_path)]
        )
        == 0
    )
    report = json.loads((tmp_path / "report.json").read_text())
    assert report["reasoner_diagnostics"]["viable"] and len(report["gflownet_training"]) == 3
    assert len(CertifiedReplayBuffer.load(tmp_path / "certified_replay.json")) >= 2
    assert NextorchEngine.load_checkpoint(tmp_path / "checkpoint.pt").parameter_count > 0


def test_verify_cli_exit_status_is_bound_to_solver_result(tmp_path):
    path = tmp_path / "problem.json"
    path.write_text(json.dumps({"premises": [[0, 1]], "source": 0, "target": 1}))
    assert main(["verify", str(path)]) == 0
    path.write_text(json.dumps({"premises": [[0, 1]], "source": 0, "target": 2}))
    assert main(["verify", str(path)]) == 1
    with pytest.raises(SystemExit):
        main(["demo", "--cycles", "0"])
