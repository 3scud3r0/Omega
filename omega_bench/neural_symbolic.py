from .harness import run
def compare(cases,neural,symbolic,verifier,budget,seed=0):
    cases=tuple(cases)
    return {'neural':run(cases,neural,verifier,budget,seed),
            'symbolic':run(cases,symbolic,verifier,budget,seed),'same_cases':True,'seed':seed}
