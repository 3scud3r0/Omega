"""Replay debugger for pure graph snapshots, without hidden mutation."""
from .trace import evaluate
class Debugger:
    def __init__(self,ir,state):self.frames=evaluate(ir,state);self.position=0;self.breakpoints=set()
    def add_breakpoint(self,index):
        if type(index) is not int or not 0<=index<len(self.frames):raise ValueError('Invalid breakpoint')
        self.breakpoints.add(index)
    def seek(self,index):
        if type(index) is not int or not 0<=index<=len(self.frames):raise ValueError('Invalid trace position')
        self.position=index
    def step(self):
        if self.position==len(self.frames):raise StopIteration
        frame=self.frames[self.position];self.position+=1;return frame
    def resume(self):
        frames=[]
        while self.position<len(self.frames):
            frames.append(self.step())
            if self.position in self.breakpoints:break
        return tuple(frames)
