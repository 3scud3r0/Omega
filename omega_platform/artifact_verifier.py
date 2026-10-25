"""Verify declared build bytes separately from generator execution."""
import json
from pathlib import Path
from .manifest import verify,sha256
from omega_selfhost.driver import verify_result
class ArtifactVerifier:
    def __init__(self,root):self.root=Path(root).resolve(strict=True)
    def build(self,manifest):
        verify(manifest,self.root)
        return {'valid':True,'artifacts':len(manifest['artifacts']),'scope':'recorded byte integrity, not source-to-binary proof'}
    def execution(self,result):return verify_result(result)
    def compare(self,path,expected):
        resolved=(self.root/path).resolve(strict=True)
        if not resolved.is_relative_to(self.root):raise ValueError('Artifact escapes root')
        if sha256(resolved)!=expected:raise ValueError('Artifact digest mismatch')
        return resolved
