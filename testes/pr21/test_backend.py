from pathlib import Path
import struct
import tempfile
import pytest
from hypothesis import given,settings,strategies as st,HealthCheck
from omega_sovereign.models import call,build
from omega_sovereign.hardware import tool
from omega_platform.sandbox import run
from omega_platform.budget import Budget


def execute(source,registers=None):
    request={'source':source}
    if registers is not None:request['registers']=registers
    artifact=call('backend',request)
    with tempfile.TemporaryDirectory() as temporary:
        path=Path(temporary)/'program';path.write_bytes(bytes.fromhex(artifact['elf_hex']));path.chmod(0o500)
        result=run([tool('qemu-riscv64'),path],readonly=[path],threads=True,budget=Budget(wall_seconds=5))
    return artifact,result


def signed(text):
    n=int(text,16);return n-2**64 if n>=2**63 else n


@given(st.lists(st.tuples(st.integers(0,30),st.integers(0,15)),min_size=1,max_size=30))
@settings(derandomize=True,database=None,max_examples=32,deadline=None)
def test_linear_scan_independent_interference_oracle(raw):
    intervals=[[i,start,start+length] for i,(start,length) in enumerate(raw)]
    result=call('regalloc',{'intervals':intervals,'registers':[9,18]})
    locations=result['locations']
    stack=[]
    for i,start,end in intervals:
        kind,place=locations[str(i)]
        if kind=='spill':stack.append(place);assert 32<=place<result['frame_bytes']
        else:
            assert place in (9,18)
            for j,other_start,other_end in intervals:
                if i!=j and max(start,other_start)<=min(end,other_end):
                    assert locations[str(j)]!=['reg',place]
    assert len(stack)==len(set(stack)) and result['frame_bytes']%16==0


@given(st.integers(-50,50),st.integers(1,30),st.integers(-9,9))
@settings(derandomize=True,database=None,max_examples=24,deadline=None)
def test_loop_spills_against_python_arithmetic(initial,n,delta):
    source=f'funcao principal() {{ var i=0; var x={initial}; enquanto(i<{n}) {{ x=x+{delta}; i=i+1; }} se(x<0) {{ retornar -x; }} senao {{ retornar x; }} }}'
    artifact,result=execute(source,[9,18])
    assert result.ok and signed(result.stdout)==abs(initial+n*delta),result.stderr
    assert artifact['allocation']['spills']>0


def test_sections_symbols_relocations_and_reproducibility():
    source='funcao principal() { var x=7; retornar x*6; }'
    a,result=execute(source)
    assert result.ok and signed(result.stdout)==42
    b=call('backend',{'source':source})
    assert a['elf_hex']==b['elf_hex']
    raw=bytes.fromhex(a['elf_hex']);assert raw[:4]==b'\x7fELF'
    assert struct.unpack_from('<H',raw,18)[0]==243
    offset=struct.unpack_from('<Q',raw,40)[0]
    sh=[struct.unpack_from('<IIQQQQIIQQ',raw,offset+i*64) for i in range(6)]
    strings=raw[sh[5][4]:sh[5][4]+sh[5][5]]
    names=[strings[s[0]:].split(b'\0',1)[0] for s in sh]
    assert names==[b'',b'.text',b'.rodata',b'.symtab',b'.strtab',b'.shstrtab']
    assert sh[3][6]==4 and sh[3][9]==24 and sh[1][2]==6 and sh[2][2]==2
    assert {r[0] for r in a['relocations']}=={'R_RISCV_CALL','R_RISCV_PCREL_HI20','R_RISCV_PCREL_LO12_I'}


@pytest.mark.parametrize('expr,expected',[
    ('-9223372036854775808',-2**63),('9223372036854775807',2**63-1),('(-7)%3',-1),
    ('6/3',2),('0-1',-1),('!(3<2)',1)])
def test_checked_i64_boundaries(expr,expected):
    _,result=execute('funcao principal() { retornar '+expr+'; }')
    assert result.ok and signed(result.stdout)==expected


@pytest.mark.parametrize('expr,code',[('9223372036854775807+1',70),('1/0',71),('3/2',72),('(-9223372036854775808)/-1',70)])
def test_numeric_faults_are_observable(expr,code):
    _,result=execute('funcao principal() { retornar '+expr+'; }')
    assert result.returncode==code and result.stdout==''


@pytest.mark.parametrize('source',[
 'funcao principal() { retornar [1,2]; }','funcao principal() { retornar unknown; }',
 'funcao principal() { retornar 1.5; }','funcao f() { retornar 1; }',
 'funcao principal() { parar; }','funcao principal() { retornar 1&&2; }'])
def test_unsupported_programs_rejected_before_emission(source):
    with pytest.raises(Exception):call('backend',{'source':source})


def test_cached_backend_never_invokes_cc_for_target(monkeypatch):
    build()
    import omega_sovereign.models as models
    def prohibited(*a,**k):raise AssertionError('External C compiler invoked for target')
    monkeypatch.setattr(models,'cc',prohibited)
    artifact,result=execute('funcao principal() { retornar 42; }')
    assert result.ok and artifact['external_linker']==0
