"""Pinned supervisor authority: reconstruct and check contracts before signing.

Native clients verify this authority's attestation; they do not implement a Lean
kernel. Agent keys are separate from this issuer. No arbitrary Lean is accepted.
"""
from fractions import Fraction as Q
import hashlib
import json
import os
from pathlib import Path
import time
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from omega_refine_check.lean import prove
from omega_refine_check.syntax import parse
from omega_self_evolve_v2.bridge_lean_filter import _compiled
from .codec import canonical,subject

GENESIS='0'*64


def create_key(path):
    path=Path(path);key=Ed25519PrivateKey.generate()
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as stream:stream.write(key.private_bytes_raw());stream.flush();os.fsync(stream.fileno())
    return key


def load_key(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as stream:
        st=os.fstat(stream.fileno())
        import stat
        if not stat.S_ISREG(st.st_mode) or st.st_mode&0o077 or st.st_size!=32:raise ValueError('Private raw Ed25519 seed must be a 0600 regular file')
        return Ed25519PrivateKey.from_private_bytes(stream.read())


def public_hex(key):return key.public_key().public_bytes_raw().hex()


def check_bounds(document,bounds):
    if type(bounds) is not dict or len(bounds)>128:raise ValueError('Bounded named rational constraints required')
    goals=[]
    for path,pair in bounds.items():
        value=document
        if path:
            for component in path.split('.'):
                if type(value) is not dict or component not in value:raise ValueError('Contract path absent')
                value=value[component]
        if type(value) is not int and not isinstance(value,Q):raise ValueError('Exact rational contract value required')
        if type(pair) not in (list,tuple) or len(pair)!=2:raise ValueError('Interval pair required')
        lo,hi=map(Q,pair);q=Q(value)
        if not lo<=q<=hi:raise ValueError("Document violates the exact rational policy bounds")
        if any(max(abs(x.numerator).bit_length(),x.denominator.bit_length())>4096 for x in (q,lo,hi)):raise ValueError('Proof rational budget exceeded')
        goals.extend([parse(f'({q}) >= ({lo})'),parse(f'({q}) <= ({hi})')])
    return goals


class Authority:
    def __init__(self,key):self.key=key
    @property
    def public(self):return public_hex(self.key)
    def _issue(self,purpose,payload,policy,goals,directory,*,ttl=300):
        if type(policy) is not str or not policy or len(policy)>128 or type(ttl) is not int or not 1<=ttl<=3600:raise ValueError('Named policy and bounded expiry required')
        digest=subject(payload);proof=prove([],[],goals or [parse('1 == 1')])
        # This literal ties the compiled object to the exact authenticated payload.
        proof['source']+='\nnamespace OmegaNativePermit\ntheorem subject : ("'+digest+'" : String) = "'+digest+'" := rfl\n#print axioms subject\nend OmegaNativePermit\n'
        names=proof['admission']['theorems']+['OmegaNativePermit.subject']
        root=Path(directory);root.mkdir(parents=True,exist_ok=False)
        obj=_compiled(proof['source'],names,root)
        claims={'format':'omega-native-permit-1','purpose':purpose,'subject':digest,'policy':policy,'expires':int(time.time())+ttl,
                'lean_source_sha256':hashlib.sha256(proof['source'].encode()).hexdigest(),'olean_sha256':hashlib.sha256(obj.read_bytes()).hexdigest()}
        raw=json.dumps(claims,separators=(',',':'),ensure_ascii=False)
        token={'claims':raw,'signature':self.key.sign(raw.encode()).hex()}
        (root/'permit.json').write_text(json.dumps(token,indent=2)+'\n')
        return token
    def database(self,*,key,document,head=GENESIS,policy,bounds,directory):
        if type(key) is not str or not 0<len(key.encode())<=1024:raise ValueError('Nonempty key of at most 1024 bytes required')
        if type(head) is not str or len(head)!=64 or any(c not in '0123456789abcdef' for c in head):raise ValueError('Trusted head SHA256 required')
        encoded=canonical(document)
        payload={'key':key,'document':encoded,'expected_head':head,'policy':policy}
        goals=[parse(f'{len(key.encode())} > 0'),*check_bounds(document,bounds)]
        return encoded,self._issue('db.insert',payload,policy,goals,directory)
    def message(self,message,*,policy,bounds,directory):
        if set(message)!={'sender','recipient','channel','nonce','payload'}:raise ValueError('Explicit proof-carrying message schema required')
        for name in ('sender','recipient','channel','nonce'):
            if type(message[name]) is not str or not 0<len(message[name].encode())<=128:raise ValueError('Bounded message identity required')
        document=__import__('omega_native.codec',fromlist=['decode']).decode(message['payload'])
        return self._issue('message',message,policy,check_bounds(document,bounds),directory)
    def packages(self,lock,*,policy,directory):
        if set(lock)!={'format','packages'} or lock['format']!='omega-native-lock-1' or type(lock['packages']) is not list or len(lock['packages'])>64:raise ValueError('Bounded offline lock required')
        packages=lock['packages'];names=[p['name'] for p in packages]
        if len(set(names))!=len(names):raise ValueError('Duplicate package')
        order=[];visiting=set()
        def visit(name):
            if name in order:return
            if name in visiting:raise ValueError('Dependency cycle')
            if name not in names:raise ValueError('Missing locked dependency')
            visiting.add(name)
            for dep in packages[names.index(name)]['dependencies']:visit(dep)
            visiting.remove(name);order.append(name)
        for name in names:visit(name)
        goals=[parse(f'{order.index(dep)} < {order.index(p["name"])}') for p in packages for dep in p['dependencies']]
        return self._issue('package.lock',lock,policy,goals,directory)
