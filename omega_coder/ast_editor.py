"""AST-span edits preserve every byte outside the selected Python node."""
import ast,hashlib
from pathlib import Path
def replace_node(source,node,replacement,expected_sha256):
    data=source.encode('utf-8')
    if hashlib.sha256(data).hexdigest()!=expected_sha256:raise ValueError('Source changed before edit')
    if not isinstance(node,(ast.expr,ast.stmt)) or node.end_lineno is None:raise ValueError('A located expression/statement is required')
    parsed=ast.parse(replacement,mode='eval' if isinstance(node,ast.expr) else 'exec')
    if isinstance(node,ast.stmt) and len(parsed.body)!=1:raise ValueError('Exactly one replacement statement required')
    lines=data.splitlines(keepends=True)
    start=sum(map(len,lines[:node.lineno-1]))+node.col_offset
    end=sum(map(len,lines[:node.end_lineno-1]))+node.end_col_offset
    indent=lines[node.lineno-1][:node.col_offset].decode('utf-8')
    text=replacement.replace('\n','\n'+indent) if isinstance(node,ast.stmt) else replacement
    result=data[:start]+text.encode()+data[end:]
    ast.parse(result.decode())
    return result.decode()
def apply_in_worktree(path,content,capability,verifier,principal):
    path=Path(path);verifier.require(capability,principal,'code.write',path=path)
    if path.is_symlink():raise PermissionError('Cannot edit symlink')
    from omega_security.filesystem import write
    claim=verifier.require(capability,principal,'code.write',path=path)
    root=Path(claim['root']).resolve(strict=True)
    write(root,path.resolve().relative_to(root).as_posix(),content.encode('utf-8'))
