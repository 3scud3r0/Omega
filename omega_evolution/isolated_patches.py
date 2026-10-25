from pathlib import Path
from omega_coder.worktrees import Worktree
class IsolatedPatch:
    def __init__(self,worktree,registry,component,verifier,principal,capability):
        self.worktree=worktree;self.registry=registry;self.component=component;self.verifier=verifier;self.principal=principal;self.capability=capability
    def apply(self,changes):
        self.registry.require_patch(self.component,changes)
        root=self.worktree.path.resolve(strict=True)
        prepared=[]
        for relative,content in changes.items():
            path=(root/relative).resolve()
            if not path.is_relative_to(root) or '.git' in Path(relative).parts:raise PermissionError('Patch outside isolated source tree')
            self.verifier.require(self.capability,self.principal,'code.write',path=path)
            if len(content.encode())>1024*1024:raise ValueError('Patch file budget exceeded')
            prepared.append((path,content))
        for path,content in prepared:
            from omega_security.filesystem import write
            write(root,path.relative_to(root).as_posix(),content.encode('utf-8'),create=True)
        return self.worktree.diff()
