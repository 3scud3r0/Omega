"""Hybrid lexical/cosine retrieval with deterministic ties and supplied embeddings."""
import collections,math,re
class HybridIndex:
    def __init__(self,dimension,alpha=.5):
        if not 1<=dimension<=4096 or not 0<=alpha<=1:raise ValueError('Invalid retrieval configuration')
        self.dimension=dimension;self.alpha=alpha;self.documents={}
    def _vector(self,vector):
        if len(vector)!=self.dimension or any(not math.isfinite(x) for x in vector):raise ValueError('Embedding mismatch')
        norm=math.sqrt(sum(x*x for x in vector));return tuple(x/norm if norm else 0.0 for x in vector)
    def add(self,id,text,embedding,evidence):
        if len(self.documents)>=10000 and id not in self.documents:raise ValueError('Retrieval quota exceeded')
        if not evidence or len(text)>65536:raise ValueError('Provenance/text required')
        tokens=collections.Counter(re.findall(r'\w+',text.lower()))
        self.documents[id]=(tokens,self._vector(embedding),tuple(evidence))
    def search(self,text,embedding,k=10):
        if not 1<=k<=100:raise ValueError('Invalid retrieval count')
        query=collections.Counter(re.findall(r'\w+',text.lower()));vector=self._vector(embedding);count=len(self.documents)
        df=collections.Counter(t for tokens,_,_ in self.documents.values() for t in tokens);results=[]
        for id,(tokens,dense,evidence) in self.documents.items():
            lexical=sum(math.log(1+(count-df[t]+.5)/(df[t]+.5))*min(c,tokens[t]) for t,c in query.items())
            cosine=sum(a*b for a,b in zip(vector,dense))
            score=self.alpha*(lexical/(1+lexical))+(1-self.alpha)*(cosine+1)/2
            results.append({'id':id,'score':score,'evidence':evidence})
        return tuple(sorted(results,key=lambda r:(-r['score'],r['id']))[:k])
