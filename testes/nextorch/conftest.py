import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("MPLCONFIGDIR", os.path.join(tempfile.gettempdir(), "nextorch-matplotlib"))
os.environ.setdefault("XDG_CACHE_HOME", os.path.join(tempfile.gettempdir(), "nextorch-cache"))
os.environ.setdefault("XDG_CONFIG_HOME", os.path.join(tempfile.gettempdir(), "nextorch-config"))

import pytest
import torch


@pytest.fixture(autouse=True)
def reproducible_test():
    torch.set_num_threads(2)
    torch.manual_seed(7)
