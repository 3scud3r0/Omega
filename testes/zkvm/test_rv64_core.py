"""Differential RTL register/PC trace against an independent RV64 ISA engine."""
from pathlib import Path
import struct
from unicorn import Uc,UC_ARCH_RISCV,UC_MODE_RISCV64
from unicorn import riscv_const
from omega_sovereign.rv64 import assemble
from omega_sovereign.hardware import tool
from omega_sovereign.native import ROOT
from omega_platform.sandbox import run,trusted
from omega_platform.budget import BUILD_BUDGET


def test_monitor_core_registers_pc_memory_and_traps_against_unicorn(tmp_path):
    source='''
li x5,0x123456789abcdef0
li x6,-3
add x7,x5,x6
sub x8,x7,x5
sra x9,x5,x6
srl x10,x6,x5
sll x11,x5,x6
slt x12,x6,x0
sltu x13,x6,x0
xor x14,x5,x6
or x15,x5,x6
and x16,x5,x6
srai x17,x6,2
srli x18,x6,2
slli x19,x6,2
sltiu x20,x6,1
andi x21,x5,255
ori x22,x0,123
xori x23,x22,127
li x24,0x1000000
sd x5,0(x24)
lb x25,0(x24)
lbu x26,1(x24)
lh x27,2(x24)
lhu x28,2(x24)
lw x29,0(x24)
lwu x30,0(x24)
ld x31,0(x24)
sb x6,7(x24)
sh x6,4(x24)
sw x6,0(x24)
ld x8,0(x24)
addi x0,x0,19
bge x6,x0,skip
addi x7,x7,1
bltu x0,x5,skip
addi x7,x7,7
skip:
fence
'''
    origin=0x80000000;code,_=assemble(source,origin=origin)
    uc=Uc(UC_ARCH_RISCV,UC_MODE_RISCV64);uc.mem_map(origin,4096);uc.mem_write(origin,code)
    uc.mem_map(0x1000000,4096)
    registers=[getattr(riscv_const,f'UC_RISCV_REG_X{i}') for i in range(32)]
    pc=origin;trace=[]
    while pc<origin+len(code):
        assert len(trace)<1000
        instruction=struct.unpack_from('<I',code,pc-origin)[0]
        uc.emu_start(pc,origin+len(code),count=1)
        after=uc.reg_read(riscv_const.UC_RISCV_REG_PC)
        trace.append((instruction,after,[uc.reg_read(r) for r in registers]))
        pc=after
    lines=['''`timescale 1ns/1ps
module core_tb;
reg clk=0,reset=1;reg [31:0] ins=0;wire [63:0] pc,addr,wdata;
wire request,write,trapped;wire [7:0] mask;reg ready=1;reg [63:0] memory=0;
wire fault=request && (addr<64'h1000000 || addr>=64'h1000008);
omega_rv64_core dut(clk,reset,pc,ins,1'b0,request,write,addr,wdata,mask,memory,ready,fault,trapped);
always #5 clk=~clk;
integer j;
always @(posedge clk)if(!reset && request && ready && !fault && write)
 for(j=0;j<8;j=j+1)if(mask[j])memory[j*8+:8]<=wdata[j*8+:8];
initial begin
 @(negedge clk);reset=0;
''']
    for n,(instruction,pc,regs) in enumerate(trace):
        lines.append(f"ins=32'h{instruction:08x};@(posedge clk);#1;")
        lines.append(f"if(trapped || pc!==64'h{pc:016x})$fatal(1,\"PC/trap mismatch step {n}\");")
        for index,value in enumerate(regs):
            lines.append(f"if(dut.x[{index}]!==64'h{value:016x})$fatal(1,\"register x{index} mismatch step {n}\");")
        lines.append('@(negedge clk);')
    lines.append('''
ins=32'b0;@(posedge clk);#1;if(!trapped)$fatal(1,"Illegal instruction accepted");
@(negedge clk);reset=1;@(negedge clk);reset=0;
ins=32'h00100093;@(posedge clk);@(negedge clk); // addi x1,x0,1
ins=32'h0000b023;#1;if(request)$fatal(1,"Misaligned store had effects");
@(posedge clk);#1;if(!trapped)$fatal(1,"Misaligned store accepted");
$display("RV64_DIFFERENTIAL_TRACE_VERIFIED");$finish;
end
endmodule
''')
    tb=tmp_path/'core_tb.sv';tb.write_text('\n'.join(lines))
    compiler=Path(tool('iverilog'));plugins=compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
    command=[compiler]
    if plugins.is_dir():command+=['-B',plugins]
    command+=['-g2012','-s','core_tb','-o',tmp_path/'core.vvp',ROOT/'hardware/boot/rv64_core.v',tb]
    compiled=trusted(command,cwd=tmp_path,budget=BUILD_BUDGET)
    assert compiled.ok,compiled.stdout+compiled.stderr
    result=run([tool('vvp'),tmp_path/'core.vvp'],readonly=[tmp_path,plugins],cwd=tmp_path,budget=BUILD_BUDGET)
    assert result.ok,result.stdout+result.stderr
    assert 'RV64_DIFFERENTIAL_TRACE_VERIFIED' in result.stdout
