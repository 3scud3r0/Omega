"""Registered host tools retain capability, path and approval boundaries."""
from threading import RLock
from .contracts import Tool
from omega_security.encoding import digest
from omega_security.capabilities import Capability


class CapabilityAdapter:
    def __init__(self,verifier,principal,audit,*,approval_gate=None,max_calls=128):
        if type(max_calls) is not int or not 1<=max_calls<=10000:raise ValueError('Invalid tool call budget')
        self.verifier=verifier;self.principal=principal;self.audit=audit
        self.approval_gate=approval_gate;self.max_calls=max_calls
        self._tools={};self._calls=0;self._lock=RLock();self._sealed=False

    def register(self,tool):
        if type(tool) is not Tool:raise TypeError('Typed tool registration required')
        with self._lock:
            if self._sealed or tool.name in self._tools:raise ValueError('Tool registry is sealed or name is duplicated')
            if tool.approval_required and self.approval_gate is None:raise ValueError('Independent approval gate is missing')
            self._tools[tool.name]=tool

    def request(self,name,arguments):
        with self._lock:
            if name not in self._tools:raise PermissionError('Unknown tool')
            tool=self._tools[name]
        return {'tool':name,'action':tool.action,'arguments':tool.arguments.copy(arguments),'principal':self.principal}

    def call(self,name,arguments,capability,*,approval=None):
        if type(capability) is not Capability:raise PermissionError('Host-issued capability required')
        request=self.request(name,arguments);tool=self._tools[name];subject=digest(request)
        bound_subject=subject if 'subject' in capability.claims() else None
        def authorize():
            claim=self.verifier.require(capability,self.principal,tool.action,subject=bound_subject)
            for field in tool.path_fields:
                self.verifier.require(capability,self.principal,tool.action,path=request['arguments'][field],subject=bound_subject)
            return claim
        claim=authorize()
        with self._lock:
            if self._calls>=self.max_calls:raise ValueError('Tool call budget exhausted')
            self._sealed=True;self._calls+=1
        if tool.approval_required:self.approval_gate.consume(request,approval,self.principal)
        self.audit.append({'tool':name,'principal':self.principal,'capability_id':claim['id'],'request_sha256':subject,'status':'started'})
        authorize()
        try:
            result=tool.response.copy(tool.invoke(tool.arguments.copy(request['arguments'])))
            authorize()
        except Exception as exc:
            try:self.audit.append({'tool':name,'request_sha256':subject,'status':'failed','error_type':type(exc).__name__,'effect_may_have_happened':True})
            except Exception:pass
            raise
        self.audit.append({'tool':name,'request_sha256':subject,'response_sha256':digest(result,max_bytes=tool.response.max_bytes),'status':'completed'})
        return result
