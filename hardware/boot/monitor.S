# ROM boot monitor for omega_monitor_soc; only the implemented RV64I subset.
# Verifies 64-bit load/store and exact small integer arithmetic before output.
li s0,0x1000000
li t0,0x123456789abcdef0
sd t0,0(s0)
ld t1,0(s0)
bne t0,t1,failure
li t0,21
add t0,t0,t0
li t1,42
bne t0,t1,failure
li s1,0x10000000
la s2,message
loop:
lbu t0,0(s2)
beq t0,zero,halt
sb t0,0(s1)
addi s2,s2,1
j loop
halt:
j halt
failure:
.word 0
message:
.asciz "OMEGA RV64 MONITOR: 42 OK\n"
.align 2
