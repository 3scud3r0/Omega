# Two-queue VirtIO-net MMIO v2, one static 2KiB descriptor per queue.
# Test protocol: Ethernet/IPv4/UDP + four-byte framing + PSK HMAC-SHA3-256.
# ROLE, LOCAL_NONCE and TEST_KEY are supplied by the builder.
.equ NRX,0x80210000
.equ NTX,0x80211000
.equ NCTRL,0x80212000
.equ NCACHE,0x80213000
.equ NAUTH,0x80214000
.equ NPSEUDO,0x80215000
.equ RING0,0x80216000
.equ RING1,0x80216800

_net_start:
    li sp,0x8001f000
    li t0,NCTRL
    sd zero,0(t0)
    sd zero,8(t0)
    sd zero,24(t0)
    call net_init
    li t0,ROLE
    bne t0,zero,net_receive
    # Allow the peer's QEMU socket backend to connect before first transmission.
    li t0,0x0200bff8
    ld t1,0(t0)
    li t2,2500000
    add t1,t1,t2
net_connect_wait:
    ld t2,0(t0)
    bltu t2,t1,net_connect_wait
    li a0,1
    call net_send
    li t0,NCTRL
    li t1,1
    sd t1,24(t0)
net_receive:
    li s0,100000000
net_rx_poll:
    li t0,RING0+258
    lhu t1,0(t0)
    li t0,NCTRL
    ld t2,0(t0)
    bne t1,t2,net_rx_ready
    addi s0,s0,-1
    bne s0,zero,net_rx_poll
    j net_fail
net_rx_ready:
    # Exactly one outstanding descriptor; used ring wraps at eight entries.
    andi t2,t2,7
    slli t2,t2,3
    li t0,RING0+264
    add t0,t0,t2
    lw t1,0(t0)
    li t2,123
    bne t1,t2,net_fail
    li a0,NRX+12+14
    li a1,20
    call net_checksum
    bne a0,zero,net_fail
    li a0,NRX+12
    call net_udp_checksum
    bne a0,zero,net_fail
    li t0,NRX+12
    lbu t1,12(t0)
    li t2,8
    bne t1,t2,net_fail
    lbu t1,13(t0)
    bne t1,zero,net_fail
    lbu t1,14(t0)
    li t2,69
    bne t1,t2,net_fail
    lbu t1,23(t0)
    li t2,17
    bne t1,t2,net_fail
    lbu t1,45(t0)
    li t2,65
    bne t1,t2,net_fail
    lbu t1,42(t0)
    lbu t2,43(t0)
    or t1,t1,t2
    lbu t2,44(t0)
    or t1,t1,t2
    bne t1,zero,net_fail
    lbu t1,16(t0)
    bne t1,zero,net_fail
    lbu t1,17(t0)
    li t2,97
    bne t1,t2,net_fail
    lbu t1,38(t0)
    bne t1,zero,net_fail
    lbu t1,39(t0)
    li t2,77
    bne t1,t2,net_fail
    # Verify MAC over kind + both nonces, before consuming state or replying.
    la a0,TEST_KEY
    li a1,NAUTH
    li a2,32
    call net_copy
    li a0,NRX+12+46
    li a1,NAUTH+32
    li a2,33
    call net_copy
    li a0,NAUTH
    li a1,65
    call hmac_sha3_256
    li a1,NRX+12+79
    li a2,32
    call net_equal
    beq a0,zero,net_fail
    li t0,NRX+12+46
    lbu s1,0(t0)
    li t0,ROLE
    beq t0,zero,net_client_reply
    li t0,1
    bne s1,t0,net_server_finish
    li t0,NCTRL
    ld t1,24(t0)
    bne t1,zero,net_fail
    li t1,1
    sd t1,24(t0)
    # Remember client's challenge; bind our independent nonce in the reply.
    li a0,NRX+12+47
    li a1,NCACHE
    li a2,16
    call net_copy
    call net_rx_rearm
    li a0,2
    call net_send
    j net_receive
net_server_finish:
    li t0,NCTRL
    ld t1,24(t0)
    li t2,1
    bne t1,t2,net_fail
    li t0,3
    bne s1,t0,net_fail
    li a0,NRX+12+47
    li a1,NCACHE
    li a2,16
    call net_equal
    beq a0,zero,net_fail
    li a0,NRX+12+63
    la a1,LOCAL_NONCE
    li a2,16
    call net_equal
    beq a0,zero,net_fail
    j net_pass
net_client_reply:
    li t0,2
    bne s1,t0,net_fail
    li a0,NRX+12+47
    la a1,LOCAL_NONCE
    li a2,16
    call net_equal
    beq a0,zero,net_fail
    li a0,NRX+12+63
    li a1,NCACHE
    li a2,16
    call net_copy
    li a0,3
    call net_send
net_pass:
    la a0,net_pass_message
    call puts
    li t0,0x100000
    li t1,0x5555
    sw t1,0(t0)
    j halt
net_fail:
    la a0,net_fail_message
    call puts
    li t0,0x100000
    li t1,0x3333
    sw t1,0(t0)
    j halt

net_copy:
    beq a2,zero,net_copy_done
    lbu t0,0(a0)
    sb t0,0(a1)
    addi a0,a0,1
    addi a1,a1,1
    addi a2,a2,-1
    j net_copy
net_copy_done:
    ret
net_equal:
    li t0,0
net_equal_loop:
    lbu t1,0(a0)
    lbu t2,0(a1)
    xor t1,t1,t2
    or t0,t0,t1
    addi a0,a0,1
    addi a1,a1,1
    addi a2,a2,-1
    bne a2,zero,net_equal_loop
    sltiu a0,t0,1
    ret
net_checksum:
    li t0,0
net_checksum_loop:
    lbu t1,0(a0)
    lbu t2,1(a0)
    slli t1,t1,8
    or t1,t1,t2
    add t0,t0,t1
    addi a0,a0,2
    addi a1,a1,-2
    bne a1,zero,net_checksum_loop
    srli t1,t0,16
    li t2,65535
    and t0,t0,t2
    add t0,t0,t1
    srli t1,t0,16
    and t0,t0,t2
    add t0,t0,t1
    xor a0,t0,t2
    ret
net_udp_checksum:
    enter
    mv s0,a0
    addi a0,s0,26
    li a1,NPSEUDO
    li a2,8
    call net_copy
    li t0,NPSEUDO
    sb zero,8(t0)
    li t1,17
    sb t1,9(t0)
    sb zero,10(t0)
    li t1,77
    sb t1,11(t0)
    sb zero,89(t0)
    addi a0,s0,34
    li a1,NPSEUDO+12
    li a2,77
    call net_copy
    li a0,NPSEUDO
    li a1,90
    call net_checksum
    leave

net_init:
    enter
    li s0,0x10001000
    li s1,8
net_probe:
    lw t0,8(s0)
    li t1,1
    beq t0,t1,net_found
    li t0,4096
    add s0,s0,t0
    addi s1,s1,-1
    bne s1,zero,net_probe
    j net_fail
net_found:
    lw t0,4(s0)
    li t1,2
    bne t0,t1,net_fail
    li t0,NCTRL
    sd s0,16(t0)
    sw zero,112(s0)
    li t0,3
    sw t0,112(s0)
    li t0,1
    sw t0,20(s0)
    lw t1,16(s0)
    andi t1,t1,1
    beq t1,zero,net_fail
    sw t0,36(s0)
    sw t0,32(s0)
    sw zero,36(s0)
    sw zero,32(s0)
    li t0,11
    sw t0,112(s0)
    lw t0,112(s0)
    andi t0,t0,8
    beq t0,zero,net_fail
    li s1,0
net_queue_init:
    sw s1,48(s0)
    lw t0,52(s0)
    li t1,8
    bltu t0,t1,net_fail
    sw t1,56(s0)
    li s2,RING0
    li t0,2048
    mul t0,t0,s1
    add s2,s2,t0
    mv t0,s2
    li t1,64
net_ring_zero:
    sd zero,0(t0)
    addi t0,t0,8
    addi t1,t1,-1
    bne t1,zero,net_ring_zero
    sw s2,128(s0)
    sw zero,132(s0)
    addi t0,s2,128
    sw t0,144(s0)
    sw zero,148(s0)
    addi t0,s2,256
    sw t0,160(s0)
    sw zero,164(s0)
    li t0,1
    sw t0,68(s0)
    addi s1,s1,1
    li t0,2
    bne s1,t0,net_queue_init
    li t0,RING0
    li t1,NRX
    sd t1,0(t0)
    li t1,2048
    sw t1,8(t0)
    li t1,2
    sh t1,12(t0)
    li t1,1
    sh t1,130(t0)
    fence
    li t0,15
    sw t0,112(s0)
    sw zero,80(s0)
    leave
net_rx_rearm:
    li t0,NCTRL
    ld t1,0(t0)
    addi t1,t1,1
    sd t1,0(t0)
    andi t2,t1,7
    slli t2,t2,1
    li t3,RING0+132
    add t3,t3,t2
    sh zero,0(t3)
    li t3,RING0+130
    addi t1,t1,1
    fence
    sh t1,0(t3)
    fence
    ld t0,16(t0)
    sw zero,80(t0)
    ret

net_send:
    enter
    mv s0,a0
    la a0,net_frame_template
    li a1,NTX
    li a2,123
    call net_copy
    li t0,NTX+12+46
    sb s0,0(t0)
    li t0,ROLE
    bne t0,zero,net_send_server_nonces
    la a0,LOCAL_NONCE
    li a1,NTX+12+47
    li a2,16
    call net_copy
    li t0,1
    beq s0,t0,net_send_auth
    li a0,NCACHE
    li a1,NTX+12+63
    li a2,16
    call net_copy
    j net_send_auth
net_send_server_nonces:
    li a0,NCACHE
    li a1,NTX+12+47
    li a2,16
    call net_copy
    la a0,LOCAL_NONCE
    li a1,NTX+12+63
    li a2,16
    call net_copy
net_send_auth:
    la a0,TEST_KEY
    li a1,NAUTH
    li a2,32
    call net_copy
    li a0,NTX+12+46
    li a1,NAUTH+32
    li a2,33
    call net_copy
    li a0,NAUTH
    li a1,65
    call hmac_sha3_256
    li a1,NTX+12+79
    li a2,32
    call net_copy
    li a0,NTX+12+14
    li a1,20
    call net_checksum
    li t0,NTX+12+24
    srli t1,a0,8
    sb t1,0(t0)
    sb a0,1(t0)
    li a0,NTX+12
    call net_udp_checksum
    li t0,NTX+12+40
    srli t1,a0,8
    sb t1,0(t0)
    sb a0,1(t0)
    li t0,RING1
    li t1,NTX
    sd t1,0(t0)
    li t1,123
    sw t1,8(t0)
    sh zero,12(t0)
    li t1,NCTRL
    ld s1,8(t1)
    andi t2,s1,7
    slli t2,t2,1
    add t2,t0,t2
    sh zero,132(t2)
    addi s1,s1,1
    sd s1,8(t1)
    fence
    sh s1,130(t0)
    fence
    ld t0,16(t1)
    li t1,1
    sw t1,80(t0)
    li s2,100000000
net_tx_poll:
    li t0,RING1+258
    lhu t1,0(t0)
    beq t1,s1,net_tx_done
    addi s2,s2,-1
    bne s2,zero,net_tx_poll
    j net_fail
net_tx_done:
    leave
net_pass_message:
    .asciz "OMEGA VIRTIO-NET MUTUAL HMAC PASS\n"
net_fail_message:
    .asciz "OMEGA VIRTIO-NET FAIL\n"
.align 2
