"""Thread-safe reservations; a cancelled scope releases only its own reservation."""
from contextlib import contextmanager
from threading import RLock,Event
class Quota:
    def __init__(self,**limits):
        if not limits or any(type(v) is not int or v<0 for v in limits.values()):raise ValueError('Nonnegative quotas required')
        self.limits=dict(limits);self.used=dict.fromkeys(limits,0);self.lock=RLock();self.revoked=Event()
    def revoke(self):self.revoked.set()
    def consume(self,**cost):
        with self.lock:
            if self.revoked.is_set():raise PermissionError('Quota revoked')
            if any(k not in self.limits or type(v) is not int or v<0 for k,v in cost.items()):raise ValueError('Invalid cost')
            if any(self.used[k]+v>self.limits[k] for k,v in cost.items()):raise ValueError('Quota exhausted')
            for k,v in cost.items():self.used[k]+=v
    @contextmanager
    def reserve(self,**cost):
        self.consume(**cost)
        try:yield
        finally:
            with self.lock:
                for k,v in cost.items():self.used[k]-=v
