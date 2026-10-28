"""Deterministic, local procedural modules, linked through parsed syntax.

Imports grant no filesystem authority beyond the explicit root. The linker
does not execute module code or accept arbitrary Python/Lean extensions.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path,PurePosixPath
import re
import stat

from omega_selfhost.bootstrap import Bootstrap,TOKEN,BUILTINS
from .typesystem import TypeCheckError


_TOKEN=re.compile(r'::|'+TOKEN.pattern,re.UNICODE)


def _tokens(source):
    if len(source)>256*1024:raise TypeCheckError('Module source budget exceeded')
    result=[];position=0
    for match in _TOKEN.finditer(source):
        if match.start()!=position:raise TypeCheckError('Invalid module source token')
        position=match.end();token=match.group()
        if not token.isspace() and not token.startswith(('#','//')):result.append(token)
        if len(result)>120000:raise TypeCheckError('Module token budget exceeded')
    if position!=len(source):raise TypeCheckError('Trailing module source data')
    return result+['<fim>']


@dataclass(frozen=True)
class Module:
    path: str
    digest: str
    imports: tuple[tuple[str,str],...]
    exports: frozenset[str]
    functions: tuple
    qualified: tuple[tuple[str,str,str],...]


class _Parser(Bootstrap):
    def __init__(self,source):self.t=_tokens(source);self.i=0

    def module(self,path,digest):
        imports={};exports=set()
        if self.accept('modulo'):self.name();self.need(';')
        while self.t[self.i] in ('importar','exportar'):
            if self.accept('importar'):
                raw=self.take()
                if not raw.startswith('"'):raise TypeCheckError('Import path must be a quoted relative path')
                target=json.loads(raw);self.need('como');alias=self.name();self.need(';')
                if alias in imports:raise TypeCheckError('Repeated module alias: '+alias)
                imports[alias]=target
            else:
                self.need('exportar');names=[self.name()]
                while self.accept(','):names.append(self.name())
                self.need(';')
                for name in names:
                    if name in exports:raise TypeCheckError('Repeated export: '+name)
                    exports.add(name)
        # Qualified calls get temporary token identities, never text replacement
        # inside a string, comment, local name or a function body literal.
        tokens=self.t[self.i:];calls=[];rewritten=[];i=0
        source_names={s for s in tokens if s.isidentifier()}
        while i<len(tokens):
            token=tokens[i]
            if i+1<len(tokens) and tokens[i+1]=='::':
                if i+3>=len(tokens) or not token.isidentifier() or not tokens[i+2].isidentifier() or tokens[i+3]!='(':
                    raise TypeCheckError('Qualified imports support function calls only')
                symbol='__omega_import_call_'+str(len(calls))
                while symbol in source_names:symbol+='_'  # prevent capture by user identifiers
                source_names.add(symbol);calls.append((symbol,token,tokens[i+2]))
                rewritten.append(symbol);i+=3
            else:rewritten.append(token);i+=1
        self.t=rewritten;self.i=0
        functions=self.parse();names=[f[0] for f in functions]
        if len(names)!=len(set(names)) or set(names)&set(BUILTINS):raise TypeCheckError('Repeated or reserved module function')
        if not exports<=set(names):raise TypeCheckError('Export names an undefined function')
        return Module(path,digest,tuple(sorted(imports.items())),frozenset(exports),tuple(functions),tuple(calls))


def _expression(ast,resolve,depth=0):
    if depth>200:raise TypeCheckError('Module AST depth exceeded')
    render=lambda child:_expression(child,resolve,depth+1)
    kind=ast[0]
    if kind=='s':return json.dumps(ast[1],ensure_ascii=False)
    if kind in ('n','v'):return ast[1]
    if kind=='list':return '['+','.join(render(child) for child in ast[1])+']'
    if kind=='index':return '('+render(ast[1])+')['+render(ast[2])+']'
    if kind=='call':return resolve(ast[1])+'('+','.join(render(child) for child in ast[2])+')'
    if kind=='un':return '('+ast[1]+render(ast[2])+')'
    if kind=='bin':return '('+render(ast[2])+ast[1]+render(ast[3])+')'
    raise TypeCheckError('Unsupported module expression')


def _statements(statements,resolve,depth=0):
    if depth>100:raise TypeCheckError('Module block nesting exceeded')
    lines=[];expr=lambda a:_expression(a,resolve)
    for statement in statements:
        kind=statement[0]
        if kind in ('var','set'):lines.append(('var ' if kind=='var' else '')+statement[1]+'='+expr(statement[2])+';')
        elif kind=='return':lines.append('retornar '+expr(statement[1])+';')
        elif kind=='break':lines.append('parar;')
        elif kind=='expr':lines.append(expr(statement[1])+';')
        elif kind in ('se','enquanto'):
            body=kind+'('+expr(statement[1])+'){'+_statements(statement[2],resolve,depth+1)+'}'
            if statement[3]:body+='senao{'+_statements(statement[3],resolve,depth+1)+'}'
            lines.append(body)
        else:raise TypeCheckError('Unsupported module statement')
    return '\n'.join(lines)


@dataclass(frozen=True)
class LinkedProgram:
    source: str
    _manifest: bytes

    def manifest(self):return json.loads(self._manifest)


def link(entry,root):
    root=Path(root).resolve(strict=True)
    if not root.is_dir():raise TypeCheckError('Module root must be a directory')
    modules={};resolved_imports={};active=[];order=[];total=0
    def path_for(raw,parent=''):
        if type(raw) is not str or '\\' in raw or ':' in raw or any(ord(c)<32 for c in raw) or len(raw)>1024:
            raise TypeCheckError('Invalid module path')
        relative=PurePosixPath(raw)
        if relative.is_absolute():raise TypeCheckError('Module imports must be relative')
        parts=[]
        for part in (PurePosixPath(parent)/relative).parts:
            if part=='..':
                if not parts:raise TypeCheckError('Module import escapes its root')
                parts.pop()
            elif part not in ('','.'):parts.append(part)
        path=PurePosixPath(*parts)
        if path.suffix!='.omega':raise TypeCheckError('Imports require regular .omega files')
        return path.as_posix()
    entry_path=Path(entry)
    if entry_path.is_absolute():
        try:entry_name=path_for(entry_path.relative_to(root).as_posix())
        except ValueError:raise TypeCheckError('Entry module escapes its root') from None
    else:entry_name=path_for(entry_path.as_posix())
    def read(name):
        # Open relative to an anchored root descriptor, without a symlink
        # check/open race or a blocking read from a device/FIFO.
        directory=os.dup(root_fd)
        try:
            parts=PurePosixPath(name).parts
            for part in parts[:-1]:
                child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=directory)
                os.close(directory);directory=child
            fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=directory)
            with os.fdopen(fd,'rb') as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise TypeCheckError('Module is not a regular file')
                return stream.read(1024*1024+1)
        except OSError as exc:raise TypeCheckError('Cannot read a regular module within root: '+name) from exc
        finally:os.close(directory)
    def visit(name):
        nonlocal total
        if name in active:raise TypeCheckError('Module dependency cycle: '+' -> '.join([*active,name]))
        if name in modules:return
        if len(modules)+len(active)>=64:raise TypeCheckError('Module count budget exceeded')
        active.append(name)
        data=read(name)
        total+=len(data)
        if total>1024*1024:raise TypeCheckError('Module graph byte budget exceeded')
        try:module=_Parser(data.decode('utf-8')).module(name,hashlib.sha256(data).hexdigest())
        except (ValueError,UnicodeError,RecursionError,IndexError) as exc:raise TypeCheckError('Invalid module '+name+': '+str(exc)) from exc
        dependencies={alias:path_for(raw,PurePosixPath(name).parent) for alias,raw in module.imports}
        resolved_imports[name]=dependencies
        for dependency in sorted(set(dependencies.values())):visit(dependency)
        active.pop();modules[name]=module;order.append(name)
    root_fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:visit(entry_name)
    finally:os.close(root_fd)
    names={name:'om_mod_'+str(i)+'_' for i,name in enumerate(sorted(modules))}
    origins={};pieces=[]
    for name in order:
        module=modules[name];functions={f[0] for f in module.functions};qualified={s:(a,f) for s,a,f in module.qualified}
        if name!=entry_name and 'principal' in functions:raise TypeCheckError('Library module cannot define principal')
        if name==entry_name and 'principal' not in functions:raise TypeCheckError('Entry module must define principal')
        def symbol(function):return 'principal' if name==entry_name and function=='principal' else names[name]+function
        def resolve(function):
            if function in qualified:
                alias,target=qualified[function]
                if alias not in resolved_imports[name]:raise TypeCheckError('Unknown import alias: '+alias)
                imported=resolved_imports[name][alias]
                if target not in modules[imported].exports:raise TypeCheckError('Function is not exported: '+alias+'::'+target)
                return names[imported]+target
            if function in BUILTINS:return function
            if function not in functions:raise TypeCheckError('Unknown module function: '+function)
            return symbol(function)
        for function,args,body in sorted(module.functions,key=lambda f:f[0]):
            output=symbol(function);origins[output]={'module':name,'function':function}
            pieces.append('funcao '+output+'('+','.join(args)+'){\n'+_statements(body,resolve)+'\n}')
    source='\n'.join(pieces)+'\n'
    if len(source)>256*1024:raise TypeCheckError('Linked source budget exceeded')
    from .procedural_types import infer_procedural
    inferred=infer_procedural(source)
    manifest={'format':'omega-modules-1','entry':entry_name,'order':order,
              'modules':{name:{'sha256':modules[name].digest,'imports':resolved_imports[name],
                               'exports':sorted(modules[name].exports)} for name in sorted(modules)},
              'origins':origins,'linked_sha256':hashlib.sha256(source.encode()).hexdigest(),
              'types':inferred.to_dict()}
    return LinkedProgram(source,json.dumps(manifest,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode())


def verify_manifest(manifest,root):
    if type(manifest) is not dict or manifest.get('format')!='omega-modules-1' or type(manifest.get('entry')) is not str:
        raise TypeCheckError('Malformed module manifest')
    expected=link(manifest['entry'],root).manifest()
    try:
        encode=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
        same=encode(manifest)==encode(expected)
    except (ValueError,TypeError,RecursionError):raise TypeCheckError('Malformed module manifest') from None
    if not same:raise TypeCheckError('Module manifest or source closure has changed')
    return True
