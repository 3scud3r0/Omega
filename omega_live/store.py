"""Transactional event history and revisioned controls, shared across processes.

SQLite WAL supplies durability and serialization; a SHA256 chain supplies
integrity relative to an independently pinned head. It cannot defeat the owner
of both the database and its checkpoint. No network endpoint executes code.
"""
from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import uuid

ZERO='0'*64
TERMINAL={'completed','failed','cancelled'}


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False)
def digest(value):return hashlib.sha256(encode(value).encode()).hexdigest()


class Conflict(ValueError):pass


class Store:
    def __init__(self,directory):
        self.root=Path(directory).resolve();self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.path=self.root/'history.sqlite3'
        if self.path.is_symlink():raise ValueError('History must be a regular local database')
        with self.connection() as db:
            db.executescript('''CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,run TEXT NOT NULL,kind TEXT NOT NULL,actor TEXT NOT NULL,time_ns INTEGER NOT NULL,payload TEXT NOT NULL,previous TEXT NOT NULL,hash TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,revision INTEGER NOT NULL,state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY,run TEXT NOT NULL,revision INTEGER NOT NULL,kind TEXT NOT NULL,value TEXT NOT NULL,status TEXT NOT NULL,event_seq INTEGER NOT NULL);
CREATE INDEX IF NOT EXISTS event_run ON events(run,seq);
CREATE INDEX IF NOT EXISTS command_pending ON commands(run,status,revision);''')
        os.chmod(self.path,0o600)
    @contextmanager
    def connection(self):
        db=sqlite3.connect(self.path,timeout=15,isolation_level=None)
        db.row_factory=sqlite3.Row;db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA busy_timeout=15000')
        try:yield db
        finally:db.close()
    @contextmanager
    def transaction(self):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            try:yield db;db.execute('COMMIT')
            except BaseException:db.execute('ROLLBACK');raise
    def _event(self,db,run,kind,payload,actor):
        if type(payload) is not dict or len(encode(payload).encode())>1024**2:raise ValueError('Bounded event object required')
        if not all(type(x) is str and 0<len(x)<=128 for x in (run,kind,actor)):raise ValueError('Bounded event identity required')
        last=db.execute('SELECT seq,hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
        row={'seq':last['seq']+1 if last else 1,'run':run,'kind':kind,'actor':actor,'time_ns':time.time_ns(),'payload':payload,'previous':last['hash'] if last else ZERO}
        row['hash']=digest(row)
        db.execute('INSERT INTO events VALUES(?,?,?,?,?,?,?,?)',(row['seq'],run,kind,actor,row['time_ns'],encode(payload),row['previous'],row['hash']))
        return row
    def event(self,run,kind,payload,actor='worker'):
        with self.transaction() as db:
            if not db.execute('SELECT 1 FROM runs WHERE id=?',(run,)).fetchone():raise KeyError('Unknown run')
            return self._event(db,run,kind,payload,actor)
    def create(self,*,kind='synthesis',config=None,tasks=None,run_id=None):
        config=config or {};tasks=tasks or []
        if type(tasks) is not list or len(tasks)>256:raise ValueError('Task budget')
        names={t['id'] for t in tasks}
        if len(names)!=len(tasks):raise ValueError('Duplicate task')
        order=[]
        while len(order)<len(tasks):
            candidates=[t['id'] for t in tasks if t['id'] not in order and set(t['dependencies'])<=set(order)]
            if not candidates:raise ValueError('Task graph is cyclic or has missing dependencies')
            order.extend(candidates)
        run_id=run_id or uuid.uuid4().hex
        state={'id':run_id,'kind':kind,'status':'created','desired_status':'running','revision':0,'applied_revision':0,'step_budget':0,'iteration':0,'config':config,'tasks':tasks,'task_order':order,'worker':None,'lease_until_ns':0}
        with self.transaction() as db:
            db.execute('INSERT INTO runs VALUES(?,?,?)',(run_id,0,encode(state)))
            self._event(db,run_id,'run.created',state,'supervisor')
        return state
    def _state(self,db,run):
        row=db.execute('SELECT state FROM runs WHERE id=?',(run,)).fetchone()
        if row is None:raise KeyError('Unknown run')
        return json.loads(row['state'])
    def snapshot(self,run):
        with self.connection() as db:return self._state(db,run)
    def list_runs(self):
        with self.connection() as db:return [json.loads(x['state']) for x in db.execute('SELECT state FROM runs ORDER BY rowid DESC LIMIT 256')]
    def _save(self,db,state):db.execute('UPDATE runs SET revision=?,state=? WHERE id=?',(state['revision'],encode(state),state['id']))
    def command(self,run,kind,*,expected_revision,value=None,actor='operator',command_id=None):
        if type(expected_revision) is not int or expected_revision<0:raise ValueError('Expected revision required')
        if kind not in {'pause','resume','step','cancel','weights','iterations'}:raise ValueError('Command cannot modify proofs, keys, source or constitution')
        if kind=='step' and (type(value) is not int or not 1<=value<=64):raise ValueError('Step budget 1..64')
        if kind=='iterations' and (type(value) is not int or not 1<=value<=4096):raise ValueError('Iteration budget 1..4096')
        if kind=='weights':
            if type(value) is not list or len(value)!=4 or any(type(x) not in (str,int) for x in value):raise ValueError('Four exact weights required')
            weights=[Fraction(x) for x in value]
            if any(q<0 or max(abs(q.numerator).bit_length(),q.denominator.bit_length())>4096 for q in weights) or not sum(weights):raise ValueError('Positive bounded objective vector required')
            value=[str(q) for q in weights]
        cid=command_id or uuid.uuid4().hex
        if type(cid) is not str or not 1<=len(cid)<=128:raise ValueError('Bounded command identity required')
        with self.transaction() as db:
            state=self._state(db,run)
            old=db.execute('SELECT * FROM commands WHERE id=?',(cid,)).fetchone()
            if old:
                if old['run']!=run or old['kind']!=kind or json.loads(old['value'])!=value or old['revision']!=expected_revision+1:raise Conflict('Command identity was reused')
                return dict(old)
            if state['revision']!=expected_revision:raise Conflict('Stale revision; refresh before controlling this run')
            if state['status'] in TERMINAL:raise Conflict('Run has terminated')
            if kind=='step' and state['desired_status']!='paused':raise Conflict('Pause before stepping')
            if kind in ('pause','resume','cancel'):state['desired_status']={'pause':'paused','resume':'running','cancel':'cancelled'}[kind]
            state['revision']+=1
            event=self._event(db,run,'control.requested',{'id':cid,'kind':kind,'value':value,'revision':state['revision']},actor)
            db.execute('INSERT INTO commands VALUES(?,?,?,?,?,?,?,?)',(cid,run,state['revision'],kind,encode(value),'pending',event['seq']))
            self._save(db,state)
        return {'id':cid,'run':run,'revision':state['revision'],'kind':kind,'value':value,'status':'pending','event_seq':event['seq']}
    def checkpoint(self,run,worker,*,iteration=None,lease_seconds=30):
        """Only the lease holder applies controls, at deterministic safe points."""
        if type(lease_seconds) is not int or not 1<=lease_seconds<=300:raise ValueError('Bounded worker lease required')
        with self.transaction() as db:
            state=self._state(db,run);now=time.time_ns()
            if state['status'] in TERMINAL:return state
            if state['worker'] not in (None,worker) and state['lease_until_ns']>now:raise Conflict('Run already has a live worker')
            if state['worker']!=worker:
                self._event(db,run,'worker.claimed',{'worker':worker,'previous_worker':state['worker']},worker)
            state['worker']=worker;state['lease_until_ns']=now+lease_seconds*10**9
            for command in db.execute('SELECT * FROM commands WHERE run=? AND status=? ORDER BY revision',(run,'pending')).fetchall():
                kind=command['kind'];value=json.loads(command['value'])
                if kind in ('pause','resume','cancel'):state['status']={'pause':'paused','resume':'running','cancel':'cancelled'}[kind];state['step_budget']=0
                elif kind=='step':state['step_budget']=value
                elif kind=='weights':state['config']['objectives']=value
                elif kind=='iterations':state['config']['iterations']=value
                state['applied_revision']=command['revision']
                db.execute('UPDATE commands SET status=? WHERE id=?',('applied',command['id']))
                self._event(db,run,'control.applied',{'id':command['id'],'kind':kind,'value':value,'revision':command['revision']},worker)
            if state['status']=='created':state['status']='running'
            if iteration is not None:
                if type(iteration) is not int or iteration<state['iteration']:raise ValueError('Iteration must be monotonic')
                state['iteration']=iteration
            self._save(db,state);return state
    def take_step(self,run,worker):
        with self.transaction() as db:
            state=self._state(db,run)
            if state['worker']!=worker or state['lease_until_ns']<time.time_ns():raise Conflict('Worker lease expired')
            allowed=state['status']=='running' or state['status']=='paused' and state['step_budget']>0
            if state['status']=='paused' and allowed:state['step_budget']-=1
            self._save(db,state);return allowed
    def finish(self,run,worker,*,status='completed',result=None):
        if status not in TERMINAL:raise ValueError('Terminal status required')
        with self.transaction() as db:
            state=self._state(db,run)
            if state['worker']!=worker:raise Conflict('Only lease holder may finish')
            if state['status'] in TERMINAL and state['status']!=status:raise Conflict('Terminal state cannot be rewritten')
            state['status']=status;state['desired_status']=status;state['lease_until_ns']=0
            self._event(db,run,'run.'+status,{'result':result or {},'iteration':state['iteration']},worker);self._save(db,state)
        return state
    def events(self,*,after=0,run=None,limit=256):
        if type(after) is not int or after<0 or type(limit) is not int or not 1<=limit<=1024:raise ValueError('Bounded event cursor required')
        with self.connection() as db:
            sql='SELECT * FROM events WHERE seq>?'+(' AND run=?' if run else '')+' ORDER BY seq LIMIT ?'
            args=[after,*([run] if run else []),limit]
            return [{**dict(row),'payload':json.loads(row['payload'])} for row in db.execute(sql,args)]
    def audit(self,*,expected_head=None):
        previous=ZERO;seq=0
        with self.connection() as db:
            for raw in db.execute('SELECT * FROM events ORDER BY seq'):
                row={**dict(raw),'payload':json.loads(raw['payload'])};claimed=row.pop('hash')
                if row['seq']!=seq+1 or row['previous']!=previous or digest(row)!=claimed:raise ValueError('History integrity failure')
                seq+=1;previous=claimed
        if expected_head is not None and previous!=expected_head:raise ValueError('History does not match pinned head')
        return {'events':seq,'head':previous,'valid':True}
    def export(self,path):
        path=Path(path)
        with path.open('x') as stream:
            cursor=0
            while batch:=self.events(after=cursor,limit=1024):
                for event in batch:stream.write(encode(event)+'\n')
                cursor=batch[-1]['seq']
            stream.flush();os.fsync(stream.fileno())
        return {'path':str(path),'anchor':self.audit()}
