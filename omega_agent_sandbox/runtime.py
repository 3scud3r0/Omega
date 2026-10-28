"""Admission and compilation finish before the registered external effect runs."""
from pathlib import Path
import tempfile
from types import MappingProxyType
from .proofs import verify
from .policy import Policy


class Runtime:
    def __init__(self,policy,ledger,*,public_key,capability_verifier,principal,adapters):
        if type(policy) is not Policy:raise TypeError('Host-owned immutable policy required')
        if not hasattr(capability_verifier,'require'):raise TypeError('Independent signed capability verifier required')
        self.policy=policy;self.ledger=ledger;self.public_key=public_key
        self.verifier=capability_verifier;self.principal=principal;self.adapters=MappingProxyType(dict(adapters))
    def dispatch(self,bundle,capability):
        domain=self.policy.data['id'];snapshot=self.ledger.snapshot(domain)
        statement=verify(self.policy,snapshot,bundle,public_key=self.public_key)
        subject=bundle['subject'];effect=statement['effect']
        if effect not in self.adapters:raise PermissionError('No host adapter is registered for this effect')
        self.verifier.require(capability,self.principal,'agent.dispatch.'+effect,subject=subject)
        # Never execute proposer-supplied code: the proof renderer already
        # reconstructed this exact pure arithmetic program from policy data.
        from omega_selfhost.driver import build,run
        with tempfile.TemporaryDirectory(prefix='omega-proof-action-') as temporary:
            root=Path(temporary);source=root/'action.omega';source.write_text(bundle['program'])
            build(source,root/'action');result,admission=run(root/'action')
            for i,(name,value) in enumerate(statement['post_state']['values'].items()):
                from fractions import Fraction
                if Fraction(result['values'][f'after_{i}'])!=Fraction(value):raise ValueError('Native action disagrees with its proved poststate')
        # Recheck authorization after proof/build latency and reserve the state
        # transactionally. No adapter has run before these gates.
        self.verifier.require(capability,self.principal,'agent.dispatch.'+effect,subject=subject)
        self.ledger.claim(domain,subject,statement)
        try:
            receipt=self.adapters[effect].dispatch(statement,idempotency_key=subject)
            if type(receipt) is not dict or receipt.get('acknowledged') is not True or receipt.get('idempotency_key')!=subject:raise ValueError('External adapter did not acknowledge this exact action')
            self.ledger.finish(domain,subject,statement,receipt)
        except BaseException as error:
            self.ledger.uncertain(subject,error);raise
        return {'valid':True,'subject':subject,'post_state':statement['post_state'],'native_admission':admission,'receipt':receipt}
