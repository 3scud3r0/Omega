"""Version pointers guarded by an independently configured promotion authority.

The private root belongs to the supervisor, never a candidate worktree. A
failed activation consumes its ticket conservatively; it cannot auto-retry an
external approval after a crash. This is a pointer transaction, not atomic
replacement of every running service or an OS-level deployment transaction.
"""
import fcntl
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from pathlib import Path
from threading import RLock
from omega_security.encoding import canonical, decode, digest, snapshot


class Versions:
    def __init__(self, root, *, promotion_gate=None, initial_version=None,
                 initial_artifacts_sha256=None, authorize_rollback=None, audit=None):
        if initial_version is not None:
            self._version(initial_version)
            if type(initial_artifacts_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', initial_artifacts_sha256):
                raise ValueError('Authenticated initial artifact manifest digest required')
        elif initial_artifacts_sha256 is not None:
            raise ValueError('Initial artifact digest requires an initial version')
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.pointer = self.root / 'current.json'
        self.lock = RLock()
        self.promotion_gate = promotion_gate
        self.initial_version = initial_version
        self.initial_artifacts_sha256 = initial_artifacts_sha256
        self.authorize_rollback = authorize_rollback
        self.audit = audit if audit is not None else getattr(promotion_gate, 'audit', None)

    @staticmethod
    def _version(value):
        if type(value) is not str or not 0 < len(value) <= 256 or any(ord(c) < 32 for c in value):
            raise ValueError('Invalid version identity')
        return value

    def _read(self, path, limit):
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('Regular supervisor state required')
            data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError('Supervisor state quota exceeded')
        return data

    def current(self):
        try:
            raw = self._read(self.pointer, 65536)
        except FileNotFoundError:
            return None
        value = decode(raw, max_bytes=65536)
        fields = {'format', 'version', 'previous', 'artifacts_sha256', 'authorization_sha256'}
        if type(value) is not dict or set(value) != fields or value['format'] != 'omega-version-pointer-1':
            raise ValueError('Unknown version pointer; explicit migration required')
        self._version(value['version'])
        for name in ('artifacts_sha256', 'authorization_sha256'):
            if type(value[name]) is not str or not re.fullmatch('[0-9a-f]{64}', value[name]):
                raise ValueError('Invalid version provenance')
        previous = value['previous']
        if previous is not None:
            if type(previous) is not dict or set(previous) != {'version', 'artifacts_sha256'}:
                raise ValueError('Invalid previous version')
            self._version(previous['version'])
            if type(previous['artifacts_sha256']) is not str or not re.fullmatch('[0-9a-f]{64}', previous['artifacts_sha256']):
                raise ValueError('Invalid previous artifact digest')
        if canonical(value, max_bytes=65536) != raw:
            raise ValueError('Noncanonical version pointer')
        return value

    def _sync_directory(self):
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    def _write(self, value):
        data = canonical(value, max_bytes=65536)
        fd, name = tempfile.mkstemp(prefix='.version-', dir=self.root)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.pointer)
            self._sync_directory()
        finally:
            Path(name).unlink(missing_ok=True)

    def _restore(self, previous):
        if previous is not None:
            self._write(previous)
        else:
            self.pointer.unlink(missing_ok=True)
            self._sync_directory()

    @contextmanager
    def transaction(self):
        with self.lock:
            fd = os.open(self.root / '.version-lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'r+b') as stream:
                fcntl.flock(stream, fcntl.LOCK_EX)
                yield

    def _consume(self, receipt):
        """Durable replay record, written before publishing any new pointer."""
        if not re.fullmatch('[0-9a-f]{64}', receipt):
            raise ValueError('Invalid activation receipt')
        path = self.root / 'consumed-promotions.txt'
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        with os.fdopen(fd, 'r+b') as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError('Regular replay ledger required')
            raw = stream.read(8 * 1024**2 + 1)
            if len(raw) > 8 * 1024**2 - 65:
                raise ValueError('Promotion ledger full; supervisor maintenance required')
            entries = raw.splitlines()
            if (raw and not raw.endswith(b'\n')) or any(not re.fullmatch(b'[0-9a-f]{64}', entry) for entry in entries):
                raise ValueError('Damaged promotion replay ledger')
            if receipt.encode('ascii') in entries:
                raise PermissionError('Promotion approval already consumed')
            stream.seek(0, 2)
            stream.write(receipt.encode('ascii') + b'\n')
            stream.flush()
            os.fsync(stream.fileno())
        self._sync_directory()

    def activate(self, version, decision, healthcheck):
        self._version(version)
        if self.promotion_gate is None or self.audit is None or not callable(healthcheck):
            raise PermissionError('Independent promotion authority, audit and health adapter required')
        with self.transaction():
            previous = self.current()
            baseline = previous['version'] if previous else self.initial_version
            baseline_sha = previous['artifacts_sha256'] if previous else self.initial_artifacts_sha256
            if baseline is None or version == baseline:
                raise PermissionError('Explicit initial baseline and a distinct target required')
            authorization = self.promotion_gate.authorize(decision, version, baseline, baseline_artifacts_sha256=baseline_sha)
            if healthcheck(version) is not True:
                raise ValueError('Version failed health gate')
            # No failed candidate becomes globally current during its health check.
            authorization = self.promotion_gate.authorize(decision, version, baseline, baseline_artifacts_sha256=baseline_sha)
            value = {'format': 'omega-version-pointer-1', 'version': version,
                     'previous': {'version': baseline, 'artifacts_sha256': baseline_sha},
                     'artifacts_sha256': authorization['artifacts_sha256'],
                     'authorization_sha256': authorization['subject']}
            self.audit.append({'event': 'activation_started', **authorization})
            self._consume(authorization['receipt'])
            try:
                self.promotion_gate.authorize(decision, version, baseline, baseline_artifacts_sha256=baseline_sha)
                self._write(value)
                self.audit.append({'event': 'activation_committed', **authorization})
            except BaseException:
                self._restore(previous)
                raise
            return snapshot(value)

    def rollback(self, authorization, healthcheck):
        """Manual rollback also needs a host approval bound to the exact target."""
        if not callable(self.authorize_rollback) or self.audit is None or not callable(healthcheck):
            raise PermissionError('Independent rollback authority required')
        with self.transaction():
            current = self.current()
            if not current or current['previous'] is None:
                raise ValueError('No previous authenticated version')
            target = current['previous']
            action = {'format': 'omega-rollback-1', 'current': current['version'], 'target': target,
                      'authorization_sha256': current['authorization_sha256']}
            subject = digest(action)
            if self.authorize_rollback(snapshot(action), authorization) is not True:
                raise PermissionError('Rollback approval absent')
            if healthcheck(target['version']) is not True:
                raise ValueError('Rollback target failed health gate')
            if self.authorize_rollback(snapshot(action), authorization) is not True:
                raise PermissionError('Rollback approval expired or revoked')
            value = {'format': 'omega-version-pointer-1', 'version': target['version'], 'previous': None,
                     'artifacts_sha256': target['artifacts_sha256'], 'authorization_sha256': subject}
            self.audit.append({'event': 'rollback_started', 'subject': subject})
            try:
                self._write(value)
                self.audit.append({'event': 'rollback_committed', 'subject': subject})
            except BaseException:
                self._restore(current)
                raise
            return snapshot(value)
