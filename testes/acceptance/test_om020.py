"""OM-020: executable checks; source delivery, not a recorded pass."""
from pathlib import Path
import shutil
import pytest
from omega_platform.budget import Budget,BUILD_BUDGET
from omega_platform.sandbox import c_tool,run,instrumented

@pytest.mark.parametrize('sanitized',[False,True])
def test_arena_bounds_alignment_reset_and_overflow(tmp_path,sanitized):
    root=Path(__file__).resolve().parents[2];source=Path(__file__).with_name('memory_harness.c');binary=tmp_path/'arena'
    compiler=shutil.which('cc')
    assert compiler is not None,'C toolchain required for memory acceptance'
    flags=['-fsanitize=address,undefined','-fno-pie','-no-pie','-g'] if sanitized else ['-O2']
    c_tool([compiler,'-std=c11',*flags,'-I',root/'omega_selfhost',source,'-o',binary],inputs=[source,root/'omega_selfhost'],output_directory=tmp_path,budget=BUILD_BUDGET,check=True)
    outcome=(instrumented if sanitized else run)([binary],budget=Budget(wall_seconds=15,cpu_seconds=10),check=True)
    assert outcome.stdout.strip()=='arena-ok' and outcome.sandboxed
