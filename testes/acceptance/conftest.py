import hashlib
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[2]

@pytest.fixture
def typed_graph():
    from omega.sintaxe import analisar
    from omega.motor_v1 import CompiladorV1
    from omega.typed_ir import TypedIR
    return TypedIR.from_legacy(CompiladorV1().programa(analisar('parametro x=2;perda l=x*x;mostrar l;')))

@pytest.fixture
def signed_authority(tmp_path):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from omega_security.signatures import SignatureVerifier
    from omega_security.capabilities import CapabilityVerifier,Capability
    from omega_security.revocation import Revocations
    from omega_security.encoding import canonical
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    verifier=CapabilityVerifier(SignatureVerifier({'owner':public}),Revocations())
    def mint(actions,*,subject=None,expires=4102444800,root=None,principal='agent',id='cap-1'):
        claim={'id':id,'actions':list(actions),'expires':expires,'root':str(root or tmp_path),'principal':principal}
        if subject is not None:claim['subject']=subject
        payload=canonical(claim)
        return Capability(payload,private.sign(payload),'owner')
    return verifier,mint

class Events:
    def __init__(self):self.events=[]
    def append(self,event):self.events.append(event);return str(len(self.events))

@pytest.fixture
def events():return Events()

@pytest.fixture
def lean_case():
    def run(number):
        import re
        from omega_selfhost.proof import lake_binary
        from omega_platform.sandbox import trusted
        from omega_platform.budget import PROOF_BUDGET
        path=ROOT/f'testes/lean/OM{number:03d}.lean'
        outcome=trusted([str(lake_binary()),'env','lean',str(path)],cwd=ROOT/'formal/tensor',budget=PROOF_BUDGET,check=True)
        assert outcome.ok
        assert 'sorryAx' not in outcome.stdout
        names={26:'evaluation_sound',27:'finish_preserves_type',28:'progress',29:'add_zero_rule',
               30:'compose_correct',31:'native_compilation_result',32:'division_nonzero',
               33:'derivative_dual',34:'slope_at_zero',35:'transpose_twice'}
        expected='OmegaFormal.'+names[number]
        assert "'"+expected+"'" in outcome.stdout
        for name,body in re.findall(r"'([^']+)' depends on axioms: \[([^\]]*)\]",outcome.stdout):
            assert {value.strip() for value in body.split(',') if value.strip()}<={'propext','Classical.choice','Quot.sound'}
        return outcome
    return run

@pytest.fixture
def approval_authority():
    from dataclasses import asdict
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from omega_security.signatures import SignatureVerifier
    from omega_security.encoding import canonical
    from omega_tools.approvals import ApprovalGate,Approval
    private=Ed25519PrivateKey.generate()
    public=private.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
    signatures=SignatureVerifier({'reviewer':public})
    gate=ApprovalGate(signatures.record,['reviewer'])
    def issue(action,expires=4102444800):
        values={'actor':'reviewer','action_digest':gate.digest(action),'expires':expires}
        return Approval(**values,signature=private.sign(canonical(values)))
    return gate,issue

@pytest.fixture
def promotion_authority(tmp_path,events):
    import hashlib
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization
    from omega_security.signatures import SignatureVerifier
    from omega_security.encoding import canonical
    from omega_security.roles import Roles,Attestation
    from omega_evolution.component_registry import Component,ComponentRegistry
    from omega_evolution.proposals import Proposal
    from omega_evolution.promotion import PromotionGate
    from omega_platform.artifact_verifier import ArtifactVerifier
    private={actor:Ed25519PrivateKey.generate() for actor in ('checker','publisher')}
    signatures=SignatureVerifier({actor:key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw) for actor,key in private.items()})
    roles=Roles({'checker':['verifier'],'publisher':['promoter']},signatures.record)
    registry=ComponentRegistry([Component('planner',('omega_agent',),True,('unit','safety'))])
    artifacts=tmp_path/'artifacts';artifacts.mkdir();file=artifacts/'program';file.write_bytes(b'compiled')
    gate=PromotionGate(roles,registry,ArtifactVerifier(artifacts).promotion,events)
    def issue(version='v1',baseline='v0',baseline_sha='b'*64,expires=4102444800):
        proposal=Proposal('planner','smaller search',.1,1,'f'*64,'developer',baseline)
        manifest={'patch_sha256':proposal.patch_sha256,'baseline_version':baseline,'baseline_artifacts_sha256':baseline_sha,
                  'files':{'program':hashlib.sha256(file.read_bytes()).hexdigest()}}
        paths=['omega_agent/search.py'];checks={'unit':True,'safety':True}
        payload=gate.prepare(proposal,paths,checks,manifest,version=version)
        subject=hashlib.sha256(payload).hexdigest()
        def attest(actor):
            value={'actor':actor,'subject':subject,'decision':'approve','expires':expires}
            return Attestation(**value,signature=private[actor].sign(canonical(value)))
        return gate.approve(proposal,paths,checks,attest('checker'),attest('publisher'),manifest,version=version)
    return gate,issue,file
