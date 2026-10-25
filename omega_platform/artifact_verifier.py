"""Verify declared build bytes separately from generator execution."""
import json
import re
from pathlib import Path
from .manifest import verify,sha256
from omega_selfhost.driver import verify_result
class ArtifactVerifier:
    def __init__(self,root):self.root=Path(root).resolve(strict=True)
    def build(self,manifest):
        verify(manifest,self.root)
        return {'valid':True,'artifacts':len(manifest['artifacts']),'scope':'recorded byte integrity, not source-to-binary proof'}
    def execution(self,result):return verify_result(result)
    def promotion(self,manifest):
        """Byte integrity callback for PromotionGate, not source/binary equivalence.

        Independent attestations bind the manifest to a patch and baseline;
        this callback checks only the declared artifacts in a pinned root.
        """
        from omega_security.encoding import canonical
        from omega_evolution.component_registry import _path
        canonical(manifest)
        if type(manifest) is not dict or type(manifest.get('files')) is not dict or not manifest['files']:
            raise ValueError('Promotion artifact files required')
        if type(manifest.get('patch_sha256')) is not str or not re.fullmatch('[0-9a-f]{64}',manifest['patch_sha256']):
            raise ValueError('Patch provenance required')
        if type(manifest.get('baseline_version')) is not str or not manifest['baseline_version']:
            raise ValueError('Baseline provenance required')
        if type(manifest.get('baseline_artifacts_sha256')) is not str or not re.fullmatch('[0-9a-f]{64}',manifest['baseline_artifacts_sha256']):
            raise ValueError('Baseline artifact manifest digest required')
        for path,expected in manifest['files'].items():
            _path(path)
            if type(expected) is not str or not re.fullmatch('[0-9a-f]{64}',expected):raise ValueError('Full artifact digest required')
            self.compare(path,expected)
        return True
    def compare(self,path,expected):
        resolved=(self.root/path).resolve(strict=True)
        if not resolved.is_relative_to(self.root):raise ValueError('Artifact escapes root')
        if sha256(resolved)!=expected:raise ValueError('Artifact digest mismatch')
        return resolved
