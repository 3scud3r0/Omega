"""Bounded static symbol/import/call index; dynamic resolution is not inferred."""
import ast,hashlib,re
from pathlib import Path
def index(root,max_bytes=16*1024**2,max_files=2048):
    root=Path(root).resolve();records={};total=0
    for path in sorted(root.rglob('*')):
        if any(p in {'.git','.venv','.lake','__pycache__','node_modules'} for p in path.relative_to(root).parts):continue
        if path.is_symlink() or not path.is_file() or path.suffix not in {'.py','.omega','.c','.h','.lean'}:continue
        data=path.read_bytes();total+=len(data)
        if total>max_bytes or len(records)>=max_files:raise ValueError('Repository index budget exceeded')
        source=data.decode('utf-8');symbols=[];calls=[];imports=[]
        if path.suffix=='.py':
            tree=ast.parse(source)
            for node in ast.walk(tree):
                if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):symbols.append({'name':node.name,'line':node.lineno,'kind':type(node).__name__})
                if isinstance(node,ast.Call):calls.append({'callee':ast.unparse(node.func),'line':node.lineno})
                if isinstance(node,ast.Import):imports.extend(x.name for x in node.names)
                if isinstance(node,ast.ImportFrom):imports.append('.'*node.level+(node.module or ''))
        else:
            pattern=r'\b(funcao|def|theorem|lemma)\s+([^\W\d]\w*)'
            for match in re.finditer(pattern,source):symbols.append({'name':match[2],'line':source.count('\n',0,match.start())+1,'kind':match[1]})
            imports=re.findall(r'^\s*(?:import\s+([^\n]+)|#include\s+"([^"]+)")',source,re.MULTILINE)
        records[path.relative_to(root).as_posix()]={'sha256':hashlib.sha256(data).hexdigest(),'symbols':symbols,'calls':calls,'imports':imports}
    return records
