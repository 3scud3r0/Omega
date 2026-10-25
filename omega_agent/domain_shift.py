"""Diagonal standardized-distance detector with explicit abstention threshold."""
import math,statistics
class DomainShift:
    def __init__(self,training):
        rows=tuple(tuple(float(v) for v in row) for row in training)
        if len(rows)<2 or not rows[0] or len(rows[0])>4096 or any(len(r)!=len(rows[0]) for r in rows):raise ValueError('Rectangular training features required')
        if any(not math.isfinite(v) for r in rows for v in r):raise ValueError('Finite features required')
        self.mean=tuple(statistics.mean(c) for c in zip(*rows));self.variance=tuple(max(statistics.variance(c),1e-12) for c in zip(*rows));self.threshold=None
    def score(self,row):
        if len(row)!=len(self.mean) or any(not math.isfinite(v) for v in row):raise ValueError('Feature mismatch')
        return sum((v-m)**2/s for v,m,s in zip(row,self.mean,self.variance))/len(row)
    def calibrate(self,heldout,quantile=.95):
        scores=sorted(self.score(r) for r in heldout)
        if not scores or not 0<quantile<1:raise ValueError('Calibration cases required')
        self.threshold=scores[min(math.ceil(len(scores)*quantile)-1,len(scores)-1)]
    def abstain(self,row):
        if self.threshold is None:raise ValueError('Detector is not calibrated')
        return self.score(row)>self.threshold
