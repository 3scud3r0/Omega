#!/usr/bin/env python3
"""Build reproducible Python archives for a fixed source tree/toolchain."""
import gzip
import io
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from omega_platform.budget import BUILD_BUDGET
from omega_platform.sandbox import trusted

epoch=int(subprocess.run(['git','log','-1','--format=%ct'],cwd=ROOT,
                         capture_output=True,text=True,check=True).stdout.strip())
os.environ['SOURCE_DATE_EPOCH']=str(epoch)
os.environ['PYTHONHASHSEED']='0'
destination=ROOT/'dist';destination.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='.omega-packaging-',dir=destination) as tmp:
    trusted([sys.executable,'-m','build','--no-isolation','--outdir',tmp],
            cwd=ROOT,budget=BUILD_BUDGET,check=True)
    for path in sorted(Path(tmp).iterdir()):
        if path.name.endswith('.tar.gz'):
            # Source-checkout mtimes, ownership and gzip timestamps must not
            # change the sdist bytes across two clean checkouts of one commit.
            with tarfile.open(path,'r:gz') as source:
                data=io.BytesIO()
                with tarfile.open(fileobj=data,mode='w',format=tarfile.PAX_FORMAT) as output:
                    for member in sorted(source.getmembers(),key=lambda m:m.name):
                        stream=source.extractfile(member) if member.isfile() else None
                        member.uid=member.gid=0;member.uname=member.gname=''
                        member.mtime=epoch;member.pax_headers={}
                        member.mode=0o755 if member.isdir() or member.mode&0o111 else 0o644
                        output.addfile(member,stream)
                with path.open('wb') as target:
                    with gzip.GzipFile(filename='',mode='wb',fileobj=target,mtime=epoch) as zipped:
                        zipped.write(data.getvalue())
        os.replace(path,destination/path.name)
        print(destination/path.name)
