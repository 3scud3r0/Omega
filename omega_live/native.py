"""One registered native entry point for the 48 .omega subsystem modules."""
import json
from pathlib import Path
import tempfile
from omega_native.toolchain import build
from omega_platform.sandbox import run
from omega_platform.budget import COMPILER_BUDGET


def invoke(module,request,*,readonly=(),writable=()):
    binary=build('tools/society_suite.omega')
    with tempfile.TemporaryDirectory(prefix='omega-society-request-') as temporary:
        path=Path(temporary)/'request.json';path.write_text(json.dumps(request,ensure_ascii=False,allow_nan=False,separators=(',',':')))
        outcome=run([binary,module,path],readonly=[path,*readonly],writable=list(writable),budget=COMPILER_BUDGET,check=True)
        return json.loads(outcome.stdout.strip().splitlines()[-1])
