"""Only a discharged contradiction may justify pruning a partial subtree."""
from omega_refine_check.syntax import parse,substitute
from omega_refine_check.lean import prove


def contains_hole(node):
    if node[0]=='hole':return True
    return any(contains_hole(child) for child in node[1:] if isinstance(child,(tuple,list)))


class LeanPruner:
    def __init__(self,variables,*,enabled=True):
        self.variables=variables;self.enabled=enabled;self.cache={};self.certificates=[]
    def prune(self,partial):
        if not self.enabled:return False
        denominator=None
        def visit(node):
            nonlocal denominator
            if node[0]=='/' and not contains_hole(node[2]):denominator=node[2]
            for child in node[1:]:
                if isinstance(child,(tuple,list)):visit(child)
        visit(partial)
        if denominator is None:return False
        key=repr(denominator)
        if key in self.cache:return self.cache[key]
        # Test exact constant contradictions cheaply before invoking Lean.
        if denominator[0]!='const' or denominator[1]!='0':self.cache[key]=False;return False
        names=list(self.variables);premises=[]
        for name,predicate in self.variables.items():premises.append(substitute(parse(predicate),{'self':('var',name),**{v:('var',v) for v in names}}))
        proof=prove(names,premises,[('==',denominator,('const','0'))])
        self.certificates.append({'reason':'identically zero divisor in every completion','denominator':denominator,'proof':proof})
        self.cache[key]=True;return True
