"""Bootstrap a C/GMP-free RV64 scalar compiler from audited assembly.

Python is used only to build the seed. The seed subsequently reads Omega text
and writes ELF executables itself, including exact signed-limb arithmetic.
"""
from pathlib import Path
from hashlib import sha256
import argparse
import json
from .rv64 import assemble, elf

ROOT = Path(__file__).resolve().parents[1]
SOURCES=ROOT if (ROOT/'sovereign/native/bigq.S').is_file() else ROOT/'omega_native/_sources'


def assembly(limbs):
    return (SOURCES/'sovereign/native/bigq.S').read_text().replace(
        '.equ LIMBS,128',f'.equ LIMBS,{limbs}')+'\n'+(SOURCES/'sovereign/native/compiler.S').read_text()


def build_crypto(destination):
    source=assembly(16)
    for name in ('sha3.S','x25519.S','crypto.S'):
        source+='\n'+(SOURCES/'sovereign/native'/name).read_text()
    expanded=[]
    for line in source.splitlines():
        if not line.strip():continue
        op,*rest=line.strip().split(None,1)
        if op in ('.fadd','.fsub','.fmul','.fcopy'):
            args=[s.strip() for s in rest[0].split(',')]
            if len(args)!=(2 if op=='.fcopy' else 3):raise ValueError('Field macro arity')
            expanded.extend(f'li a{i},{arg}' for i,arg in enumerate(args))
            expanded.append('call '+{'.fadd':'field_add','.fsub':'field_sub','.fmul':'field_mul','.fcopy':'big_copy'}[op])
        else: expanded.append(line)
    source='\n'.join(expanded)
    image,symbols=assemble(source)
    binary=elf(image,entry=symbols['_crypto_start'])
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as output:output.write(binary)
    destination.chmod(0o500)
    return {'format':'omega-crypto-reference-v1','sha256':sha256(binary).hexdigest(),
            'source_sha256':sha256(source.encode()).hexdigest(),'bytes':len(binary),
            'algorithms':['SHA3-256','HMAC-SHA3-256-key32','X25519'], 'constant_time_x25519':False,
            'production_approved':False}


def build_seed(destination, *, limbs=128):
    if type(limbs) is not int or not 16 <= limbs <= 1024:
        raise ValueError('limbs must be an integer in [16,1024]')
    source = assembly(limbs)
    image, symbols = assemble(source)
    binary = elf(image, entry=symbols['_start'])
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output:
        output.write(binary)
    destination.chmod(0o500)
    return {'format':'omega-native-seed-v1', 'architecture':'rv64im-linux',
            'sha256':sha256(binary).hexdigest(), 'source_sha256':sha256(source.encode()).hexdigest(),
            'bytes':len(binary), 'limbs':limbs, 'bits':32*limbs,
            'fragment':'closed scalar rational expressions; mostrar statements',
            'external_runtime_dependencies':[], 'bootstrap':'Python RV64 assembler'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    parser.add_argument('--limbs',type=int,default=128)
    args=parser.parse_args()
    print(json.dumps(build_seed(args.destination,limbs=args.limbs),indent=2))


if __name__=='__main__': main()
