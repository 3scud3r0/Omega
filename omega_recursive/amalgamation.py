"""Reproduce the six-component mixed source file without padding or execution."""
from pathlib import Path
import argparse
import hashlib
import json

from omega.modules import link
from omega_security.encoding import canonical
from omega_kernel.amalgamation import (_pretty, HEADER, MARKER, FILE, END, MAX_BYTES,
                                       inspect, extract)
from .runtime import ROOT

COMPONENTS = (
    'omega_brain/solomonoff_induction.omega',
    'omega_singularity/godel_recursive_improver.omega',
    'omega_episteme/synthetic_universe_generator.omega',
    'omega_brain/symbolic_neuro_dag.omega',
    'omega_hive/decentralized_epistemic_swarm.omega',
    'omega_gpu/parallel_induction_substrate.omega',
)
OUTPUT = ROOT/'omega_singularity.omega'
if not OUTPUT.is_file() and (Path(__file__).parent/'omega_singularity.omega').is_file():
    OUTPUT = Path(__file__).parent/'omega_singularity.omega'


def generate(root=ROOT):
    root = Path(root)
    program = link('omega_singularity/main.omega',root,dynamic=True)
    names = set(program.manifest()['modules'])
    names.update(path.relative_to(root).as_posix() for path in (root/'omega_recursive').glob('*.py'))
    names.update('kernel/native/'+name for name in ('logic.h','json.h','sha256.h','tensor.h','main.c',
                                                 'tensor_gmp.h','tensor_graph.h'))
    names.update('omega_selfhost/'+name for name in ('bootstrap.py','compiler.omega','runtime.h',
                                                   'native_std.h','memory.h','bounded_rational.h'))
    names.add('omega_gpu/parallel_induction.wgsl')
    names.add('omega_singularity/README.md')
    for directory in ('omega_singularity/examples','testes/recursive'):
        names.update(path.relative_to(root).as_posix() for path in (root/directory).glob('*')
                     if path.suffix in {'.json','.py'})
    sources = {name:(root/name).read_text() for name in sorted(names)}
    prefix = ('# Six finite research components: native Omega with inert C/Python/WGSL source frames.\n'
              '# Generate: python -m omega_recursive.amalgamation --generate\n'
              '# No universal Solomonoff, intelligence-growth or physical-GPU performance claim.\n'+_pretty(program.source))
    files = {name:{'sha256':hashlib.sha256(text.encode()).hexdigest(),'bytes':len(text.encode()),
                   'lines':len(text.splitlines()),'trailing_newline':text.endswith('\n')}
             for name,text in sources.items()}
    new = {name for name in sources if name.startswith(('omega_recursive/','omega_brain/','omega_singularity/',
                                                      'omega_episteme/','omega_hive/','omega_gpu/','testes/recursive/'))}
    manifest = {'format':'omega-kernel-amalgamation-1','bundle':'omega-recursive-six-1',
                'components':list(COMPONENTS),'files':files,'module_manifest':program.manifest(),
                'prefix_sha256':hashlib.sha256(prefix.encode()).hexdigest(),
                'tree_sha256':hashlib.sha256(canonical(files)).hexdigest(),
                'line_accounting':{'linked_omega_lines':len(prefix.splitlines()),
                    'component_source_lines':sum(info['lines'] for name,info in files.items() if name in new),
                    'reused_source_lines':sum(info['lines'] for name,info in files.items() if name not in new),
                    'linked_and_original_omega_overlap':True,'line_count_is_not_acceptance':True}}
    pieces = [prefix,HEADER+json.dumps(manifest,sort_keys=True,separators=(',',':'))+'\n',MARKER]
    for name,text in sources.items():
        pieces.append(FILE+json.dumps(name)+'\n')
        pieces.extend('#|'+line for line in text.splitlines(keepends=True))
        if text and not text.endswith('\n'):
            pieces.append('\n')
        pieces.append(END)
    result = ''.join(pieces)
    if len(result.encode()) > MAX_BYTES:
        raise ValueError('Recursive source distribution byte quota')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--generate',action='store_true')
    group.add_argument('--check',action='store_true')
    group.add_argument('--extract',type=Path)
    parser.add_argument('--file',type=Path,default=OUTPUT)
    args = parser.parse_args(argv)
    if args.generate:
        args.file.write_text(generate())
    elif args.check:
        if args.file.read_text() != generate():
            raise SystemExit('Stale recursive amalgamation')
        inspect(args.file.read_bytes())
    else:
        extract(args.file.read_bytes(),args.extract)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
