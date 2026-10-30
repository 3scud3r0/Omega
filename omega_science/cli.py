"""CLI for native scientific modules and independent numeric Lean checking."""
import argparse
import json
from pathlib import Path
import sys
from fractions import Fraction
from omega_platform.results import attempt, Err
from omega_security.encoding import decode
from .runtime import catalog, run, build, prove, REQUEST_LIMIT


def main(argv=None):
    parser = argparse.ArgumentParser(prog='omega science')
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('list', help='Show the exact 115-file inventory and declared scopes')
    create = sub.add_parser('build', help='Build one bounded native scientific application')
    create.add_argument('group')
    create.add_argument('--saida', type=Path)
    execute = sub.add_parser('run', help='Execute a native scientific kernel in sandbox')
    execute.add_argument('kernel', type=int)
    execute.add_argument('request', type=Path)
    proof = sub.add_parser('prove', help='Check closed numeric observations with Lean CPU')
    proof.add_argument('request', type=Path)
    proof.add_argument('--saida', type=Path, required=True)
    experiment = sub.add_parser('experiment', help='Native execution, reviewed numeric Lean obligations and encoded paper')
    experiment.add_argument('kernel', type=int)
    experiment.add_argument('request', type=Path)
    experiment.add_argument('--saida', type=Path, required=True)
    args = parser.parse_args(argv)
    def operation():
        if args.action == 'list':
            return catalog()
        if args.action == 'build':
            return {'binary': str(build(args.group, args.saida)), 'scientific_acceptance': False}
        with args.request.open('rb') as stream:
            data = stream.read(REQUEST_LIMIT+1)
        if len(data) > REQUEST_LIMIT:
            raise ValueError('Scientific request byte budget exceeded')
        request = decode(data, max_bytes=REQUEST_LIMIT, max_nodes=50000, max_depth=40)
        if args.action == 'experiment':
            from .experiment import execute
            return execute(args.kernel, request, args.saida)
        return run(args.kernel, request) if args.action == 'run' else prove(request, args.saida)
    result = attempt('science', operation)
    def encode(value):
        if type(value) is Fraction:
            return str(value)
        raise TypeError('Unsupported scientific result')
    if isinstance(result, Err):
        print(json.dumps(result.to_dict(), ensure_ascii=False), file=sys.stderr)
        return 1
    print(json.dumps(result.to_dict(), ensure_ascii=False, default=encode))
    return 0
