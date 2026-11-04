# Own signed limb arithmetic with a configured base-2^32 limb budget.
# Header sign at 0, length at 8, u64 slots at 16. No libc/GMP/allocator.
# Functions require disjoint output/input objects except explicitly in-place
# operations. Zero is sign=0,len=0. Arithmetic faults terminate explicitly.
.equ LIMBS,128
.equ BIG,16+LIMBS*8
.equ QSIZE,BIG*2
.equ TMP0,0x620000
.equ TMP1,TMP0+BIG
.equ TMP2,TMP1+BIG
.equ TMP3,TMP2+BIG
.equ GCA,TMP3+BIG
.equ GCB,GCA+BIG
.equ GCQ,GCB+BIG
.equ GCR,GCQ+BIG

big_zero:
    sd zero,0(a0)
    sd zero,8(a0)
    ret
big_one:
    li t0,1
    sd t0,0(a0)
    sd t0,8(a0)
    sd t0,16(a0)
    ret
big_copy:
    ld t0,8(a1)
    addi t0,t0,2
big_copy_loop:
    beq t0,zero,big_copy_done
    ld t1,0(a1)
    sd t1,0(a0)
    addi a0,a0,8
    addi a1,a1,8
    addi t0,t0,-1
    j big_copy_loop
big_copy_done:
    ret
big_trim:
    ld t0,8(a0)
big_trim_loop:
    beq t0,zero,big_trim_zero
    slli t1,t0,3
    add t1,t1,a0
    ld t2,8(t1)
    bne t2,zero,big_trim_done
    addi t0,t0,-1
    j big_trim_loop
big_trim_zero:
    sd zero,0(a0)
big_trim_done:
    sd t0,8(a0)
    ret
big_cmp:
    ld t0,8(a0)
    ld t1,8(a1)
    bltu t0,t1,big_cmp_less
    bltu t1,t0,big_cmp_greater
big_cmp_loop:
    beq t0,zero,big_cmp_equal
    slli t2,t0,3
    add t3,a0,t2
    add t4,a1,t2
    ld t3,8(t3)
    ld t4,8(t4)
    bltu t3,t4,big_cmp_less
    bltu t4,t3,big_cmp_greater
    addi t0,t0,-1
    j big_cmp_loop
big_cmp_less:
    li a0,-1
    ret
big_cmp_greater:
    li a0,1
    ret
big_cmp_equal:
    li a0,0
    ret

# Unsigned magnitude addition. Output must not alias inputs.
mag_add:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    ld s3,8(s1)
    ld s4,8(s2)
    mv s5,s3
    bgeu s3,s4,mag_add_size
    mv s5,s4
mag_add_size:
    li s6,0
    li s7,0
mag_add_loop:
    bgeu s6,s5,mag_add_carry
    li t0,0
    li t1,0
    slli t2,s6,3
    bgeu s6,s3,mag_add_b
    add t3,s1,t2
    ld t0,16(t3)
mag_add_b:
    bgeu s6,s4,mag_add_sum
    add t3,s2,t2
    ld t1,16(t3)
mag_add_sum:
    add t0,t0,t1
    add t0,t0,s7
    srli s7,t0,32
    slli t0,t0,32
    srli t0,t0,32
    add t3,s0,t2
    sd t0,16(t3)
    addi s6,s6,1
    j mag_add_loop
mag_add_carry:
    beq s7,zero,mag_add_end
    li t0,LIMBS
    bgeu s5,t0,arithmetic_limit
    slli t0,s5,3
    add t0,t0,s0
    sd s7,16(t0)
    addi s5,s5,1
mag_add_end:
    li t0,1
    sd t0,0(s0)
    sd s5,8(s0)
    mv a0,s0
    call big_trim
    leave

# Magnitude subtraction a>=b, supports output aliasing a.
mag_sub:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    ld s3,8(s1)
    ld s4,8(s2)
    li s5,0
    li s6,0
mag_sub_loop:
    bgeu s5,s3,mag_sub_end
    slli t0,s5,3
    add t1,s1,t0
    ld t2,16(t1)
    li t3,0
    bgeu s5,s4,mag_sub_borrow
    add t1,s2,t0
    ld t3,16(t1)
mag_sub_borrow:
    add t3,t3,s6
    sltu s6,t2,t3
    sub t2,t2,t3
    slli t2,t2,32
    srli t2,t2,32
    add t1,s0,t0
    sd t2,16(t1)
    addi s5,s5,1
    j mag_sub_loop
mag_sub_end:
    bne s6,zero,arithmetic_limit
    li t0,1
    sd t0,0(s0)
    sd s3,8(s0)
    mv a0,s0
    call big_trim
    leave
big_add:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    ld s3,0(s1)
    ld s4,0(s2)
    beq s3,zero,big_add_copy_b
    beq s4,zero,big_add_copy_a
    bne s3,s4,big_add_different
    call mag_add
    sd s3,0(s0)
    j big_add_end
big_add_different:
    mv a0,s1
    mv a1,s2
    call big_cmp
    beq a0,zero,big_add_zero
    blt a0,zero,big_add_b_larger
    mv a0,s0
    mv a1,s1
    mv a2,s2
    call mag_sub
    sd s3,0(s0)
    j big_add_end
big_add_b_larger:
    mv a0,s0
    mv a1,s2
    mv a2,s1
    call mag_sub
    sd s4,0(s0)
    j big_add_end
big_add_zero:
    mv a0,s0
    call big_zero
    j big_add_end
big_add_copy_a:
    mv a0,s0
    mv a1,s1
    call big_copy
    j big_add_end
big_add_copy_b:
    mv a0,s0
    mv a1,s2
    call big_copy
big_add_end:
    leave
big_mul:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    ld s3,8(s1)
    ld s4,8(s2)
    add s5,s3,s4
    li t0,LIMBS
    bltu t0,s5,arithmetic_limit
    sd s5,8(s0)
    ld t0,0(s1)
    ld t1,0(s2)
    mul t0,t0,t1
    sd t0,0(s0)
    li s6,0
big_mul_clear:
    bgeu s6,s5,big_mul_rows
    slli t0,s6,3
    add t0,t0,s0
    sd zero,16(t0)
    addi s6,s6,1
    j big_mul_clear
big_mul_rows:
    li s6,0
big_mul_outer:
    bgeu s6,s3,big_mul_end
    li s7,0
    li s8,0
    slli t0,s6,3
    add t0,t0,s1
    ld s9,16(t0)
big_mul_inner:
    bgeu s7,s4,big_mul_store_carry
    slli t0,s7,3
    add t0,t0,s2
    ld t1,16(t0)
    mul t1,t1,s9
    add t2,s6,s7
    slli t2,t2,3
    add t2,t2,s0
    ld t3,16(t2)
    add t1,t1,t3
    add t1,t1,s8
    srli s8,t1,32
    slli t1,t1,32
    srli t1,t1,32
    sd t1,16(t2)
    addi s7,s7,1
    j big_mul_inner
big_mul_store_carry:
    add t0,s6,s4
    slli t0,t0,3
    add t0,t0,s0
    sd s8,16(t0)
    addi s6,s6,1
    j big_mul_outer
big_mul_end:
    mv a0,s0
    call big_trim
    leave

# In-place magnitude shift-left-one and append a0's bit a1.
big_shift_bit:
    ld t0,8(a0)
    li t1,0
    mv t2,a1
big_shift_loop:
    bgeu t1,t0,big_shift_carry
    slli t3,t1,3
    add t3,t3,a0
    ld t4,16(t3)
    slli t4,t4,1
    add t4,t4,t2
    srli t2,t4,32
    slli t4,t4,32
    srli t4,t4,32
    sd t4,16(t3)
    addi t1,t1,1
    j big_shift_loop
big_shift_carry:
    beq t2,zero,big_shift_done
    li t1,LIMBS
    bgeu t0,t1,arithmetic_limit
    slli t1,t0,3
    add t1,t1,a0
    sd t2,16(t1)
    addi t0,t0,1
    sd t0,8(a0)
big_shift_done:
    beq t0,zero,big_shift_return
    li t1,1
    sd t1,0(a0)
big_shift_return:
    ret

# Unsigned binary long division: q=a/b, r=a%b. Four disjoint objects.
big_divmod:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    mv s3,a3
    ld t0,8(s3)
    beq t0,zero,division_zero
    call big_zero
    mv a0,s1
    call big_zero
    ld s4,8(s2)
    slli s4,s4,5
big_div_loop:
    beq s4,zero,big_div_end
    addi s4,s4,-1
    srli t0,s4,5
    slli t0,t0,3
    add t0,t0,s2
    ld t1,16(t0)
    andi t2,s4,31
    srl t1,t1,t2
    andi a1,t1,1
    mv a0,s1
    call big_shift_bit
    mv a0,s0
    li a1,0
    call big_shift_bit
    mv a0,s1
    mv a1,s3
    call big_cmp
    blt a0,zero,big_div_loop
    mv a0,s1
    mv a1,s1
    mv a2,s3
    call mag_sub
    ld t0,8(s0)
    bne t0,zero,big_div_set
    li t0,1
    sd t0,8(s0)
    sd t0,0(s0)
    sd zero,16(s0)
big_div_set:
    ld t0,16(s0)
    ori t0,t0,1
    sd t0,16(s0)
    j big_div_loop
big_div_end:
    leave
big_gcd:
    enter
    mv s0,a0
    mv s1,a1
    mv s2,a2
    li a0,GCA
    mv a1,s1
    call big_copy
    li a0,GCB
    mv a1,s2
    call big_copy
big_gcd_loop:
    li t0,GCB
    ld t0,8(t0)
    beq t0,zero,big_gcd_end
    li a0,GCQ
    li a1,GCR
    li a2,GCA
    li a3,GCB
    call big_divmod
    li a0,GCA
    li a1,GCB
    call big_copy
    li a0,GCB
    li a1,GCR
    call big_copy
    j big_gcd_loop
big_gcd_end:
    mv a0,s0
    li a1,GCA
    call big_copy
    li t0,1
    sd t0,0(s0)
    leave

# Parse nonnegative decimal digits, return a0=first non-digit. A sign is
# handled by the rational literal caller. In-place mul-small uses <2^36.
big_decimal:
    enter
    mv s0,a0
    mv s1,a1
    call big_zero
big_decimal_loop:
    lbu t0,0(s1)
    addi t0,t0,-48
    li t1,10
    bgeu t0,t1,big_decimal_end
    mv s2,t0
    ld s3,8(s0)
    li s4,0
big_decimal_limb:
    bgeu s4,s3,big_decimal_carry
    slli t0,s4,3
    add t0,t0,s0
    ld t1,16(t0)
    li t2,10
    mul t1,t1,t2
    add t1,t1,s2
    srli s2,t1,32
    slli t1,t1,32
    srli t1,t1,32
    sd t1,16(t0)
    addi s4,s4,1
    j big_decimal_limb
big_decimal_carry:
    beq s2,zero,big_decimal_next
    li t0,LIMBS
    bgeu s3,t0,arithmetic_limit
    slli t0,s3,3
    add t0,t0,s0
    sd s2,16(t0)
    addi s3,s3,1
    sd s3,8(s0)
    li t0,1
    sd t0,0(s0)
big_decimal_next:
    addi s1,s1,1
    j big_decimal_loop
big_decimal_end:
    mv a0,s1
    leave

# Signed decimal rendering with div-small by 10. a0 input (not mutated),
# a1 destination. Returns byte length. TMP3 is private to rendering.
big_render:
    enter
    mv s0,a1
    mv s1,a1
    ld s2,0(a0)
    mv a1,a0
    li a0,TMP3
    call big_copy
    bge s2,zero,big_render_digits
    li t0,45
    sb t0,0(s1)
    addi s1,s1,1
big_render_digits:
    mv s3,s1
    li s4,TMP3
    ld t0,8(s4)
    bne t0,zero,big_render_loop
    li t0,48
    sb t0,0(s1)
    addi s1,s1,1
    j big_render_reverse
big_render_loop:
    ld s5,8(s4)
    li s6,0
big_render_div:
    beq s5,zero,big_render_digit
    addi s5,s5,-1
    slli t0,s5,3
    add t0,t0,s4
    ld t1,16(t0)
    slli s6,s6,32
    or t1,t1,s6
    li t2,10
    divu t3,t1,t2
    remu s6,t1,t2
    sd t3,16(t0)
    j big_render_div
big_render_digit:
    addi t0,s6,48
    sb t0,0(s1)
    addi s1,s1,1
    mv a0,s4
    call big_trim
    ld t0,8(s4)
    bne t0,zero,big_render_loop
big_render_reverse:
    addi s2,s1,-1
big_render_swap:
    bgeu s3,s2,big_render_done
    lbu t0,0(s3)
    lbu t1,0(s2)
    sb t1,0(s3)
    sb t0,0(s2)
    addi s3,s3,1
    addi s2,s2,-1
    j big_render_swap
big_render_done:
    sub a0,s1,s0
    leave

# Rational in-place normalization with independent numerator/denominator GCD.
q_normalize:
    enter
    mv s0,a0
    li t0,BIG
    add s1,s0,t0
    ld t0,8(s1)
    beq t0,zero,division_zero
    ld s2,0(s0)
    ld t0,0(s1)
    mul s2,s2,t0
    li t0,1
    sd t0,0(s1)
    beq s2,zero,q_normalize_zero
    li a0,TMP2
    mv a1,s0
    mv a2,s1
    call big_gcd
    li a0,TMP0
    li a1,TMP1
    mv a2,s0
    li a3,TMP2
    call big_divmod
    mv a0,s0
    li a1,TMP0
    call big_copy
    sd s2,0(s0)
    li a0,TMP0
    li a1,TMP1
    mv a2,s1
    li a3,TMP2
    call big_divmod
    mv a0,s1
    li a1,TMP0
    call big_copy
    j q_normalize_done
q_normalize_zero:
    mv a0,s1
    call big_one
q_normalize_done:
    leave
