"""Small audited RV64IM assembler and ELF writer. No C, GNU as or linker.

The bootstrap utility runs in Python; emitted executables contain only RV64
instructions and static data. It is not the compiler for all Omega syntax.
"""
import ast
import re
import struct

REGISTERS = {f'x{i}':i for i in range(32)}
REGISTERS.update(dict(zip(('zero','ra','sp','gp','tp','t0','t1','t2','s0','s1',
                          'a0','a1','a2','a3','a4','a5','a6','a7','s2','s3','s4','s5',
                          's6','s7','s8','s9','s10','s11','t3','t4','t5','t6'),range(32))))
CSRS = {'mstatus':0x300,'mie':0x304,'mtvec':0x305,'mscratch':0x340,'mepc':0x341,
        'mcause':0x342,'mip':0x344,'medeleg':0x302,'mideleg':0x303,'pmpcfg0':0x3a0,
        'pmpaddr0':0x3b0,'sstatus':0x100,'sie':0x104,'stvec':0x105,'sscratch':0x140,
        'sepc':0x141,'scause':0x142,'stval':0x143,'sip':0x144,'satp':0x180}


def expression(text,symbols):
    tree=ast.parse(text,mode='eval')
    def visit(node):
        if isinstance(node,ast.Constant) and type(node.value) is int:return node.value
        if isinstance(node,ast.Name) and node.id in symbols:return symbols[node.id]
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.USub,ast.UAdd,ast.Invert)):
            n=visit(node.operand)
            return -n if isinstance(node.op,ast.USub) else ~n if isinstance(node.op,ast.Invert) else n
        if isinstance(node,ast.BinOp):
            a,b=visit(node.left),visit(node.right)
            if isinstance(node.op,ast.Add):return a+b
            if isinstance(node.op,ast.Sub):return a-b
            if isinstance(node.op,ast.Mult):return a*b
            if isinstance(node.op,ast.LShift) and 0<=b<64:return a<<b
            if isinstance(node.op,ast.RShift) and 0<=b<64:return a>>b
            if isinstance(node.op,ast.BitAnd):return a&b
            if isinstance(node.op,ast.BitOr):return a|b
        raise ValueError('Unsupported assembler expression: '+text)
    return visit(tree.body)


def reg(name):
    if name not in REGISTERS:raise ValueError('Unknown RV register '+name)
    return REGISTERS[name]


def signed(value,bits):
    if not -(1<<(bits-1))<=value<(1<<(bits-1)):raise ValueError('RV immediate range')
    return value&((1<<bits)-1)


def rtype(op,rd,rs1,rs2,f3=0,f7=0):
    return op|rd<<7|f3<<12|rs1<<15|rs2<<20|f7<<25


def itype(op,rd,rs1,imm,f3=0):
    return op|rd<<7|f3<<12|rs1<<15|signed(imm,12)<<20


def jump(rd,delta):
    if delta%2:raise ValueError('Unaligned JAL')
    bits=signed(delta,21)
    return 0x6f|rd<<7|((bits>>20)&1)<<31|((bits>>1)&1023)<<21|((bits>>11)&1)<<20|((bits>>12)&255)<<12


def branch(rs1,rs2,condition,delta):
    if delta%2:raise ValueError('Unaligned branch')
    v=signed(delta,13)
    return 0x63|condition<<12|rs1<<15|rs2<<20|((v>>12)&1)<<31|((v>>5)&63)<<25|((v>>1)&15)<<8|((v>>11)&1)<<7


def li(rd,value):
    value=((value+(1<<63))%(1<<64))-(1<<63)
    parts=[]
    for _ in range(5):
        low=(value+2048)%4096-2048
        parts.append(low);value=(value-low)//4096
    words=[itype(0x13,rd,0,value)]
    for low in reversed(parts):
        words += [itype(0x13,rd,rd,12,1),itype(0x13,rd,rd,low)]
    return words


def assemble(source,origin=0x401000,max_bytes=1024**2):
    if type(source) is not str or len(source)>512*1024:raise ValueError('Assembly source budget')
    statements=[];symbols={};pc=origin
    for number,raw in enumerate(source.splitlines(),1):
        line=raw.split('#',1)[0].strip()
        if not line:continue
        if line.endswith(':'):
            name=line[:-1]
            if not re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',name) or name in symbols:raise ValueError('Label')
            symbols[name]=pc;continue
        fields=line.split(None,1);op=fields[0];args=fields[1].strip() if len(fields)>1 else ''
        if op in ('.global','.text','.data','.section'):continue
        if op=='.equ':
            name,value=args.split(',',1)
            if name.strip() in symbols:raise ValueError('Duplicate constant')
            symbols[name.strip()]=expression(value.strip(),symbols);continue
        if op=='.align':size=(-pc)%(1<<int(args,0))
        elif op in ('.ascii','.asciz'):
            value=ast.literal_eval(args)
            if type(value) is not str:raise ValueError('ASCII string required')
            size=len(value.encode('ascii'))+(op=='.asciz')
        elif op=='.zero':size=int(args,0)
        elif op=='.quad':size=8*len(args.split(','))
        elif op=='.word':size=4*len(args.split(','))
        elif op in ('li','la'):size=44
        elif op=='enter':size=56
        elif op=='leave':size=60
        elif op in ('beq','bne','blt','bge','bltu','bgeu'):size=8
        else:size=4
        if size<0 or pc-origin+size>max_bytes:raise ValueError('Assembler image budget')
        statements.append((pc,number,op,args,size));pc+=size
    output=bytearray()
    for pc,number,op,raw,size in statements:
        a=[s.strip() for s in raw.split(',')]
        value=lambda text:expression(text,{**CSRS,**symbols})
        words=[]
        try:
            if op in ('.ascii','.asciz'):
                output.extend(ast.literal_eval(raw).encode('ascii')+(b'\0' if op=='.asciz' else b''));continue
            if op in ('.align','.zero'):output.extend(bytes(size));continue
            if op in ('.word','.quad'):
                fmt='<I' if op=='.word' else '<Q'
                for text in a:output.extend(struct.pack(fmt,value(text)))
                continue
            if op in ('li','la'):words=li(reg(a[0]),value(a[1]))
            elif op in ('enter','leave'):
                saved=[1,8,9,*range(18,28)]
                if op=='enter':
                    words=[itype(0x13,2,2,-112)]
                    for index,register in enumerate(saved):
                        imm=index*8;words.append(0x23|(imm&31)<<7|3<<12|2<<15|register<<20|(imm>>5)<<25)
                else:
                    words=[itype(3,register,2,index*8,3) for index,register in enumerate(saved)]
                    words += [itype(0x13,2,2,112),itype(0x67,0,1,0)]
            elif op in ('add','sub','mul','mulh','mulhu','div','divu','rem','remu','and','or','xor','slt','sltu','sll','srl','sra'):
                f3={'add':0,'sub':0,'mul':0,'mulh':1,'mulhu':3,'div':4,'divu':5,'rem':6,'remu':7,
                    'and':7,'or':6,'xor':4,'slt':2,'sltu':3,'sll':1,'srl':5,'sra':5}[op]
                f7=1 if op in ('mul','mulh','mulhu','div','divu','rem','remu') else 32 if op in ('sub','sra') else 0
                words=[rtype(0x33,reg(a[0]),reg(a[1]),reg(a[2]),f3,f7)]
            elif op in ('addi','andi','ori','xori','sltiu','slli','srli','srai'):
                imm=value(a[2]);f3={'addi':0,'andi':7,'ori':6,'xori':4,'sltiu':3,'slli':1,'srli':5,'srai':5}[op]
                if op in ('slli','srli','srai'):
                    if not 0<=imm<64:raise ValueError('Shift immediate')
                    if op=='srai':imm+=1024
                words=[itype(0x13,reg(a[0]),reg(a[1]),imm,f3)]
            elif op in ('ld','lw','lwu','lbu','lhu','lb','lh','sd','sw','sb','sh'):
                match=re.fullmatch(r'(.+)\((\w+)\)',a[1])
                if not match:raise ValueError('Memory operand')
                imm=value(match[1]);base=reg(match[2]);target=reg(a[0])
                if op[0]=='l':words=[itype(3,target,base,imm,{'lb':0,'lh':1,'lw':2,'ld':3,'lbu':4,'lhu':5,'lwu':6}[op])]
                else:
                    bits=signed(imm,12);words=[0x23|(bits&31)<<7|{'sb':0,'sh':1,'sw':2,'sd':3}[op]<<12|base<<15|target<<20|(bits>>5)<<25]
            elif op in ('beq','bne','blt','bge','bltu','bgeu'):
                condition={'beq':0,'bne':1,'blt':4,'bge':5,'bltu':6,'bgeu':7}[op]
                words=[branch(reg(a[0]),reg(a[1]),condition^1,8),jump(0,value(a[2])-(pc+4))]
            elif op in ('j','call'):words=[jump(0 if op=='j' else 1,value(a[0])-pc)]
            elif op=='ret':words=[itype(0x67,0,1,0)]
            elif op=='mv':words=[itype(0x13,reg(a[0]),reg(a[1]),0)]
            elif op=='jalr':words=[itype(0x67,reg(a[0]),reg(a[1]),value(a[2]))]
            elif op in ('csrr','csrw','csrs','csrc'):
                if op=='csrr':rd,csr,rs1,f3=reg(a[0]),value(a[1]),0,2
                else:rd,csr,rs1,f3=0,value(a[0]),reg(a[1]),{'csrw':1,'csrs':2,'csrc':3}[op]
                if not 0<=csr<4096:raise ValueError('CSR')
                words=[0x73|rd<<7|f3<<12|rs1<<15|csr<<20]
            elif op in ('ecall','mret','sret','wfi','sfence.vma','fence','nop'):
                words=[{'ecall':0x73,'mret':0x30200073,'sret':0x10200073,'wfi':0x10500073,
                        'sfence.vma':0x12000073,'fence':0x0ff0000f,'nop':0x13}[op]]
            else:raise ValueError('Unknown instruction '+op)
            if len(words)*4!=size:raise ValueError('Assembler sizing mismatch')
            output.extend(b''.join(struct.pack('<I',word) for word in words))
        except (ValueError,KeyError,IndexError,TypeError) as exc:
            raise ValueError(f'Assembly line {number}: {op} {raw}: {exc}') from exc
    return bytes(output),symbols


def elf(image,*,address=0x400000,entry=0x401000,bss_address=0x600000,bss_bytes=64*1024**2):
    if len(image)>1024**2 or bss_bytes>128*1024**2:raise ValueError('ELF resource bounds')
    ident=b'\x7fELF\x02\x01\x01'+bytes(9)
    header=ident+struct.pack('<HHIQQQIHHHHHH',2,243,1,entry,64,0,0,64,56,3,0,0,0)
    size=4096+len(image)
    segments=(struct.pack('<IIQQQQQQ',1,5,0,address,address,size,size,4096)+
              struct.pack('<IIQQQQQQ',1,6,0,bss_address,bss_address,0,bss_bytes,4096)+
              struct.pack('<IIQQQQQQ',0x6474e551,6,0,0,0,0,0,16))
    return header+segments+bytes(4096-len(header)-len(segments))+image
