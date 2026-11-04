from pathlib import Path
import signal
import pytest
from omega_platform.budget import PROOF_BUDGET,Budget
from omega_platform.sandbox import trusted
from omega_selfhost.proof import lake_binary
from omega_sovereign.native import ROOT
from omega_sovereign.boot import simulate


def test_lean_arithmetic_induction_and_instruction_bytes():
    result=trusted([lake_binary(),'build','ExpressionCompiler','RiscvEncoding','CompilerCorrectness'],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET)
    assert result.ok,result.stdout+result.stderr
    assert 'sorryAx' not in result.stdout and 'Lean.ofReduceBool' not in result.stdout


def test_monitor_boot_and_exact_uart_transcript(tmp_path):
    report=simulate(tmp_path/'boot')
    assert report['boot_simulated'] and not report['board_programmed']
    assert report['serial_bytes']==26


def test_supervisor_preserves_uncatchable_child_signal():
    supervisor=ROOT/'omega_platform/_supervisor.py'
    result=trusted(['/usr/bin/python3',supervisor,'','/usr/bin/python3','-c','import os,signal;os.kill(os.getpid(),signal.SIGKILL)'],budget=Budget())
    assert result.returncode==-signal.SIGKILL
    assert 'Traceback' not in result.stderr


def test_tiny_tapeout_qpu_protocol_and_rejections(tmp_path):
    from omega_sovereign.hardware import tool
    from omega_platform.sandbox import run
    from omega_platform.budget import BUILD_BUDGET
    compiler=Path(tool('iverilog'));plugins=compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
    command=[compiler]
    if plugins.is_dir():command+=['-B',plugins]
    command+=['-g2012','-s','tt_tb','-o',tmp_path/'tt.vvp',ROOT/'hardware/sovereign/qpu_exact.v',
              ROOT/'hardware/tinytapeout/tt_um_omega_qpu.v',ROOT/'hardware/tinytapeout/tt_tb.sv']
    compiled=trusted(command,cwd=tmp_path,budget=BUILD_BUDGET)
    assert compiled.ok,compiled.stdout+compiled.stderr
    result=run([tool('vvp'),tmp_path/'tt.vvp'],readonly=[tmp_path,plugins],cwd=tmp_path,budget=BUILD_BUDGET)
    assert result.ok,result.stdout+result.stderr
    assert 'TINY_TAPEOUT_PROTOCOL_VERIFIED' in result.stdout
