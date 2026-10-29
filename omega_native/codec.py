"""The byte-for-byte tagged rational document format used by std/string.omega."""
from fractions import Fraction
import hashlib
import json


def quote(text):
    if '\x00' in text:raise ValueError('Native strings cannot contain NUL')
    escaped=[]
    for c in text:
        if c=='"':escaped.append('\\"')
        elif c=='\\':escaped.append('\\\\')
        elif c=='\n':escaped.append('\\n')
        elif c=='\r':escaped.append('\\r')
        elif c=='\t':escaped.append('\\t')
        elif ord(c)<32:escaped.append('\\u%04x'%ord(c))
        else:escaped.append(c)
    return '"'+''.join(escaped)+'"'



def canonical(value,depth=0):
    if depth>64:raise ValueError('Document nesting budget exceeded')
    if type(value) is int or isinstance(value,Fraction):
        q=Fraction(value);return '["q",'+quote(f'{q.numerator}/{q.denominator}')+']'
    if type(value) is str:return '["s",'+quote(value)+']'
    if type(value) is list:return '["a",['+','.join(canonical(x,depth+1) for x in value)+']]'
    if type(value) is dict and all(type(k) is str for k in value):
        return '["o",['+','.join('['+quote(k)+','+canonical(value[k],depth+1)+']' for k in sorted(value))+']]'
    raise ValueError('Documents contain only integers, Fractions, strings, arrays and string-keyed objects')


def decode(text):
    def visit(node,depth=0):
        if depth>64 or type(node) is not list or len(node)!=2:raise ValueError('Malformed tagged document')
        tag,value=node
        if tag=='q' and type(value) is str:return Fraction(value)
        if tag=='s' and type(value) is str:return value
        if tag=='a' and type(value) is list:return [visit(x,depth+1) for x in value]
        if tag=='o' and type(value) is list:
            result={}
            for k,v in value:
                if type(k) is not str or k in result:raise ValueError('Duplicate document key')
                result[k]=visit(v,depth+1)
            return result
        raise ValueError('Unknown document tag')
    value=visit(json.loads(text))
    if canonical(value)!=text:raise ValueError('Noncanonical rational document')
    return value


def subject(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
