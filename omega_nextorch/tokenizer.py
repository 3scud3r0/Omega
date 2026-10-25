"""Lossless UTF-8 byte tokenizer, versioned independently of neural weights."""
VERSION='omega-byte-tokenizer-1'
BOS,EOS,PAD=256,257,258
VOCAB_SIZE=259
def encode(text,*,boundaries=True,max_bytes=65536):
    if type(text) is not str:raise TypeError('Text required')
    data=text.encode('utf-8')
    if len(data)>max_bytes:raise ValueError('Token budget exceeded')
    return ([BOS] if boundaries else [])+list(data)+([EOS] if boundaries else [])
def decode(tokens):
    tokens=tuple(tokens)
    if len(tokens)>65538 or any(type(v) is not int or not 0<=v<VOCAB_SIZE for v in tokens):raise ValueError('Invalid token stream')
    if tokens and tokens[0]==BOS:tokens=tokens[1:]
    if tokens and tokens[-1]==EOS:tokens=tokens[:-1]
    if any(v>255 for v in tokens):raise ValueError('Special token inside text')
    return bytes(tokens).decode('utf-8')
def descriptor():return {'version':VERSION,'vocab_size':VOCAB_SIZE,'encoding':'utf-8','normalization':'none'}
