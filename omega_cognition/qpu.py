"""Executable specification for bounded rational RTL (not fabricated silicon)."""
from fractions import Fraction as Q
from omega_refine_check.syntax import rational
from omega_refine_check.contracts import verify_contract


def stein(a,b):
    if any(type(x) is not int or not 0<=x<2**128 for x in (a,b)):
        raise ValueError('Unsigned 128-bit operands required')
    shifts=0;cycles=0
    if not a:return b,cycles
    if not b:return a,cycles
    while not (a|b)&1:a>>=1;b>>=1;shifts+=1;cycles+=1
    while not a&1:a>>=1;cycles+=1
    while b:
        while not b&1:b>>=1;cycles+=1
        if a>b:a,b=b,a
        b-=a;cycles+=1
    return a<<shifts,cycles


def execute(op,a,b,*,bits=16,max_denominator=None,prove=True):
    if type(bits) is not int or not 2<=bits<=32:raise ValueError('RTL width must be in [2,32]')
    limit=2**(bits-1)-1
    max_denominator=limit if max_denominator is None else max_denominator
    if type(max_denominator) is not int or not 1<=max_denominator<=limit:raise ValueError('Invalid denominator register bound')
    a,b=rational(a),rational(b)
    if any(abs(q.numerator)>limit or q.denominator>limit for q in (a,b)):raise OverflowError('Operand register overflow')
    if op not in ('+','-','*','/'):raise ValueError('Unknown Q-PU opcode')
    if op=='/' and not b:raise ZeroDivisionError('Q-PU zero divisor trap')
    exact={'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[op]()
    value=exact.limit_denominator(max_denominator)
    if abs(value.numerator)>limit:raise OverflowError('Q-PU numerator overflow trap')
    error=abs(exact-value)
    result={'value':str(value),'exact':str(exact),'error':str(error),'interrupt':bool(error),
            'scope':'nearest denominator-bounded rational; no downstream decision guarantee without a margin proof'}
    if prove:
        result['certificate']=verify_contract({},str(exact),f'result - ({value}) <= ({error}) and ({value}) - result <= ({error})')
    return result
