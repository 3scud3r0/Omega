import json
from pathlib import Path
import runpy
import subprocess
import sys

import pytest

ROOT=Path(__file__).resolve().parents[2]
FILE=ROOT/'omega/omega_3_monolith.py'


@pytest.fixture
def bundle():
    return runpy.run_path(str(FILE))


def test_bundle_contains_real_sources_and_reports_pending_acceptance(bundle):
    report=bundle['verify']()
    assert report['embedded_code_lines']>=10000
    assert len(FILE.read_text().splitlines())>=10000
    assert report['all_150_tasks_accepted'] is False
    tasks=bundle['coverage']()
    assert [t['id'] for t in tasks]==[f'OM-{i:03}' for i in range(18,151)]
    assert not any(t['accepted'] for t in tasks)


def test_every_extracted_byte_matches_its_declared_source(bundle,tmp_path):
    root=bundle['extract'](tmp_path/'source')
    for name,data in bundle['validated_sources']().items():
        assert (root/name).read_bytes()==data
        if name!='omega/monolith_components.py':
            assert (ROOT/name).read_bytes()==data
    assert (root/'omega_selfhost/runtime.h').is_file()
    assert (root/'scripts/monolith-components.py.txt').is_file()


def test_existing_files_directories_and_symlinks_are_never_replaced(bundle,tmp_path):
    existing=tmp_path/'existing';existing.mkdir();(existing/'keep').write_text('preserve')
    alias=tmp_path/'alias';alias.symlink_to(existing,target_is_directory=True)
    file=tmp_path/'file';file.write_text('preserve')
    for target in (existing,alias,file):
        with pytest.raises(FileExistsError):bundle['extract'](target)
    assert (existing/'keep').read_text()==file.read_text()=='preserve'


@pytest.mark.parametrize('name',['../outside','/absolute','a/../../outside','a\\outside','.git/config','a/./b',42])
def test_unsafe_names_rejected_before_writes(bundle,tmp_path,name):
    scope=bundle['validated_sources'].__globals__
    scope['SOURCES']=((name,'payload'),)
    with pytest.raises(ValueError):bundle['extract'](tmp_path/'target')
    assert not (tmp_path/'target').exists()


def test_hash_tampering_rejected_before_writes(bundle,tmp_path):
    scope=bundle['validated_sources'].__globals__
    original=scope['SOURCES'];name,content=original[0]
    scope['SOURCES']=((name,content+'tampered'),*original[1:])
    with pytest.raises(ValueError,match='integrity'):bundle['extract'](tmp_path/'target')
    assert not (tmp_path/'target').exists()


def test_atomic_publication_does_not_replace_a_concurrent_destination(bundle,tmp_path):
    scope=bundle['extract'].__globals__;publish=scope['_publish']
    target=tmp_path/'target'
    def race(stage,destination):
        target.mkdir();(target/'preserve').write_text('concurrent')
        publish(stage,destination)
    scope['_publish']=race
    with pytest.raises(FileExistsError):bundle['extract'](target)
    assert (target/'preserve').read_text()=='concurrent'
    assert not list(tmp_path.glob('.omega-source-*'))


def test_standalone_entry_points_use_embedded_application(tmp_path):
    for arguments in (['verify'],['self-test'],['omega','--versao']):
        process=subprocess.run([sys.executable,str(FILE),*arguments],cwd=tmp_path,capture_output=True,text=True,timeout=30)
        assert process.returncode==0,process.stderr
        if arguments==['verify']:assert json.loads(process.stdout)['embedded_code_lines']>=10000
        if arguments[0]=='omega':assert process.stdout.strip()=='Ômega 2.0.0'


def test_generator_is_reproducible():
    process=subprocess.run([sys.executable,str(ROOT/'scripts/build-monolith.py'),'--check'],cwd=ROOT,capture_output=True,text=True,timeout=30)
    assert process.returncode==0,process.stdout+process.stderr
