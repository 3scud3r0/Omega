"""Bounded data-only rational syntax. No Python eval, imports or source proofs."""
from fractions import Fraction as Q
import re

TOKEN = re.compile(r'\s+|\#[^\n]*|//[^\n]*|"(?:[^"\\]|\\.)*"|\d+(?:\.\d+)?|[A-Za-z_][A-Za-z_0-9]*|>=|<=|!=|==|&&|\|\||[{}\[\](),;:.+*/^<>=!%-]')
IDENT = re.compile(r'[A-Za-z_][A-Za-z_0-9]{0,63}\Z')
OPS = {'or':1,'||':1,'and':2,'&&':2,'==':3,'!=':3,'<':3,'<=':3,'>':3,'>=':3,
       '+':4,'-':4,'*':5,'/':5,'^':6}


def tokens(source):
    if type(source) is not str or len(source.encode())>1024*1024:
        raise ValueError('Source byte budget exceeded')
    out=[];position=0
    for match in TOKEN.finditer(source):
        if match.start()!=position:raise ValueError(f'Unexpected source at {position}')
        position=match.end();value=match.group()
        if not value.isspace() and not value.startswith(('#','//')):out.append(value)
        if len(out)>100000:raise ValueError('Token budget exceeded')
    if position!=len(source):raise ValueError('Trailing source data')
    return out


def rational(value):
    if type(value) not in (str,int,Q) or type(value) is str and (len(value)>2500 or not re.fullmatch(r'-?\d+(?:/\d+|\.\d+)?',value)):
        raise ValueError('Exact bounded rational required')
    try:q=Q(value)
    except (ValueError,ZeroDivisionError):raise ValueError('Invalid rational') from None
    if max(abs(q.numerator).bit_length(),q.denominator.bit_length())>4096:raise ValueError('Rational bit budget exceeded')
    return q


def identifier(name):
    if type(name) is not str or not IDENT.fullmatch(name):raise ValueError('Bounded ASCII identifier required')
    return name


class Reader:
    def __init__(self,sequence):self.t=list(sequence)+['<end>'];self.i=0;self.count=0
    def peek(self):return self.t[self.i]
    def take(self):
        value=self.peek()
        if value=='<end>':raise ValueError('Unexpected end of input')
        self.i+=1;return value
    def accept(self,value):
        if self.peek()==value:self.i+=1;return True
        return False
    def need(self,value):
        if not self.accept(value):raise ValueError(f'Expected {value}, got {self.peek()}')
    def expr(self,minimum=0,depth=0):
        self.count+=1
        if self.count>4096 or depth>128:raise ValueError('Expression budget exceeded')
        current=self.take()
        if current in ('-','!','not'):
            left=('neg' if current=='-' else 'not',self.expr(7,depth+1))
        elif current=='(':
            left=self.expr(0,depth+1);self.need(')')
        elif current=='[':
            values=[]
            if not self.accept(']'):
                values.append(self.expr(0,depth+1))
                while self.accept(','):values.append(self.expr(0,depth+1))
                self.need(']')
            if not 1<=len(values)<=256:raise ValueError('Bounded nonempty tensor required')
            left=('vector',tuple(values))
        elif re.fullmatch(r'\d+(?:\.\d+)?',current):left=('const',str(rational(current)))
        elif current in ('true','false'):left=(current,)
        elif IDENT.fullmatch(current):
            identifier(current)
            if self.accept('('):
                if current not in ('norm','soma','relu','dot'):raise ValueError('Unknown contract function')
                args=[]
                if not self.accept(')'):
                    args.append(self.expr(0,depth+1))
                    while self.accept(','):args.append(self.expr(0,depth+1))
                    self.need(')')
                if len(args)!=(2 if current=='dot' else 1):raise ValueError('Function arity mismatch')
                left=(current,*args)
            else:left=('var',current)
        else:raise ValueError('Invalid expression token: '+current)
        if self.accept('.'):
            self.need('denom');left=('denom',left)
        if self.accept('['):
            raw=self.take()
            if not raw.isascii() or not raw.isdigit() or len(raw)>3:raise ValueError('Static coordinate required')
            self.need(']');left=('index',left,int(raw))
        while self.peek() in OPS and OPS[self.peek()]>=minimum:
            op=self.take();precedence=OPS[op]
            right=self.expr(precedence+(0 if op=='^' else 1),depth+1)
            left=({'&&':'and','||':'or','^':'pow'}.get(op,op),left,right)
            if left[0] in ('+','-','*','/') and left[1][0]==left[2][0]=='const':
                a,b=Q(left[1][1]),Q(left[2][1])
                if left[0]!='/' or b!=0:
                    left=('const',str({'+':lambda:a+b,'-':lambda:a-b,'*':lambda:a*b,'/':lambda:a/b}[left[0]]()))
        return left


def parse(source):
    reader=Reader(tokens(source));tree=reader.expr()
    if reader.peek()!='<end>':raise ValueError('Trailing expression tokens')
    return tree


def tree(value, *, partial=False):
    """Validate and freeze external AST data, including explicit grammar holes."""
    remaining=4096
    def visit(node,depth=0):
        nonlocal remaining
        remaining-=1
        if remaining<0 or depth>128 or type(node) not in (tuple,list) or not node or type(node[0]) is not str:
            raise ValueError('Invalid AST or AST budget exceeded')
        op=node[0]
        if op=='hole' and partial and len(node)==1:return ('hole',)
        if op=='const' and len(node)==2:return ('const',str(rational(node[1])))
        if op=='var' and len(node)==2:return ('var',identifier(node[1]))
        if op in ('true','false') and len(node)==1:return (op,)
        if op=='vector' and len(node)==2 and type(node[1]) in (tuple,list) and 1<=len(node[1])<=256:
            return (op,tuple(visit(x,depth+1) for x in node[1]))
        if op=='index' and len(node)==3 and type(node[2]) is int and 0<=node[2]<256:return (op,visit(node[1],depth+1),node[2])
        arity=1 if op in ('neg','not','denom','norm','soma','relu') else 2 if op in ('+','-','*','/','pow','dot','==','!=','<=','>=','<','>','and','or') else -1
        if len(node)!=arity+1:raise ValueError('Unknown AST operation or arity')
        return (op,*(visit(x,depth+1) for x in node[1:]))
    return visit(value)


def substitute(node,environment):
    if node[0]=='var':
        if node[1] not in environment:raise ValueError('Unknown variable: '+node[1])
        return environment[node[1]]
    if node[0]=='vector':return ('vector',tuple(substitute(x,environment) for x in node[1]))
    if node[0] in ('const','true','false','hole'):return node
    if node[0]=='index':
        value=substitute(node[1],environment)
        if value[0]!='vector' or node[2]>=len(value[1]):raise ValueError('Tensor index outside static shape')
        return value[1][node[2]]
    return (node[0],*(substitute(x,environment) for x in node[1:]))


def evaluate(node,environment):
    op=node[0]
    if op=='const':return rational(node[1])
    if op=='var':return environment[node[1]]
    if op=='vector':return tuple(evaluate(x,environment) for x in node[1])
    if op=='true':return True
    if op=='false':return False
    if op=='index':return evaluate(node[1],environment)[node[2]]
    a=evaluate(node[1],environment)
    if op=='neg':return -a
    if op=='not':return not a
    if op=='denom':return Q(a.denominator)
    if op=='soma':return sum(a,Q(0))
    if op=='relu':return max(Q(0),a)
    if op=='norm':raise ValueError('Use a norm comparison, not an irrational rational value')
    b=evaluate(node[2],environment)
    if op=='+':return a+b
    if op=='-':return a-b
    if op=='*':return a*b
    if op=='/':
        if b==0:raise ValueError('Division by zero')
        return a/b
    if op=='pow':
        if b.denominator!=1 or not 0<=b<=20:raise ValueError('Bounded integral exponent required')
        return a**int(b)
    if op=='dot':return sum((x*y for x,y in zip(a,b,strict=True)),Q(0))
    if op=='and':return bool(a and b)
    if op=='or':return bool(a or b)
    return {'==':lambda:a==b,'!=':lambda:a!=b,'<=':lambda:a<=b,'>=':lambda:a>=b,'<':lambda:a<b,'>':lambda:a>b}[op]()


def render(node):
    op=node[0]
    if op=='const':
        q=rational(node[1]);return f'({q.numerator}/{q.denominator})'
    if op=='var':return node[1]
    if op=='neg':return '(-'+render(node[1])+')'
    if op=='vector':return '['+','.join(render(x) for x in node[1])+']'
    if op in ('+','-','*','/','pow'):return '('+render(node[1])+('^' if op=='pow' else op)+render(node[2])+')'
    if op in ('relu','soma','dot'):return op+'('+','.join(render(x) for x in node[1:])+')'
    raise ValueError('Expression is not executable Omega arithmetic')


def lower(source):
    """Independent parser for the native refinement metadata protocol."""
    reader=Reader(tokens(source));types=[]
    while reader.accept('type'):
        name=identifier(reader.take());reader.need('=');base=[]
        while reader.peek()!='where':base.append(reader.take())
        reader.need('where');reader.need('{');predicate=[]
        while reader.peek()!='}':predicate.append(reader.take())
        reader.need('}');reader.accept(';')
        types.append({'name':name,'base':base,'predicate':predicate})
    out=[];bindings=[]
    while reader.peek()!='<end>':
        item=reader.take();out.append(item)
        if item in ('parametro','tensor','vetor','matriz','perda'):
            name=identifier(reader.take());out.append(name)
            if reader.accept(':'):bindings.append({'kind':item,'name':name,'type':identifier(reader.take())})
    return {'format':'omega-refinement-source-1','types':types,'bindings':bindings,'source':' '.join(out)}
