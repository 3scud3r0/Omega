"""Resource-bounded FPGA flow with immutable input and output provenance."""
from pathlib import Path
from hashlib import sha256
import json
import os
import shutil
from omega_platform.sandbox import trusted
from omega_platform.budget import BUILD_BUDGET
from .native import ROOT,SOURCES


def tool(name):
    path=shutil.which(name)
    fallback=ROOT.parent/'.tools/sovereign/usr/bin'/name
    if not path and fallback.is_file():path=str(fallback)
    if not path:raise FileNotFoundError('Required hardware tool: '+name)
    return path


def digest(path):return sha256(Path(path).read_bytes()).hexdigest()


def fpga(destination, *, seed=1):
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    if type(seed) is not int or not 1<=seed<2**31:raise ValueError('Seed')
    destination.mkdir(parents=True)
    canonical=SOURCES/'hardware/sovereign'
    names=('qpu_exact.v','icestick_top.v','icestick.pcf')
    for name in names:shutil.copyfile(canonical/name,destination/name)
    commands=[
      [tool('yosys'),'-p','read_verilog qpu_exact.v icestick_top.v; synth_ice40 -top icestick_top -json design.json'],
      [tool('nextpnr-ice40'),'--hx1k','--package','tq144','--json','design.json','--pcf','icestick.pcf',
       '--asc','design.asc','--freq','12','--seed',str(seed),'--report','timing.json'],
      [tool('icepack'),'design.asc','qpu.bin']]
    # Debian nextpnr locates external chip databases at an absolute path. Mount
    # the extracted, checksum-pinned share directory there in a private namespace
    # instead of modifying /usr or silently selecting a different device.
    database=ROOT.parent/'.tools/sovereign/usr/share/nextpnr'
    if not Path('/usr/share/nextpnr/ice40/chipdb-1k.bin').is_file() and database.is_dir():
        bubblewrap=ROOT.parent/'.tools/bubblewrap-0.12.0/bin/bwrap'
        commands[1]=[str(bubblewrap),'--unshare-all','--die-with-parent','--new-session',
                     '--ro-bind','/','/','--bind',str(destination),str(destination),
                     '--tmpfs','/usr/share',
                     '--ro-bind',str(database),'/usr/share/nextpnr','--',*commands[1]]
    outcomes=[]
    for index,command in enumerate(commands):
        result=trusted(command,cwd=destination,budget=BUILD_BUDGET)
        (destination/f'{index}.log').write_text(result.stdout+result.stderr)
        outcomes.append({'argv':command,'exit':result.returncode,'seconds':result.wall_seconds})
        if not result.ok:raise RuntimeError(f'FPGA flow failed: {destination}/{index}.log')
    if not (destination/'qpu.bin').stat().st_size:raise RuntimeError('Empty bitstream')
    report={'format':'omega-fpga-build-v1','target':'iCEstick HX1K TQ144','clock_mhz':12,
            'seed':seed,'board_programmed':False,'tools':outcomes,
            'inputs':{name:digest(destination/name) for name in names},
            'artifacts':{name:digest(destination/name) for name in ('design.json','design.asc','timing.json','qpu.bin')}}
    (destination/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def asic(destination, *, pdk_root):
    """Run an installed OpenLane 2/PDK, never manufacture or assert tape-out.

    Requires explicitly provisioned PDK. Missing tools/results are errors, and
    no DRC/LVS claim is inferred from a successful command alone.
    """
    executable=tool('openlane')
    pdk_root=Path(pdk_root).resolve()
    if not (pdk_root/'sky130A').is_dir():raise FileNotFoundError('sky130A PDK required')
    destination=Path(destination).resolve()
    if destination.exists():raise FileExistsError(destination)
    destination.mkdir(parents=True)
    for name in ('sky130.json','qpu_exact.v'):
        shutil.copyfile(SOURCES/'hardware/sovereign'/name,destination/name)
    command=[executable,'--pdk-root',str(pdk_root),'--pdk','sky130A',
             '--run-tag','omega',str(destination/'sky130.json')]
    result=trusted(command,cwd=destination,budget=BUILD_BUDGET)
    (destination/'openlane.log').write_text(result.stdout+result.stderr)
    if not result.ok:raise RuntimeError('OpenLane failed; inspect openlane.log')
    gdss=list(destination.rglob('*.gds'))
    if not gdss:raise RuntimeError('OpenLane did not produce GDS')
    report={'format':'omega-asic-layout-v1','pdk':'sky130A','fabricated':False,
            'signoff_approved':False,'gds':{str(p.relative_to(destination)):digest(p) for p in gdss},
            'configuration_sha256':digest(destination/'sky130.json')}
    (destination/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
