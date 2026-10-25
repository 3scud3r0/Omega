import hashlib,json
class ObjectiveGuard:
    def __init__(self,goal,owner,authorize_change):
        self.goal=goal;self.owner=owner;self.authorize_change=authorize_change;self.digest=self._hash(goal)
    def _hash(self,goal):return hashlib.sha256(json.dumps(goal,sort_keys=True,allow_nan=False).encode()).hexdigest()
    def check(self,goal):
        if self._hash(goal)!=self.digest:raise PermissionError('Objective mutation denied')
        return True
    def replace(self,goal,approval):
        new=self._hash(goal)
        if self.authorize_change(self.owner,self.digest,new,approval) is not True:raise PermissionError('Objective change not authorized')
        self.goal=goal;self.digest=new
