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


def build_crypto(destination,*,fixed_field=False):
    source=assembly(16)
    for name in ('sha3.S','x25519.S','crypto.S'):
        part=(SOURCES/'sovereign/native'/name).read_text()
        if name=='x25519.S' and fixed_field:
            definitions=part[:part.index('field_reduce:')]
            ladder=part[part.index('\nx25519:'):]
            ladder=ladder.replace('call big_one','call field_one').replace('call big_zero','call field_zero')
            ladder=ladder.replace('    ld t1,8(t0)\n    beq t1,zero,crypto_reject_zero', '''    li t1,0
    li t2,8
    addi t3,t0,16
x25519_public_zero_check:
    ld t4,0(t3)
    or t1,t1,t4
    addi t3,t3,8
    addi t2,t2,-1
    bne t2,zero,x25519_public_zero_check
    beq t1,zero,crypto_reject_zero
    li t1,8''')
            # The fixed representation also initializes the public A24 constant.
            ladder=ladder.replace('    call big_decimal','    call big_decimal\n    li t0,FA24\n    li t1,8\n    sd t1,8(t0)')
            part=definitions+(SOURCES/'sovereign/native/field25519_ct.S').read_text()+ladder
        source+='\n'+part
    expanded=[]
    for line in source.splitlines():
        if not line.strip():continue
        op,*rest=line.strip().split(None,1)
        if op in ('.fadd','.fsub','.fmul','.fcopy'):
            args=[s.strip() for s in rest[0].split(',')]
            if len(args)!=(2 if op=='.fcopy' else 3):raise ValueError('Field macro arity')
            expanded.extend(f'li a{i},{arg}' for i,arg in enumerate(args))
            expanded.append('call '+{'.fadd':'field_add','.fsub':'field_sub','.fmul':'field_mul','.fcopy':'field_copy' if fixed_field else 'big_copy'}[op])
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
            'fixed_control_flow_field':fixed_field,
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
