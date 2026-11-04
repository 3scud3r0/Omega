# RFC 7748 X25519 reference using our own base-2^32 field arithmetic.
# WARNING: limb normalization and binary division have variable execution time.
# Research/differential implementation, NOT suitable for secret production keys.
.equ FP,0x820000
.equ FX1,FP+BIG
.equ FX2,FX1+BIG
.equ FZ2,FX2+BIG
.equ FX3,FZ2+BIG
.equ FZ3,FX3+BIG
.equ FA,FZ3+BIG
.equ FAA,FA+BIG
.equ FB,FAA+BIG
.equ FBB,FB+BIG
.equ FE,FBB+BIG
.equ FC,FE+BIG
.equ FD,FC+BIG
.equ FDA,FD+BIG
.equ FCB,FDA+BIG
.equ FT1,FCB+BIG
.equ FT2,FT1+BIG
.equ FA24,FT2+BIG
.equ FRESULT,FA24+BIG
.equ FWIDE,0x830000
.equ FQUOT,FWIDE+BIG
.equ FREM,FQUOT+BIG

field_reduce:
    enter
    mv s0,a0
    mv a2,a1
    li a0,FQUOT
    li a1,FREM
    li a3,FP
    call big_divmod
    mv a0,s0
    li a1,FREM
    call big_copy
    leave
field_add:
    enter
    mv s0,a0
    li a0,FWIDE
    call mag_add
    mv a0,s0
    li a1,FWIDE
    call field_reduce
    leave
field_sub:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    li a0,FWIDE
    li a2,FP
    call mag_add
    li a0,FWIDE
    li a1,FWIDE
    mv a2,s2
    call mag_sub
    mv a0,s0
    li a1,FWIDE
    call field_reduce
    leave
field_mul:
    enter
    mv s0,a0
    li a0,FWIDE
    call big_mul
    mv a0,s0
    li a1,FWIDE
    call field_reduce
    leave
field_cswap:
    sub t0,zero,a0
    li t1,BIG>>3
field_cswap_loop:
    ld t2,0(a1)
    ld t3,0(a2)
    xor t4,t2,t3
    and t4,t4,t0
    xor t2,t2,t4
    xor t3,t3,t4
    sd t2,0(a1)
    sd t3,0(a2)
    addi a1,a1,8
    addi a2,a2,8
    addi t1,t1,-1
    bne t1,zero,field_cswap_loop
    ret
field_from_bytes:
    enter
    mv s0,a0
    mv s1,a1
    li t0,1
    sd t0,0(s0)
    li t0,8
    sd t0,8(s0)
    li t0,0
field_decode_loop:
    slli t1,t0,2
    add t1,t1,s1
    lwu t1,0(t1)
    slli t2,t0,3
    add t2,t2,s0
    sd t1,16(t2)
    addi t0,t0,1
    li t1,8
    bne t0,t1,field_decode_loop
    mv a0,s0
    call big_trim
    leave

x25519:
    enter
    mv s0,a0
    lbu t0,0(s0)
    andi t0,t0,248
    sb t0,0(s0)
    lbu t0,31(s0)
    andi t0,t0,127
    ori t0,t0,64
    sb t0,31(s0)
    lbu t0,63(s0)
    andi t0,t0,127
    sb t0,63(s0)
    li a0,FP
    la a1,prime_le
    call field_from_bytes
    li a0,FWIDE
    addi a1,s0,32
    call field_from_bytes
    li a0,FX1
    li a1,FWIDE
    call field_reduce
    li a0,FX2
    call big_one
    li a0,FZ2
    call big_zero
    .fcopy FX3,FX1
    li a0,FZ3
    call big_one
    li a0,FA24
    la a1,a24_decimal
    call big_decimal
    li s1,254
    li s2,0
x25519_ladder:
    srli t0,s1,3
    add t0,t0,s0
    lbu t0,0(t0)
    andi t1,s1,7
    srl t0,t0,t1
    andi s3,t0,1
    xor s2,s2,s3
    mv a0,s2
    li a1,FX2
    li a2,FX3
    call field_cswap
    mv a0,s2
    li a1,FZ2
    li a2,FZ3
    call field_cswap
    mv s2,s3
    .fadd FA,FX2,FZ2
    .fmul FAA,FA,FA
    .fsub FB,FX2,FZ2
    .fmul FBB,FB,FB
    .fsub FE,FAA,FBB
    .fadd FC,FX3,FZ3
    .fsub FD,FX3,FZ3
    .fmul FDA,FD,FA
    .fmul FCB,FC,FB
    .fadd FT1,FDA,FCB
    .fmul FX3,FT1,FT1
    .fsub FT1,FDA,FCB
    .fmul FT2,FT1,FT1
    .fmul FZ3,FX1,FT2
    .fmul FX2,FAA,FBB
    .fmul FT1,FA24,FE
    .fadd FT2,FAA,FT1
    .fmul FZ2,FE,FT2
    addi s1,s1,-1
    bge s1,zero,x25519_ladder
    mv a0,s2
    li a1,FX2
    li a2,FX3
    call field_cswap
    mv a0,s2
    li a1,FZ2
    li a2,FZ3
    call field_cswap
    li a0,FT1
    call big_one
    li s1,254
x25519_inverse:
    .fmul FT2,FT1,FT1
    .fcopy FT1,FT2
    li t0,2
    beq s1,t0,x25519_inverse_next
    li t0,4
    beq s1,t0,x25519_inverse_next
    .fmul FT2,FT1,FZ2
    .fcopy FT1,FT2
x25519_inverse_next:
    addi s1,s1,-1
    bge s1,zero,x25519_inverse
    .fmul FRESULT,FX2,FT1
    li t0,FRESULT
    ld t1,8(t0)
    beq t1,zero,crypto_reject_zero
    # Zero the destination, then encode only active limbs; unused storage may
    # contain earlier operands and must never leak into the public result.
    li s1,INPUT+256
    sd zero,0(s1)
    sd zero,8(s1)
    sd zero,16(s1)
    sd zero,24(s1)
    li t2,0
x25519_encode:
    bgeu t2,t1,x25519_return
    slli t3,t2,3
    add t3,t3,t0
    ld t3,16(t3)
    slli t4,t2,2
    add t4,t4,s1
    sw t3,0(t4)
    addi t2,t2,1
    j x25519_encode
x25519_return:
    mv a0,s1
    leave
.align 2
prime_le:
    .word 0xffffffed,0xffffffff,0xffffffff,0xffffffff
    .word 0xffffffff,0xffffffff,0xffffffff,0x7fffffff
a24_decimal:
    .asciz "121665"
.align 2
