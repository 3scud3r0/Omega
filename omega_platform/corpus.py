"""Manifest-driven differential regression, with explicit failure categories."""
from __future__ import annotations
from dataclasses import asdict,dataclass
import hashlib
import json
from pathlib import Path
import re
import tempfile

from .budget import Budget
from .sandbox import ExecutionFailure,IsolationUnavailable,run


class CorpusError(ValueError):pass


@dataclass(frozen=True)
class Case:
    path: str
    language: str
    expected: str
    reference: str
    stderr_pattern: str=''
    stdout: str=''


@dataclass(frozen=True)
class CaseResult:
    path: str
    status: str
    stage: str
    detail: str


def load(path,root):
    data=json.loads(Path(path).read_text())
    if data.get('format')!='omega-corpus-1':raise CorpusError('Unsupported corpus manifest')
    cases=[Case(**c) for c in data['cases']]
    names=[c.path for c in cases]
    if len(names)!=len(set(names)):raise CorpusError('Duplicate example in manifest')
    actual={str(p.relative_to(root)) for p in (Path(root)/'exemplos').rglob('*.omega')}
    if set(names)!=actual:
        raise CorpusError(f'Corpus coverage mismatch; missing={sorted(actual-set(names))}; stale={sorted(set(names)-actual)}')
    for c in cases:
        p=(Path(root)/c.path).resolve()
        if not p.is_relative_to(Path(root).resolve()):raise CorpusError('Example escapes repository')
        if c.language not in ('tensor','procedural') or c.expected not in ('accept','compile_reject','run_reject'):
            raise CorpusError('Invalid case classification')
        if c.reference not in ('v1','classic','bootstrap','rejection'):raise CorpusError('Reference required')
        if c.expected!='accept' and not c.stderr_pattern:raise CorpusError('Negative cases need a precise rejection pattern')
    return cases


def _serial(value):
    if isinstance(value,(tuple,list)):return [_serial(x) for x in value]
    return str(value)


def compare_reference(path,result,reference):
    from omega.sintaxe import analisar
    commands=analisar(path.read_text())
    if reference=='v1':
        from omega.motor_v1 import CompiladorV1,MaquinaV1,num
        from omega_selfhost.driver import compile_ir
        ir=CompiladorV1().programa(commands)
        if compile_ir(path)!=ir:raise AssertionError('Native IR differs from the reference')
        ref=MaquinaV1(ir).executar()
        if result['outputs']!=ref.saidas:raise AssertionError('Native output differs from reference')
        if result['state']!={k:num(v) for k,v in ref.estado.items()}:
            raise AssertionError('Native state differs from reference')
    elif reference=='classic':
        from omega.execucao import MaquinaOmega
        ref=MaquinaOmega().executar(commands)
        theorems={c.nome for c in commands if c.tipo=='teorema'}
        names={c.nome for c in commands if c.tipo=='mostrar'}-theorems
        observed=lambda lines:[line for line in lines if any(line.startswith(n+' = ') for n in names)]
        if observed(result['outputs'])!=observed(ref.saidas):
            raise AssertionError('Observable scalar/tensor values differ from the classic reference')
        def coordinates(tree):
            if isinstance(tree,(tuple,list)):return [coordinates(x) for x in tree]
            return str(ref.parametros[tree])
        for name,value in result['state'].items():
            expected=coordinates(ref.parametros_tensoriais[name]) if name in ref.parametros_tensoriais else str(ref.parametros[name])
            if value!=expected:raise AssertionError('Classic parameter state differs: '+name)


def evaluate(case:Case,root:Path):
    from omega_selfhost import driver
    source=root/case.path
    stage='compile'
    try:
        with tempfile.TemporaryDirectory(prefix='omega-corpus-') as tmp:
            binary=Path(tmp)/'program'
            driver.build(source,binary)
            if case.expected=='compile_reject':
                return CaseResult(case.path,'failed',stage,'Compiler accepted a designated invalid example')
            stage='execute'
            execution=run([binary],check=True)
            if case.expected=='run_reject':
                return CaseResult(case.path,'failed',stage,'Runtime accepted a designated invalid example')
            stage='verify'
            if case.language=='procedural':
                if execution.stdout!=case.stdout:raise AssertionError('Procedural stdout differs from its contract')
                from omega_selfhost.bootstrap import compile_source
                if binary.with_suffix('.c').read_text()!=compile_source(source.read_text()):
                    raise AssertionError('Self-hosted procedural lowering differs from stage zero')
            else:
                result=json.loads(execution.stdout)
                driver.verify_result(result)
                compare_reference(source,result,case.reference)
        return CaseResult(case.path,'passed','complete','Native, verifier and reference agree')
    except IsolationUnavailable as exc:
        return CaseResult(case.path,'infrastructure',stage,str(exc))
    except ExecutionFailure as exc:
        out=exc.outcome
        rejected=(case.expected=='compile_reject' and stage=='compile') or (case.expected=='run_reject' and stage=='execute')
        if rejected and out.returncode==1 and not out.timed_out and re.search(case.stderr_pattern,out.stderr):
            return CaseResult(case.path,'expected_rejection',stage,out.stderr.strip())
        status='infrastructure' if out.timed_out else 'failed'
        return CaseResult(case.path,status,stage,str(exc))
    except (FileNotFoundError,PermissionError) as exc:
        return CaseResult(case.path,'infrastructure',stage,str(exc))
    except (AssertionError,RuntimeError,ValueError,KeyError,TypeError) as exc:
        return CaseResult(case.path,'failed',stage,str(exc))


def regression(root,manifest=None):
    root=Path(root).resolve();manifest=Path(manifest or root/'testes/corpus.json')
    cases=load(manifest,root)
    results=[evaluate(c,root) for c in cases]
    expected=sum(c.expected=='accept' for c in cases)
    passed=sum(r.status=='passed' for r in results)
    rejected=sum(r.status=='expected_rejection' for r in results)
    failed=[asdict(r) for r in results if r.status in ('failed','infrastructure')]
    return {'format':'omega-corpus-report-1','expected_positive':expected,
            'passed_positive':passed,'expected_negative':len(cases)-expected,
            'observed_negative':rejected,'count_matches':passed==expected and rejected==len(cases)-expected,
            'infrastructure_failures':sum(r.status=='infrastructure' for r in results),
            'example_failures':sum(r.status=='failed' for r in results),
            'valid':not failed and passed==expected and rejected==len(cases)-expected,
            'manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),
            'results':[asdict(r) for r in results]}
