from omega.otimizador_v1 import otimizar
from omega.equivalence import certify
def optimize(ir,measure):
    transformed,certificate=otimizar(ir)
    proof=certify(certificate,require_lean=True)
    baseline=measure(ir);candidate=measure(transformed)
    if baseline<=0 or candidate<=0:raise ValueError('Positive resource measurements required')
    return {'ir':transformed,'certificate':certificate,'proof':proof,'baseline_cost':baseline,
            'candidate_cost':candidate,'improved':candidate<baseline}
