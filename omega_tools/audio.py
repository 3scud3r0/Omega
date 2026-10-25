import io,wave,hashlib
def inspect_wav(data):
    if type(data) is not bytes or len(data)>32*1024**2:raise ValueError('Audio byte budget exceeded')
    with wave.open(io.BytesIO(data),'rb') as stream:
        channels=stream.getnchannels();rate=stream.getframerate();width=stream.getsampwidth();frames=stream.getnframes()
        if channels not in (1,2) or width not in (2,3) or not 8000<=rate<=96000 or frames>rate*60:raise ValueError('Unsupported PCM audio budget/format')
        if len(stream.readframes(frames))!=frames*channels*width:raise ValueError('Truncated PCM audio')
    return {'channels':channels,'sample_rate':rate,'sample_width':width,'frames':frames,'sha256':hashlib.sha256(data).hexdigest()}
def transcribe(data,provider,*,capability,verifier,principal):
    verifier.require(capability,principal,'audio.transcribe');metadata=inspect_wav(data);text=provider(data,metadata)
    if type(text) is not str or len(text)>65536:raise ValueError('Invalid transcription')
    return {'text':text,'audio':metadata,'authority':False}
def synthesize(text,provider,*,capability,verifier,principal):
    verifier.require(capability,principal,'audio.synthesize')
    if type(text) is not str or len(text)>4096:raise ValueError('Speech text budget exceeded')
    data=provider(text);inspect_wav(data);return data
