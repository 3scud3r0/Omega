"""Build a no-SBI RV64IM firmware with Sv39/CLINT/PLIC/VirtIO smoke checks."""
from pathlib import Path
from hashlib import sha256
from .rv64 import assemble, elf
from .native import SOURCES


def build(destination):
    source=(SOURCES/'sovereign/baremetal/boot.S').read_text()
    sha3=(SOURCES/'sovereign/native/sha3.S').read_text()
    # Firmware uses only the unkeyed permutation, not the Linux tool's HMAC
    # scratch addresses. Keep unused helper out of the executable image.
    sha3=sha3[:sha3.index('# RFC 2104')]+sha3[sha3.index('\nsha3_256:'):]
    for name,old,new in (('KS','0x800000','0x80208000'),('KC','0x800100','0x80208100'),
                         ('KD','0x800140','0x80208140'),('KB','0x800180','0x80208180')):
        sha3=sha3.replace(f'.equ {name},{old}',f'.equ {name},{new}')
    source+='\n.align 2\n'+sha3
    # Interrupt frames preserve all GPRs, with original sp restored last.
    registers=[i for i in range(1,32) if i!=2]
    save=['addi sp,sp,-256']+[f'sd x{r},{i*8}(sp)' for i,r in enumerate(registers)]
    restore=[f'ld x{r},{i*8}(sp)' for i,r in enumerate(registers)]+['addi sp,sp,256']
    source=source.replace('.save_all','\n'.join(save)).replace('.restore_all','\n'.join(restore))
    image,symbols=assemble(source,origin=0x80000000,max_bytes=65536)
    binary=elf(image,address=0x7ffff000,entry=symbols['_start'],
               bss_address=0x80010000,bss_bytes=4*1024**2-65536)
    destination=Path(destination)
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open('xb') as output: output.write(binary)
    return {'format':'omega-baremetal-v1','sha256':sha256(binary).hexdigest(),
            'source_sha256':sha256(source.encode()).hexdigest(),'bytes':len(binary),
            'target':'QEMU virt RV64IM, one hart, Sv39, VirtIO MMIO v2',
            'physical_hardware_validated':False}
