from dataclasses import dataclass,asdict
import hashlib,json,math
@dataclass(frozen=True)
class Proposal:
    component: str
    hypothesis: str
    expected_gain: float
    reserved_cost: float
    patch_sha256: str
    proposer: str
    baseline_version: str
    def __post_init__(self):
        if not self.hypothesis or not self.proposer or not self.baseline_version or len(self.patch_sha256)!=64:raise ValueError('Incomplete improvement hypothesis')
        if not math.isfinite(self.expected_gain) or not math.isfinite(self.reserved_cost) or self.reserved_cost<=0:raise ValueError('Invalid improvement estimate')
    @property
    def id(self):return hashlib.sha256(json.dumps(asdict(self),sort_keys=True,separators=(',',':')).encode()).hexdigest()
