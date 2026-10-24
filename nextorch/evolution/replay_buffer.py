"""Bounded, deduplicated replay with verifier-owned admission and rechecked persistence."""

import hashlib
import json
import os
import tempfile
from collections import OrderedDict
from dataclasses import asdict, dataclass
from pathlib import Path

from nextorch.formal import FormalBarrier, LogicalProblem, VerificationResult


@dataclass(frozen=True)
class VerifiedExample:
    problem: LogicalProblem
    target: int
    certificate: VerificationResult
    origin: str

    @property
    def key(self):
        return hashlib.sha256(
            json.dumps([self.problem.premises, self.problem.source, self.target]).encode()
        ).hexdigest()


def atomic_json(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class CertifiedReplayBuffer:
    def __init__(self, capacity=4096, barrier=None):
        if capacity <= 0:
            raise ValueError("Replay capacity must be positive")
        self.capacity, self.barrier = capacity, barrier or FormalBarrier()
        self._entries = OrderedDict()

    def __len__(self):
        return len(self._entries)

    def __iter__(self):
        return iter(tuple(self._entries.values()))

    def admit(self, problem, target, origin="model"):
        certificate = self.barrier.certify(problem, target)
        if not certificate.valid:
            return False, certificate
        item = VerifiedExample(problem, target, certificate, origin)
        if item.key in self._entries:
            return False, certificate
        self._entries[item.key] = item
        if len(self) > self.capacity:
            self._entries.popitem(last=False)
        return True, certificate

    def to_dict(self):
        return {
            "version": 1,
            "capacity": self.capacity,
            "require_lean": self.barrier.require_lean,
            "entries": [asdict(item) for item in self],
        }

    def save(self, path):
        atomic_json(path, self.to_dict())

    @classmethod
    def from_dict(cls, payload, barrier=None):
        if payload.get("version") != 1:
            raise ValueError("Unsupported replay format")
        buffer = cls(
            payload["capacity"],
            barrier=barrier or FormalBarrier(require_lean=payload.get("require_lean", False)),
        )
        if len(payload["entries"]) > buffer.capacity:
            raise ValueError("Replay payload exceeds capacity")
        for record in payload["entries"]:
            problem = LogicalProblem(**record["problem"])
            # Never trust a serialized 'valid' flag or a certificate hash on its own.
            added, result = buffer.admit(problem, record["target"], record["origin"])
            if not added or not result.valid or record["certificate"]["status"] != "valid":
                raise ValueError("Uncertified or duplicate replay entry")
            if record["certificate"]["statement"] != result.statement:
                raise ValueError("Certificate is bound to a different statement")
        return buffer

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
