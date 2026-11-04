# Native RV64IM compiler for the closed scalar Omega fragment:
# program := ('mostrar' expr ';')+ ; expr uses integer literals, +-*/ and ().
# It emits calls to its own exact signed-limb runtime into an ELF image.
# No host compiler, GMP, Python, assembler or linker is invoked by this binary.
.equ FILEBASE,0x400000
.equ OUTBUF,0x700000
.equ INPUT,0x601000
.equ DEPTH,0x600020
.equ CURCODE,0x600030
.equ CURLIT,0x600038
.equ PARSE_DEPTH,0x600040
.equ QSTACK,0x640000
.equ QOUT,GCR+BIG

_start:
    ld t0,0(sp)
    li t1,3
    bne t0,t1,syntax_error
    ld s9,16(sp)
    ld s10,24(sp)
    ld s11,8(sp)
    li sp,0x6ff000
    li a0,-100
    mv a1,s11
    li a2,0
    li a3,0
    li a7,56
    ecall
    blt a0,zero,io_error
    mv s8,a0
    li a1,OUTBUF
    li a2,image_end-FILEBASE
    call read_all
    li t0,image_end-FILEBASE
    bne a0,t0,io_error
    mv a0,s8
    li a7,57
    ecall
    li a0,-100
    mv a1,s9
    li a2,0
    li a3,0
    li a7,56
    ecall
    blt a0,zero,io_error
    mv s8,a0
    li a1,INPUT
    li a2,16384
    call read_all
    # The input is bytes, not a NUL-terminated prefix chosen by the caller.
    # Embedded NUL must not hide a trailing invalid program.
    li t0,INPUT
    mv t1,a0
source_check:
    beq t1,zero,source_checked
    lbu t2,0(t0)
    beq t2,zero,syntax_error
    addi t0,t0,1
    addi t1,t1,-1
    j source_check
source_checked:
    li t0,INPUT
    add t0,t0,a0
    sb zero,0(t0)
    mv a0,s8
    li a7,57
    ecall
    li t0,CURCODE
    li t1,OUTBUF+compiled_program-FILEBASE
    sd t1,0(t0)
    li t0,CURLIT
    li t1,OUTBUF+literal_pool-FILEBASE
    sd t1,0(t0)
    li gp,INPUT
    call skip_space
    lbu t0,0(gp)
    beq t0,zero,syntax_error
compile_statements:
    la s0,keyword
compile_keyword:
    lbu t0,0(s0)
    beq t0,zero,compile_expression
    lbu t1,0(gp)
    bne t0,t1,syntax_error
    addi gp,gp,1
    addi s0,s0,1
    j compile_keyword
compile_expression:
    lbu t0,0(gp)
    li t1,32
    beq t0,t1,keyword_boundary
    li t1,9
    beq t0,t1,keyword_boundary
    li t1,10
    beq t0,t1,keyword_boundary
    li t1,13
    beq t0,t1,keyword_boundary
    li t1,40
    beq t0,t1,keyword_boundary
    li t1,45
    bne t0,t1,syntax_error
keyword_boundary:
    call parse_expression
    call skip_space
    lbu t0,0(gp)
    li t1,59
    bne t0,t1,syntax_error
    addi gp,gp,1
    la a0,print_top
    call emit_call
    call skip_space
    lbu t0,0(gp)
    bne t0,zero,compile_statements
    la a0,program_exit
    call emit_call
    li t0,OUTBUF+24
    la t1,_eval_start
    sd t1,0(t0)
    li a0,-100
    mv a1,s10
    li a2,193
    li a3,320
    li a7,56
    ecall
    blt a0,zero,io_error
    mv s8,a0
    li a1,OUTBUF
    li a2,image_end-FILEBASE
    call write_all
    mv a0,s8
    li a7,57
    ecall
    j program_exit

read_all:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    li s3,0
read_all_loop:
    beq s3,s2,read_all_tail
    mv a0,s0
    add a1,s1,s3
    sub a2,s2,s3
    li a7,63
    ecall
    li t0,-4
    beq a0,t0,read_all_loop
    blt a0,zero,io_error
    beq a0,zero,read_all_done
    add s3,s3,a0
    j read_all_loop
read_all_tail:
    mv a0,s0
    li a1,0x600080
    li a2,1
    li a7,63
    ecall
    li t0,-4
    beq a0,t0,read_all_tail
    bne a0,zero,io_error
read_all_done:
    mv a0,s3
    leave
write_all:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    li s3,0
write_all_loop:
    bgeu s3,s2,write_all_done
    mv a0,s0
    add a1,s1,s3
    sub a2,s2,s3
    li a7,64
    ecall
    li t0,-4
    beq a0,t0,write_all_loop
    bge zero,a0,io_error
    add s3,s3,a0
    j write_all_loop
write_all_done:
    leave
skip_space:
    lbu t0,0(gp)
    li t1,32
    beq t0,t1,skip_space_next
    li t1,9
    beq t0,t1,skip_space_next
    li t1,10
    beq t0,t1,skip_space_next
    li t1,13
    bne t0,t1,skip_space_done
skip_space_next:
    addi gp,gp,1
    j skip_space
skip_space_done:
    ret
parse_expression:
    enter
    call parse_term
parse_expression_loop:
    call skip_space
    lbu s0,0(gp)
    li t0,43
    beq s0,t0,parse_expression_more
    li t0,45
    bne s0,t0,parse_expression_done
parse_expression_more:
    addi gp,gp,1
    call parse_term
    la a0,q_add_op
    li t0,43
    beq s0,t0,parse_expression_emit
    la a0,q_sub_op
parse_expression_emit:
    call emit_call
    j parse_expression_loop
parse_expression_done:
    leave
parse_term:
    enter
    call parse_unary
parse_term_loop:
    call skip_space
    lbu s0,0(gp)
    li t0,42
    beq s0,t0,parse_term_more
    li t0,47
    bne s0,t0,parse_term_done
parse_term_more:
    addi gp,gp,1
    call parse_unary
    la a0,q_mul_op
    li t0,42
    beq s0,t0,parse_term_emit
    la a0,q_div_op
parse_term_emit:
    call emit_call
    j parse_term_loop
parse_term_done:
    leave
parse_unary:
    enter
    li t0,PARSE_DEPTH
    ld t1,0(t0)
    li t2,64
    bgeu t1,t2,arithmetic_limit
    addi t1,t1,1
    sd t1,0(t0)
    call skip_space
    lbu t0,0(gp)
    li t1,45
    bne t0,t1,parse_unary_atom
    addi gp,gp,1
    call parse_unary
    la a0,q_neg_op
    call emit_call
    j parse_unary_done
parse_unary_atom:
    call parse_atom
parse_unary_done:
    li t0,PARSE_DEPTH
    ld t1,0(t0)
    addi t1,t1,-1
    sd t1,0(t0)
    leave
parse_atom:
    enter
    call skip_space
    lbu t0,0(gp)
    li t1,40
    bne t0,t1,parse_digits
    addi gp,gp,1
    call parse_expression
    call skip_space
    lbu t0,0(gp)
    li t1,41
    bne t0,t1,syntax_error
    addi gp,gp,1
    j parse_atom_done
parse_digits:
    addi t1,t0,-48
    li t2,10
    bgeu t1,t2,syntax_error
    li s0,CURLIT
    ld s1,0(s0)
    mv s2,s1
parse_digits_loop:
    lbu t0,0(gp)
    addi t1,t0,-48
    li t2,10
    bgeu t1,t2,parse_digits_end
    li t1,OUTBUF+image_end-FILEBASE
    bgeu s2,t1,arithmetic_limit
    sb t0,0(s2)
    addi s2,s2,1
    addi gp,gp,1
    j parse_digits_loop
parse_digits_end:
    li t1,OUTBUF+image_end-FILEBASE
    bgeu s2,t1,arithmetic_limit
    sb zero,0(s2)
    addi s2,s2,1
    sd s2,0(s0)
    li t0,OUTBUF-FILEBASE
    sub a0,s1,t0
    call emit_literal
parse_atom_done:
    leave
emit_word:
    li t0,CURCODE
    ld t1,0(t0)
    li t2,OUTBUF+literal_pool-FILEBASE
    bgeu t1,t2,arithmetic_limit
    sw a0,0(t1)
    addi t1,t1,4
    sd t1,0(t0)
    ret
emit_literal:
    enter
    mv s0,a0
    addi t0,s0,2047
    addi t0,t0,1
    srli t0,t0,12
    slli t0,t0,12
    ori a0,t0,1335
    call emit_word
    li t0,4095
    and t0,s0,t0
    slli t0,t0,20
    li t1,328979
    or a0,t0,t1
    call emit_word
    la a0,push_literal
    call emit_call
    leave
emit_call:
    enter
    li t0,CURCODE
    ld t0,0(t0)
    li t1,OUTBUF-FILEBASE
    sub t0,t0,t1
    sub s0,a0,t0
    # Signed 21-bit aligned JAL range. All seed functions share this image.
    li t0,-1048576
    blt s0,t0,arithmetic_limit
    li t0,1048576
    bge s0,t0,arithmetic_limit
    andi t0,s0,1
    bne t0,zero,arithmetic_limit
    srli t0,s0,20
    andi t0,t0,1
    slli t0,t0,31
    srli t1,s0,1
    andi t1,t1,1023
    slli t1,t1,21
    or t0,t0,t1
    srli t1,s0,11
    andi t1,t1,1
    slli t1,t1,20
    or t0,t0,t1
    srli t1,s0,12
    andi t1,t1,255
    slli t1,t1,12
    or t0,t0,t1
    ori a0,t0,239
    call emit_word
    leave

_eval_start:
    li sp,0x6ff000
    li t0,DEPTH
    sd zero,0(t0)
    j compiled_program
push_literal:
    enter
    mv s0,a0
    li s1,DEPTH
    ld s2,0(s1)
    li t0,32
    bgeu s2,t0,arithmetic_limit
    li t0,QSIZE
    mul s3,s2,t0
    li t0,QSTACK
    add s3,s3,t0
    mv a0,s3
    mv a1,s0
    call big_decimal
    li t0,BIG
    add a0,s3,t0
    call big_one
    addi s2,s2,1
    sd s2,0(s1)
    leave
q_neg_op:
    li t0,DEPTH
    ld t0,0(t0)
    beq t0,zero,syntax_error
    addi t0,t0,-1
    li t1,QSIZE
    mul t0,t0,t1
    li t1,QSTACK
    add t0,t0,t1
    ld t1,0(t0)
    sub t1,zero,t1
    sd t1,0(t0)
    ret
q_add_op:
    li a0,0
    j q_binary
q_sub_op:
    li a0,1
    j q_binary
q_mul_op:
    li a0,2
    j q_binary
q_div_op:
    li a0,3
q_binary:
    enter
    mv s0,a0
    li s1,DEPTH
    ld s2,0(s1)
    li t0,2
    bltu s2,t0,syntax_error
    addi t0,s2,-2
    li t1,QSIZE
    mul t0,t0,t1
    li s3,QSTACK
    add s3,s3,t0
    add s4,s3,t1
    li t0,BIG
    add s5,s3,t0
    add s6,s4,t0
    li t0,2
    bgeu s0,t0,q_binary_product
    li a0,TMP0
    mv a1,s3
    mv a2,s6
    call big_mul
    li a0,TMP1
    mv a1,s4
    mv a2,s5
    call big_mul
    beq s0,zero,q_binary_sum
    li t0,TMP1
    ld t1,0(t0)
    sub t1,zero,t1
    sd t1,0(t0)
q_binary_sum:
    li a0,QOUT
    li a1,TMP0
    li a2,TMP1
    call big_add
    li a0,QOUT+BIG
    mv a1,s5
    mv a2,s6
    call big_mul
    j q_binary_normalize
q_binary_product:
    li t0,2
    bne s0,t0,q_binary_divide
    li a0,QOUT
    mv a1,s3
    mv a2,s4
    call big_mul
    li a0,QOUT+BIG
    mv a1,s5
    mv a2,s6
    call big_mul
    j q_binary_normalize
q_binary_divide:
    li a0,QOUT
    mv a1,s3
    mv a2,s6
    call big_mul
    li a0,QOUT+BIG
    mv a1,s5
    mv a2,s4
    call big_mul
q_binary_normalize:
    li a0,QOUT
    call q_normalize
    mv a0,s3
    li a1,QOUT
    call big_copy
    mv a0,s5
    li a1,QOUT+BIG
    call big_copy
    addi s2,s2,-1
    sd s2,0(s1)
    leave
print_top:
    enter
    li s0,DEPTH
    ld s1,0(s0)
    li t0,1
    bne s1,t0,syntax_error
    li a0,QSTACK
    li a1,INPUT
    call big_render
    mv s2,a0
    li t0,INPUT
    add t0,t0,s2
    li t1,47
    sb t1,0(t0)
    addi s2,s2,1
    li a0,QSTACK+BIG
    li a1,INPUT
    add a1,a1,s2
    call big_render
    add s2,s2,a0
    li t0,INPUT
    add t0,t0,s2
    li t1,10
    sb t1,0(t0)
    addi a2,s2,1
    li a0,1
    li a1,INPUT
    call write_all
    sd zero,0(s0)
    leave
program_exit:
    li a0,0
    li a7,93
    ecall
syntax_error:
    li s11,2
    j error_exit
io_error:
    li s11,3
    j error_exit
arithmetic_limit:
    li s11,4
    j error_exit
division_zero:
    li s11,5
error_exit:
    li a0,2
    la a1,error_message
    li a2,19
    li a7,64
    ecall
    mv a0,s11
    li a7,93
    ecall
keyword:
    .asciz "mostrar"
error_message:
    .ascii "OMEGA native error\n"
    .align 2
compiled_program:
    .zero 8192
literal_pool:
    .zero 16384
image_end:
