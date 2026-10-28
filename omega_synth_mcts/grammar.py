"""Finite-budget traversals of an unbounded rational expression grammar."""
from omega_refine_check.syntax import tree,identifier,rational,render


def size(node):
    return 1+sum(size(x) for x in node[1:] if isinstance(x,(tuple,list)))


def holes(node):
    if node[0]=='hole':return 1
    return sum(holes(x) for x in node[1:] if isinstance(x,(tuple,list)))


def first_hole(node,path=()):
    if node[0]=='hole':return path
    for i,child in enumerate(node[1:],1):
        if isinstance(child,(tuple,list)):
            found=first_hole(child,path+(i,))
            if found is not None:return found
    return None


def replace(node,path,replacement):
    if not path:return replacement
    result=list(node);result[path[0]]=replace(node[path[0]],path[1:],replacement)
    return tuple(result)


class Grammar:
    def __init__(self,variables,constants=(0,1,-1),*,operators=('+','-','*','/','neg','relu'),max_nodes=15,max_depth=8):
        self.variables=tuple(identifier(v) for v in variables)
        self.constants=tuple(dict.fromkeys(str(rational(c)) for c in constants))
        if not self.variables and not self.constants:raise ValueError('A grammar atom is required')
        if len(self.variables)>32 or len(self.constants)>64:raise ValueError('Grammar atom budget exceeded')
        if any(op not in ('+','-','*','/','neg','relu') for op in operators) or len(set(operators))!=len(operators):raise ValueError('Unsupported grammar production')
        if type(max_nodes) is not int or not 1<=max_nodes<=63 or type(max_depth) is not int or not 1<=max_depth<=16:raise ValueError('Grammar resource budget exceeded')
        self.operators=tuple(operators);self.max_nodes=max_nodes;self.max_depth=max_depth
    def productions(self,partial):
        path=first_hole(partial)
        if path is None:return []
        options=[('var:'+v,('var',v)) for v in self.variables]+[('const:'+c,('const',c)) for c in self.constants]
        for op in self.operators:
            arity=1 if op in ('neg','relu') else 2
            if len(path)+1<self.max_depth and size(partial)+arity<=self.max_nodes:
                options.append((op,(op,*[('hole',)]*arity)))
        return [(label,replace(partial,path,value)) for label,value in options]
    def complete(self,partial,rng):
        while holes(partial):
            choices=self.productions(partial)
            atoms=[choice for choice in choices if holes(choice[1])<holes(partial)]
            if not choices:raise ValueError('Grammar cannot complete partial AST')
            pool=atoms if rng.random()<0.72 else choices
            partial=rng.choice(pool)[1]
        return partial
