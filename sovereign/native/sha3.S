# SHA3-256, FIPS 202 Keccak-f[1600]. All data-dependent operations are bitwise;
# round counts, rotation offsets and indices depend only on public parameters.
# This is not a claim of audited physical side-channel resistance.
.equ KS,0x800000
.equ KC,0x800100
.equ KD,0x800140
.equ KB,0x800180
.equ HINNER,0x841000
.equ HOUTER,0x846000

# RFC 2104 HMAC using SHA3-256 and a fixed 32-byte key, followed by the message.
hmac_sha3_256:
    enter
    mv s0,a0
    mv s1,a1
    li s2,0
hmac_key:
    li t0,0
    li t1,32
    bgeu s2,t1,hmac_pad
    add t0,s0,s2
    lbu t0,0(t0)
hmac_pad:
    li t1,HINNER
    add t1,t1,s2
    xori t2,t0,54
    sb t2,0(t1)
    li t1,HOUTER
    add t1,t1,s2
    xori t2,t0,92
    sb t2,0(t1)
    addi s2,s2,1
    li t0,136
    bne s2,t0,hmac_key
    addi s1,s1,-32
    addi s0,s0,32
    li t0,HINNER+136
    li t1,0
hmac_message:
    bgeu t1,s1,hmac_hash_inner
    add t2,s0,t1
    lbu t2,0(t2)
    add t3,t0,t1
    sb t2,0(t3)
    addi t1,t1,1
    j hmac_message
hmac_hash_inner:
    li a0,HINNER
    addi a1,s1,136
    call sha3_256
    li t0,HOUTER+136
    li t1,4
hmac_digest:
    ld t2,0(a0)
    sd t2,0(t0)
    addi a0,a0,8
    addi t0,t0,8
    addi t1,t1,-1
    bne t1,zero,hmac_digest
    li a0,HOUTER
    li a1,168
    call sha3_256
    leave

sha3_256:
    enter
    mv s0,a0
    mv s1,a1
    li s2,0
    li t0,KS
    li t1,25
sha3_clear:
    sd zero,0(t0)
    addi t0,t0,8
    addi t1,t1,-1
    bne t1,zero,sha3_clear
sha3_absorb:
    beq s1,zero,sha3_padding
    li t0,KS
    add t0,t0,s2
    lbu t1,0(s0)
    lbu t2,0(t0)
    xor t1,t1,t2
    sb t1,0(t0)
    addi s0,s0,1
    addi s1,s1,-1
    addi s2,s2,1
    li t0,136
    bne s2,t0,sha3_absorb
    call keccak
    li s2,0
    j sha3_absorb
sha3_padding:
    li t0,KS
    add t0,t0,s2
    lbu t1,0(t0)
    xori t1,t1,6
    sb t1,0(t0)
    li t0,KS+135
    lbu t1,0(t0)
    xori t1,t1,128
    sb t1,0(t0)
    call keccak
    li a0,KS
    leave

keccak:
    enter
    li s0,0
keccak_round:
    li s1,0
keccak_c:
    slli t0,s1,3
    li t1,KS
    add t1,t1,t0
    ld t2,0(t1)
    ld t3,40(t1)
    xor t2,t2,t3
    ld t3,80(t1)
    xor t2,t2,t3
    ld t3,120(t1)
    xor t2,t2,t3
    ld t3,160(t1)
    xor t2,t2,t3
    li t1,KC
    add t1,t1,t0
    sd t2,0(t1)
    addi s1,s1,1
    li t0,5
    bne s1,t0,keccak_c
    li s1,0
keccak_d:
    addi t0,s1,4
    li t1,5
    remu t0,t0,t1
    slli t0,t0,3
    li t2,KC
    add t0,t0,t2
    ld t3,0(t0)
    addi t0,s1,1
    remu t0,t0,t1
    slli t0,t0,3
    add t0,t0,t2
    ld t4,0(t0)
    slli t5,t4,1
    srli t4,t4,63
    or t4,t4,t5
    xor t3,t3,t4
    li t0,KD
    slli t1,s1,3
    add t0,t0,t1
    sd t3,0(t0)
    addi s1,s1,1
    li t0,5
    bne s1,t0,keccak_d
    li s1,0
keccak_theta:
    li t0,5
    remu t0,s1,t0
    slli t0,t0,3
    li t1,KD
    add t0,t0,t1
    ld t2,0(t0)
    slli t0,s1,3
    li t1,KS
    add t0,t0,t1
    ld t3,0(t0)
    xor t2,t2,t3
    sd t2,0(t0)
    addi s1,s1,1
    li t0,25
    bne s1,t0,keccak_theta
    li s1,0
keccak_rho_pi:
    li t0,5
    remu t1,s1,t0
    divu t2,s1,t0
    slli t3,t1,1
    li t4,3
    mul t4,t2,t4
    add t3,t3,t4
    remu t3,t3,t0
    mul t3,t3,t0
    add t3,t3,t2
    slli t3,t3,3
    li t4,KB
    add t3,t3,t4
    la t0,keccak_rotations
    add t0,t0,s1
    lbu t0,0(t0)
    li t1,KS
    slli t2,s1,3
    add t1,t1,t2
    ld t1,0(t1)
    sll t2,t1,t0
    li t4,64
    sub t4,t4,t0
    srl t1,t1,t4
    or t1,t1,t2
    sd t1,0(t3)
    addi s1,s1,1
    li t0,25
    bne s1,t0,keccak_rho_pi
    li s1,0
keccak_chi:
    li t0,5
    remu t1,s1,t0
    sub t2,s1,t1
    addi t3,t1,1
    remu t3,t3,t0
    add t3,t3,t2
    slli t3,t3,3
    li t4,KB
    add t3,t3,t4
    ld t3,0(t3)
    xori t3,t3,-1
    addi t1,t1,2
    remu t1,t1,t0
    add t1,t1,t2
    slli t1,t1,3
    add t1,t1,t4
    ld t1,0(t1)
    and t3,t3,t1
    slli t0,s1,3
    add t1,t0,t4
    ld t1,0(t1)
    xor t3,t3,t1
    li t1,KS
    add t0,t0,t1
    sd t3,0(t0)
    addi s1,s1,1
    li t0,25
    bne s1,t0,keccak_chi
    la t0,keccak_constants
    slli t1,s0,3
    add t0,t0,t1
    ld t0,0(t0)
    li t1,KS
    ld t2,0(t1)
    xor t0,t0,t2
    sd t0,0(t1)
    addi s0,s0,1
    li t0,24
    bne s0,t0,keccak_round
    leave
.align 3
keccak_constants:
    .quad 0x1,0x8082,0x800000000000808a,0x8000000080008000
    .quad 0x808b,0x80000001,0x8000000080008081,0x8000000000008009
    .quad 0x8a,0x88,0x80008009,0x8000000a
    .quad 0x8000808b,0x800000000000008b,0x8000000000008089,0x8000000000008003
    .quad 0x8000000000008002,0x8000000000000080,0x800a,0x800000008000000a
    .quad 0x8000000080008081,0x8000000000008080,0x80000001,0x8000000080008008
keccak_rotations:
    .ascii "\x00\x01\x3e\x1c\x1b\x24\x2c\x06\x37\x14\x03\x0a\x2b\x19\x27\x29\x2d\x0f\x15\x08\x12\x02\x3d\x38\x0e"
.align 2
