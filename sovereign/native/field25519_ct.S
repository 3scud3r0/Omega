# Fixed eight-limb field arithmetic modulo 2^255-19. Every field operation
# executes the same loop bounds/addresses for all canonical operands. No div,
# normalization, lookup by secret, or branch on a secret scalar bit is used.
# Physical latency/cache/speculation noninterference is NOT proved here.
.equ FRED,0x850000
.equ FMRES,0x850100
.equ FMWORK,0x850200
.equ FMBITS,0x850300
.equ FMSELECT,0x850400

field_zero:
    li t0,1
    sd t0,0(a0)
    li t0,8
    sd t0,8(a0)
    li t0,0
field_zero_loop:
    slli t1,t0,3
    add t1,t1,a0
    sd zero,16(t1)
    addi t0,t0,1
    li t1,8
    bne t0,t1,field_zero_loop
    ret
field_one:
    enter
    mv s0,a0
    call field_zero
    li t0,1
    sd t0,16(s0)
    leave
field_copy:
    li t0,10
field_copy_loop:
    ld t1,0(a1)
    sd t1,0(a0)
    addi a0,a0,8
    addi a1,a1,8
    addi t0,t0,-1
    bne t0,zero,field_copy_loop
    ret
field_from_bytes:
    li t0,1
    sd t0,0(a0)
    li t0,8
    sd t0,8(a0)
    li t0,0
field_decode:
    slli t1,t0,2
    add t1,t1,a1
    lwu t1,0(t1)
    slli t2,t0,3
    add t2,t2,a0
    sd t1,16(t2)
    addi t0,t0,1
    li t1,8
    bne t0,t1,field_decode
    ret

# Pre: input <2p; post: canonical [0,p). In-place permitted.
field_reduce:
    li t0,0
    li t1,0
field_subtract_prime:
    slli t2,t0,3
    add t3,t2,a1
    ld t3,16(t3)
    li t4,FP
    add t4,t4,t2
    ld t4,16(t4)
    sub t3,t3,t4
    sub t3,t3,t1
    srli t1,t3,63
    slli t3,t3,32
    srli t3,t3,32
    li t4,FRED
    add t4,t4,t2
    sd t3,0(t4)
    addi t0,t0,1
    li t2,8
    bne t0,t2,field_subtract_prime
    sub a3,zero,t1
    li t0,0
field_select_reduction:
    slli t2,t0,3
    li t3,FRED
    add t3,t3,t2
    ld t3,0(t3)
    add t4,a1,t2
    ld t4,16(t4)
    xor t4,t4,t3
    and t4,t4,a3
    xor t3,t3,t4
    add t4,a0,t2
    sd t3,16(t4)
    addi t0,t0,1
    li t1,8
    bne t0,t1,field_select_reduction
    li t0,1
    sd t0,0(a0)
    li t0,8
    sd t0,8(a0)
    ret
field_add:
    li t0,0
    li t1,0
field_add_loop:
    slli t2,t0,3
    add t3,a1,t2
    ld t3,16(t3)
    add t4,a2,t2
    ld t4,16(t4)
    add t3,t3,t4
    add t3,t3,t1
    srli t1,t3,32
    slli t3,t3,32
    srli t3,t3,32
    add t4,a0,t2
    sd t3,16(t4)
    addi t0,t0,1
    li t2,8
    bne t0,t2,field_add_loop
    mv a1,a0
    j field_reduce
field_sub:
    li t0,0
    li t1,0
field_sub_loop:
    slli t2,t0,3
    add t3,a1,t2
    ld t3,16(t3)
    add t4,a2,t2
    ld t4,16(t4)
    sub t3,t3,t4
    sub t3,t3,t1
    srli t1,t3,63
    slli t3,t3,32
    srli t3,t3,32
    add t4,a0,t2
    sd t3,16(t4)
    addi t0,t0,1
    li t2,8
    bne t0,t2,field_sub_loop
    sub a3,zero,t1
    li t0,0
    li t1,0
field_add_prime_mask:
    slli t2,t0,3
    li t3,FP
    add t3,t3,t2
    ld t3,16(t3)
    and t3,t3,a3
    add t4,a0,t2
    ld t5,16(t4)
    add t3,t3,t5
    add t3,t3,t1
    srli t1,t3,32
    slli t3,t3,32
    srli t3,t3,32
    sd t3,16(t4)
    addi t0,t0,1
    li t2,8
    bne t0,t2,field_add_prime_mask
    li t0,1
    sd t0,0(a0)
    li t0,8
    sd t0,8(a0)
    ret
field_mul:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    li a0,FMWORK
    call field_copy
    li a0,FMBITS
    mv a1,s2
    call field_copy
    li a0,FMRES
    call field_zero
    li s3,0
field_mul_bit:
    srli t0,s3,5
    slli t0,t0,3
    li t1,FMBITS
    add t0,t0,t1
    ld t0,16(t0)
    andi t1,s3,31
    srl t0,t0,t1
    andi t0,t0,1
    sub t0,zero,t0
    li t1,0
field_mul_select:
    slli t2,t1,3
    li t3,FMWORK
    add t3,t3,t2
    ld t3,16(t3)
    and t3,t3,t0
    li t4,FMSELECT
    add t4,t4,t2
    sd t3,16(t4)
    addi t1,t1,1
    li t2,8
    bne t1,t2,field_mul_select
    li a0,FMRES
    li a1,FMRES
    li a2,FMSELECT
    call field_add
    li a0,FMWORK
    li a1,FMWORK
    li a2,FMWORK
    call field_add
    addi s3,s3,1
    li t0,255
    bne s3,t0,field_mul_bit
    mv a0,s0
    li a1,FMRES
    call field_copy
    leave
field_cswap:
    sub t0,zero,a0
    li t1,10
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
