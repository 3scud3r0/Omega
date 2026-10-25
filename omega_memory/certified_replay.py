import random,hashlib,json
class CertifiedReplay:
    def __init__(self,verify,capacity=1000):
        if not 1<=capacity<=100000:raise ValueError('Invalid replay capacity')
        self.verify=verify;self.capacity=capacity;self.items={};self.order=[]
    def add(self,sample,certificate):
        if self.verify(sample,certificate) is not True:raise ValueError('Uncertified replay sample')
        payload=json.dumps([sample,certificate],sort_keys=True,allow_nan=False);key=hashlib.sha256(payload.encode()).hexdigest()
        if key not in self.items:
            if len(self.order)==self.capacity:del self.items[self.order.pop(0)]
            self.order.append(key);self.items[key]=payload
        return key
    def sample(self,count,seed):
        if not 0<=count<=len(self.order):raise ValueError('Replay sample count exceeds buffer')
        result=[]
        for key in random.Random(seed).sample(self.order,count):
            sample,certificate=json.loads(self.items[key])
            if self.verify(sample,certificate) is not True:raise ValueError('Replay certificate no longer valid')
            result.append((sample,certificate))
        return tuple(result)
