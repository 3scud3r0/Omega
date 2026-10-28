"""Native metadata extraction, independent parsing, proof admission, then build."""
import hashlib
import json
from pathlib import Path
import tempfile
from .syntax import tokens,lower
from .contracts import check_program


def is_refined(source):
    # Avoid changing ordinary source parsing, including Unicode identifiers.
    import re
    return bool(re.search(r'(?m)^\s*type\s+[A-Za-z_]',source))


def native_metadata(path):
    from omega_selfhost.driver import compiler
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    path=Path(path).absolute()
    with tempfile.TemporaryDirectory(prefix='omega-refinement-parser-') as temporary:
        target=Path(temporary)/'metadata.json'
        run([compiler(),path,target,'--refinement-ir'],readonly=[path],writable=[temporary],budget=COMPILER_BUDGET,check=True)
        metadata=json.loads(target.read_text())
    expected=lower(path.read_text())
    if metadata!=expected:raise ValueError('Native and independent refinement parsers disagree')
    return metadata


def build(source,destination,*,optimize=False,optimization='-O2',static=False):
    from omega_selfhost.driver import build as native_build
    source=Path(source).absolute();destination=Path(destination).absolute()
    metadata=native_metadata(source)
    proof=check_program(source.read_text())
    extra=[destination.with_suffix('.refine.json'),destination.with_suffix('.refine.lean'),destination.with_suffix('.lowered.omega')]
    if any(p.exists() for p in extra):raise ValueError('Refinement artifacts already exist')
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.omega-refined-',dir=destination.parent) as temporary:
        lowered=Path(temporary)/'lowered.omega';lowered.write_text(metadata['source'])
        result=native_build(lowered,destination,optimize=optimize,optimization=optimization,static=static)
    extra[2].write_text(metadata['source']);extra[1].write_text(proof['source'])
    record={k:v for k,v in proof.items() if k!='source'}
    record['binary_sha256']=hashlib.sha256(destination.read_bytes()).hexdigest()
    extra[0].write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    return {**result,'refinement':str(extra[0]),'refinement_obligations':proof['obligations']}


def audit(source,binary):
    source=Path(source);binary=Path(binary)
    record=json.loads(binary.with_suffix('.refine.json').read_text())
    proof=check_program(source.read_text())
    if record['source_sha256']!=proof['source_sha256'] or record['binary_sha256']!=hashlib.sha256(binary.read_bytes()).hexdigest():
        raise ValueError('Changed refined source or binary')
    if binary.with_suffix('.refine.lean').read_text()!=proof['source']:raise ValueError('Changed refinement proof')
    if record['metadata']!=proof['metadata']:raise ValueError('Changed refinement metadata')
    return {'valid':True,'obligations':proof['obligations'],'admission':proof['admission']}
