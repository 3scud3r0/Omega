from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

import pytest

from omega.modules import link,verify_manifest
from omega.typesystem import TypeCheckError
from omega_selfhost import driver
from omega_platform.sandbox import run
from omega_platform.manifest import verify


def project(root):
    (root/'lib').mkdir()
    (root/'lib'/'base.omega').write_text('modulo base;exportar dobro;funcao dobro(x){retornar x*2;}')
    (root/'lib'/'math.omega').write_text('''importar "base.omega" como base;
exportar calcular;
funcao private(x){retornar x+1;}
funcao calcular(x){retornar private(base::dobro(x));}''')
    (root/'main.omega').write_text('''importar "lib/math.omega" como math;
funcao private(x){retornar x+100;}
funcao principal(){
var math="math::calcular(3)";
print(math);print(math::calcular(3));print(private(1));retornar 0;
}''')
    return root/'main.omega'


def test_end_to_end_qualified_names_local_shadowing_and_private_functions(tmp_path):
    entry=project(tmp_path);binary=tmp_path/'app'
    report=driver.build_module(entry,binary,root=tmp_path)
    assert run([binary],check=True).stdout=='math::calcular(3)\n7\n101\n'
    linked=Path(report['linked_source']).read_text()
    assert 'math::calcular(3)' in linked  # a string literal is preserved
    assert 'importar' not in linked and len(report['types']['functions'])>=4
    record=json.loads(binary.with_suffix('.build.json').read_text())
    assert verify(record,tmp_path)
    assert record['source_sha256']==hashlib.sha256(linked.encode()).hexdigest()
    assert verify_manifest(record['module_graph'],tmp_path)
    changed=deepcopy(record);changed['module_graph']['linked_sha256']='0'*64
    with pytest.raises(ValueError):verify(changed,tmp_path)


def test_dependency_order_bytes_and_provenance_are_deterministic(tmp_path):
    entry=project(tmp_path);first=link(entry,tmp_path);second=link('main.omega',tmp_path)
    assert first==second
    assert first.manifest()['order']==['lib/base.omega','lib/math.omega','main.omega']
    manifest=first.manifest();manifest['entry']='other.omega'
    assert first.manifest()['entry']=='main.omega'
    (tmp_path/'lib/base.omega').write_text('# harmless comment\n'+(tmp_path/'lib/base.omega').read_text())
    third=link(entry,tmp_path)
    assert first.source==third.source and first.manifest()!=third.manifest()
    with pytest.raises(TypeCheckError):verify_manifest(first.manifest(),tmp_path)


@pytest.mark.parametrize('source,libraries',[
    ('importar "a.omega" como a;funcao principal(){retornar a::hidden(0);}',{'a.omega':'funcao hidden(x){retornar x;}'}),
    ('importar "a.omega" como a;funcao principal(){retornar missing::f(0);}',{'a.omega':'exportar f;funcao f(x){retornar x;}'}),
    ('importar "a.omega" como a;importar "b.omega" como a;funcao principal(){retornar 0;}',{}),
    ('exportar unknown;funcao principal(){retornar 0;}',{}),
    ('exportar principal,principal;funcao principal(){retornar 0;}',{}),
    ('funcao principal(){retornar unknown(1);}',{}),
    ('funcao principal(){retornar missing::value;}',{}),
    ('importar "a.omega" como a;funcao principal(){retornar 0;}',{'a.omega':'funcao principal(){retornar 0;}'}),
    ('importar "a.omega" como a;funcao principal(){retornar 0;}',{'a.omega':'exportar f;funcao f(x){retornar "x"-x;}'}),
    ('funcao f(){retornar 0;}',{}),
])
def test_invalid_resolution_interfaces_and_types_rejected(tmp_path,source,libraries):
    for name,text in libraries.items():(tmp_path/name).write_text(text)
    (tmp_path/'main.omega').write_text(source)
    with pytest.raises(TypeCheckError):link('main.omega',tmp_path)


def test_cycle_has_reproducible_dependency_path(tmp_path):
    (tmp_path/'a.omega').write_text('importar "b.omega" como b;funcao principal(){retornar 0;}')
    (tmp_path/'b.omega').write_text('importar "a.omega" como a;funcao f(){retornar 0;}')
    with pytest.raises(TypeCheckError,match='a.omega -> b.omega -> a.omega'):link('a.omega',tmp_path)


@pytest.mark.parametrize('target',['../outside.omega','/etc/passwd','https://example.org/unsafe.omega','a\\b.omega'])
def test_paths_never_escape_explicit_root(tmp_path,target):
    (tmp_path/'main.omega').write_text('importar '+json.dumps(target)+' como x;funcao principal(){retornar 0;}')
    with pytest.raises(TypeCheckError):link('main.omega',tmp_path)


@pytest.mark.parametrize('kind',['file_symlink','directory_symlink','fifo'])
def test_symlinks_and_non_regular_files_rejected_without_blocking(tmp_path,kind):
    root=tmp_path/'root';root.mkdir();other=tmp_path/'outside';other.mkdir()
    (other/'lib.omega').write_text('exportar f;funcao f(){retornar 0;}')
    if kind=='file_symlink':(root/'lib.omega').symlink_to(other/'lib.omega');target='lib.omega'
    elif kind=='directory_symlink':(root/'sub').symlink_to(other,target_is_directory=True);target='sub/lib.omega'
    else:os.mkfifo(root/'lib.omega');target='lib.omega'
    (root/'main.omega').write_text('importar "'+target+'" como x;funcao principal(){retornar 0;}')
    with pytest.raises(TypeCheckError):link('main.omega',root)


def test_symlink_swap_at_final_open_cannot_read_outside_root(tmp_path,monkeypatch):
    from omega import modules
    root=tmp_path/'root';root.mkdir()
    outside=tmp_path/'outside.omega';outside.write_text('exportar secret;funcao secret(){retornar 42;}')
    library=root/'lib.omega';library.write_text('exportar f;funcao f(){retornar 0;}')
    (root/'main.omega').write_text('importar "lib.omega" como l;funcao principal(){retornar 0;}')
    original=modules.os.open
    def swap(path,*args,**kwargs):
        if str(path)=='lib.omega':library.unlink();library.symlink_to(outside)
        return original(path,*args,**kwargs)
    monkeypatch.setattr(modules.os,'open',swap)
    with pytest.raises(TypeCheckError,match='within root'):link('main.omega',root)


def test_placeholder_cannot_capture_user_function_and_relative_parent_stays_inside_root(tmp_path):
    (tmp_path/'sub').mkdir();(tmp_path/'base.omega').write_text('exportar f;funcao f(x){retornar x;}')
    (tmp_path/'sub/main.omega').write_text('''importar "../base.omega" como base;
funcao __omega_import_call_0(x){retornar x+1;}
funcao principal(){retornar base::f(__omega_import_call_0(0));}''')
    linked=link('sub/main.omega',tmp_path)
    assert len(linked.manifest()['origins'])==3
    assert linked.manifest()['modules']['sub/main.omega']['imports']=={'base':'base.omega'}


def test_module_count_source_limits_and_output_collisions(tmp_path):
    for i in range(65):
        (tmp_path/f'm{i}.omega').write_text((f'importar "m{i+1}.omega" como next;' if i<64 else '')+'funcao f(){retornar 0;}')
    with pytest.raises(TypeCheckError,match='count budget'):link('m0.omega',tmp_path)
    (tmp_path/'huge.omega').write_text('#'+'x'*(256*1024))
    with pytest.raises(TypeCheckError,match='source budget'):link('huge.omega',tmp_path)
    path=tmp_path/'plain.omega';path.write_text('funcao principal(){retornar 0;}')
    with pytest.raises(ValueError,match='distinct'):driver.build(path,tmp_path/'app.c')
    assert not (tmp_path/'app.c').exists()


def test_cli_link_and_build_provenance_and_no_overwrites(tmp_path,capsys):
    from omega.cli import principal
    entry=project(tmp_path);linked=tmp_path/'linked.omega';binary=tmp_path/'program'
    assert principal(['module-link',str(entry),'--raiz',str(tmp_path),'--saida',str(linked)])==0
    result=json.loads(capsys.readouterr().out)
    assert hashlib.sha256(linked.read_bytes()).hexdigest()==result['sha256']
    assert principal(['module-build',str(entry),'--raiz',str(tmp_path),'--saida',str(binary)])==0
    report=json.loads(capsys.readouterr().out)
    assert report['modules']==3 and run([binary],check=True).stdout.endswith('7\n101\n')
    before=binary.read_bytes()
    assert principal(['module-build',str(entry),'--raiz',str(tmp_path),'--saida',str(binary)])==1
    assert json.loads(capsys.readouterr().err)['ok'] is False and binary.read_bytes()==before
