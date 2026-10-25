"""Finite MDP simulator with explicit state/action/reward contracts."""
import math,random
class Simulation:
    def __init__(self,transitions,initial,terminal=(),seed=0):
        self.transitions=transitions;self.initial=initial;self.state=initial;self.terminal=frozenset(terminal);self.rng=random.Random(seed);self.steps=0
        if len(transitions)>10000 or initial not in transitions:raise ValueError('Invalid simulation state space')
        for state,actions in transitions.items():
            for action,outcomes in actions.items():
                if not outcomes or abs(sum(p for p,s,r in outcomes)-1)>1e-8:raise ValueError('Transition probabilities must sum to one')
                if any(not 0<=p<=1 or s not in transitions or not math.isfinite(r) for p,s,r in outcomes):raise ValueError('Invalid finite transition')
    def reset(self):self.state=self.initial;self.steps=0;return self.state
    def actions(self):return tuple(sorted(self.transitions[self.state],key=repr))
    def step(self,action):
        if self.state in self.terminal or self.steps>=10000:raise ValueError('Simulation terminated')
        outcomes=self.transitions[self.state][action];index=self.rng.choices(range(len(outcomes)),weights=[p for p,s,r in outcomes],k=1)[0]
        _,state,reward=outcomes[index];self.state=state;self.steps+=1
        return {'state':state,'reward':reward,'terminal':state in self.terminal,'step':self.steps}
