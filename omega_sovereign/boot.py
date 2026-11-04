"""Generate, simulate and synthesize the RV64I monitor ROM for ULX3S 85F.

This is a separate minimal platform, not the privileged Sv39 QEMU virt kernel.
A bitstream build never sets board_programmed or fabricated to true.
"""
from pathlib import Path
import json
import shutil
import struct

from omega_platform.budget import BUILD_BUDGET,COMPILER_BUDGET
from omega_platform.sandbox import trusted,run
from omega_sovereign.hardware import digest,tool
from omega_sovereign.native import ROOT,SOURCES
from omega_sovereign.rv64 import assemble
from omega_platform.budget import Budget

FPGA_BUDGET=Budget(wall_seconds=900,cpu_seconds=800,memory_bytes=4*1024**3,
                   file_bytes=512*1024**2,processes=1024)


def sources(destination):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    destination.mkdir(parents=True)
    names=('rv64_core.v','monitor_soc.v','monitor.S','ulx3s85f.lpf','monitor_tb.sv','ulx3s_top.v')
    for name in names:shutil.copyfile(SOURCES/'hardware/boot'/name,destination/name)
    image,_=assemble((destination/'monitor.S').read_text(),origin=0x80000000,max_bytes=512)
    if len(image)%4:raise ValueError('ROM alignment')
    words=struct.unpack('<'+'I'*(len(image)//4),image)
    (destination/'monitor.hex').write_text(''.join(f'{x:08x}\n' for x in words)+('00000000\n'*(128-len(words))))
    return destination,names


def simulate(destination):
    destination,names=sources(destination)
    compiler=Path(tool('iverilog'))
    plugins=compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
    command=[compiler]
    if plugins.is_dir():command+=['-B',plugins]
    command+=['-g2012','-s','monitor_tb','-o','monitor.vvp','rv64_core.v','monitor_soc.v','monitor_tb.sv']
    result=trusted(command,cwd=destination,budget=BUILD_BUDGET,check=True)
    (destination/'compile.log').write_text(result.stdout+result.stderr)
    ro=[destination]
    if plugins.is_dir():ro.append(plugins)
    result=run([tool('vvp'),destination/'monitor.vvp'],readonly=ro,cwd=destination,budget=COMPILER_BUDGET,check=True)
    (destination/'serial.log').write_text(result.stdout+result.stderr)
    if 'OMEGA RV64 MONITOR: 42 OK\nBOOT_SERIAL_VERIFIED' not in result.stdout:raise ValueError('Monitor serial transcript mismatch')
    report={'format':'omega-monitor-rtl-v1','boot_simulated':True,'board_programmed':False,
            'isa':'RV64I subset; no privileged ISA, MMU, interrupts or M/A/F/D/C',
            'serial_bytes':26,'inputs':{n:digest(destination/n) for n in (*names,'monitor.hex')}}
    (destination/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def fpga(destination,*,seed=1):
    if type(seed) is not int or not 1<=seed<2**31:raise ValueError('Seed')
    destination,names=sources(destination)
    tools_root=ROOT.parent/'.tools/sovereign/usr/share'
    database=tools_root/'nextpnr'
    command=[tool('nextpnr-ecp5'),'--router','router2','--85k','--package','CABGA381','--speed','6','--json','monitor.json',
             '--lpf','ulx3s85f.lpf','--textcfg','monitor.config','--freq','6.25','--seed',str(seed),'--report','timing.json','--log','route.log']
    if database.is_dir() and not Path('/usr/share/nextpnr/ecp5').is_dir():
        command=[str(ROOT.parent/'.tools/bubblewrap-0.12.0/bin/bwrap'),'--unshare-all','--die-with-parent','--new-session',
                 '--ro-bind','/','/','--bind',str(destination),str(destination),'--tmpfs','/usr/share',
                 '--ro-bind',str(database),'/usr/share/nextpnr','--',*command]
    pack=[tool('ecppack'),'--compress']
    trellis=tools_root/'trellis/database'
    if trellis.is_dir():pack+=['--db',trellis]
    pack+=['monitor.config','monitor.bit']
    commands=[[tool('yosys'),'-p','read_verilog rv64_core.v monitor_soc.v ulx3s_top.v; synth_ecp5 -top ulx3s_monitor_top -json monitor.json'],command,pack]
    outcomes=[]
    for i,cmd in enumerate(commands):
        result=trusted(cmd,cwd=destination,budget=FPGA_BUDGET)
        (destination/f'{i}.log').write_text(result.stdout+result.stderr)
        if not result.ok:raise RuntimeError(f'Monitor FPGA build failed: {destination}/{i}.log')
        if i==0:
            netlist=json.loads((destination/'monitor.json').read_text())['modules']['ulx3s_monitor_top']
            if not any(type(bit) is int for bit in netlist['ports']['ftdi_rxd']['bits']):
                raise RuntimeError('Synthesis eliminated serial transmitter')
        outcomes.append({'command':list(map(str,cmd)),'exit':result.returncode,'seconds':result.wall_seconds})
    report={'format':'omega-monitor-fpga-v1','target':'ULX3S LFE5U-85F-6BG381C','seed':seed,'clock_mhz':6.25,'input_clock_mhz':25,
            'board_programmed':False,'physical_boot_verified':False,'fabricated':False,
            'inputs':{n:digest(destination/n) for n in (*names,'monitor.hex')},'tools':outcomes,
            'artifacts':{n:digest(destination/n) for n in ('monitor.json','monitor.config','monitor.bit','timing.json')}}
    report['mapped_simulation']=check_synthesized_serial(destination)
    (destination/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def check_synthesized_serial(destination):
    """Simulate the technology-mapped ECP5 netlist, including the clock divider.

    A synthesized netlist that merely has an output wire is insufficient; this
    check compares the actual UART bytes after synthesis. No board is implied.
    """
    destination=Path(destination).resolve()
    if not (destination/'monitor.json').is_file():raise FileNotFoundError('Synthesized JSON required')
    result=trusted([tool('yosys'),'-p','read_json monitor.json; write_verilog -noattr monitor-netlist.v'],cwd=destination,budget=FPGA_BUDGET,check=True)
    (destination/'netlist-export.log').write_text(result.stdout+result.stderr)
    bench=destination/'gate_tb.sv'
    bench.write_text('''`timescale 1ns/1ps
module gate_tb;
reg clk=0,reset_n=0;wire serial,trapped;
reg [7:0] received;integer i,count;
reg [8*26-1:0] expected="OMEGA RV64 MONITOR: 42 OK\\n";
always #20 clk=~clk;
ulx3s_monitor_top dut(clk,reset_n,serial,trapped);
initial begin #100000000;$fatal(1,"Mapped monitor timeout");end
always @(posedge clk)if(reset_n && trapped)$fatal(1,"Mapped core trap");
initial begin
 repeat(50)@(negedge clk);reset_n=1;
 for(count=0;count<26;count=count+1)begin
  @(negedge serial);#12960;
  for(i=0;i<8;i=i+1)begin received[i]=serial;#8640;end
  if(!serial || received!==expected[(25-count)*8+:8])$fatal(1,"Mapped UART mismatch %d",count);
 end
 $display("MAPPED_SERIAL_VERIFIED");$finish;
end
endmodule
''')
    compiler=Path(tool('iverilog'));plugins=compiler.parent.parent/'lib/x86_64-linux-gnu/ivl'
    library=Path(tool('yosys')).parent.parent/'share/yosys/ecp5/cells_sim.v'
    command=[compiler]
    if plugins.is_dir():command+=['-B',plugins]
    command+=['-g2012','-I',library.parent,'-s','gate_tb','-o','gate.vvp','monitor-netlist.v',library,bench]
    result=trusted(command,cwd=destination,budget=FPGA_BUDGET,check=True)
    (destination/'gate-compile.log').write_text(result.stdout+result.stderr)
    result=run([tool('vvp'),destination/'gate.vvp'],readonly=[destination,plugins],cwd=destination,budget=FPGA_BUDGET,check=True)
    (destination/'gate-serial.log').write_text(result.stdout+result.stderr)
    if 'MAPPED_SERIAL_VERIFIED' not in result.stdout:raise ValueError('Mapped serial check did not finish')
    return {'passed':True,'seconds':result.wall_seconds,'netlist_sha256':digest(destination/'monitor-netlist.v')}
