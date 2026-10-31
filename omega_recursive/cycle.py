"""Bounded propose/check/execute loop; stable activation has a separate authority."""
from pathlib import Path
import json

from omega_kernel.protocol import elf_bytes, sha256
from omega_kernel.runtime import execute
from omega_evolution.rollback import Versions
from .runtime import call, SOURCE_ROOT
from .certificates import (encoded, improvement_certificate, verify_improvement,
                           certify_claim, verify_claim, read_dag)


def inventory():
    """Read-only source anchors; candidate data never selects these paths."""
    paths = [SOURCE_ROOT/'omega_selfhost/compiler.omega']
    if not paths[0].is_file():
        from omega_selfhost.driver import PACKAGE
        paths = [PACKAGE/'compiler.omega']
    paths += sorted((SOURCE_ROOT/'omega_core').glob('*.omega'))
    out = {}
    total = 0
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise ValueError('Regular compiler/component inventory required')
        with path.open('rb') as stream:
            data = stream.read(256*1024+1)
        total += len(data)
        if len(data) > 256*1024 or total > 2*1024**2:
            raise ValueError('Component inventory quota')
        out[path.name] = sha256(data)
    return out


def prove_task(task):
    """Independently check the synthetic answer key against both partitions."""
    observations = task['observations']+task['holdout']
    certificate = certify_claim({'format':'omega-epistemic-claim-1',
                                 'dag':task['answer_key'],'observations':observations})
    result = verify_claim(certificate)
    return {'task_id':task['id'],'certificate':certificate,'verification':result}


def run_cycle(baseline, observations, *, rounds=4, architecture='x86_64'):
    if type(rounds) is not int or not 1 <= rounds <= 8:
        raise ValueError('Evolution rounds 1..8')
    read_dag(baseline)
    # Snapshot before all proposal generation, not references owned by callers.
    from omega_kernel.protocol import plain
    current = plain(baseline)
    observations = plain(observations)
    if type(observations) is not list or not 1 <= len(observations) <= 16:
        raise ValueError('Finite validation observations required')
    anchors = inventory()
    events = []
    stop = 'round-budget'
    for generation in range(rounds):
        proposal = call('improve',{'baseline':current,'rounds':4})
        if not proposal['strict_cost_improvement']:
            stop = 'no-strict-cost-improvement'
            break
        certificate = improvement_certificate(proposal['baseline'],proposal['candidate'])
        checked = verify_improvement(certificate)
        if not checked['accepted']:
            stop = 'kernel-rejected'
            break
        claim = certify_claim({'format':'omega-epistemic-claim-1','dag':proposal['candidate'],
                               'observations':observations})
        checked_points = verify_claim(claim)
        if not checked_points['accepted']:
            stop = 'counterexample'
            break
        binaries = []
        executions = []
        for dag in (proposal['baseline'],proposal['candidate']):
            lowered = call('dag',{'dag':dag,'lower_i64':1})
            binary = call('compile',{'source':lowered['source'],'architecture':architecture})
            outcomes = []
            for inputs,target in observations:
                if type(target) is not int or any(type(x) is not int for x in inputs):
                    raise ValueError('Direct ELF validation requires integer observation values')
                outcome = execute(binary,inputs)
                if not outcome['accepted'] or outcome['value'] != target:
                    raise ValueError('Baseline or candidate failed isolated ELF validation')
                outcomes.append(outcome)
            binaries.append({'source':lowered['source'],'elf_sha256':sha256(elf_bytes(binary))})
            executions.append(outcomes)
        previous = events[-1]['event_sha256'] if events else '0'*64
        event = {'generation':generation,'previous':previous,'proposal':proposal,
                 'certificate':certificate,'verification':checked,'point_certificate':claim,
                 'point_verification':checked_points,'binaries':binaries,'executions':executions}
        from omega_security.encoding import canonical
        event['event_sha256'] = sha256(canonical(event,max_bytes=4*1024**2,max_nodes=100000))
        events.append(event)
        # This updates the in-memory search frontier only. It grants no ability
        # to overwrite the compiler, kernel, installed binary or stable pointer.
        current = proposal['candidate']
    return {'format':'omega-bounded-evolution-1','inventory':anchors,'baseline':plain(baseline),
            'final_candidate':current,'generations':events,'stop_reason':stop,
            'stable_version_modified':False,'intelligence_gain_proved':False,
            'cost_scope':'unique rational DAG arithmetic nodes; no wall-time guarantee'}


def activate(versions, version, decision, healthcheck):
    """Use the existing authenticated verifier/promoter gate, never a boolean."""
    if type(versions) is not Versions:
        raise TypeError('Supervisor-owned Versions instance required')
    return versions.activate(version,decision,healthcheck)


def self_play(request, *, backend='cpu'):
    """Finite six-module loop. Answer keys never enter the learner request."""
    from .gpu import sieve
    rounds,tasks,seed = request.get('rounds',1),request.get('tasks',2),request.get('seed',0)
    if (type(rounds) is not int or not 1 <= rounds <= 4 or
            type(tasks) is not int or not 1 <= tasks <= 4 or
            type(seed) is not int or not 0 <= seed <= (1<<32)-1):
        raise ValueError('Self-play budget: 1..4 rounds/tasks, u32 seed')
    policy = [0]*6
    knowledge = set()
    records = []
    for epoch in range(rounds):
        generated = call('universe',{'domain':request.get('domain','affine'),'seed':(seed+epoch)%(1<<32),
                                     'tasks':tasks,'train':3,'heldout':2})
        for task in generated['tasks']:
            # No answer_key or other generator internals are passed to induction.
            learner = {'variables':task['variables'],'observations':task['observations'],
                       'holdout':task['holdout'],'constants':[-3,-2,-1,0,1,2,3],
                       'max_nodes':5,'max_candidates':1024,'beam_width':8,
                       'opcode_prior':policy[3:6]}
            learned = call('induce',learner)
            row = {'epoch':epoch,'task_id':task['id'],'learner':learned,'admitted':False}
            if learned['training_error']==0 and learned['holdout_valid'] and learned['holdout_error']==0:
                observed = task['observations']+task['holdout']
                sieved = sieve([learned['winner']],observed,backend=backend)
                row['sieve'] = sieved
                if sieved['admitted']:
                    cert = sieved['admitted'][0]['certificate']
                    row['quarantine'] = call('quarantine',{'messages':[cert['claim']]})
                    row['improvement'] = call('improve',{'baseline':learned['winner'],'rounds':4})
                    if row['improvement']['strict_cost_improvement']:
                        rewrite = improvement_certificate(learned['winner'],row['improvement']['candidate'])
                        row['rewrite_verification'] = verify_improvement(rewrite)
                        row['rewrite_certificate'] = rewrite
                    features = [0]*6
                    opcodes = ['const','var','neg','add','sub','mul']
                    for op,payload,children in learned['winner']['nodes']:
                        features[opcodes.index(op)] += 1
                    policy = call('dag',{'mode':'policy-update','weights':policy,
                                         'features':features,'reward':1,'rate':'1/16'})['weights']
                    identifier = sieved['admitted'][0]['verification']['claim_sha256']
                    row['novel_local_claim'] = identifier not in knowledge
                    knowledge.add(identifier)
                    row['admitted'] = True
            records.append(row)
    return {'format':'omega-finite-self-play-1','rounds':rounds,'records':records,
            'verified_claims':len(knowledge),'advisory_policy':policy,'stop_reason':'task-round-budget',
            'stable_version_modified':False,'network_actions':0,'scope':'finite synthetic tasks and observation certificates'}


def export_proposal(result, destination):
    destination = Path(destination)
    destination.mkdir(mode=0o700,parents=False,exist_ok=False)
    with (destination/'proposal.json').open('x') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    if result['generations']:
        source = result['generations'][-1]['binaries'][1]['source']
        with (destination/'candidate.omega').open('x') as stream:
            stream.write(source+'\n')
    return destination
