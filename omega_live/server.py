"""Authenticated loopback monitor. REST controls, replayable SSE and WebSocket.

The transport never accepts source code or proof-verifier settings. All control
changes go through Store.command and await a worker checkpoint for application.
"""
import base64
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib
import hmac
import json
import secrets
import socket
import struct
import time
from urllib.parse import urlsplit,parse_qs
from .store import Store,Conflict,encode

PAGE='''<!doctype html><meta charset="utf-8"><title>Ômega — Rastreador ao vivo</title>
<style>body{font:16px system-ui;background:#101721;color:#e4edf4;margin:2em}button,input{padding:.5em;margin:.3em}pre{white-space:pre-wrap;background:#192434;padding:1em}#history{max-height:55vh;overflow:auto}.pending{color:#ffc66d}</style>
<h1>Ômega · execução e histórico</h1><p>Conecte usando o token do monitor. Controles só aparecem como aplicados após confirmação do executor.</p>
<label>Token <input id="token" type="password" autocomplete="off"></label><button id="connect">Conectar</button>
<label>Execução <select id="runs"></select></label><button id="refresh">Atualizar</button>
<div id="controls"><button data-kind="pause">Pausar</button><button data-kind="resume">Retomar</button><button data-kind="step">Um passo</button><button data-kind="cancel">Cancelar</button></div>
<label>Objetivos: qualidade, velocidade, memória, complexidade <input id="weights" value="4/5,1/5,0,0"></label><button id="setweights">Aplicar pesos</button>
<label>Orçamento de iterações <input id="iterations" type="number" min="1" max="4096" value="128"></label><button id="setiterations">Aplicar orçamento</button>
<p id="message" role="status"></p><pre id="state"></pre><h2>Histórico persistente</h2><p>Reconexões retomam do último cursor. Eventos anteriores podem ser exportados por CLI.</p><pre id="history"></pre>
<script>
let cursor=0,state=null,stream=null;const $=x=>document.getElementById(x);
async function api(path,options={}){let response=await fetch(path,{...options,headers:{Authorization:'Bearer '+$('token').value,'Content-Type':'application/json',...(options.headers||{})}});if(!response.ok)throw Error(await response.text());return response.json()}
async function refresh(){let list=await api('/api/runs');let selected=$('runs').value;$('runs').replaceChildren(...list.map(x=>{let o=document.createElement('option');o.value=x.id;o.textContent=x.id+' · '+x.status;return o}));if(list.some(x=>x.id===selected))$('runs').value=selected;if($('runs').value){state=await api('/api/runs/'+encodeURIComponent($('runs').value));$('state').textContent=JSON.stringify(state,null,2)}}
async function control(kind,value=null){try{if(!state)throw Error('Selecione uma execução');let r=await api('/api/runs/'+encodeURIComponent(state.id)+'/controls',{method:'POST',body:JSON.stringify({kind,value,expected_revision:state.revision})});$('message').textContent='Comando '+r.id+' recebido; aguardando checkpoint do executor.';await refresh()}catch(e){$('message').textContent=e.message;await refresh()}}
async function watch(){if(stream)stream.abort();stream=new AbortController();try{let response=await fetch('/api/stream?after='+cursor,{headers:{Authorization:'Bearer '+$('token').value},signal:stream.signal});if(!response.ok)throw Error(await response.text());let reader=response.body.getReader(),decoder=new TextDecoder(),pending='';while(true){let {value,done}=await reader.read();if(done)break;pending+=decoder.decode(value,{stream:true});let blocks=pending.split('\\n\\n');pending=blocks.pop();for(let b of blocks){let data=b.split('\\n').find(l=>l.startsWith('data: '));if(data){let event=JSON.parse(data.slice(6));cursor=event.seq;$('history').textContent+=JSON.stringify(event)+'\\n';let lines=$('history').textContent.split('\\n');if(lines.length>501)$('history').textContent=lines.slice(-500).join('\\n');$('history').scrollTop=$('history').scrollHeight;await refresh()}}}}catch(e){if(e.name!=='AbortError')$('message').textContent=e.message+' · reconectando'}setTimeout(watch,1000)}
$('connect').onclick=async()=>{try{await refresh();watch()}catch(e){$('message').textContent=e.message}};$('refresh').onclick=refresh;$('runs').onchange=refresh;
for(let b of document.querySelectorAll('[data-kind]'))b.onclick=()=>control(b.dataset.kind,b.dataset.kind==='step'?1:null);
$('setweights').onclick=()=>control('weights',$('weights').value.split(',').map(x=>x.trim()));$('setiterations').onclick=()=>control('iterations',Number($('iterations').value));
</script>'''


class Monitor(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=True
    def __init__(self,address,store,token=None):
        if address[0] not in ('127.0.0.1','::1','localhost'):raise ValueError('Monitor binds loopback only; use an authenticated forwarding service for remote access')
        self.store=store;self.token=token or secrets.token_urlsafe(32)
        if len(self.token)<24:raise ValueError('Monitor token must have at least 24 characters')
        super().__init__(address,Handler)


class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass # Never log bearer tokens or request URLs.
    def send(self,status,value,content_type='application/json'):
        data=value.encode() if type(value) is str else encode(value).encode()
        self.send_response(status);self.send_header('Content-Type',content_type+'; charset=utf-8');self.send_header('Content-Length',str(len(data)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(data)
    def allowed(self):
        origin=self.headers.get('Origin')
        if origin and origin!='http://'+self.headers.get('Host',''):return False
        return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+self.server.token)
    def do_GET(self):
        url=urlsplit(self.path)
        if url.path=='/':return self.send(200,PAGE,'text/html')
        if not self.allowed():return self.send(401,{'error':'Bearer authentication required'})
        query=parse_qs(url.query)
        try:
            if url.path=='/api/runs':return self.send(200,self.server.store.list_runs())
            if url.path.startswith('/api/runs/'):return self.send(200,self.server.store.snapshot(url.path.rsplit('/',1)[1]))
            if url.path=='/api/events':return self.send(200,self.server.store.events(after=int(query.get('after',['0'])[0]),run=query.get('run',[None])[0]))
            if url.path=='/api/audit':return self.send(200,self.server.store.audit(expected_head=query.get('head',[None])[0]))
            if url.path=='/api/stream':return self.stream(int(query.get('after',['0'])[0]),query.get('run',[None])[0])
            if url.path=='/api/ws':return self.websocket(int(query.get('after',['0'])[0]))
            return self.send(404,{'error':'Unknown route'})
        except (ValueError,KeyError) as error:return self.send(400,{'error':str(error)})
        except (BrokenPipeError,ConnectionResetError,TimeoutError):return
    def do_POST(self):
        if not self.allowed():return self.send(401,{'error':'Bearer authentication required'})
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=65536:raise ValueError('Body budget 1..65536')
            data=json.loads(self.rfile.read(length));parts=urlsplit(self.path).path.split('/')
            if len(parts)!=5 or parts[1:3]!=['api','runs'] or parts[4]!='controls':return self.send(404,{'error':'Unknown control endpoint'})
            if type(data) is not dict or set(data)-{'kind','value','expected_revision','command_id'}:raise ValueError('Unknown control field')
            result=self.server.store.command(parts[3],data['kind'],expected_revision=data['expected_revision'],value=data.get('value'),command_id=data.get('command_id'),actor='dashboard')
            self.send(202,result)
        except Conflict as error:self.send(409,{'error':str(error)})
        except (ValueError,KeyError,TypeError) as error:self.send(400,{'error':str(error)})
    def stream(self,after,run):
        self.send_response(200);self.send_header('Content-Type','text/event-stream');self.send_header('Cache-Control','no-store');self.send_header('Connection','close');self.end_headers();self.close_connection=True
        self.connection.settimeout(5);started=time.monotonic()
        while time.monotonic()-started<60:
            batch=self.server.store.events(after=after,run=run)
            for event in batch:
                self.wfile.write(('id: '+str(event['seq'])+'\ndata: '+encode(event)+'\n\n').encode());after=event['seq']
            if not batch:self.wfile.write(b': keepalive\n\n')
            self.wfile.flush();time.sleep(.2)
    def websocket(self,after):
        if self.headers.get('Upgrade','').lower()!='websocket' or self.headers.get('Sec-WebSocket-Version')!='13':raise ValueError('WebSocket version 13 required')
        key=self.headers.get('Sec-WebSocket-Key','')
        if len(base64.b64decode(key,validate=True))!=16:raise ValueError('Invalid WebSocket key')
        accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest()).decode()
        self.send_response(101);self.send_header('Upgrade','websocket');self.send_header('Connection','Upgrade');self.send_header('Sec-WebSocket-Accept',accept);self.end_headers();self.close_connection=True;self.connection.settimeout(.2)
        def frame(op,payload):
            size=len(payload);header=bytes([0x80|op,size]) if size<126 else bytes([0x80|op,126])+struct.pack('!H',size) if size<65536 else bytes([0x80|op,127])+struct.pack('!Q',size)
            self.wfile.write(header+payload);self.wfile.flush()
        started=time.monotonic()
        while time.monotonic()-started<60:
            for event in self.server.store.events(after=after):frame(1,encode(event).encode());after=event['seq']
            try:
                head=self.rfile.read(2)
                if not head:return
                if len(head)!=2 or not head[0]&0x80 or not head[1]&0x80 or head[0]&0x70:raise ValueError('Only masked complete WebSocket frames supported')
                op=head[0]&15;size=head[1]&127
                if size==126:size=struct.unpack('!H',self.rfile.read(2))[0]
                elif size==127:size=struct.unpack('!Q',self.rfile.read(8))[0]
                if size>65536 or op>=8 and size>125:raise ValueError('WebSocket frame budget')
                mask=self.rfile.read(4);raw=self.rfile.read(size)
                if len(mask)!=4 or len(raw)!=size:return
                payload=bytes(x^mask[i%4] for i,x in enumerate(raw))
                if op==8:frame(8,payload);return
                if op==9:frame(10,payload)
                elif op!=10:frame(8,struct.pack('!H',1003));return # writes use revisioned REST only
            except socket.timeout:time.sleep(.1)
