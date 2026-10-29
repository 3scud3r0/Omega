"""A fork-shared, fixed-slot memory ring; payload views avoid serialization.

Reserve/commit and borrow/release are explicit. The lock orders metadata; this
is not a zero-latency claim or an unrestricted C pointer lifetime proof.
"""
import mmap
import multiprocessing
import struct
from contextlib import contextmanager

HEADER=struct.Struct('<QQ');SLOT=struct.Struct('<QQ')


class SharedRing:
    def __init__(self,capacity=64,slot_bytes=4096):
        if type(capacity) is not int or not 1<=capacity<=4096 or type(slot_bytes) is not int or not 1<=slot_bytes<=1048576 or capacity*slot_bytes>64*1024**2:raise ValueError('Shared ring capacity budget')
        self.capacity=capacity;self.slot_bytes=slot_bytes;self.lock=multiprocessing.RLock();self.memory=mmap.mmap(-1,HEADER.size+capacity*(SLOT.size+slot_bytes));HEADER.pack_into(self.memory,0,0,0)
    def _slot(self,sequence):return HEADER.size+(sequence%self.capacity)*(SLOT.size+self.slot_bytes)
    @contextmanager
    def reserve(self,size):
        if type(size) is not int or not 0<=size<=self.slot_bytes:raise ValueError('Slot payload budget')
        with self.lock:
            read,write=HEADER.unpack_from(self.memory)
            if write-read>=self.capacity:raise BufferError('Ring full')
            if write==2**64-1:raise OverflowError('Ring sequence exhausted')
            at=self._slot(write);view=memoryview(self.memory)[at+SLOT.size:at+SLOT.size+size]
            try:
                yield view
                SLOT.pack_into(self.memory,at,write,size);HEADER.pack_into(self.memory,0,read,write+1)
            finally:view.release()
    @contextmanager
    def borrow(self):
        with self.lock:
            read,write=HEADER.unpack_from(self.memory)
            if read==write:raise BufferError('Ring empty')
            at=self._slot(read);sequence,size=SLOT.unpack_from(self.memory,at)
            if sequence!=read or size>self.slot_bytes:raise ValueError('Ring metadata corrupted')
            view=memoryview(self.memory)[at+SLOT.size:at+SLOT.size+size].toreadonly()
            try:
                yield view
                HEADER.pack_into(self.memory,0,read+1,write)
            finally:view.release()
    def close(self):self.memory.close()
