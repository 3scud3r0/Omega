"""OM-120: executable checks; source delivery, not a recorded pass."""
import io,wave
import pytest
from omega_tools.audio import inspect_wav,transcribe

def test_audio_pcm_metadata_and_provider_output_are_checked(signed_authority):
    buffer=io.BytesIO()
    with wave.open(buffer,'wb') as stream:stream.setparams((1,2,8000,0,'NONE','not compressed'));stream.writeframes(b'\0\0'*80)
    data=buffer.getvalue();assert inspect_wav(data)['frames']==80
    verifier,mint=signed_authority
    result=transcribe(data,lambda raw,metadata:'hello',capability=mint(['audio.transcribe']),verifier=verifier,principal='agent')
    assert result['text']=='hello' and result['authority'] is False
    with pytest.raises((wave.Error,EOFError)):inspect_wav(b'bad')
