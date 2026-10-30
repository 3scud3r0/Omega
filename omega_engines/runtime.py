"""Data-only requests to native engines using the existing verified build cache."""
from pathlib import Path
import tempfile

from omega_native.codec import decode
from omega_platform.budget import Budget, COMPILER_BUDGET
from omega_platform.sandbox import run as isolated_run
from omega_security.encoding import canonical, decode as bounded_decode
from omega_science.runtime import SOURCE_ROOT, REQUEST_LIMIT, _plain, build


def catalog():
    value = bounded_decode((SOURCE_ROOT/'omega_core/catalogo.json').read_bytes(),
                           max_bytes=1024**2, max_nodes=20000)
    if (value.get('format') != 'omega-fundamental-engines-1'
            or [x['id'] for x in value['engines']] != list(range(1, 17))):
        raise ValueError('The engine catalog must contain exactly sixteen ordered IDs')
    return value


def run(identifier, request, *, budget=COMPILER_BUDGET):
    if type(identifier) is not int or type(request) is not dict or type(budget) is not Budget:
        raise ValueError('Integer engine ID, exact data object and OS budget required')
    entries = [x for x in catalog()['engines'] if x['id'] == identifier]
    if len(entries) != 1:
        raise ValueError('Unknown fundamental engine ID')
    payload = canonical(_plain(request), max_bytes=REQUEST_LIMIT, max_nodes=50000, max_depth=40)
    binary = build(entries[0]['group'])
    with tempfile.TemporaryDirectory(prefix='omega-engine-request-') as tmp:
        path = Path(tmp)/'request.json'
        path.write_bytes(payload)
        result = isolated_run([binary, str(identifier), path], readonly=[path],
                              budget=budget, check=True)
    return decode(result.stdout.strip())
