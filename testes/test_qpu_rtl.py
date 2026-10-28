from fractions import Fraction as Q
from pathlib import Path
import math
import os
import random
import shutil
import subprocess
import pytest
from omega_cognition.qpu import execute,stein


def simulator():
    compiler=shutil.which('iverilog')
    if compiler:return [compiler],shutil.which('vvp')
    root=Path(__file__).resolve().parents[2]/'.tools/iverilog/usr'
    if (root/'bin/iverilog').exists():return [str(root/'bin/iverilog'),'-B',str(root/'lib/x86_64-linux-gnu/ivl')],str(root/'bin/vvp')
    pytest.skip('Icarus Verilog is required for RTL co-simulation')


def test_qpu_error_witness_and_traps():
    result=execute('/',Q(7,11),Q(5,13),bits=8,max_denominator=10)
    assert result['certificate']['admission'] and Q(result['error'])==abs(Q(result['exact'])-Q(result['value']))
    assert result['interrupt']
    with pytest.raises(ZeroDivisionError):execute('/',1,0)
    with pytest.raises(OverflowError):execute('*',127,127,bits=8)
    for a in range(40):
        for b in range(40):assert stein(a,b)[0]==math.gcd(a,b)


@pytest.mark.parametrize('bits',[8,16,32])
def test_rtl_alu_matches_fraction_and_error_witness(tmp_path,bits):
    command,vvp=simulator();root=Path(__file__).resolve().parents[1]
    limit=2**(bits-1)-1;rng=random.Random(72)
    cases=[(0,1,3,2,3,limit),(3,7,11,5,13,10),(3,1,1,0,1,limit),(2,limit,1,limit,1,limit)]
    cases += [(rng.randrange(4),rng.randint(-limit,limit),rng.randint(1,limit),rng.randint(-limit,limit),rng.randint(1,limit),rng.randint(1,limit)) for _ in range(240)]
    lines=[f'module tb;reg clk=0;always #5 clk=~clk;reg reset=1,start=0;reg[1:0]op;reg signed[{bits-1}:0]an,bn;reg[{bits-1}:0]ad,bd,m;wire ready,valid,error,irq;wire signed[{bits-1}:0]pn;wire[{bits-1}:0]pd;wire[{3*bits+2}:0]en,ed;',
           f'rational_alu #(.W({bits})) dut(clk,reset,start,op,an,bn,ad,bd,m,ready,valid,error,irq,pn,pd,en,ed);',
           'initial begin #11;reset=0;']
    for i,(op,an,ad,bn,bd,m) in enumerate(cases):
        lines.append(f'@(negedge clk);op={op};an={an};ad={ad};bn={bn};bd={bd};m={m};start=1;@(posedge clk);#1;$display("R {i} %0d %0d %0d %0d %0d %0d",error,irq,pn,pd,en,ed);')
    lines += ['$finish;end endmodule'];tb=tmp_path/'tb.sv';tb.write_text('\n'.join(lines))
    binary=tmp_path/'sim'
    subprocess.run([*command,'-g2012','-s','tb','-o',str(binary),str(tb),*[str(p) for p in sorted((root/'hardware/qpu').glob('*.sv'))]],check=True,capture_output=True)
    output=subprocess.check_output([vvp,str(binary)],text=True,timeout=30)
    rows=[line.split() for line in output.splitlines() if line.startswith('R ')]
    assert len(rows)==len(cases)
    for row,case in zip(rows,cases):
        _,index,error,irq,pn,pd,en,ed=row;op,an,ad,bn,bd,m=case
        try:expected=execute(['+','-','*','/'][op],Q(an,ad),Q(bn,bd),bits=bits,max_denominator=m,prove=False)
        except (OverflowError,ZeroDivisionError):assert int(error)==1;continue
        assert int(error)==0,(case,row,expected)
        assert Q(int(pn),int(pd))==Q(expected['value']),(case,row,expected)
        assert Q(int(en),int(ed))==Q(expected['error'])
        assert bool(int(irq))==expected['interrupt']


def test_rtl_stein_gcd_handshake(tmp_path):
    command,vvp=simulator();root=Path(__file__).resolve().parents[1]
    pairs=[(0,0),(0,65535),(48,18),(65535,255),(32768,8192),(65521,65519)]
    lines=['module tb;reg clk=0;always #1 clk=~clk;reg reset=1,start=0;reg[15:0]a,b;wire ready,valid;wire[15:0]result;integer cycles;',
           'gcd_stein dut(clk,reset,start,a,b,ready,valid,result);initial begin #3;reset=0;']
    for a,b in pairs:
        lines.append(f'@(negedge clk);a={a};b={b};start=1;@(negedge clk);start=0;cycles=0;while(!valid&&cycles<200)begin @(negedge clk);cycles=cycles+1;end if(!valid)$fatal; $display("G %0d",result);')
    lines+=['$finish;end endmodule'];tb=tmp_path/'gcd.sv';tb.write_text('\n'.join(lines));binary=tmp_path/'sim'
    subprocess.run([*command,'-g2012','-s','tb','-o',str(binary),str(tb),str(root/'hardware/qpu/gcd_stein.sv')],check=True,capture_output=True)
    output=subprocess.check_output([vvp,str(binary)],text=True,timeout=10)
    assert [int(s.split()[1]) for s in output.splitlines() if s.startswith('G ')]==[math.gcd(*p) for p in pairs]
