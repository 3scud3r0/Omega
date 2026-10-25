from threading import RLock,Event
class Revocations:
    def __init__(self):self.lock=RLock();self.revoked=set();self.stop=Event();self.callbacks={}
    def active(self,id):
        with self.lock:return not self.stop.is_set() and id not in self.revoked
    def register(self,id,cancel):
        with self.lock:
            if not self.active(id):raise PermissionError('Capability revoked')
            self.callbacks.setdefault(id,[]).append(cancel)
    def unregister(self,id,cancel):
        with self.lock:
            callbacks=self.callbacks.get(id,[])
            self.callbacks[id]=[callback for callback in callbacks if callback is not cancel]
            if not self.callbacks[id]:self.callbacks.pop(id,None)
    def revoke(self,id):
        with self.lock:self.revoked.add(id);callbacks=self.callbacks.pop(id,[])
        failures=[]
        for cancel in callbacks:
            try:cancel()
            except Exception as exc:failures.append(type(exc).__name__)
        return tuple(failures)
    def shutdown(self):
        self.stop.set()
        with self.lock:ids=tuple(self.callbacks)
        return {id:self.revoke(id) for id in ids}
