"""Hypothesis→Lean bridge. No proposer-supplied Lean source is ever executed."""
import hashlib
from omega_refine_check.syntax import render,tree,substitute,rational


def hypothesis_to_lemma(candidate,problem):
    from omega_refine_check.syntax import parse
    from omega_refine_check.lean import source,divisions
    names=list(problem['contracts'])
    premises=[substitute(parse(problem['contracts'][name]),{'self':('var',name)}) for name in names]
    node=tree(candidate)
    obligations=[('!=',d,('const','0')) for d in [*divisions(node),*divisions(problem['reference'])]]
    obligations.append(('==',node,problem['reference']))
    return source(names,premises,obligations,namespace='OmegaBicameral')


def prove(candidate,problem,directory):
    from omega.certified_proof import check
    directory.mkdir(parents=True,exist_ok=False)
    source,names=hypothesis_to_lemma(candidate,problem)
    (directory/'hypothesis.lean').write_text(source)
    admission=check(source,names)
    return {'source':source,'admission':admission,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),
            'candidate_expression':render(tree(candidate)),
            'scope':'all rational inputs inside declared intervals, not just the sampled grid'}


def emit_rv64(candidate,problem,directory):
    """Emit/run a closed rational specialization. The universal theorem covers
    the expression; general source→RV64 compiler correctness remains unproved.
    """
    from fractions import Fraction
    from omega_sovereign.native import build_seed
    from omega_sovereign.hardware import tool
    from omega_platform.sandbox import run
    from omega_platform.budget import COMPILER_BUDGET
    from omega_refine_check.syntax import evaluate
    directory.mkdir(parents=True,exist_ok=False)
    sample=problem['training'][0]['inputs'];env={k:rational(v) for k,v in sample.items()}
    closed=substitute(tree(candidate),{k:('const',str(v)) for k,v in env.items()})
    source=directory/'specialization.omega';source.write_text('mostrar '+render(closed)+';\n')
    seed=directory/'compiler.elf';manifest=build_seed(seed)
    binary=directory/'candidate.elf';qemu=tool('qemu-riscv64')
    outcome=run([qemu,seed,source,binary],readonly=[seed],writable=[directory],threads=True,budget=COMPILER_BUDGET,check=True)
    binary.chmod(0o500)
    executed=run([qemu,binary],readonly=[binary],threads=True,budget=COMPILER_BUDGET,check=True)
    expected=evaluate(tree(candidate),env)
    if Fraction(executed.stdout.strip())!=expected:raise ValueError('RV64 specialization differs from proved expression')
    return {'sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'expected':str(expected),'observed':executed.stdout.strip(),
            'sample':sample,'target':'rv64im-linux','compiler':manifest,'universal_compiler_equivalence_proved':False}


def zk_specialization(candidate,problem,engine):
    """Derive the expected statement using a caller-selected trusted compiler."""
    from omega_refine_check.syntax import evaluate
    from fractions import Fraction
    inputs=problem['training'][0]['inputs'];lines=[]
    for i,name in enumerate(problem['grid']):lines.append(f'var {name}=private({i});')
    source='funcao principal() { '+' '.join(lines)+' retornar '+render(candidate)+'; }'
    expected=evaluate(candidate,{k:Fraction(v) for k,v in inputs.items()})
    if expected.denominator!=1:raise ValueError('ZK u32 specialization requires an integer result')
    values=[Fraction(inputs[n]) for n in problem['grid']]
    if any(v.denominator!=1 for v in values):raise ValueError('ZK u32 specialization requires integer inputs')
    return engine.compile(source,expected.numerator)


def seal(candidate,problem,*,prover,verifier):
    """Independent u32 execution proof, distinct from the RV64 artifact."""
    from omega_zk.execution import Engine
    from fractions import Fraction
    check=Engine(verifier)
    program=zk_specialization(candidate,problem,check)
    values=[Fraction(problem['training'][0]['inputs'][n]) for n in problem['grid']]
    raw,metrics=Engine(prover).prove(program,[int(v) for v in values]+[0]*(8-len(values)))
    identity=check.image_id(program);verified=check.verify(raw,identity,program.journal)
    return raw,{'proving':metrics,'verification':verified,'image_id':identity,'journal':program.journal.decode(),
                'scope':'checked-u32 RV32IM specialization; not a proof of the RV64 binary'}
