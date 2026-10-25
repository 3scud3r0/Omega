"""Explicitly authorized HTTPS retrieval; redirects need their own capability scope."""
import datetime,hashlib,urllib.request,urllib.parse
from omega_security.untrusted_data import UntrustedDocument
class Retrieval:
    def __init__(self,verifier,principal,capability):self.verifier=verifier;self.principal=principal;self.capability=capability
    def require(self,url):
        parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.port not in (None,443):raise PermissionError('Only ordinary HTTPS URLs allowed')
        self.verifier.require(self.capability,self.principal,'network:'+parsed.hostname.lower())
    def get(self,url,max_bytes=4*1024**2,timeout=15):
        if not 1<=max_bytes<=8*1024**2 or not 0<timeout<=30:raise ValueError('Invalid retrieval budget')
        self.require(url);owner=self
        class Redirect(urllib.request.HTTPRedirectHandler):
            max_redirections=3
            def redirect_request(self,request,fp,code,msg,headers,newurl):
                owner.require(newurl);return super().redirect_request(request,fp,code,msg,headers,newurl)
        opener=urllib.request.build_opener(Redirect())
        request=urllib.request.Request(url,headers={'User-Agent':'Omega-Research/2.0','Accept':'text/*,application/json,application/pdf'})
        with opener.open(request,timeout=timeout) as response:
            self.require(response.url);content=response.read(max_bytes+1);final=response.url
        if len(content)>max_bytes:raise ValueError('Retrieval byte budget exceeded')
        observed=datetime.datetime.now(datetime.timezone.utc).isoformat()
        return UntrustedDocument(final,content,observed)
