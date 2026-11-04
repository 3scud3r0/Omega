from fractions import Fraction
from pathlib import Path
import hashlib
import hmac
import random
import struct
import tempfile
import pytest
from omega_sovereign.native import build_seed,build_crypto
from omega_sovereign.rv64 import assemble,elf,li,expression
from omega_sovereign.hardware import tool
from omega_platform.sandbox import run
from omega_platform.budget import COMPILER_BUDGET


@pytest.fixture(scope='module')
def qemu():return tool('qemu-riscv64')
@pytest.fixture(scope='module')
def seed(tmp_path_factory):
    path=tmp_path_factory.mktemp('rv64')/'compiler';build_seed(path);return path
@pytest.fixture(scope='module')
def crypto(tmp_path_factory):
    path=tmp_path_factory.mktemp('rv64-crypto')/'crypto';build_crypto(path);return path


def invoke(qemu,binary,*args,writable=()):
    return run([qemu,binary,*args],readonly=[binary,*[p for p in args if isinstance(p,Path) and p.exists()]],
               writable=writable,threads=True,budget=COMPILER_BUDGET)


def test_native_compiler_differential_4096_bit(seed,qemu,tmp_path):
    rng=random.Random(7748);program=[];expected=[]
    for i in range(64):
        a=rng.randrange(-2**250,2**250);b=rng.randrange(1,2**120);c=rng.randrange(-2**200,2**200);d=rng.randrange(1,2**110)
        op=('+','-','*','/')[i%4]
        left=Fraction(a,b);right=Fraction(c or 1,d)
        value={'+':lambda:left+right,'-':lambda:left-right,'*':lambda:left*right,'/':lambda:left/right}[op]()
        program.append(f'mostrar ({a}/{b}) {op} ({c or 1}/{d});')
        expected.append(f'{value.numerator}/{value.denominator}')
    source=tmp_path/'source.omega';source.write_text('\n'.join(program));out=tmp_path/'result'
    assert invoke(qemu,seed,source,out,writable=[tmp_path]).ok
    result=invoke(qemu,out)
    assert result.ok and result.sandboxed
    assert result.stdout.splitlines()==expected
    blob=out.read_bytes();assert blob[:4]==b'\x7fELF' and struct.unpack_from('<H',blob,18)[0]==243
    assert b'libgmp' not in blob and b'GLIBC' not in blob


@pytest.mark.parametrize('text,code',[('mostrar 1/0;',5),('mostrar (1+);',2),
    ('mostrar '+ '(' * 80 +'1'+')'*80+';',4),('mostrar 1; junk',2),('',2),
    ('mostrar '+str(2**5000)+';',4),('mostrar 1;\0junk',2),('mostrar1;',2)])
def test_native_fail_closed(seed,qemu,tmp_path,text,code):
    source=tmp_path/'source';source.write_text(text);out=tmp_path/'result'
    result=invoke(qemu,seed,source,out,writable=[tmp_path])
    if result.ok:result=invoke(qemu,out)
    assert result.returncode==code and not result.timed_out


def test_compiler_does_not_overwrite(seed,qemu,tmp_path):
    source=tmp_path/'source';source.write_text('mostrar 1;');out=tmp_path/'existing';out.write_text('keep')
    result=invoke(qemu,seed,source,out,writable=[tmp_path])
    assert result.returncode==3 and out.read_text()=='keep'


@pytest.mark.parametrize('length',[0,1,3,135,136,137,272,1024,16384])
def test_native_sha3_fips202(crypto,qemu,tmp_path,length):
    value=bytes((i*37)%256 for i in range(length));source=tmp_path/'input';source.write_bytes(value)
    result=invoke(qemu,crypto,'sha3',source)
    assert result.ok and result.stdout.strip()==hashlib.sha3_256(value).hexdigest()


def test_native_x25519_rfc7748_and_reference(crypto,qemu,tmp_path):
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey,X25519PublicKey
    rng=random.Random(25519)
    cases=[(bytes.fromhex('77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a'),b'\x09'+bytes(31))]
    cases += [(rng.randbytes(32),rng.randbytes(32)) for _ in range(12)]
    for secret,public in cases:
        source=tmp_path/'input';source.write_bytes(secret+public)
        result=invoke(qemu,crypto,'x25519',source)
        expected=X25519PrivateKey.from_private_bytes(secret).exchange(X25519PublicKey.from_public_bytes(public))
        assert result.ok and bytes.fromhex(result.stdout.strip())==expected
    source.write_bytes(bytes(64));assert invoke(qemu,crypto,'x25519',source).returncode==6


@pytest.mark.parametrize('length',[0,1,136,1024,16352])
def test_native_hmac_sha3(crypto,qemu,tmp_path,length):
    key=bytes(range(32));message=bytes(i%256 for i in range(length));source=tmp_path/'input';source.write_bytes(key+message)
    result=invoke(qemu,crypto,'hmac-sha3',source)
    assert result.ok and result.stdout.strip()==hmac.new(key,message,hashlib.sha3_256).hexdigest()


def test_assembler_rejects_invalid_and_reproducible():
    assert assemble('li a0,-9223372036854775808\nret')==assemble('li a0,-9223372036854775808\nret')
    for source in ('ld a0,2048(sp)','slli a0,a1,64','x:\nx:\nret','j 0x100000000','bogus a0,a1','li fake,1'):
        with pytest.raises(ValueError):assemble(source)
    with pytest.raises(ValueError):expression('__import__("os")',{})
