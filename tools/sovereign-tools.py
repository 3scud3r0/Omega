#!/usr/bin/env python3
"""Unprivileged, checksum-pinned Debian 13 foundation tools; no postinst runs."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]
LOCK=ROOT/'requirements/sovereign-tools.json'
PACKAGES=['iverilog','yosys','nextpnr-ice40','fpga-icestorm','qemu-system-riscv','qemu-user']


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resolve',type=Path,help='explicit Packages.xz snapshot to resolve/update lock')
    parser.add_argument('--destination',type=Path,default=ROOT.parent/'.tools/sovereign')
    args=parser.parse_args()
    if args.resolve:
        records={}
        for record in lzma.open(args.resolve,'rt').read().split('\n\n'):
            fields={line.split(': ',1)[0]:line.split(': ',1)[1] for line in record.splitlines() if ': ' in line and not line.startswith(' ')}
            if fields.get('Architecture') in ('amd64','all'):records[fields.get('Package')]=fields
        selected={}
        def installed(name):
            result=subprocess.run(['dpkg-query','-W','-f=${Status}',name],capture_output=True,text=True)
            return result.returncode==0 and result.stdout=='install ok installed'
        def visit(name,force=False):
            if name in selected or (not force and installed(name)):return
            if name not in records:raise ValueError('Dependency not in snapshot: '+name)
            r=records[name]
            selected[name]={'version':r['Version'],'path':r['Filename'],'sha256':r['SHA256'],'bytes':int(r['Size'])}
            for dependency in r.get('Depends','').split(','):
                alternatives=[re.split(r'[: (]',part.strip())[0] for part in dependency.split('|')]
                if any(installed(part) for part in alternatives):continue
                if alternatives==['']:continue
                candidate=next((part for part in alternatives if part in records),None)
                if candidate is None:raise ValueError('Unresolved dependency '+dependency)
                visit(candidate)
        for name in PACKAGES:visit(name,True)
        LOCK.write_text(json.dumps({'format':'omega-debian-tools-1','distribution':'trixie','packages':selected},indent=2)+'\n')
    lock=json.loads(LOCK.read_text())
    args.destination.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='omega-debs-') as tmp:
        for name,record in lock['packages'].items():
            if not re.fullmatch('[0-9a-f]{64}',record['sha256']) or not record['path'].startswith('pool/') or '..' in record['path']:
                raise ValueError('Unsafe tool lock entry')
            archive=Path(tmp)/(name+'.deb')
            subprocess.run(['curl','--fail','--location','--retry','2','--max-time','120','-sS','-o',archive,
                            'https://deb.debian.org/debian/'+record['path']],check=True)
            data=archive.read_bytes()
            if len(data)!=record['bytes'] or hashlib.sha256(data).hexdigest()!=record['sha256']:
                raise ValueError('Downloaded package integrity mismatch')
            subprocess.run(['dpkg-deb','-x',archive,args.destination],check=True)
            print(name,record['version'],flush=True)
    print('Tool directory:',args.destination)


if __name__=='__main__':main()
