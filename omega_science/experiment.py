"""Closed numerical experiment evidence; no scientific-law or deployment approval."""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib
import json

from omega_native.codec import canonical as native_document
from omega_security.encoding import canonical
from .runtime import ROOT, SOURCE_ROOT, kernel, run, build, prove, _plain, _hash


def obligations(identifier, request, observed):
    """Host-selected contracts; a proposal cannot choose a weaker checker."""
    if identifier == 1:
        return [{'left':[observed['energy_before']], 'right':[observed['energy_after']]}]
    if identifier == 23:
        return [{'left_dot':[row, observed['value']], 'right':[0]} for row in request['conservation_matrix']]
    if identifier == 50:
        return [{'left': observed['value'], 'right':[1]},
                {'left_dot':[observed['value'],[1,Fraction(1,2),0]], 'right':[observed['allele_frequency']]}]
    if identifier == 53:
        return [{'left_dot':[[request['inside_concentration'],request['outside_concentration']],
                             [request['inside_volume'],request['outside_volume']]],
                 'right_dot':[observed['value'],[request['inside_volume'],request['outside_volume']]]}]
    if identifier == 70:
        return [{'left_squares':observed['value'], 'right':[1]}]
    if identifier == 102:
        return [{'left':[observed['total_energy_before']], 'right':[observed['total_energy_after']]},
                {'left':[request['amount_A'],request['amount_B']], 'right':observed['value'][4:6]}]
    raise ValueError('No reviewed numeric experiment contract for this kernel; use run for the declared model')


def execute(identifier, request, directory):
    if identifier not in (1,23,50,53,70,102):
        raise ValueError('Choose an implemented independent numeric experiment contract')
    entry = kernel(identifier)
    directory = Path(directory).absolute()
    directory.mkdir(parents=True, exist_ok=False)
    # Snapshot data before granting native execution any access to a temporary request.
    request = deepcopy(_plain(request))
    (directory/'request.json').write_bytes(canonical(request, max_bytes=4*1024**2, max_nodes=50000))
    binary = build(entry['group'])
    build_record = binary.with_suffix('.science.json').read_bytes()
    binary_digest = _hash(binary)
    observed = run(identifier, request)
    if build(entry['group']) != binary or _hash(binary) != binary_digest or binary.with_suffix('.science.json').read_bytes() != build_record:
        raise ValueError('Scientific source/binary changed during the experiment')
    (directory/'observation.json').write_text(native_document(observed))
    witnesses = {'witnesses': obligations(identifier,request,observed)}
    receipt = prove(witnesses, directory/'proof')
    module_record = json.loads(binary.with_suffix('.modules.json').read_text())
    from omega.modules import link
    linked = link('ciencia/apps/'+entry['group']+'.omega', SOURCE_ROOT, dynamic=True)
    if linked.manifest() != module_record:
        raise ValueError('Experiment module provenance changed before packaging')
    dependencies = {name:(ROOT/name).read_text() for name in (
        'omega_selfhost/runtime.h','omega_selfhost/native_std.h','omega_selfhost/memory.h')}
    package = run(108, {'article': 'Reproducible bounded numerical experiment.\n'
                                 'Numeric obligations verified; physical model and compiler refinement require separate review.\n',
                        'omega_source': linked.source, 'c_source':binary.with_suffix('.c').read_text(),
                        'binary_hex': binary.read_bytes().hex(),
                        'lean_source':(directory/'proof/Observation.lean').read_text(),
                        'verification_record':json.dumps(receipt,sort_keys=True)})
    (directory/'paper.json').write_text(native_document(package))
    # Header payloads and exact build provenance accompany the encoded executable.
    (directory/'runtime-headers.json').write_bytes(canonical(dependencies,max_bytes=2*1024**2))
    (directory/'build.json').write_bytes(build_record)
    result = {'format':'omega-science-experiment-1','kernel':identifier,
              'numeric_obligations_verified': True, 'scientific_model_accepted':False,
              'global_law_proved':False, 'external_publication':False,
              'files': {str(p.relative_to(directory)):_hash(p) for p in sorted(directory.rglob('*')) if p.is_file()}}
    (directory/'experiment.json').write_bytes(canonical(result,max_bytes=2*1024**2))
    return result
