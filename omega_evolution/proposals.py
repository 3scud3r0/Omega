"""Immutable improvement claims; measurements and approvals remain separate."""
from dataclasses import dataclass, asdict
import math
import re
from omega_security.encoding import digest


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
        for name, limit in (('component', 256), ('hypothesis', 16384), ('proposer', 256), ('baseline_version', 256)):
            value = getattr(self, name)
            if type(value) is not str or not 0 < len(value) <= limit:
                raise ValueError('Incomplete improvement hypothesis: ' + name)
        if type(self.patch_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', self.patch_sha256):
            raise ValueError('Full patch digest required')
        if any(type(v) not in (int, float) or not math.isfinite(v) for v in (self.expected_gain, self.reserved_cost)) or self.reserved_cost <= 0:
            raise ValueError('Invalid improvement estimate')

    @property
    def id(self):
        return digest(asdict(self))
