import json,subprocess
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from omega_self_evolve_v2.bridge_lean_filter import prove_candidate
from omega_self_evolve_v2.cycle import evolve_from_receipt,publish_generation
from omega_self_mutate.activation import load_active


@pytest.fixture(scope='module')
def generation(tmp_path_factory):
    root=tmp_path_factory.mktemp('hyper-evolution');key=Ed25519PrivateKey.generate()
    spec={'variables':{'x':'true'},'ensures':'result==(x*2)-x',
          'examples':[{'inputs':{'x':str(x)},'output':str(x)} for x in (-2,0,2)]}
    receipt=prove_candidate(spec,{'ast':['var','x']},root/'tier2',signing_key=key)
    result=evolve_from_receipt('(x*2)-x',receipt,root/'tier2',root/'generation',public_key=key.public_key())
    return root,result,key,receipt


def repository(root):
    from omega_selfhost.driver import PACKAGE
    (root/'omega_selfhost').mkdir(parents=True)
    (root/'omega_selfhost/compiler.omega').write_bytes((PACKAGE/'compiler.omega').read_bytes())
    subprocess.run(['git','init',str(root)],check=True,capture_output=True)
    subprocess.run(['git','-C',str(root),'config','user.name','Hyper Test'],check=True)
    subprocess.run(['git','-C',str(root),'config','user.email','hyper-test@example.invalid'],check=True)
    (root/'.gitignore').write_text('build/\n')
    subprocess.run(['git','-C',str(root),'add','.'],check=True)
    subprocess.run(['git','-C',str(root),'commit','-m','baseline'],check=True,capture_output=True)


def test_receipt_to_four_stage_compiler_install_and_scoped_commit(generation,tmp_path):
    root,result,key,receipt=generation;repository(tmp_path);calls=[]
    epoch=publish_generation(root/'generation',repo=tmp_path,replace_source=True,commit=True,restart_runtime=lambda value:calls.append(value['binary_sha256']))
    assert epoch['git_commit'] and calls and result['bootstrap']['fixed_point']
    assert load_active(selection_root=tmp_path/'build/selfhost')
    assert 'synth_match' in (tmp_path/'omega_selfhost/compiler.omega').read_text()
    changed=subprocess.check_output(['git','-C',str(tmp_path),'show','--pretty=','--name-only','HEAD'],text=True).splitlines()
    assert 'omega_selfhost/compiler.omega' in changed
    assert all(name=='omega_selfhost/compiler.omega' or name.startswith('omega_selfhost/evolved/') for name in changed)


def test_runtime_restart_failure_rolls_back_source_and_selector(generation,tmp_path):
    root,*_=generation;repository(tmp_path);path=tmp_path/'omega_selfhost/compiler.omega';original=path.read_bytes()
    def fail(_):raise OSError('Supervisor restart failed')
    with pytest.raises(OSError):publish_generation(root/'generation',repo=tmp_path,replace_source=True,restart_runtime=fail)
    assert path.read_bytes()==original and not (tmp_path/'build/selfhost/active.json').exists()


def test_automatic_commit_refuses_user_changes(generation,tmp_path):
    root,*_=generation;repository(tmp_path);(tmp_path/'user.txt').write_text('preserve me')
    with pytest.raises(ValueError,match='clean'):publish_generation(root/'generation',repo=tmp_path,replace_source=True,commit=True)
    assert (tmp_path/'user.txt').read_text()=='preserve me'
