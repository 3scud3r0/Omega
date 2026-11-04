"""Independent RV32IM CPU execution in Unicorn. This is not a ZK verifier.

A minimal RISC Zero platform ABI handler checks I/O and successful termination.
Used to validate emitted guest bytes even when the cryptographic prover's
recursion artifact is unavailable. It must never substitute for a proof test.
"""
import struct
from unicorn import Uc,UC_ARCH_RISCV,UC_MODE_RISCV32,UC_HOOK_INTR
from unicorn.riscv_const import (UC_RISCV_REG_PC,UC_RISCV_REG_A0,UC_RISCV_REG_A1,
    UC_RISCV_REG_A2,UC_RISCV_REG_A3,UC_RISCV_REG_A4,UC_RISCV_REG_A5,UC_RISCV_REG_T0,UC_RISCV_REG_T6)
from omega_zk.execution import TEXT,DATA


def execute(program,private):
    uc=Uc(UC_ARCH_RISCV,UC_MODE_RISCV32)
    uc.mem_map(0x200000,1024*1024)
    uc.mem_map(DATA,8192)
    uc.mem_write(TEXT,program.elf[4096:])
    out=bytearray();exit_code=[];calls=[]
    def syscall(machine,interrupt,_):
        read=machine.reg_read
        a=[read(r) for r in (UC_RISCV_REG_A0,UC_RISCV_REG_A1,UC_RISCV_REG_A2,UC_RISCV_REG_A3,UC_RISCV_REG_A4,UC_RISCV_REG_A5)]
        if read(UC_RISCV_REG_T0)==0:
            exit_code.append(a[0]>>8);machine.emu_stop();return
        assert read(UC_RISCV_REG_T0)==2
        nr=read(UC_RISCV_REG_T6)
        name=bytes(machine.mem_read(a[2],96)).split(b'\0')[0]
        calls.append(nr)
        if nr==11:
            assert name.endswith(b'::SYS_RANDOM') and a[1]==4
            machine.mem_write(a[0],bytes(range(16)))
        elif nr==12:
            assert name.endswith(b'::SYS_READ') and a[3]==0 and a[4]==32 and a[1]==32
            machine.mem_write(a[0],struct.pack('<8I',*private))
            machine.reg_write(UC_RISCV_REG_A0,32)
        elif nr==16:
            assert name.endswith(b'::SYS_WRITE') and a[3]==3 and a[5]<=1024
            out.extend(machine.mem_read(a[4],a[5]))
        else:raise AssertionError('Unexpected guest syscall')
        # Unicorn's ECALL interrupt hook already advances PC by four bytes.
    uc.hook_add(UC_HOOK_INTR,syscall)
    uc.emu_start(TEXT,0,timeout=5_000_000,count=4_194_304)
    if not exit_code:raise ValueError('Guest did not halt within instruction budget')
    return exit_code[0],bytes(out),calls
