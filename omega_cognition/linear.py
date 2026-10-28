"""Generation-tagged linear ownership; borrowing never duplicates ownership."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Borrow:
    resource:int
    generation:int
    serial:int
    mutable:bool


class LinearContext:
    def __init__(self,capacity):
        if type(capacity) is not int or not 1<=capacity<=2**30:raise ValueError('Bounded linear arena capacity required')
        self.capacity=capacity;self.resources={};self.names={};self.borrows={};self.serial=0;self.used=0;self.events=[]
    def allocate(self,name,size):
        if type(name) is not str or not name or name in self.names or type(size) is not int or not 1<=size<=self.capacity-self.used:raise ValueError('Invalid linear allocation')
        identity=len(self.resources);self.resources[identity]={'owner':name,'bytes':size,'generation':0,'alive':True}
        self.names[name]=identity;self.used+=size;self.events.append(('allocate',name,size));return identity
    def _resource(self,name):
        if name not in self.names:raise ValueError('Unknown or consumed owner')
        identity=self.names[name];resource=self.resources[identity]
        if not resource['alive'] or resource['owner']!=name:raise ValueError('Use after move or release')
        return identity,resource
    def move(self,source,target):
        identity,resource=self._resource(source)
        if target in self.names or any(b.resource==identity for b in self.borrows.values()):raise ValueError('Move requires exclusive ownership and a fresh destination')
        del self.names[source];self.names[target]=identity;resource['owner']=target;resource['generation']+=1
        self.events.append(('move',source,target));return identity
    def borrow(self,name,*,mutable=False):
        identity,resource=self._resource(name)
        if type(mutable) is not bool:raise ValueError('Explicit borrow mutability required')
        active=[b for b in self.borrows.values() if b.resource==identity]
        if active and (mutable or any(b.mutable for b in active)):raise ValueError('Aliasing mutable borrow')
        self.serial+=1;token=Borrow(identity,resource['generation'],self.serial,mutable);self.borrows[token.serial]=token
        return token
    def release_borrow(self,token):
        if type(token) is not Borrow or self.borrows.get(token.serial)!=token:raise ValueError('Expired or forged borrow')
        resource=self.resources[token.resource]
        if not resource['alive'] or resource['generation']!=token.generation:raise ValueError('Borrow generation expired')
        del self.borrows[token.serial]
    def consume(self,name):
        identity,resource=self._resource(name)
        if any(b.resource==identity for b in self.borrows.values()):raise ValueError('Resource still borrowed')
        resource['alive']=False;resource['generation']+=1;self.used-=resource['bytes'];del self.names[name]
        self.events.append(('consume',name));return resource['bytes']
    def finish(self):
        if self.names or self.borrows:raise ValueError('Unconsumed linear resources or outstanding borrows')
        return {'valid':True,'peak_capacity':self.capacity,'events':tuple(self.events),'remaining_bytes':self.used}
