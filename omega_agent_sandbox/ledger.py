"""Durable state/version CAS and exactly-once dispatch reservations.

An external effect and SQLite cannot form one general atomic transaction.
Uncertain outcomes remain locked for explicit host reconciliation, never retry.
"""
import json
from pathlib import Path
import sqlite3
import hashlib
from omega_selfhost.proof_protocol import encode


class Ledger:
    def __init__(self,path):
        self.path=Path(path)
        if self.path.is_symlink():raise ValueError('Symlinked ledgers are refused')
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript('CREATE TABLE IF NOT EXISTS states (domain TEXT PRIMARY KEY, version INTEGER NOT NULL, body TEXT NOT NULL, busy TEXT);'
                             'CREATE TABLE IF NOT EXISTS operations (subject TEXT PRIMARY KEY, domain TEXT NOT NULL, nonce TEXT NOT NULL, status TEXT NOT NULL, body TEXT NOT NULL, receipt TEXT, UNIQUE(domain,nonce));')
    def connect(self):
        db=sqlite3.connect(self.path,timeout=10,isolation_level=None);db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');return db
    def initialize(self,domain,values):
        from omega_refine_check.syntax import identifier,rational
        identifier(domain);normalized={k:str(rational(v)) for k,v in values.items()}
        with self.connect() as db:
            db.execute('INSERT INTO states VALUES (?,?,?,NULL)',(domain,0,encode(normalized).decode()))
    def snapshot(self,domain):
        with self.connect() as db:row=db.execute('SELECT version,body,busy FROM states WHERE domain=?',(domain,)).fetchone()
        if row is None:raise ValueError('Unknown state domain')
        if row[2] is not None:raise RuntimeError('Domain has an unresolved external action')
        return {'version':row[0],'values':json.loads(row[1])}
    def claim(self,domain,subject,statement):
        with self.connect() as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT version,body,busy FROM states WHERE domain=?',(domain,)).fetchone()
                if row is None or row[2] is not None or row[0]!=statement['state']['version'] or json.loads(row[1])!=statement['state']['values']:raise ValueError('Action snapshot is stale or already reserved')
                db.execute('INSERT INTO operations VALUES (?,?,?,?,?,NULL)',(subject,domain,statement['proposal']['nonce'],'reserved',encode(statement).decode()))
                db.execute('UPDATE states SET busy=? WHERE domain=?',(subject,domain));db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:db.execute('ROLLBACK')
                raise
    def finish(self,domain,subject,statement,receipt):
        raw=encode(receipt)
        if len(raw)>65536:raise ValueError('External receipt exceeds budget')
        with self.connect() as db:
            try:
                db.execute('BEGIN IMMEDIATE')
                row=db.execute('SELECT busy FROM states WHERE domain=?',(domain,)).fetchone()
                if row!=(subject,):raise ValueError('Dispatch reservation changed')
                post=statement['post_state']
                db.execute('UPDATE states SET version=?,body=?,busy=NULL WHERE domain=?',(post['version'],encode(post['values']).decode(),domain))
                db.execute('UPDATE operations SET status=?,receipt=? WHERE subject=?',('completed',raw.decode(),subject));db.execute('COMMIT')
            except BaseException:
                if db.in_transaction:db.execute('ROLLBACK')
                raise
    def uncertain(self,subject,error):
        with self.connect() as db:db.execute('UPDATE operations SET status=?,receipt=? WHERE subject=?',('uncertain',str(error)[:2000],subject))
    def operation(self,subject):
        with self.connect() as db:row=db.execute('SELECT status,receipt FROM operations WHERE subject=?',(subject,)).fetchone()
        if row is None:raise ValueError('Unknown operation')
        return {'status':row[0],'receipt':row[1]}
