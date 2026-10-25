"""Token-level masking with grammar/type-state supplied by a bounded decoder."""
import math,random
class ConstrainedDecoder:
    def __init__(self,grammar,max_tokens=4096):
        if not 1<=max_tokens<=65536:raise ValueError('Invalid decoding budget')
        self.grammar=grammar;self.max_tokens=max_tokens
    def generate(self,logits,initial,seed=0):
        state=initial;tokens=[];rng=random.Random(seed)
        for _ in range(self.max_tokens):
            if self.grammar.complete(state):return tuple(tokens),state
            allowed=tuple(sorted(self.grammar.allowed(state)))
            scores=logits(tuple(tokens),state)
            if not allowed or any(t<0 or t>=len(scores) for t in allowed):raise ValueError('Grammar has no valid next token')
            finite=[(t,scores[t]) for t in allowed if math.isfinite(scores[t])]
            if not finite:raise ValueError('No finite valid proposal logits')
            maximum=max(s for t,s in finite);weights=[math.exp(s-maximum) for t,s in finite]
            token=rng.choices([t for t,s in finite],weights=weights,k=1)[0]
            state=self.grammar.advance(state,token);tokens.append(token)
        raise TimeoutError('Constrained generation budget exhausted')
