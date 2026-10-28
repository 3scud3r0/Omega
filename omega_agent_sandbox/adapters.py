"""Host-supplied effects. Tests and demos use Recorder, never actual actuators."""
from dataclasses import dataclass
from threading import RLock
from urllib.parse import urlsplit
import json


class Recorder:
    def __init__(self):self.receipts={};self.lock=RLock()
    def dispatch(self,statement,*,idempotency_key):
        with self.lock:
            if idempotency_key in self.receipts:return self.receipts[idempotency_key]
            receipt={'acknowledged':True,'idempotency_key':idempotency_key,'effect':statement['effect'],
                     'parameters':statement['proposal']['parameters']}
            self.receipts[idempotency_key]=receipt
            return receipt


class CallbackAdapter:
    def __init__(self,callback):
        if not callable(callback):raise TypeError('Host driver callback required')
        self.callback=callback
    def dispatch(self,statement,*,idempotency_key):
        return self.callback(statement['proposal']['parameters'],idempotency_key=idempotency_key)


class HTTPSAdapter:
    def __init__(self,url,*,allowed_hosts,headers=None,timeout=5):
        parsed=urlsplit(url)
        if parsed.scheme!='https' or parsed.hostname not in allowed_hosts or parsed.username or parsed.password or parsed.fragment:
            raise ValueError('Explicit HTTPS host allowlist and credential-free URL required')
        if type(timeout) not in (int,float) or not 0<timeout<=30:raise ValueError('Bounded HTTPS timeout required')
        self.url=url;self.headers=dict(headers or {});self.timeout=timeout
    def dispatch(self,statement,*,idempotency_key):
        import urllib.request
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self,*args,**kwargs):raise PermissionError('Action redirects are refused')
        body=json.dumps(statement['proposal']['parameters'],sort_keys=True).encode()
        headers={**self.headers,'Content-Type':'application/json','Idempotency-Key':idempotency_key}
        request=urllib.request.Request(self.url,data=body,headers=headers,method='POST')
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=self.timeout) as response:
            data=response.read(65537)
            if len(data)>65536:raise ValueError('Action response byte budget exceeded')
            return {'acknowledged':200<=response.status<300,'status':response.status,'idempotency_key':idempotency_key,
                    'response_sha256':__import__('hashlib').sha256(data).hexdigest()}
