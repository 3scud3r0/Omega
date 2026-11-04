# RV64IM QEMU virt: M-mode boot, PMP, Sv39, delegated interrupts and faults.
# No SBI, host OS, C, libc, GMP, or external assembler in the guest.
.equ UART,0x10000000
.equ ROOT,0x80200000
.equ L1,0x80201000
.equ L0,0x80202000
.equ TIMER_COUNT,0x80203000
.equ IRQ_COUNT,0x80203008
.equ PAGE_COUNT,0x80203010
.equ QUEUE,0x80204000
.equ REQUEST,0x80205000
.equ DATA,0x80206000

_start:
    li sp,0x8001f000
    li t0,ROOT
    li t1,0x80210000
boot_zero:
    sd zero,0(t0)
    addi t0,t0,8
    bltu t0,t1,boot_zero
    la t0,machine_trap
    csrw mtvec,t0
    li t0,-1
    srli t0,t0,2
    csrw pmpaddr0,t0
    li t0,15
    csrw pmpcfg0,t0
    li t0,ROOT
    li t1,0xc7
    sd t1,0(t0)
    li t1,(L1>>2)|1
    sd t1,16(t0)
    li t0,L1
    li t1,(L0>>2)|1
    sd t1,0(t0)
    li t1,(ROOT>>2)|0xc7
    sd t1,8(t0)
    li t0,L0
    li t1,0x200000cb
    li t2,16
map_text:
    sd t1,0(t0)
    addi t0,t0,8
    addi t1,t1,1024
    addi t2,t2,-1
    bne t2,zero,map_text
    li t1,0x200040c7
    li t2,16
map_stack:
    sd t1,0(t0)
    addi t0,t0,8
    addi t1,t1,1024
    addi t2,t2,-1
    bne t2,zero,map_stack
    li t0,(8<<60)|(ROOT>>12)
    csrw satp,t0
    sfence.vma
    li t0,(1<<12)|(1<<13)|(1<<15)
    csrw medeleg,t0
    li t0,(1<<1)|(1<<9)
    csrw mideleg,t0
    la t0,supervisor_trap
    csrw stvec,t0
    li t0,(1<<1)|(1<<9)
    csrw sie,t0
    li t0,2
    csrs sstatus,t0
    li t0,0x0200bff8
    ld t1,0(t0)
    li t2,100000
    add t1,t1,t2
    li t0,0x02004000
    sd t1,0(t0)
    li t0,642
    csrw mie,t0
    # MPP=S and MPIE=1. mret starts guest supervisor with paging enabled.
    li t0,2178
    csrw mstatus,t0
    la t0,supervisor
    csrw mepc,t0
    mret

supervisor:
    li t0,2
    csrs sstatus,t0
    la a0,boot_message
    call puts
    # UART interrupt 10, PLIC supervisor context 1.
    li t0,0x0c000028
    li t1,1
    sw t1,0(t0)
    li t0,0x0c002080
    li t1,1024
    sw t1,0(t0)
    li t0,0x0c201000
    sw zero,0(t0)
    li t0,UART
    li t1,2
    sb t1,1(t0)
    li s0,5000000
wait_interrupts:
    li t0,TIMER_COUNT
    ld t1,0(t0)
    ld t2,8(t0)
    and t1,t1,t2
    bne t1,zero,interrupts_done
    addi s0,s0,-1
    bne s0,zero,wait_interrupts
    j fail
interrupts_done:
    la a0,interrupt_message
    call puts
    # Real supervisor load page fault: root[1] is absent.
    li t0,0x40000000
    ld t1,0(t0)
    # Real instruction page fault: DATA is mapped RW, never executable.
    li t0,DATA
    jalr zero,t0,0
nx_resume:
    li t0,PAGE_COUNT
    ld t1,0(t0)
    li t2,2
    bne t1,t2,fail
    la a0,mmu_message
    call puts
    call block_init
    li t0,DATA
    li t1,0x4f4d454741534f56
    sd t1,0(t0)
    li a0,1
    li a1,1
    call block_transfer
    li t0,DATA
    sd zero,0(t0)
    li a0,0
    li a1,1
    call block_transfer
    li t0,DATA
    ld t1,0(t0)
    li t2,0x4f4d454741534f56
    bne t1,t2,fail
    la a0,block_message
    call puts
    # A fresh append-only two-sector CAS record: payload in sector 1 and its
    # SHA3-256 address in sector 2. This is a storage primitive, not a complete
    # filesystem, allocator or power-loss-safe root transaction protocol.
    li a0,DATA
    li a1,512
    call sha3_256
    li t0,DATA
    li t1,64
cas_clear:
    sd zero,0(t0)
    addi t0,t0,8
    addi t1,t1,-1
    bne t1,zero,cas_clear
    li t0,DATA
    li t1,0x80207000
    li t2,4
cas_digest_copy:
    ld t3,0(a0)
    sd t3,0(t0)
    sd t3,0(t1)
    addi a0,a0,8
    addi t0,t0,8
    addi t1,t1,8
    addi t2,t2,-1
    bne t2,zero,cas_digest_copy
    li a0,1
    li a1,2
    call block_transfer
    li a0,0
    li a1,2
    call block_transfer
    li t0,DATA
    li t1,0x80207000
    li t2,4
cas_digest_check:
    ld t3,0(t0)
    ld t4,0(t1)
    bne t3,t4,fail
    addi t0,t0,8
    addi t1,t1,8
    addi t2,t2,-1
    bne t2,zero,cas_digest_check
    li a0,0
    li a1,1
    call block_transfer
    li a0,DATA
    li a1,512
    call sha3_256
    li t0,0x80207000
    li t1,4
cas_payload_check:
    ld t2,0(a0)
    ld t3,0(t0)
    bne t2,t3,fail
    addi a0,a0,8
    addi t0,t0,8
    addi t1,t1,-1
    bne t1,zero,cas_payload_check
    la a0,cas_message
    call puts
    la a0,pass_message
    call puts
    li t0,0x100000
    li t1,0x5555
    sw t1,0(t0)
    j halt

puts:
    lbu t1,0(a0)
    beq t1,zero,puts_done
    li t0,UART
puts_wait:
    lbu t2,5(t0)
    andi t2,t2,32
    beq t2,zero,puts_wait
    sb t1,0(t0)
    addi a0,a0,1
    j puts
puts_done:
    ret

# Exactly one outstanding request; three bounded descriptors, 512-byte sector.
# Device discovery/feature negotiation are VirtIO 1.0 MMIO, not legacy PFNs.
block_init:
    enter
    li s8,0x10001000
    li t2,8
block_probe:
    lw t0,0(s8)
    li t1,0x74726976
    bne t0,t1,block_next
    lw t0,8(s8)
    li t1,2
    beq t0,t1,block_found
block_next:
    addi s8,s8,2047
    addi s8,s8,2047
    addi s8,s8,2
    addi t2,t2,-1
    bne t2,zero,block_probe
    j fail
block_found:
    lw t0,4(s8)
    li t1,2
    bne t0,t1,fail
    sw zero,112(s8)
    li t0,3
    sw t0,112(s8)
    li t0,1
    sw t0,20(s8)
    lw t1,16(s8)
    andi t1,t1,1
    beq t1,zero,fail
    sw t0,36(s8)
    sw t0,32(s8)
    sw zero,36(s8)
    sw zero,32(s8)
    li t0,11
    sw t0,112(s8)
    lw t1,112(s8)
    andi t1,t1,8
    beq t1,zero,fail
    sw zero,48(s8)
    lw t0,52(s8)
    li t1,8
    bltu t0,t1,fail
    sw t1,56(s8)
    li t0,QUEUE
    sw t0,128(s8)
    sw zero,132(s8)
    li t0,QUEUE+128
    sw t0,144(s8)
    sw zero,148(s8)
    li t0,QUEUE+256
    sw t0,160(s8)
    sw zero,164(s8)
    # Reset ring indices before exposing the queue to the device. Otherwise a
    # re-initialization can consume stale descriptors before the next request.
    li t0,QUEUE
    sh zero,130(t0)
    sh zero,258(t0)
    fence
    li t0,1
    sw t0,68(s8)
    li t0,15
    sw t0,112(s8)
    # Return transport base in s8 explicitly across enter/leave.
    mv a0,s8
    leave

block_transfer:
    enter
    # Re-discover transport rather than relying on callee-saved side effects.
    mv s0,a0
    mv s2,a1
    call block_init
    mv s8,a0
    li t0,REQUEST
    sw s0,0(t0)
    sw zero,4(t0)
    sd s2,8(t0)
    li t0,REQUEST+512
    li t1,255
    sb t1,0(t0)
    li t0,QUEUE
    li t1,REQUEST
    sd t1,0(t0)
    li t1,16
    sw t1,8(t0)
    li t1,1
    sh t1,12(t0)
    sh t1,14(t0)
    li t1,DATA
    sd t1,16(t0)
    li t1,512
    sw t1,24(t0)
    li t1,1
    bne s0,zero,block_data_flags
    li t1,3
block_data_flags:
    sh t1,28(t0)
    li t1,2
    sh t1,30(t0)
    li t1,REQUEST+512
    sd t1,32(t0)
    li t1,1
    sw t1,40(t0)
    li t1,2
    sh t1,44(t0)
    sh zero,46(t0)
    sh zero,128(t0)
    sh zero,130(t0)
    sh zero,132(t0)
    sh zero,256(t0)
    sh zero,258(t0)
    fence
    li t1,1
    sh t1,130(t0)
    fence
    sw zero,80(s8)
    li s1,5000000
block_poll:
    fence
    li t0,QUEUE+258
    lhu t1,0(t0)
    bne t1,zero,block_complete
    addi s1,s1,-1
    bne s1,zero,block_poll
    j fail
block_complete:
    li t0,REQUEST+512
    lbu t1,0(t0)
    bne t1,zero,fail
    lw t0,96(s8)
    sw t0,100(s8)
    leave

machine_trap:
    # Generated save/restore sequence is inserted by the build utility.
    .save_all
    csrr t0,mcause
    li t1,0x8000000000000007
    bne t0,t1,fail
    li t0,0x02004000
    li t1,-1
    sd t1,0(t0)
    li t0,2
    csrs mip,t0
    .restore_all
    mret

supervisor_trap:
    .save_all
    csrr t0,scause
    li t1,0x8000000000000001
    beq t0,t1,supervisor_timer
    li t1,0x8000000000000009
    beq t0,t1,supervisor_irq
    li t1,13
    beq t0,t1,supervisor_page
    li t1,12
    beq t0,t1,supervisor_nx
    j fail
supervisor_timer:
    li t0,2
    csrc sip,t0
    li t0,TIMER_COUNT
    ld t1,0(t0)
    addi t1,t1,1
    sd t1,0(t0)
    j supervisor_return
supervisor_irq:
    li t0,0x0c201004
    lw t1,0(t0)
    li t2,10
    bne t1,t2,fail
    li t2,UART
    sb zero,1(t2)
    sw t1,0(t0)
    li t0,IRQ_COUNT
    ld t1,0(t0)
    addi t1,t1,1
    sd t1,0(t0)
    j supervisor_return
supervisor_page:
    csrr t0,sepc
    addi t0,t0,4
    csrw sepc,t0
    j supervisor_fault_count
supervisor_nx:
    la t0,nx_resume
    csrw sepc,t0
supervisor_fault_count:
    li t0,PAGE_COUNT
    ld t1,0(t0)
    addi t1,t1,1
    sd t1,0(t0)
supervisor_return:
    .restore_all
    sret

fail:
    la a0,fail_message
    call puts
    li t0,0x100000
    li t1,0x3333
    sw t1,0(t0)
halt:
    wfi
    j halt
boot_message:
    .asciz "OMEGA baremetal: supervisor Sv39 active\n"
interrupt_message:
    .asciz "CLINT timer + PLIC UART: PASS\n"
mmu_message:
    .asciz "Sv39 unmapped + NX faults: PASS\n"
block_message:
    .asciz "VirtIO block sector write/read: PASS\n"
cas_message:
    .asciz "CAS SHA3 content binding: PASS\n"
pass_message:
    .asciz "OMEGA BAREMETAL PASS\n"
fail_message:
    .asciz "OMEGA BAREMETAL FAIL\n"
