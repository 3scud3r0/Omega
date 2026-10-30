"""Actual sandboxed execution of generated programs and the fixed-arena backend.

The native engine proposes data/code. Fixed host contracts check the result;
neither path deploys a model, changes source files or executes external actions.
"""
from fractions import Fraction as Q
from pathlib import Path
import hashlib
import json
import re

from omega_platform.budget import COMPILER_BUDGET
from omega_platform.sandbox import run as isolated_run
from omega_security.encoding import canonical
from omega_selfhost.driver import compiler, cc
from omega_science.runtime import SOURCE_ROOT, _plain, _hash, prove as check_numeric
from .runtime import run


def _save(directory, name, value):
    (directory/name).write_bytes(canonical(_plain(value), max_bytes=4*1024**2, max_nodes=50000))


def _receipts(witnesses, directory):
    if not 1 <= len(witnesses) <= 256:
        raise ValueError('Independent engine proof contract supports 1..256 numeric obligations')
    return [check_numeric({'witnesses': witnesses[i:i+32]}, directory/('batch-'+str(i//32)))
            for i in range(0, len(witnesses), 32)]


def synthesize(request, destination):
    """Compile a native hypernetwork proposal, execute every case, then use Lean.

    Proofs are closed coefficient/monomial/value equalities on these cases;
    this is not a global compiler refinement or a generalization guarantee.
    """
    request = _plain(request)
    proposal = run(15, request)
    if proposal['examples_passed'] != 1:
        raise ValueError('Generated polynomial fails the supplied examples')
    source = proposal['source']
    if (type(source) is not str or len(source.encode()) > 65536
            or hashlib.sha256(source.encode()).hexdigest() != proposal['source_sha256']):
        raise ValueError('Native candidate source/hash budget mismatch')
    directory = Path(destination).absolute()
    directory.mkdir(parents=True, exist_ok=False)
    _save(directory, 'request.json', request)
    path = directory/'candidate.omega'; path.write_text(source)
    c_source = directory/'candidate.c'; binary = directory/'candidate'
    native_compiler = compiler(); compiler_hash = _hash(native_compiler)
    isolated_run([native_compiler, path, c_source], readonly=[path], writable=[directory],
                 budget=COMPILER_BUDGET, check=True)
    cc(c_source, binary)
    code_hashes = {p.name: _hash(p) for p in (path, c_source, binary)}
    observations = []; witnesses = []
    polynomial = proposal['polynomial']
    if type(polynomial) is not list or len(polynomial) > 16:
        raise ValueError('Generated polynomial term budget')
    for case in request['cases']:
        point = [Q(x) for x in case['input']]
        argv = [binary]
        for x in point:
            argv.extend((str(x.numerator), str(x.denominator)))
        result = isolated_run(argv, budget=COMPILER_BUDGET, check=True)
        tokens = result.stdout.split()
        if len(tokens) != 2 or any(not re.fullmatch(r'-?[0-9]{1,3000}', t) for t in tokens):
            raise ValueError('Generated executable did not return one exact rational')
        value = Q(int(tokens[0]), int(tokens[1]))
        coefficients = []; monomials = []
        for coefficient, exponents in polynomial:
            if (len(exponents) != len(point) or any(e.denominator != 1 or not 0 <= e <= 12 for e in exponents)
                    or sum(exponents) > 12):
                raise ValueError('Generated polynomial is outside its DSL')
            monomial = Q(1)
            for x, e in zip(point, exponents):
                monomial *= x**int(e)
            coefficients.append(coefficient); monomials.append(monomial)
        expected = Q(case['expected'])
        independent = sum((c*m for c, m in zip(coefficients, monomials)), Q(0))
        if value != expected or value != independent:
            raise ValueError('Native program disagrees with the independent exact case contract')
        witnesses.append({'left_dot': [coefficients, monomials], 'right': [value]})
        observations.append({'input': point, 'output': value, 'expected': expected})
        if any(_hash(directory/name) != digest for name, digest in code_hashes.items()):
            raise ValueError('Generated artifact changed during execution')
    receipts = _receipts(witnesses, directory/'proof')
    if _hash(native_compiler) != compiler_hash:
        raise ValueError('Compiler changed during candidate verification')
    headers = directory/'headers'; headers.mkdir()
    for name in ('runtime.h','native_std.h','memory.h'):
        original = Path(__file__).resolve().parents[1]/'omega_selfhost'/name
        (headers/name).write_bytes(original.read_bytes())
    _save(directory, 'observations.json', observations)
    result = {'format': 'omega-engine-synthesis-1', 'compiled': True, 'cases_passed': len(observations),
              'numeric_obligations_verified': True, 'global_program_correctness_proven': False,
              'generalization_proven': False, 'promoted': False, 'proof_batches': len(receipts),
              'compiler_sha256': compiler_hash, 'verifier_sha256': _hash(Path(__file__)),
              'files': {str(p.relative_to(directory)): _hash(p) for p in sorted(directory.rglob('*')) if p.is_file()}}
    (directory/'receipt.json').write_bytes(canonical(result))
    return result


_OPCODES = {name: 'OMEGA_MICRO_'+name.upper() for name in
            ('set', 'add', 'mul', 'assert', 'send', 'recv', 'jump', 'jnz', 'yield', 'halt')}
_STATUSES = ('ready', 'blocked_send', 'blocked_receive', 'halted')


def _c_rational(value):
    value = Q(value)
    if abs(value.numerator) > 2**63-1 or value.denominator > 2**63-1:
        raise ValueError('Fixed-arena rational storage exceeded')
    return '{INT64_C('+str(value.numerator)+'),UINT64_C('+str(value.denominator)+')}'


def arena_native(request, destination):
    """Run a reviewed C microkernel in real arenas, checking the Omega trace.

    The allocation-free kernel receives buffers. Only this Linux test harness
    uses mmap/stdio; it has no authority to read a model, file or credential.
    """
    request = _plain(request)
    reference = run(16, request)
    actors, registers, stride = (int(Q(request[k])) for k in ('actors', 'registers', 'arena_bytes'))
    if stride % 8:
        raise ValueError('The fixed-arena C ABI requires stride aligned to 8 bytes')
    instructions = []
    for op, reg, target, value in reference['shared_program']:
        if op not in _OPCODES:
            raise ValueError('Unrecognized native microkernel opcode')
        instructions.append('{'+','.join((_OPCODES[op], str(int(reg)), str(int(target)), _c_rational(value)))+'}')
    initializer = []
    if 'initial' in request:
        for i, row in enumerate(request['initial']):
            for j, value in enumerate(row):
                initializer.append('omega_micro_cell(&runtime,'+str(i)+')->registers['+str(j)+']=(OmegaMicroQ)'+_c_rational(value)+';')
    # Every interpolated field is a validated integer, rational or fixed enum.
    source = '''#include "cellular_micro_arena.h"
#include <stdio.h>
#include <inttypes.h>
#include <sys/mman.h>
static const OmegaMicroInstruction program[] = {PROGRAM};
int main(void) {
    const size_t bytes = (size_t)ACTORS * STRIDE;
    void *memory = mmap(0,bytes,PROT_READ|PROT_WRITE,MAP_PRIVATE|MAP_ANONYMOUS,-1,0);
    if(memory==MAP_FAILED)return 21;
    OmegaMicroRuntime runtime;
    if(omega_micro_init(&runtime,memory,bytes,STRIDE,ACTORS,REGISTERS,MAILBOX,QUANTUM,program,sizeof program/sizeof program[0]))return 22;
    INITIALIZER
    int fault=omega_micro_run(&runtime,MAX_TURNS); if(fault)return 30-fault;
    for(uint32_t i=0;i<runtime.actors;i++) {
        OmegaMicroCell *cell=omega_micro_cell(&runtime,i);
        printf("S %u %u %u %u\\n",i,cell->status,cell->pc,cell->count);
        for(uint32_t j=0;j<runtime.registers;j++)printf("R %u %u %" PRId64 " %" PRIu64 "\\n",i,j,cell->registers[j].n,cell->registers[j].d);
    }
    printf("T %" PRIu64 " %" PRIu64 " %" PRIu64 " %" PRIu64 " %u %u\\n",runtime.turns,runtime.instructions,runtime.messages,runtime.mailbox_peak,runtime.completed,runtime.deadlock);
    printf("A %zu %zu\\n",bytes,sizeof(OmegaMicroCell));
    if(munmap(memory,bytes))return 23;
    return 0;
}
'''
    replacements = {'PROGRAM': ',\n'.join(instructions), 'ACTORS': str(actors), 'STRIDE': str(stride),
                    'REGISTERS': str(registers), 'MAILBOX': str(int(Q(request['mailbox_capacity']))),
                    'QUANTUM': str(int(Q(request['quantum']))), 'MAX_TURNS': str(int(Q(request['max_turns']))),
                    'INITIALIZER': '\n'.join(initializer)}
    source = re.sub(r'\b(?:'+ '|'.join(replacements)+r')\b', lambda m: replacements[m.group()], source)
    directory = Path(destination).absolute(); directory.mkdir(parents=True, exist_ok=False)
    _save(directory, 'request.json', request)
    header = SOURCE_ROOT/'runtime/cellular_micro_arena.h'
    (directory/header.name).write_bytes(header.read_bytes())
    c_source = directory/'microkernel.c'; c_source.write_text(source)
    binary = directory/'microkernel'; cc(c_source, binary)
    result = isolated_run([binary], budget=COMPILER_BUDGET, check=True)
    (directory/'stdout.log').write_text(result.stdout)
    expected = {}
    for i in range(actors):
        expected[('S',i)] = [_STATUSES.index(reference['statuses'][i]), int(reference['program_counters'][i]), int(reference['mailbox_counts'][i])]
        for j in range(registers):
            value = reference['value'][i][j]
            expected[('R',i,j)] = [value.numerator, value.denominator]
    expected[('T',)] = [int(reference[k]) for k in ('turns','instructions','messages','mailbox_peak','completed','deadlock')]
    seen = set(); allocation = None
    for line in result.stdout.splitlines():
        fields = line.split(); kind = fields[0]
        if kind == 'A':
            if allocation is not None:
                raise ValueError('Duplicate allocation report')
            allocation = list(map(int, fields[1:])); continue
        width = {'S':2, 'R':3, 'T':1}.get(kind)
        if width is None:
            raise ValueError('Unexpected microkernel output')
        key = (kind, *map(int, fields[1:width]))
        if key in seen or key not in expected or list(map(int,fields[width:])) != expected[key]:
            raise ValueError('C microkernel disagrees with the independent Omega reference')
        seen.add(key)
    if seen != set(expected) or allocation is None or len(allocation)!=2 or allocation[0]!=actors*stride or allocation[1]>stride:
        raise ValueError('Missing microkernel observation or invalid arena layout')
    receipt = {'format':'omega-microarena-native-1', 'differential_check_passed':True,
               'arena_bytes_allocated':allocation[0], 'cell_control_bytes':allocation[1],
               'process_RSS_measured':False, 'M_to_N_fibers':False,
               'verifier_sha256':_hash(Path(__file__)),
               'sandboxed':result.sandboxed, 'wall_seconds':result.wall_seconds,
               'files':{p.name:_hash(p) for p in sorted(directory.iterdir()) if p.is_file()}}
    (directory/'receipt.json').write_bytes(canonical(receipt))
    return receipt
