"""Proof reuse binds statement, checker and dependencies and rechecks certificates."""
import hashlib,json
from .content_cache import ContentCache
class ProofCache:
    def __init__(self,root):self.blobs=ContentCache(root);self.index={}
    def key(self,statement,checker,dependencies):
        return hashlib.sha256(json.dumps([statement,checker,sorted(dependencies)],sort_keys=True,separators=(',',':')).encode()).hexdigest()
    def store(self,statement,checker,dependencies,certificate,verify):
        if verify(statement,certificate) is not True:raise ValueError('Certificate refused')
        key=self.key(statement,checker,dependencies)
        blob=self.blobs.put(json.dumps(certificate,sort_keys=True,separators=(',',':'),allow_nan=False).encode())
        self.index[key]=blob;return key
    def lookup(self,statement,checker,dependencies,verify):
        key=self.key(statement,checker,dependencies)
        if key not in self.index:return None
        certificate=json.loads(self.blobs.get(self.index[key]))
        if verify(statement,certificate) is not True:raise ValueError('Cached certificate failed revalidation')
        return certificate
