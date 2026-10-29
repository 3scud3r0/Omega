from fractions import Fraction
import ctypes as C
from .build import compile_host


class Rational64(C.Structure):
    _fields_=[('num',C.c_int64),('den',C.c_uint64)]
    @classmethod
    def from_q(cls,value):
        if type(value) not in (int,str,Fraction):raise ValueError('Exact rational required')
        value=Fraction(value)
        if abs(value.numerator)>2**63-1 or value.denominator>2**63-1:raise OverflowError('Rational64 register overflow')
        return cls(value.numerator,value.denominator)
    def fraction(self):return Fraction(self.num,self.den)


class Numeric:
    def __init__(self,*,sanitize=False):
        self.library=C.CDLL(str(compile_host(numeric_only=True,sanitize=sanitize)))
        self.library.omega_host_gcd.argtypes=[C.c_uint64,C.c_uint64];self.library.omega_host_gcd.restype=C.c_uint64
        self.library.omega_host_rational.argtypes=[C.c_int,Rational64,Rational64,C.POINTER(Rational64)]
        self.library.omega_host_prune.argtypes=[Rational64,C.c_uint64,C.POINTER(Rational64),C.POINTER(C.c_uint64)]
    def gcd(self,a,b):
        if any(type(x) is not int or not 0<=x<2**64 for x in (a,b)):raise ValueError('Unsigned 64-bit arguments required')
        return self.library.omega_host_gcd(a,b)
    def operation(self,op,a,b=0):
        codes={'+':2,'-':3,'*':4,'/':5,'neg':6,'relu':7}
        if op not in codes:raise ValueError('Unknown rational opcode')
        out=Rational64();status=self.library.omega_host_rational(codes[op],Rational64.from_q(a),Rational64.from_q(b),C.byref(out))
        if status==1:raise ZeroDivisionError('CUDA-compatible rational zero divisor')
        if status:raise OverflowError(f'CUDA-compatible rational failure {status}')
        return out.fraction()
    def prune(self,a,max_den):
        if type(max_den) is not int or not 1<=max_den<=2**63-1:raise ValueError('Positive int64 denominator limit required')
        out=Rational64();words=(C.c_uint64*4)()
        status=self.library.omega_host_prune(Rational64.from_q(a),max_den,C.byref(out),words)
        if status:raise OverflowError(f'Rational pruning failed {status}')
        error=Fraction(words[0]+(words[1]<<64),words[2]+(words[3]<<64))
        return out.fraction(),error
