"""Bounded canonical UTF-8 JSON for signed requests and data-only boundaries."""
import hashlib
import json
import math


def _string_size(value, remaining):
    # Account before serialization, including JSON escaping and UTF-8 width.
    # Repeated references must not expand into an unbounded temporary string.
    size = 2
    if len(value) + size > remaining:
        raise ValueError('Data byte budget exceeded')
    for char in value:
        code = ord(char)
        if char in ('"', '\\', '\b', '\f', '\n', '\r', '\t'):
            size += 2
        elif code < 32:
            size += 6
        elif code < 128:
            size += 1
        elif code < 2048:
            size += 2
        elif 0xD800 <= code <= 0xDFFF:
            raise ValueError('Unpaired Unicode surrogate')
        elif code < 65536:
            size += 3
        else:
            size += 4
        if size > remaining:
            raise ValueError('Data byte budget exceeded')
    return size


def canonical(value, *, max_bytes=1024*1024, max_nodes=10000, max_depth=64):
    if any(type(v) is not int or v < 1 for v in (max_bytes, max_nodes, max_depth)):
        raise ValueError('Positive data budgets required')
    pending = [(value, 0)]
    count = 0
    size = 0
    while pending:
        item, depth = pending.pop()
        count += 1
        if depth > max_depth or count > max_nodes:
            raise ValueError('Data structure budget exceeded')
        kind = type(item)
        if kind is dict:
            if count + len(pending) + len(item) > max_nodes:
                raise ValueError('Data structure budget exceeded')
            size += 2 + max(0, len(item)-1) + len(item)
            for key in item:
                if type(key) is not str or len(key) > 1024:
                    raise ValueError('Bounded string object keys required')
                size += _string_size(key, max_bytes-size)
            pending.extend((child, depth+1) for child in item.values())
        elif kind in (list, tuple):
            if count + len(pending) + len(item) > max_nodes:
                raise ValueError('Data structure budget exceeded')
            size += 2 + max(0, len(item)-1)
            pending.extend((child, depth+1) for child in item)
        elif kind is str:
            size += _string_size(item, max_bytes-size)
        elif kind is int:
            if item.bit_length() > 4096:
                raise ValueError('Integer data budget exceeded')
            size += len(str(item))
        elif kind is float:
            if not math.isfinite(item):
                raise ValueError('Finite numeric data required')
            size += len(json.dumps(item, allow_nan=False))
        elif kind is bool:
            size += 4 if item else 5
        elif kind is type(None):
            size += 4
        else:
            raise TypeError('Only JSON data may cross this boundary')
        if size > max_bytes:
            raise ValueError('Data byte budget exceeded')
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def _integer(text):
    if len(text) > 1240:
        raise ValueError('Integer text budget exceeded')
    return int(text)


def _constant(text):
    raise ValueError('Nonfinite JSON constant')


def decode(data, *, max_bytes=1024*1024, **limits):
    if type(data) is not bytes or len(data) > max_bytes:
        raise ValueError('Data byte budget exceeded')
    try:
        value = json.loads(data.decode('utf-8'), object_pairs_hook=_pairs,
                           parse_int=_integer, parse_constant=_constant)
        canonical(value, max_bytes=max_bytes, **limits)
    except (UnicodeError, RecursionError) as exc:
        raise ValueError('Malformed JSON data') from exc
    return value


def snapshot(value, **limits):
    return decode(canonical(value, **limits), **limits)


def digest(value, **limits):
    return hashlib.sha256(canonical(value, **limits)).hexdigest()
