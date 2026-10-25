"""OM-087: executable checks; source delivery, not a recorded pass."""
import pytest
from omega_nextorch.tokenizer import encode,decode,descriptor,BOS,PAD

def test_byte_tokenizer_lossless_unicode_and_special_token_rejection():
    text='Ômega λ\n代码'
    assert decode(encode(text))==text and descriptor()['normalization']=='none'
    with pytest.raises(ValueError):decode([BOS,PAD,1])
    with pytest.raises(ValueError):encode(text,max_bytes=1)
