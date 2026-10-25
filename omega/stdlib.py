"""Bounded rational containers and installation of their native Omega module.

Mutation is atomic on rejected inputs. Empty/full conditions are explicit
exceptions. Rational values are exact; floats and bools are not accepted.
"""
from collections import deque
from fractions import Fraction
from importlib.resources import files
from pathlib import Path

MAX_CAPACITY=4096


def _capacity(value):
    if type(value) is not int or not 1<=value<=MAX_CAPACITY:
        raise ValueError('Capacity must be an integer in 1..4096')
    return value


def _rational(value):
    if type(value) not in (int,Fraction):raise TypeError('Exact rational required')
    return Fraction(value)


def _key(value):
    if type(value) is not str or '\0' in value or len(value.encode('utf-8'))>4096:
        raise ValueError('A non-NUL UTF-8 string of at most 4096 bytes is required')
    return value


class RationalQueue:
    def __init__(self,capacity):self.capacity=_capacity(capacity);self._data=deque()
    def __len__(self):return len(self._data)
    def push(self,value):
        value=_rational(value)
        if len(self)==self.capacity:raise OverflowError('Queue is full')
        self._data.append(value)
    def pop(self):
        if not self._data:raise IndexError('Queue is empty')
        return self._data.popleft()
    def values(self):return tuple(self._data)


class RationalStack(RationalQueue):
    def pop(self):
        if not self._data:raise IndexError('Stack is empty')
        return self._data.pop()


class RationalMap:
    def __init__(self,capacity):self.capacity=_capacity(capacity);self._data={}
    def __len__(self):return len(self._data)
    def put(self,key,value):
        key=_key(key);value=_rational(value)
        if key not in self._data and len(self)==self.capacity:raise OverflowError('Map is full')
        self._data[key]=value
    def has(self,key):return _key(key) in self._data
    def get(self,key):return self._data[_key(key)]
    def keys(self):return tuple(self._data)
    def items(self):return tuple(self._data.items())


def install_library(destination):
    """Copy the bundled module into an explicit module root, without overwrite."""
    data=files('omega_selfhost').joinpath('stdlib.omega').read_bytes()
    path=Path(destination)
    with path.open('xb') as stream:stream.write(data)
    return path
