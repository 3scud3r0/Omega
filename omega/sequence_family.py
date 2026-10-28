"""Finite length polymorphism through individually checked specializations.

All lengths 1..maximum are required. An incomplete build never publishes the
signed family index. Runtime-value-dependent arbitrary Python loops are refused.
"""
import hashlib
import json
from pathlib import Path
from .pci import digest, verify_export
from omega_selfhost.proof_protocol import encode


def export_family(model, examples, directory, *, input_bounds, output_bounds,
                  signing_key, nonce, max_error, target='critical-system', precision_bits=32):
    import torch
    from .certify import export
    if type(examples) is not dict or not 1<=len(examples)<=16 or set(examples)!=set(range(1,len(examples)+1)):
        raise ValueError('Provide exactly every sequence length from 1 through a maximum of 16')
    if type(nonce) is not str or not 1<=len(nonce)<=200:
        raise ValueError('Bounded family nonce required')
    if set(input_bounds)!=set(examples) or set(output_bounds)!=set(examples):
        raise ValueError('Every length requires its own input and output contracts')
    widths=set()
    for n,x in examples.items():
        if not isinstance(x,torch.Tensor) or x.ndim not in (2,3) or x.shape[-2]!=n:
            raise ValueError('Example shapes must be [length, embedding] or [batch, length, embedding]')
        widths.add((tuple(x.shape[:-2]),x.shape[-1]))
    if len(widths)!=1:raise ValueError('Embedding width must remain fixed')
    root=Path(directory).absolute();root.mkdir(parents=True,exist_ok=False)
    entries=[]
    for n in sorted(examples):
        context=f'{target}/length/{n}'
        result=export(model,examples[n],root/f'length-{n}',input_bounds=input_bounds[n],output_bounds=output_bounds[n],
                      signing_key=signing_key,nonce=f'{nonce}:{n}',target=context,max_error=max_error,precision_bits=precision_bits)
        statement=result['certificate']['payload']['statement']
        path=root/f'length-{n}'/'certificate.json'
        entries.append({'length':n,'directory':f'length-{n}','graph_sha256':statement['graph_sha256'],
                        'certificate_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                        'nonce':f'{nonce}:{n}','context':context})
    payload={'format':'omega-sequence-family-1','maximum_length':len(examples),'members':entries}
    manifest={'payload':payload,'signature':signing_key.sign(encode(payload)).hex()}
    temporary=root/'.family.tmp';temporary.write_bytes(encode(manifest))
    temporary.rename(root/'family.json')
    return manifest


def verify_family(directory, *, public_key, expected_members):
    from omega.typed_ir import _pairs
    root=Path(directory)
    manifest_path=root/'family.json'
    if manifest_path.is_symlink() or manifest_path.stat().st_size>65536:
        raise ValueError('Bounded regular family manifest required')
    manifest=json.loads(manifest_path.read_bytes(),object_pairs_hook=_pairs)
    if type(manifest) is not dict or set(manifest)!={'payload','signature'}:
        raise ValueError('Unknown family envelope')
    payload=manifest['payload'];public_key.verify(bytes.fromhex(manifest['signature']),encode(payload))
    if type(payload) is not dict or set(payload)!={'format','maximum_length','members'} or payload['format']!='omega-sequence-family-1':
        raise ValueError('Unknown family format')
    maximum=payload['maximum_length']
    if type(maximum) is not int or not 1<=maximum<=16 or set(expected_members)!=set(range(1,maximum+1)) or len(payload['members'])!=maximum:
        raise ValueError('Unrelated sequence length contract')
    results={}
    for n,entry in enumerate(payload['members'],1):
        if type(entry) is not dict or set(entry)!={'length','directory','graph_sha256','certificate_sha256','nonce','context'} or entry['length']!=n or entry['directory']!=f'length-{n}':
            raise ValueError('Invalid sequence family membership')
        folder=root/f'length-{n}'
        if folder.is_symlink():raise ValueError('Symlinked family members are refused')
        path=folder/'certificate.json'
        if path.is_symlink() or path.stat().st_size>8*1024**2 or hashlib.sha256(path.read_bytes()).hexdigest()!=entry['certificate_sha256']:
            raise ValueError('Changed sequence certificate')
        expected=expected_members[n]
        if expected['expected_graph_sha256']!=entry['graph_sha256'] or expected['expected_nonce']!=entry['nonce'] or expected['expected_context']!=entry['context']:
            raise ValueError('Unrelated sequence member identity')
        results[n]=verify_export(folder,public_key=public_key,**expected)
    return {'valid':True,'maximum_length':maximum,'members':results,'family_sha256':digest(payload)}
