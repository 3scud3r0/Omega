"""Intent must supply a logical specification; prose never grants authority."""
import json
from pathlib import Path
from omega_synth_mcts.search import synthesize


def distill(intent,specification,directory,**limits):
    if type(intent) is not str or not 1<=len(intent)<=16384:raise ValueError('Bounded hypothesis text required')
    result=synthesize(specification,directory,**limits)
    record={'format':'omega-inverse-distillation-1','intent':intent,'formal_specification':specification,
            'result':result,'scope':'the supplied formal contract; natural-language interpretation is unproved'}
    (Path(directory)/'distillation.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
    return record
