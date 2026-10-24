"""Explicit pipeline results. A failed result can never be unwrapped as a value."""
from __future__ import annotations

from dataclasses import dataclass,field
from enum import Enum
from types import MappingProxyType
from typing import Generic,TypeVar,Callable
import json


class Code(str,Enum):
    TYPE='input.type'
    INVALID='input.invalid'
    JSON='data.json'
    MISSING='io.missing'
    EXISTS='io.exists'
    DENIED='io.denied'
    IO='io.failed'
    ISOLATION='sandbox.unavailable'
    WALL='limit.wall'
    OUTPUT='limit.output'
    ANALYSIS='limit.analysis'
    MEMORY='memory.exhausted'
    SIGNAL='process.signal'
    EXIT='process.exit'
    PROOF='proof.failed'
    PIPELINE='pipeline.failed'
    INTERNAL='internal.error'


@dataclass(frozen=True)
class Problem:
    code: Code
    stage: str
    message: str
    details: dict=field(default_factory=dict)

    def __post_init__(self):
        if type(self.code) is not Code or type(self.stage) is not str or not 1<=len(self.stage)<=64:
            raise ValueError('Invalid problem code or stage')
        if type(self.message) is not str or len(self.message)>4096:raise ValueError('Invalid problem message')
        if type(self.details) is not dict or not set(self.details)<={'returncode','signal','termination','exception'}:
            raise ValueError('Invalid problem detail fields')
        for key,value in self.details.items():
            if key in ('returncode','signal') and value is not None and type(value) is not int:raise ValueError('Invalid process status')
            if key in ('termination','exception') and (type(value) is not str or len(value)>128):raise ValueError('Invalid diagnostic classification')
        object.__setattr__(self,'details',MappingProxyType(dict(self.details)))

    def to_dict(self):return {'code':self.code.value,'stage':self.stage,'message':self.message,'details':dict(self.details)}


class PipelineFailure(RuntimeError):
    def __init__(self,problem):
        self.problem=problem
        super().__init__(f'{problem.code.value} [{problem.stage}]: {problem.message}')


T=TypeVar('T')


@dataclass(frozen=True)
class Ok(Generic[T]):
    value: T
    @property
    def is_ok(self):return True
    def unwrap(self):return self.value
    def __bool__(self):raise TypeError('Use result.is_ok to inspect a Result')
    def to_dict(self):return {'format':'omega-result-1','ok':True,'value':self.value}


@dataclass(frozen=True)
class Err:
    problem: Problem
    cause: Exception|None=field(default=None,repr=False,compare=False)
    def __post_init__(self):
        if type(self.problem) is not Problem or (self.cause is not None and not isinstance(self.cause,Exception)):
            raise ValueError('Err requires a typed problem and optional exception')
    @property
    def is_ok(self):return False
    def unwrap(self):raise PipelineFailure(self.problem) from self.cause
    def __bool__(self):raise TypeError('Use result.is_ok to inspect a Result')
    def to_dict(self):return {'format':'omega-result-1','ok':False,'error':self.problem.to_dict()}


Result=Ok[T]|Err


def attempt(stage:str,operation:Callable[...,T],*args,**kwargs)->Result[T]:
    """Retain causes, never turn KeyboardInterrupt/SystemExit into success.

    Process status comes from the supervisor, not candidate stderr. Messages
    intentionally omit process argv, stdout and stderr. In-process validation
    errors may contain user names/paths; callers control their disclosure.
    """
    from .sandbox import ExecutionFailure,IsolationUnavailable
    from omega.typesystem import TypeCheckError
    from omega.sintaxe import ErroOmega
    try:return Ok(operation(*args,**kwargs))
    except PipelineFailure as exc:return Err(exc.problem,exc)
    except Exception as exc:
        details={}
        if isinstance(exc,ExecutionFailure):
            status=exc.outcome
            details={'returncode':status.returncode,'signal':status.signal,'termination':status.termination}
            code={'wall_limit':Code.WALL,'output_limit':Code.OUTPUT,'signal':Code.SIGNAL}.get(status.termination,Code.PROOF if stage=='proof' else Code.EXIT)
            message='Execution did not complete successfully'
        elif isinstance(exc,IsolationUnavailable):code=Code.ISOLATION;message='Required isolation is unavailable'
        elif isinstance(exc,TypeCheckError):code=Code.TYPE;message=str(exc)
        elif isinstance(exc,FileNotFoundError):code=Code.MISSING;message=str(exc)
        elif isinstance(exc,FileExistsError):code=Code.EXISTS;message=str(exc)
        elif isinstance(exc,PermissionError):code=Code.DENIED;message=str(exc)
        elif isinstance(exc,OSError):code=Code.IO;message=str(exc)
        elif isinstance(exc,json.JSONDecodeError):code=Code.JSON;message=str(exc)
        elif isinstance(exc,RecursionError):code=Code.ANALYSIS;message='Analysis recursion budget exceeded'
        elif isinstance(exc,MemoryError):code=Code.MEMORY;message='Host allocation failed'
        elif isinstance(exc,(ErroOmega,ValueError,UnicodeError,OverflowError)):
            code=Code.PROOF if stage=='proof' else Code.INVALID;message=str(exc)
        elif isinstance(exc,RuntimeError):code=Code.PROOF if stage=='proof' else Code.PIPELINE;message=str(exc)
        else:
            code=Code.INTERNAL;message='Unexpected pipeline error; original exception retained'
            details={'exception':type(exc).__name__}
        return Err(Problem(code,stage,message[:4096],details),exc)
