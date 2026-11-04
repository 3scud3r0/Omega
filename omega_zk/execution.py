"""Omega procedural -> checked-u32 RV32IM guest for the RISC Zero zkVM.

The public statement binds source, exact lowered IR, result and fuel. The guest
reads eight private words, executes the program, checks the public result, then
commits that statement. This is not a proof of the RV64 ELF backend or a proof
that the source-to-IR compiler itself is correct. Zero knowledge is provided by
RISC Zero's succinct receipt, not by the older AIR research module.
"""
from __future__ import annotations
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import struct
import tempfile

from omega_sovereign.models import call
from omega_sovereign.rv64 import assemble
from omega_platform.budget import Budget
from omega_platform.sandbox import run

TEXT=0x200800
DATA=0x1000000
UINT_MAX=2**32-1
SCHEME='risc0-succinct-stark-3.0.3'
PROOF_BUDGET=Budget(wall_seconds=1800,cpu_seconds=1800,memory_bytes=12*1024**3,
                    file_bytes=64*1024**2,processes=128,output_bytes=1024**2)


def uint(n):
    if type(n) is not int or not 0<=n<=UINT_MAX:raise ValueError('Checked u32 required')
    return n


def canonical(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode('ascii')


@dataclass(frozen=True)
class Program:
    elf: bytes
    journal: bytes
    ir: tuple
    fuel: int


def lower(source):
    if type(source) is not str or not 0<len(source.encode())<=32768:raise ValueError('Source budget')
    model=call('zk-lower',{'source':source})
    ir=model['ir']
    if not 0<len(ir)<=4096:raise ValueError('IR budget')
    return ir


def statement(source,ir,expected,fuel):
    uint(expected)
    if type(fuel) is not int or not 1<=fuel<=10000:raise ValueError('Fuel in [1,10000] required')
    return canonical({'format':'omega-zk-u32-v1','source_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'ir_sha256':hashlib.sha256(canonical(ir)).hexdigest(),'result':expected,'fuel':fuel,
        'private_words':8,'semantics':'checked-u32-exact-division'})


def elf32(code):
    """Deterministic RV32IM ELF. No assembler, linker or guest SDK required."""
    if not 0<len(code)<=512*1024:raise ValueError('Guest image budget')
    ident=b'\x7fELF\x01\x01\x01'+bytes(9)
    header=ident+struct.pack('<HHIIIIIHHHHHH',2,243,1,TEXT,52,0,0,52,32,2,0,0,0)
    ph=(struct.pack('<IIIIIIII',1,4096,TEXT,TEXT,len(code),len(code),5,4)+
        struct.pack('<IIIIIIII',1,0,DATA,DATA,0,8192,6,4))
    return header+ph+bytes(4096-len(header)-len(ph))+code


def guest(ir,journal,output_digest,fuel):
    if len(output_digest)!=32:raise ValueError('Output digest must be 32 bytes')
    # All macros used here are RV32IM-compatible. The shared assembler's wide
    # li expansion uses only ADDI/SLLI(12); RV32 truncation gives the low word.
    lines=['li sp,0x200400','li a0,0x1001000','li a1,4','la a2,sys_random',
           'li t0,2','li t6,11','ecall',
           'li a0,0x1000000','li a1,32','la a2,sys_read','li a3,0','li a4,32',
           'li t0,2','li t6,12','ecall','li t1,32','bne a0,t1,failure',
           'li s0,0x1000000','li s1,0x1000100',f'li s2,{uint(json.loads(journal)["result"])}',
           f'li s11,{fuel}']
    def load(reg,id):
        if type(id) is not int or not 0<=id<240:raise ValueError('Virtual register')
        lines.append(f'lw {reg},{id*4}(s1)')
    def store(id):
        if type(id) is not int or not 0<=id<240:raise ValueError('Virtual register')
        lines.append(f'sw t3,{id*4}(s1)')
    for x in ir:
        op=x[0]
        if op=='label':lines.append(x[1]+':');continue
        lines+=['beq s11,zero,failure','addi s11,s11,-1']
        if op=='const':lines.append(f'li t3,{uint(x[2])}');store(x[1])
        elif op=='input':
            if type(x[2]) is not int or not 0<=x[2]<8:raise ValueError('Private input index')
            lines.append(f'lw t3,{4*x[2]}(s0)');store(x[1])
        elif op=='move':load('t3',x[2]);store(x[1])
        elif op=='un':
            load('t1',x[3])
            if x[2]=='!':lines.append('sltiu t3,t1,1')
            elif x[2]=='-':lines+=['bne t1,zero,failure','li t3,0']
            else:raise ValueError('Unary operator')
            store(x[1])
        elif op=='bin':
            load('t1',x[3]);load('t2',x[4]);operator=x[2]
            if operator=='+':lines+=['add t3,t1,t2','bltu t3,t1,failure']
            elif operator=='-':lines+=['bltu t1,t2,failure','sub t3,t1,t2']
            elif operator=='*':lines+=['mulhu t4,t1,t2','bne t4,zero,failure','mul t3,t1,t2']
            elif operator in ('/','%'):
                lines+=['beq t2,zero,failure','remu t3,t1,t2']
                if operator=='/':lines+=['bne t3,zero,failure','divu t3,t1,t2']
            elif operator in ('==','!='):
                lines+=['xor t3,t1,t2','sltiu t3,t3,1' if operator=='==' else 'sltu t3,zero,t3']
            elif operator in ('<','>','<=','>='):
                lines.append('sltu t3,t1,t2' if operator in ('<','>=') else 'sltu t3,t2,t1')
                if operator in ('<=','>='):lines.append('xori t3,t3,1')
            else:raise ValueError('Binary operator outside checked-u32 subset')
            store(x[1])
        elif op=='jump':lines.append('j '+x[1])
        elif op=='zero':load('t1',x[1]);lines.append('beq t1,zero,'+x[2])
        elif op=='return':load('t1',x[1]);lines+=['bne t1,s2,failure','j success']
        elif op=='trap':lines.append('j failure')
        else:raise ValueError('Unsupported IR instruction')
    lines+=['success:','li a0,0','li a1,0','la a2,sys_write','li a3,3','la a4,journal',
            f'li a5,{len(journal)}','li t0,2','li t6,16','ecall','li s10,0','j halt',
            'failure:','li s10,256','halt:','mv a0,s10','la a1,output_digest','li t0,0','ecall',
            '.align 2','output_digest:', '.word '+','.join(map(str,struct.unpack('<8I',output_digest))),
            'journal:', '.ascii '+json.dumps(journal.decode('ascii')),
            'sys_read:','.asciz "risc0_zkvm_platform::syscall::nr::SYS_READ"',
            'sys_write:','.asciz "risc0_zkvm_platform::syscall::nr::SYS_WRITE"',
            'sys_random:','.asciz "risc0_zkvm_platform::syscall::nr::SYS_RANDOM"']
    code,_=assemble('\n'.join(lines),origin=TEXT,max_bytes=512*1024)
    return elf32(code)


class Engine:
    """Explicit local tool path; no remote prover or development-mode fallback."""
    def __init__(self,tool):
        self.tool=Path(tool).resolve(strict=True)
        if not self.tool.is_file():raise ValueError('Local prover/verifier executable required')
    def invoke(self,args,*,inputs=(),outputs=(),budget=PROOF_BUDGET):
        result=run([self.tool,*map(str,args)],readonly=[self.tool,*inputs],writable=outputs,
                   threads=True,budget=budget,check=True)
        return result.stdout.strip()
    def compile(self,source,expected,*,fuel=1000):
        ir=lower(source);public=statement(source,ir,expected,fuel)
        with tempfile.TemporaryDirectory(prefix='omega-zk-compile-') as tmp:
            j=Path(tmp)/'journal';j.write_bytes(public)
            digest=bytes.fromhex(self.invoke(['output-digest',j],inputs=[j]))
        return Program(guest(ir,public,digest,fuel),public,tuple(ir),fuel)
    def image_id(self,program):
        with tempfile.TemporaryDirectory(prefix='omega-zk-image-') as tmp:
            p=Path(tmp)/'guest.elf';p.write_bytes(program.elf)
            return self.invoke(['image-id',p],inputs=[p])
    def prove(self,program,private):
        if type(private) not in (list,tuple) or len(private)!=8:raise ValueError('Eight private u32 words required')
        raw=struct.pack('<8I',*(uint(x) for x in private))
        with tempfile.TemporaryDirectory(prefix='omega-zk-prove-') as tmp:
            folder=Path(tmp);elf=folder/'guest.elf';elf.write_bytes(program.elf)
            j=folder/'journal';j.write_bytes(program.journal)
            witness=folder/'private';witness.write_bytes(raw)
            proof=folder/'proof.bin'
            metrics=json.loads(self.invoke(['prove',elf,witness,j,proof],inputs=[elf,j,witness],outputs=[folder]))
            return proof.read_bytes(),metrics
    def verify(self,proof,image_id,journal):
        if type(proof) is not bytes or not 0<len(proof)<=4*1024**2:raise ValueError('Proof byte budget')
        if type(journal) is not bytes or not 0<len(journal)<=1024:raise ValueError('Public journal budget')
        if type(image_id) is not str or len(image_id)!=64 or any(c not in '0123456789abcdef' for c in image_id):raise ValueError('Expected image ID required')
        with tempfile.TemporaryDirectory(prefix='omega-zk-verify-') as tmp:
            p=Path(tmp)/'proof';p.write_bytes(proof);j=Path(tmp)/'journal';j.write_bytes(journal)
            return json.loads(self.invoke(['verify',p,image_id,j],inputs=[p,j]))
