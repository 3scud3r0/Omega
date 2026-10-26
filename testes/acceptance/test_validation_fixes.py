"""Regression coverage for exact trace inputs and nested ASan resource limits."""
from fractions import Fraction
import json
import sys
import pytest
from omega.trace import evaluate
from omega.motor_v1 import CompiladorV1
from omega.sintaxe import analisar
from omega.typed_ir import TypedIR
from omega_platform.budget import Budget
from omega_platform.sandbox import trusted,ASAN_VIRTUAL_BYTES


@pytest.mark.parametrize('value',[3,Fraction(3),Fraction(1,3)])
def test_trace_accepts_exact_scalars_without_mutating_input(typed_graph,value):
    state={'x':value};frames=evaluate(typed_graph,state)
    assert frames[-1].value==str(Fraction(value)**2)
    assert state=={'x':value} and type(state['x']) is type(value)


def test_trace_normalizes_list_vectors_and_checks_shape_before_copying():
    ir=TypedIR.from_legacy(CompiladorV1().programa(analisar('parametro vetor w=[1,2];perda l=dot(w,w);mostrar l;')))
    state={'w':[3,4]}
    assert evaluate(ir,state)[-1].value=='25'
    assert state=={'w':[3,4]}
    with pytest.raises(ValueError):evaluate(ir,{'w':[3,4,5]})


@pytest.mark.parametrize('value',[True,3.0,'3',float('nan')])
def test_trace_does_not_silently_coerce_inexact_or_ambiguous_scalars(typed_graph,value):
    with pytest.raises(TypeError):evaluate(typed_graph,{'x':value})


@pytest.mark.parametrize('diagnostics',[False,True])
def test_only_explicit_trusted_diagnostic_profile_can_raise_as_limit(diagnostics):
    program='''import json,resource
before=resource.getrlimit(resource.RLIMIT_AS)
raised=False
try:
    resource.setrlimit(resource.RLIMIT_AS,(32*1024**4,32*1024**4))
    raised=True
except (ValueError,OSError):pass
print(json.dumps({'before':before,'after':resource.getrlimit(resource.RLIMIT_AS),'raised':raised}))
'''
    budget=Budget(memory_bytes=64*1024**2,cpu_seconds=2,wall_seconds=10,processes=1024)
    result=trusted([sys.executable,'-c',program],budget=budget,check=True,instrumented_children=diagnostics)
    observed=json.loads(result.stdout)
    assert observed['before'][0]==budget.memory_bytes
    assert observed['before'][1]==(ASAN_VIRTUAL_BYTES if diagnostics else budget.memory_bytes)
    assert observed['raised'] is diagnostics
    assert observed['after']==([ASAN_VIRTUAL_BYTES]*2 if diagnostics else [budget.memory_bytes]*2)


@pytest.mark.parametrize('extra',['tools','dev'])
def test_cpu_lock_satisfies_optional_validation_dependencies(extra):
    from pathlib import Path
    import tomllib
    from packaging.requirements import Requirement
    from packaging.utils import canonicalize_name
    root=Path(__file__).resolve().parents[2]
    requirements={}
    for line in (root/'requirements/cpu-py312.lock').read_text().splitlines():
        if not line.strip() or line.lstrip().startswith('#'):continue
        requirement=Requirement(line)
        pins=[specifier.version for specifier in requirement.specifier if specifier.operator=='==']
        assert len(pins)==1
        requirements[canonicalize_name(requirement.name)]=pins[0]
    project=tomllib.loads((root/'pyproject.toml').read_text())
    for raw in project['project']['optional-dependencies'][extra]:
        requirement=Requirement(raw)
        assert requirements[canonicalize_name(requirement.name)] in requirement.specifier
