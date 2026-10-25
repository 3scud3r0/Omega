"""Bounded authenticated worker RPC; the host supplies TLS transport and keys.

Transport must enforce its timeout and TLS verification. This module opens no
connections on import and provides no ambient credentials to candidate jobs.
Quotas are per supervisor-owned instance, not reset for each incoming RPC.
"""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from threading import BoundedSemaphore, Event, RLock, Timer
from urllib.parse import urlsplit
import base64
import re
import time
import uuid
from pathlib import Path
from .budget import Budget
from .quotas import Quota
from .scheduler import Job, execute, admit, BatchLimits
from omega_security.capabilities import Capability
from omega_security.encoding import canonical, digest, snapshot

REQUEST_FORMAT = 'omega-worker-request-1'
RESPONSE_FORMAT = 'omega-worker-response-1'
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 128 * 1024**2 + 65536
RESPONSE_FIELDS = {'format', 'worker', 'request_id', 'job_id', 'job_sha256',
                   'returncode', 'stdout', 'stderr', 'termination', 'sandboxed', 'signature'}


def _id(value):
    return type(value) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,128}', value) is not None


def _authorize(verifier, capability, principal, action, subject, *, path=None):
    if type(capability) is not Capability:
        raise PermissionError('Signed worker capability required')
    bound = subject if 'subject' in capability.claims() else None
    return verifier.require(capability, principal, action, path=path, subject=bound)


def _encode_capability(token):
    if type(token) is not Capability:
        raise PermissionError('Signed worker capability required')
    token.claims()  # Bounded parsing, before constructing a transport envelope.
    if type(token.signature) is not bytes or not 0 < len(token.signature) <= 1024:
        raise ValueError('Invalid worker capability signature')
    return {'issuer': token.issuer, 'payload': base64.b64encode(token.payload).decode('ascii'),
            'signature': base64.b64encode(token.signature).decode('ascii')}


def _decode_capability(value):
    if type(value) is not dict or set(value) != {'issuer', 'payload', 'signature'}:
        raise ValueError('Unknown capability envelope')
    if type(value['issuer']) is not str or not 0 < len(value['issuer']) <= 256:
        raise ValueError('Invalid capability issuer')
    if any(type(value[name]) is not str or not 0 < len(value[name]) <= limit
           for name, limit in (('payload', 32768), ('signature', 2048))):
        raise ValueError('Capability envelope budget exceeded')
    return Capability(base64.b64decode(value['payload'], validate=True),
                      base64.b64decode(value['signature'], validate=True), value['issuer'])


def job_subject(job):
    """Digest a typed job, used by optional per-job signed capabilities."""
    if type(job) is not Job:
        raise TypeError('Job required')
    return digest(asdict(job))


@dataclass(frozen=True)
class Worker:
    id: str
    endpoint: str
    slots: int

    def __post_init__(self):
        if not _id(self.id) or type(self.endpoint) is not str or len(self.endpoint) > 4096:
            raise ValueError('Invalid worker identity/endpoint')
        url = urlsplit(self.endpoint)
        if url.scheme != 'https' or not url.hostname or url.username is not None or url.password is not None or url.fragment or url.query:
            raise ValueError('Pinned HTTPS worker endpoint required')
        if type(self.slots) is not int or not 1 <= self.slots <= 8:
            raise ValueError('Invalid worker slots')


class Coordinator:
    def __init__(self, workers, transport, authenticate, verifier, principal, *, limits=BatchLimits()):
        items = []
        for worker in workers:
            if type(worker) is not Worker or len(items) >= 64:
                raise ValueError('Bounded typed worker inventory required')
            items.append(worker)
        self.workers = tuple(sorted(items, key=lambda w: w.id))
        if not items or len({w.id for w in items}) != len(items) or type(limits) is not BatchLimits:
            raise ValueError('Unique authenticated workers and typed limits required')
        if not callable(transport) or not callable(authenticate):
            raise TypeError('Bounded transport and response authenticator required')
        self.transport = transport
        self.authenticate = authenticate
        self.verifier = verifier
        self.principal = principal
        self.limits = limits
        self._slots = {w.id: BoundedSemaphore(w.slots) for w in items}
        self._total = Quota(jobs=limits.jobs, cpu_seconds=limits.reserved_cpu_seconds)
        self._concurrent = Quota(jobs=limits.workers, memory_bytes=limits.concurrent_memory_bytes)
        self._order = tuple(w for slot in range(max(w.slots for w in items)) for w in self.workers if slot < w.slots)

    def dispatch(self, jobs, capabilities):
        sequence = admit(jobs, self.limits)
        if type(capabilities) is not dict:
            raise TypeError('Host capability mapping required')
        prepared = []
        # All jobs, known mount scopes and reservations are admitted before RPC.
        for index, job in enumerate(sequence):
            worker = self._order[index % len(self._order)]
            token = capabilities.get((worker.id, job.id), capabilities.get(worker.id))
            subject = job_subject(job)
            _authorize(self.verifier, token, self.principal, 'worker.execute:' + worker.id, subject)
            for path in job.readonly:
                _authorize(self.verifier, token, self.principal, 'artifact.read', subject, path=path)
            request = {'format': REQUEST_FORMAT, 'request_id': uuid.uuid4().hex,
                       'worker': worker.id, 'job': asdict(job), 'job_sha256': subject,
                       'capability': _encode_capability(token)}
            prepared.append((worker, job, token, subject, snapshot(request, max_bytes=MAX_REQUEST_BYTES)))
        self._total.consume(jobs=len(sequence), cpu_seconds=sum(job.budget.cpu_seconds for job in sequence))

        def dispatch_one(item):
            worker, job, token, subject, request = item
            with self._slots[worker.id], self._concurrent.reserve(jobs=1, memory_bytes=job.budget.memory_bytes):
                _authorize(self.verifier, token, self.principal, 'worker.execute:' + worker.id, subject)
                # Transport owns enforced I/O deadlines; no unsafe retry fallback.
                response = self.transport(worker.endpoint, snapshot(request), timeout=job.budget.wall_seconds + 10)
                response = snapshot(response, max_bytes=min(MAX_RESPONSE_BYTES, 2 * job.budget.output_bytes + 65536))
                _check_response(worker, response)
                if response['request_id'] != request['request_id'] or response['job_id'] != job.id or response['job_sha256'] != subject:
                    raise PermissionError('Worker response does not match the dispatched job')
                if self.authenticate(worker, snapshot(response, max_bytes=MAX_RESPONSE_BYTES)) is not True:
                    raise PermissionError('Worker response authentication failed')
                _authorize(self.verifier, token, self.principal, 'worker.execute:' + worker.id, subject)
                return job.id, response

        with ThreadPoolExecutor(max_workers=self.limits.workers) as pool:
            return tuple(pool.map(dispatch_one, prepared))


def local(jobs, limits=BatchLimits(), *, cancel_event=None):
    return execute(jobs, limits, cancel_event=cancel_event)


class WorkerServer:
    """One supervisor-owned service, with shared quotas across concurrent RPCs.

    Replay records last for the instance lifetime. A persistent deployment must
    retain them outside process memory before allowing restarts/retries. Only
    pinned system executables bypass the artifact-root executable check.
    """
    def __init__(self, id, verifier, principal, sign, system_executables=(), limits=BatchLimits()):
        if not _id(id) or type(limits) is not BatchLimits or not callable(sign):
            raise ValueError('Typed worker configuration required')
        executables = []
        for path in system_executables:
            if len(executables) >= 64:
                raise ValueError('System executable inventory exceeded')
            resolved = Path(path).resolve(strict=True)
            if not resolved.is_file():
                raise ValueError('System executable must be a regular file')
            executables.append(str(resolved))
        self.id = id
        self.verifier = verifier
        self.principal = principal
        self.sign = sign
        self.executables = frozenset(executables)
        self.limits = limits
        self._total = Quota(jobs=limits.jobs, cpu_seconds=limits.reserved_cpu_seconds)
        self._concurrent = Quota(jobs=limits.workers, memory_bytes=limits.concurrent_memory_bytes)
        self._seen = set()
        self._lock = RLock()

    def handle(self, request, capability=None):
        request = snapshot(request, max_bytes=MAX_REQUEST_BYTES)
        fields = {'format', 'request_id', 'worker', 'job', 'job_sha256', 'capability'}
        if type(request) is not dict or set(request) != fields or request['format'] != REQUEST_FORMAT or request['worker'] != self.id:
            raise ValueError('Unknown worker request protocol/destination')
        nonce = request['request_id']
        if type(nonce) is not str or not re.fullmatch('[0-9a-f]{32}', nonce):
            raise ValueError('Bounded request identity required')
        transmitted = _decode_capability(request['capability'])
        if capability is not None and capability != transmitted:
            raise PermissionError('Transport capability mismatch')
        capability = transmitted
        payload = request['job']
        if type(payload) is not dict or set(payload) != {'id', 'argv', 'readonly', 'budget'}:
            raise ValueError('Unknown worker job fields')
        if type(payload['argv']) is not list or type(payload['readonly']) is not list or type(payload['budget']) is not dict:
            raise ValueError('Typed job envelope required')
        job = Job(payload['id'], tuple(payload['argv']), tuple(payload['readonly']), Budget(**payload['budget']))
        admit((job,), self.limits)
        subject = job_subject(job)
        if request['job_sha256'] != subject:
            raise ValueError('Worker request digest mismatch')

        def authorize():
            claim = _authorize(self.verifier, capability, self.principal, 'worker.execute:' + self.id, subject)
            executable = str(Path(job.argv[0]).resolve(strict=True))
            if executable not in self.executables:
                _authorize(self.verifier, capability, self.principal, 'code.execute', subject, path=executable)
            for path in job.readonly:
                _authorize(self.verifier, capability, self.principal, 'artifact.read', subject, path=path)
            return claim

        claim = authorize()
        cancelled = Event()
        cancel = cancelled.set
        with self._concurrent.reserve(jobs=1, memory_bytes=job.budget.memory_bytes):
            with self._lock:
                if nonce in self._seen:
                    raise PermissionError('Worker request already consumed')
                self._total.consume(jobs=1, cpu_seconds=job.budget.cpu_seconds)
                self._seen.add(nonce)
            self.verifier.revocations.register(claim['id'], cancel)
            expiry = Timer(max(0, claim['expires']-time.time()), cancel)
            expiry.daemon = True
            try:
                expiry.start()
                authorize()
                job_id, outcome = execute((job,), self.limits, cancel_event=cancelled)[0]
                authorize()
                result = {'format': RESPONSE_FORMAT, 'worker': self.id, 'request_id': nonce,
                          'job_id': job_id, 'job_sha256': subject, 'returncode': outcome.returncode,
                          'stdout': outcome.stdout, 'stderr': outcome.stderr,
                          'termination': outcome.termination, 'sandboxed': outcome.sandboxed}
                signature = self.sign(canonical(result, max_bytes=MAX_RESPONSE_BYTES))
                if type(signature) is not bytes or not 0 < len(signature) <= 1024:
                    raise ValueError('Worker signer returned an invalid signature')
                authorize()
                result['signature'] = base64.b64encode(signature).decode('ascii')
                return result
            finally:
                expiry.cancel()
                self.verifier.revocations.unregister(claim['id'], cancel)


def _check_response(worker, response):
    if type(response) is not dict or set(response) != RESPONSE_FIELDS or response['format'] != RESPONSE_FORMAT or response['worker'] != worker.id:
        raise PermissionError('Unknown worker response protocol/identity')
    if type(response['request_id']) is not str or not re.fullmatch('[0-9a-f]{32}', response['request_id']):
        raise ValueError('Invalid response request identity')
    if type(response['job_id']) is not str or not 0 < len(response['job_id']) <= 256:
        raise ValueError('Invalid response job identity')
    if type(response['job_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', response['job_sha256']):
        raise ValueError('Invalid response job digest')
    if type(response['returncode']) is not int or type(response['stdout']) is not str or type(response['stderr']) is not str:
        raise ValueError('Invalid worker outcome fields')
    if response['sandboxed'] is not True or response['termination'] not in {'exit', 'signal', 'wall_limit', 'output_limit', 'revoked'}:
        raise PermissionError('Worker did not report isolated execution')
    if type(response['signature']) is not str or not 0 < len(response['signature']) <= 2048:
        raise ValueError('Invalid worker signature envelope')


def verify_response(worker, response, verify_signature):
    try:
        value = snapshot(response, max_bytes=MAX_RESPONSE_BYTES)
        _check_response(worker, value)
        signature = base64.b64decode(value.pop('signature'), validate=True)
        if not 0 < len(signature) <= 1024:
            return False
        payload = canonical(value, max_bytes=MAX_RESPONSE_BYTES)
        return verify_signature(worker.id, payload, signature) is True
    except (ValueError, KeyError, TypeError, UnicodeError, RecursionError):
        return False
