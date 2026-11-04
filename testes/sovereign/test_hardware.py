from fractions import Fraction
from hashlib import sha3_256
from pathlib import Path
import json
import random
from omega_sovereign.baremetal import build
from omega_sovereign.hardware import tool,fpga,asic
from omega_sovereign.native import ROOT
from omega_platform.sandbox import trusted,run
from omega_platform.budget import BUILD_BUDGET,Budget
import pytest


def test_baremetal_real_privilege_interrupt_fault_and_block(tmp_path,monkeypatch):
    prefix=ROOT.parent/'.tools/sovereign/usr/lib/x86_64-linux-gnu'
    if prefix.is_dir():monkeypatch.setenv('LD_LIBRARY_PATH',str(prefix))
    binary=tmp_path/'boot.elf';report=build(binary);disk=tmp_path/'disk.raw';disk.write_bytes(bytes(512*1024))
    argv=[tool('qemu-system-riscv64'),'-machine','virt','-m','128M','-smp','1','-bios','none',
          '-display','none','-serial','stdio','-monitor','none','-net','none','-no-reboot','-kernel',str(binary),
          '-global','virtio-mmio.force-legacy=false','-drive',f'file={disk},format=raw,if=none,id=d',
          '-device','virtio-blk-device,drive=d']
    result=trusted(argv,budget=Budget(wall_seconds=10,memory_bytes=2*1024**3))
    assert result.ok and 'OMEGA BAREMETAL PASS' in result.stdout,result.stdout+result.stderr
    assert 'CLINT timer + PLIC UART: PASS' in result.stdout
    assert 'Sv39 unmapped + NX faults: PASS' in result.stdout
    assert disk.read_bytes()[512:520]==bytes.fromhex('564f534147454d4f')
    assert 'CAS SHA3 content binding: PASS' in result.stdout
    assert disk.read_bytes()[1024:1056]==sha3_256(disk.read_bytes()[512:1024]).digest()
    assert report['physical_hardware_validated'] is False


def test_qpu_exact_differential_reset_and_errors(tmp_path):
    rng=random.Random(130);vectors=[(1,3,1,6),(255,1,255,1),(0,255,0,255),(255,254,254,255),(1,0,1,2)]
    vectors += [tuple(rng.randrange(256) for _ in range(4)) for _ in range(64)]
    checks=[]
    for a,b,c,d in vectors:
        if b and d:
            value=Fraction(a,b)+Fraction(c,d);expected=f'if(error || n!={value.numerator} || den!={value.denominator}) $fatal(1,"Mismatch");'
        else:expected='if(!error) $fatal(1,"Missing denominator error");'
        checks.append(f'@(negedge clk);a={a};b={b};c={c};d={d};start=1;@(negedge clk);start=0; wait(done); #1; {expected}')
    source=tmp_path/'tb.v';source.write_text('''module tb;reg clk=0;always #5 clk=~clk;
reg reset=1,start=0;reg[7:0]a,b,c,d;wire busy,done,error;wire[16:0]n,den;
qpu_exact core(clk,reset,start,a,b,c,d,busy,done,error,n,den);
initial begin #22;reset=0;'''+ '\n'.join(checks)+'''\n$display("QPU PASS");$finish;end
initial begin #100000000;$fatal(1,"Timeout");end endmodule''')
    output=tmp_path/'sim.vvp';command=[tool('iverilog'),'-g2012','-s','tb','-o',str(output)]
    modules=ROOT.parent/'.tools/sovereign/usr/lib/x86_64-linux-gnu/ivl'
    if modules.is_dir():command+=['-B',str(modules)]
    command += [str(ROOT/'hardware/sovereign/qpu_exact.v'),str(source)]
    result=trusted(command,budget=BUILD_BUDGET);assert result.ok,result.stderr
    result=run([tool('vvp'),output],readonly=[output,*([modules] if modules.is_dir() else [])],budget=Budget(wall_seconds=30))
    assert result.ok and 'QPU PASS' in result.stdout,result.stdout+result.stderr


def test_fpga_bitstream_and_timing(tmp_path):
    out=tmp_path/'fpga';report=fpga(out)
    timing=json.loads((out/'timing.json').read_text())
    assert report['board_programmed'] is False
    assert (out/'qpu.bin').stat().st_size>10000
    assert all(row['achieved']>=row['constraint'] for row in timing['fmax'].values())
    assert timing['utilization']['ICESTORM_LC']['used']<=1280


def test_asic_requires_real_tools_and_pdk(tmp_path):
    with pytest.raises(FileNotFoundError):asic(tmp_path/'asic',pdk_root=tmp_path/'absent')
