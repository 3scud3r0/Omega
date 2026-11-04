_crypto_start:
    ld t0,0(sp)
    li t1,3
    bne t0,t1,syntax_error
    ld s9,16(sp)
    ld s10,24(sp)
    li sp,0x6ff000
    li a0,-100
    mv a1,s10
    li a2,0
    li a3,0
    li a7,56
    ecall
    blt a0,zero,io_error
    li a1,INPUT
    li a2,16384
    call read_all
    mv s8,a0
    mv a0,s9
    la a1,mode_sha3
    call string_equal
    bne a0,zero,crypto_sha3
    mv a0,s9
    la a1,mode_hmac
    call string_equal
    bne a0,zero,crypto_hmac
    mv a0,s9
    la a1,mode_x25519
    call string_equal
    beq a0,zero,syntax_error
    li t0,64
    bne s8,t0,syntax_error
    li a0,INPUT
    call x25519
    j crypto_render
crypto_hmac:
    li t0,32
    bltu s8,t0,syntax_error
    li a0,INPUT
    mv a1,s8
    call hmac_sha3_256
    j crypto_render
crypto_sha3:
    li a0,INPUT
    mv a1,s8
    call sha3_256
crypto_render:
    li t0,INPUT+512
    la t1,hex_digits
    li t2,32
crypto_hex_loop:
    lbu t3,0(a0)
    srli t4,t3,4
    add t4,t4,t1
    lbu t4,0(t4)
    sb t4,0(t0)
    andi t3,t3,15
    add t3,t3,t1
    lbu t3,0(t3)
    sb t3,1(t0)
    addi a0,a0,1
    addi t0,t0,2
    addi t2,t2,-1
    bne t2,zero,crypto_hex_loop
    li t1,10
    sb t1,0(t0)
    li a0,1
    li a1,INPUT+512
    li a2,65
    call write_all
    j program_exit
string_equal:
    lbu t0,0(a0)
    lbu t1,0(a1)
    bne t0,t1,string_unequal
    beq t0,zero,string_same
    addi a0,a0,1
    addi a1,a1,1
    j string_equal
string_unequal:
    li a0,0
    ret
string_same:
    li a0,1
    ret
crypto_reject_zero:
    li s11,6
    j error_exit
mode_sha3:
    .asciz "sha3"
mode_x25519:
    .asciz "x25519"
mode_hmac:
    .asciz "hmac-sha3"
hex_digits:
    .ascii "0123456789abcdef"
.align 2
