"""Resource-supervised fixed-shader tool; never executes candidate source."""
from pathlib import Path
import json
import os
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from omega_security.encoding import decode
from omega_recursive.gpu import _dispatch, GPUUnavailable


def main():
    if len(sys.argv) != 2:
        raise SystemExit(2)
    with Path(sys.argv[1]).open('rb') as stream:
        plan = decode(stream.read(4*1024**2+1),max_bytes=4*1024**2,max_nodes=100000)
    os.environ.setdefault('XDG_RUNTIME_DIR',str(Path(sys.argv[1]).parent))
    try:
        result = _dispatch(plan)
    except (GPUUnavailable,ValueError) as exc:
        print(json.dumps({'status':'unavailable','reason':str(exc)}))
        return
    except Exception as exc:
        print(json.dumps({'status':'failed','reason':type(exc).__name__+': '+str(exc)[:1500]}))
        return
    print(json.dumps({'status':'computed','result':result},default=str))


if __name__ == '__main__':
    main()
