"""Register bounded UTF-8 file tools anchored in a supervisor-selected root."""
import hashlib
import re
from pathlib import Path
from .contracts import Contract, Tool
from omega_security.filesystem import read, write


def register_files(adapter, root, *, writable=False, max_bytes=256 * 1024):
    root = Path(root).resolve(strict=True)
    if not root.is_dir() or type(writable) is not bool or type(max_bytes) is not int or not 1 <= max_bytes <= 256 * 1024:
        raise ValueError('Explicit file root and bounded byte limit required')
    if writable and adapter.approval_gate is None:
        raise PermissionError('Independent file mutation approval gate required')

    def relative(path):
        if type(path) is not str:
            raise TypeError('Absolute file path required')
        target = Path(path)
        if not target.is_absolute() or str(target) != path or '..' in target.parts:
            raise PermissionError('Normalized absolute file path required')
        # Do not resolve the candidate path: anchored operations reject symlinks.
        try:
            value = target.relative_to(root).as_posix()
        except ValueError as exc:
            raise PermissionError('File outside configured tool root') from exc
        if value == '.':
            raise PermissionError('A file, not the root directory, is required')
        return value

    def read_text(arguments):
        content = read(root, relative(arguments['path']), limit=max_bytes)
        return {'path': arguments['path'], 'content': content.decode('utf-8'),
                'sha256': hashlib.sha256(content).hexdigest(), 'authority': False}

    adapter.register(Tool('files.read_text', 'file.read',
                          Contract({'path': str}, frozenset({'path'}), 8192),
                          Contract({'path': str, 'content': str, 'sha256': str, 'authority': bool},
                                   frozenset({'path', 'content', 'sha256', 'authority'}), 2 * 1024**2),
                          read_text, path_fields=('path',)))
    if not writable:
        return

    def replace_text(arguments):
        expected = arguments['expected_sha256']
        if not re.fullmatch('[0-9a-f]{64}', expected):
            raise ValueError('Full expected content digest required')
        content = arguments['content'].encode('utf-8')
        if len(content) > max_bytes:
            raise ValueError('File write byte budget exceeded')
        sha = write(root, relative(arguments['path']), content, expected_sha256=expected)
        return {'path': arguments['path'], 'sha256': sha, 'bytes': len(content)}

    adapter.register(Tool('files.replace_text', 'file.write',
                          Contract({'path': str, 'content': str, 'expected_sha256': str},
                                   frozenset({'path', 'content', 'expected_sha256'}), 2 * 1024**2),
                          Contract({'path': str, 'sha256': str, 'bytes': int},
                                   frozenset({'path', 'sha256', 'bytes'}), 8192),
                          replace_text, path_fields=('path',), approval_required=True))
