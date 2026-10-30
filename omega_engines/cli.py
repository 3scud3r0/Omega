"""Native engine CLI; optional checked compilation never implies deployment."""
import argparse
import json
from fractions import Fraction
from pathlib import Path
import sys

from omega_platform.results import attempt, Err
from omega_science.runtime import REQUEST_LIMIT, build
from omega_security.encoding import decode
from .runtime import catalog, run


def main(argv=None):
    parser = argparse.ArgumentParser(prog='omega engines')
    commands = parser.add_subparsers(dest='action', required=True)
    commands.add_parser('list', help='Sixteen bounded research engines and their data contracts')
    create = commands.add_parser('build', help='Compile a core/ML application to native C/GMP')
    create.add_argument('group', choices=('engines_core', 'engines_ml'))
    create.add_argument('--saida', type=Path)
    execute = commands.add_parser('run', help='Run one engine with exact JSON data in a sandbox')
    execute.add_argument('engine', type=int)
    execute.add_argument('request', type=Path)
    for action, help_text in (
        ('synthesize', 'Compile the hypernetwork proposal, execute its cases and check numeric Lean obligations'),
        ('arena-native', 'Run the fixed-arena C backend and compare it against the native Omega model')):
        sub = commands.add_parser(action, help=help_text)
        sub.add_argument('request', type=Path)
        sub.add_argument('--saida', type=Path, required=True)
    proof = commands.add_parser('prove', help='Reviewed numeric LP/action/coarse-graining contracts checked in Lean')
    proof.add_argument('engine', type=int)
    proof.add_argument('request', type=Path)
    proof.add_argument('--saida', type=Path, required=True)
    args = parser.parse_args(argv)

    def operation():
        if args.action == 'list':
            return catalog()
        if args.action == 'build':
            return {'binary': str(build(args.group, args.saida))}
        with args.request.open('rb') as stream:
            raw = stream.read(REQUEST_LIMIT+1)
        if len(raw) > REQUEST_LIMIT:
            raise ValueError('Engine request byte budget')
        request = decode(raw, max_bytes=REQUEST_LIMIT, max_nodes=50000, max_depth=40)
        if args.action == 'run':
            return run(args.engine, request)
        if args.action == 'prove':
            from .proof import prove
            return prove(args.engine, request, args.saida)
        from .execution import synthesize, arena_native
        return (synthesize if args.action == 'synthesize' else arena_native)(request, args.saida)

    result = attempt('fundamental-engines', operation)
    if isinstance(result, Err):
        print(json.dumps(result.to_dict(), ensure_ascii=False), file=sys.stderr)
        return 1
    def encode(value):
        if type(value) is Fraction:
            return str(value)
        raise TypeError('Only JSON data and exact fractions can be engine results')
    print(json.dumps(result.to_dict(), ensure_ascii=False, default=encode))
    return 0
