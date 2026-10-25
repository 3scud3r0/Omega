"""Swappable proposal protocol. Models do not possess verification authority."""
from typing import Protocol
class ReasoningModel(Protocol):
    def propose(self,problem,limit:int):...
class ModelAdapter:
    def __init__(self,model,encode,decode):self.model=model;self.encode=encode;self.decode=decode
    def propose(self,problem,limit):
        if not 1<=limit<=256:raise ValueError('Proposal budget exceeded')
        encoded=self.encode(problem);outputs=self.model.generate(encoded,max_candidates=limit)
        for i,output in enumerate(outputs):
            if i>=limit:break
            yield self.decode(output)
class ModelRegistry:
    def __init__(self):self.models={}
    def register(self,name,model):
        if not name or name in self.models or not callable(getattr(model,'propose',None)):raise ValueError('Invalid model registration')
        self.models[name]=model
    def get(self,name):return self.models[name]


class NextorchBooleanAdapter:
    """Adapter for the existing Omega/Nextorch finite Boolean proposer."""
    def __init__(self,budget=None):self.budget=budget
    def propose(self,problem,limit):
        from .proposer import propose,NeuralBudget
        if not 1<=limit<=256:raise ValueError('Proposal budget exceeded')
        task=dict(problem['inputs']) if isinstance(problem,dict) and 'inputs' in problem else problem
        if isinstance(problem,dict) and 'id' in problem and 'id' not in task:task['id']=problem['id']
        proposals,diagnostics=propose(task,self.budget or NeuralBudget())
        for origin,candidate in proposals[:limit]:yield candidate


def byte_reasoner(vocab_size=259,width=128,heads=4,layers=2,context=1024,seed=0):
    """Construct an actual bounded causal byte Transformer, without pretrained weights.

    Wrap it in ModelAdapter with a tokenizer encoder and a data-only decoder.
    Training/generation are explicit calls, never import-time side effects.
    """
    import torch
    from torch import nn
    if not 4<=vocab_size<=65536 or not 16<=width<=1024 or not 1<=layers<=24 or not 1<=heads<=16 or width%heads or not 1<=context<=2048:
        raise ValueError('Invalid sequence-model dimensions')
    if 2*vocab_size*width+context*width+12*layers*width*width>50000000:raise ValueError('Sequence-model parameter budget exceeded')
    class ByteReasoner(nn.Module):
        def __init__(self):
            super().__init__();self.context=context;self.vocab_size=vocab_size
            self.embedding=nn.Embedding(vocab_size,width);self.position=nn.Embedding(context,width)
            layer=nn.TransformerEncoderLayer(width,heads,dim_feedforward=4*width,dropout=0,batch_first=True)
            self.transformer=nn.TransformerEncoder(layer,layers);self.output=nn.Linear(width,vocab_size)
        def forward(self,tokens):
            if tokens.ndim!=2 or tokens.dtype!=torch.long or not 0<tokens.shape[1]<=context or tokens.shape[0]*tokens.shape[1]**2>2000000:
                raise ValueError('Sequence batch/attention budget exceeded')
            if torch.any(tokens<0) or torch.any(tokens>=vocab_size):raise ValueError('Sequence token outside vocabulary')
            positions=torch.arange(tokens.shape[1],device=tokens.device)
            hidden=self.embedding(tokens)+self.position(positions)
            mask=torch.triu(torch.ones(tokens.shape[1],tokens.shape[1],dtype=torch.bool,device=tokens.device),diagonal=1)
            return self.output(self.transformer(hidden,mask=mask))
        def generate(self,prompt,*,max_candidates=4,max_new_tokens=128,seed=0,eos=257):
            if not 1<=max_candidates<=32 or not 1<=max_new_tokens<=256 or max_candidates*max_new_tokens>4096:raise ValueError('Generation budget exceeded')
            if not prompt or any(type(t) is not int or not 0<=t<vocab_size for t in prompt):raise ValueError('Valid prefix tokens required')
            device=next(self.parameters()).device;generator=torch.Generator(device=device).manual_seed(seed);training=self.training
            self.eval();results=[]
            try:
                with torch.no_grad():
                    for _ in range(max_candidates):
                        sequence=list(prompt[-context:]);generated=[]
                        for _ in range(max_new_tokens):
                            tokens=torch.tensor([sequence[-context:]],dtype=torch.long,device=device)
                            logits=self(tokens)[0,-1].float()
                            if vocab_size>258:logits[256]=-torch.inf;logits[258]=-torch.inf
                            if not torch.isfinite(logits).any():raise ValueError('Model has no finite next token')
                            token=int(torch.multinomial(torch.softmax(logits,dim=-1),1,generator=generator))
                            generated.append(token);sequence.append(token)
                            if token==eos:break
                        results.append(tuple(generated))
            finally:self.train(training)
            return tuple(results)
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed);return ByteReasoner()
