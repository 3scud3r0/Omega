"""Authenticated, framed, quota-limited P2P exchange of independently checked data.

No listener or connection starts on import. The explicit transport API handles
one message per connection. Sender signatures are not logical proof authority.
"""
import asyncio
import re
import sqlite3
import struct
import time

from omega_security.encoding import canonical,decode
from omega_kernel.protocol import sha256
from .certificates import verify_claim, verify_improvement

MAX_FRAME = 65536
BODY_FIELDS = {'format','sender','sequence','issued_at','expires_at','kind','certificate'}


def public_key(key):
    from cryptography.hazmat.primitives import serialization
    return key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw).hex()


def sign(certificate,key,sequence,*,kind='point',now=None,ttl=300):
    now = int(time.time()) if now is None else now
    body = {'format':'omega-epistemic-peer-1','sender':public_key(key),'sequence':sequence,
            'issued_at':now,'expires_at':now+ttl,'kind':kind,'certificate':certificate}
    raw = canonical(body,max_bytes=MAX_FRAME-200,max_nodes=60000,max_depth=48)
    return {'body':body,'signature':key.sign(raw).hex()}


class Store:
    def __init__(self,allowed_senders,*,database=':memory:',max_items=128,max_bytes=1024**2,clock=time.time):
        self.allowed = frozenset(allowed_senders)
        if not 1 <= len(self.allowed) <= 128 or any(type(k) is not str or not re.fullmatch('[0-9a-f]{64}',k) for k in self.allowed):
            raise ValueError('Explicit Ed25519 peer allowlist required')
        if type(max_items) is not int or not 1 <= max_items <= 1024 or type(max_bytes) is not int or not MAX_FRAME <= max_bytes <= 16*1024**2:
            raise ValueError('Bounded peer store quotas required')
        self.max_items,self.max_bytes,self.clock = max_items,max_bytes,clock
        self.active_connections = 0
        self.rates = {}
        self.db = sqlite3.connect(database)
        self.db.execute('CREATE TABLE IF NOT EXISTS peers (sender TEXT PRIMARY KEY, sequence INTEGER NOT NULL)')
        self.db.execute('CREATE TABLE IF NOT EXISTS claims (id TEXT PRIMARY KEY, body BLOB NOT NULL, expiry INTEGER NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    def accept(self,message):
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if type(message) is not dict or set(message) != {'body','signature'}:
            raise ValueError('Peer message exact fields')
        raw_message = canonical(message,max_bytes=MAX_FRAME,max_nodes=60000,max_depth=48)
        body,signature = message['body'],message['signature']
        if type(body) is not dict or set(body) != BODY_FIELDS or body['format'] != 'omega-epistemic-peer-1':
            raise ValueError('Peer body fields/version')
        if body['sender'] not in self.allowed or type(signature) is not str or not re.fullmatch('[0-9a-f]{128}',signature):
            raise PermissionError('Unknown peer or malformed signature')
        for field in ('sequence','issued_at','expires_at'):
            if type(body[field]) is not int or not 0 <= body[field] < (1<<63):
                raise ValueError('Peer sequence/time must be nonnegative i64')
        now = int(self.clock())
        if body['issued_at'] > now+30 or not body['issued_at'] < body['expires_at'] or body['expires_at'] <= now or body['expires_at']-body['issued_at'] > 3600:
            raise PermissionError('Expired or invalid message lifetime')
        raw_body = canonical(body,max_bytes=MAX_FRAME,max_nodes=60000,max_depth=48)
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(body['sender'])).verify(bytes.fromhex(signature),raw_body)
        window = now//60
        previous_window,count = self.rates.get(body['sender'],(window,0))
        count = count if previous_window == window else 0
        if count >= 32:
            raise PermissionError('Authenticated peer rate limit')
        self.rates[body['sender']] = (window,count+1)
        previous = self.db.execute('SELECT sequence FROM peers WHERE sender=?',(body['sender'],)).fetchone()
        if previous is not None and body['sequence'] <= previous[0]:
            raise PermissionError('Peer replay or nonmonotone sequence')
        if body['kind'] == 'point':
            checked = verify_claim(body['certificate'])
        elif body['kind'] == 'rewrite':
            checked = verify_improvement(body['certificate'])
        else:
            raise ValueError('Peer claim kind point or rewrite required')
        if not checked['accepted']:
            raise PermissionError('Independent local kernel rejected the claim')
        claim_bytes = canonical(body['certificate'],max_bytes=MAX_FRAME,max_nodes=60000,max_depth=48)
        identifier = sha256(claim_bytes)
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self.db.execute('DELETE FROM claims WHERE expiry <= ?',(now,))
            previous = self.db.execute('SELECT sequence FROM peers WHERE sender=?',(body['sender'],)).fetchone()
            if previous is not None and body['sequence'] <= previous[0]:
                raise PermissionError('Peer replay or nonmonotone sequence')
            duplicate = self.db.execute('SELECT id FROM claims WHERE id=?',(identifier,)).fetchone() is not None
            count,used = self.db.execute('SELECT COUNT(*),COALESCE(SUM(LENGTH(body)),0) FROM claims').fetchone()
            if not duplicate and (count >= self.max_items or used+len(claim_bytes) > self.max_bytes):
                raise ValueError('Peer store quota exhausted')
            if not duplicate:
                self.db.execute('INSERT INTO claims VALUES (?,?,?)',(identifier,claim_bytes,body['expires_at']))
            self.db.execute('INSERT INTO peers VALUES (?,?) ON CONFLICT(sender) DO UPDATE SET sequence=excluded.sequence',
                            (body['sender'],body['sequence']))
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise
        return {'accepted':True,'duplicate':duplicate,'id':identifier,'sender':body['sender'],
                'bytes':len(raw_message),'scope':checked['scope'],'stable_code_modified':False}


async def read_frame(reader,timeout=5):
    header = await asyncio.wait_for(reader.readexactly(4),timeout)
    length = struct.unpack('!I',header)[0]
    if not 0 < length <= MAX_FRAME:
        raise ValueError('Peer frame byte limit')
    body = await asyncio.wait_for(reader.readexactly(length),timeout)
    return decode(body,max_bytes=MAX_FRAME,max_nodes=60000,max_depth=48)


async def write_frame(writer,value,timeout=5):
    raw = canonical(value,max_bytes=MAX_FRAME,max_nodes=60000,max_depth=48)
    writer.write(struct.pack('!I',len(raw))+raw)
    await asyncio.wait_for(writer.drain(),timeout)


async def handle_peer(reader,writer,store):
    if store.active_connections >= 8:
        writer.close()
        await writer.wait_closed()
        return
    store.active_connections += 1
    try:
        message = await read_frame(reader)
        receipt = store.accept(message)
        await write_frame(writer,receipt)
    except Exception:
        try:
            await write_frame(writer,{'accepted':False,'error':'peer-message-denied'})
        except Exception:
            pass
    finally:
        store.active_connections -= 1
        writer.close()
        try:
            await writer.wait_closed()
        except (ConnectionError,OSError):
            pass
