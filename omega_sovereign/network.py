"""Explicit two-VM loopback experiment. No traffic leaves the executor.

The guest is RV64 machine code with static VirtIO buffers. Host Python/QEMU
only build and supervise; they do not parse or authenticate the guest packets.
This bounded PSK handshake is a test protocol, not TLS or a general socket API.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import struct
import time
from .native import ROOT,SOURCES
from .rv64 import assemble,elf
from .hardware import tool
from omega_platform.sandbox import trusted
from omega_platform.budget import Budget


def build(destination,role,*,key,nonce):
    if type(role) is not int or role not in (0,1) or type(key) is not bytes or len(key)!=32 or type(nonce) is not bytes or len(nonce)!=16:
        raise ValueError('Explicit role 0/1, key32 and unique nonce16 required')
    # Reuse audited UART helpers; old boot code remains unreachable at entry.
    source=(SOURCES/'sovereign/baremetal/boot.S').read_text()
    # QEMU virt's -bios none reset trampoline jumps to the kernel load base.
    source=source.replace('_start:\n','_start:\n    j _net_start\n',1)
    registers=[i for i in range(1,32) if i!=2]
    source=source.replace('.save_all','\n'.join(['addi sp,sp,-256']+[f'sd x{r},{i*8}(sp)' for i,r in enumerate(registers)]))
    source=source.replace('.restore_all','\n'.join([f'ld x{r},{i*8}(sp)' for i,r in enumerate(registers)]+['addi sp,sp,256']))
    sha3=(SOURCES/'sovereign/native/sha3.S').read_text()
    for name,old,new in (('KS','0x800000','0x80208000'),('KC','0x800100','0x80208100'),('KD','0x800140','0x80208140'),('KB','0x800180','0x80208180'),('HINNER','0x841000','0x80230000'),('HOUTER','0x846000','0x80235000')):
        sha3=sha3.replace(f'.equ {name},{old}',f'.equ {name},{new}')
    source+='\n.align 2\n'+sha3+f'\n.equ ROLE,{role}\n'+(SOURCES/'sovereign/baremetal/virtio_net.S').read_text()
    ip=struct.pack('!BBHHHBBH4s4s',69,0,97,0,16384,64,17,0,bytes((10,0,0,1+role)),bytes((10,0,0,2-role)))
    frame=bytes(12)+b'\xff'*6+bytes((2,0,0,0,0,1+role))+b'\x08\x00'+ip+struct.pack('!HHHH',23456,23456,77,0)+struct.pack('!I',65)+bytes(65)
    def data(label,raw):
        raw+=bytes((-len(raw))%4)
        return '\n.align 2\n'+label+':\n.word '+','.join(str(int.from_bytes(raw[i:i+4],'little')) for i in range(0,len(raw),4))+'\n'
    source+=data('net_frame_template',frame)+data('TEST_KEY',key)+data('LOCAL_NONCE',nonce)
    image,symbols=assemble(source,origin=0x80000000,max_bytes=65536)
    binary=elf(image,address=0x7ffff000,entry=symbols['_net_start'],bss_address=0x80010000,bss_bytes=4*1024**2-65536)
    destination=Path(destination)
    with destination.open('xb') as out:out.write(binary)
    return {'sha256':sha256(binary).hexdigest(),'source_sha256':sha256(source.encode()).hexdigest(),'bytes':len(binary),'role':role}


def experiment(directory,*,tamper_key=False):
    root=Path(directory).resolve()
    if root.exists():raise FileExistsError(root)
    root.mkdir(parents=True)
    key=sha256(b'omega-network-test-key-not-production').digest()
    builds=[build(root/f'node-{i}.elf',i,key=(bytes(32) if tamper_key and i else key),nonce=sha256(f'omega-test-challenge-{i}'.encode()).digest()[:16]) for i in range(2)]
    with socket.socket() as reservation:
        reservation.bind(('127.0.0.1',0));port=reservation.getsockname()[1]
    prefix=ROOT.parent/'.tools/sovereign/usr/lib/x86_64-linux-gnu'
    # trusted() deliberately preserves the trusted-tool environment. Keep the
    # relocation command-local through env instead of changing process globals.
    commands=[]
    for i in range(2):
        network=f'socket,id=n,{"listen" if i==0 else "connect"}=127.0.0.1:{port}'
        command=[tool('qemu-system-riscv64'),'-machine','virt','-m','128M','-smp','1','-bios','none','-display','none','-serial','stdio','-monitor','none','-no-reboot',
                 '-kernel',str(root/f'node-{i}.elf'),'-global','virtio-mmio.force-legacy=false','-netdev',network,'-device','virtio-net-device,netdev=n']
        if prefix.is_dir():command=['/usr/bin/env','LD_LIBRARY_PATH='+str(prefix),*command]
        commands.append(command)
    budget=Budget(wall_seconds=12,cpu_seconds=10,memory_bytes=2*1024**3)
    with ThreadPoolExecutor(max_workers=2) as pool:
        server=pool.submit(trusted,commands[0],budget=budget)
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            lines=Path('/proc/net/tcp').read_text().splitlines()[1:]
            if any(line.split()[1].endswith(f':{port:04X}') and line.split()[3]=='0A' for line in lines):break
            if server.done():raise RuntimeError('Network server exited before listen: '+server.result().stderr)
            time.sleep(.01)
        else:raise TimeoutError('Local QEMU listener not ready')
        client=pool.submit(trusted,commands[1],budget=budget)
        results=[server.result(),client.result()]
    report={'format':'omega-two-baremetal-nodes-1','builds':builds,'nodes':[asdict(r) for r in results],
            'authenticated':all(r.ok and 'OMEGA VIRTIO-NET MUTUAL HMAC PASS' in r.stdout for r in results),
            'physical_hardware':False,'protocol':'bounded IPv4/UDP PSK HMAC handshake; no encryption',
            'production_approved':False,'test_key_tampered':tamper_key}
    (root/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
