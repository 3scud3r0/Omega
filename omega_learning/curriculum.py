class Curriculum:
    def __init__(self,levels,minimum=5,advance=.8,retreat=.3):
        if not levels or not 0<=retreat<advance<=1 or minimum<1:raise ValueError('Invalid curriculum')
        self.levels=tuple(levels);self.position=0;self.minimum=minimum;self.advance=advance;self.retreat=retreat;self.observations=[]
    @property
    def current(self):return self.levels[self.position]
    def observe(self,verified):
        if type(verified) is not bool:raise ValueError('Independent verified outcome required')
        self.observations.append(verified)
        if len(self.observations)>=self.minimum:
            success=sum(self.observations)/len(self.observations)
            if success>=self.advance:self.position=min(self.position+1,len(self.levels)-1)
            elif success<self.retreat:self.position=max(0,self.position-1)
            self.observations=[]
        return self.current
