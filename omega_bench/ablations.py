from .harness import run
COMPONENTS=frozenset({'memory','nextorch','lean','search'})
def compare(configure,cases,verifier,budget,seed=0):
    cases=tuple(cases);records={}
    for omitted in (None,*sorted(COMPONENTS)):
        enabled=COMPONENTS if omitted is None else COMPONENTS-{omitted}
        solver=configure(frozenset(enabled))
        records['full' if omitted is None else 'without_'+omitted]=run(cases,solver,verifier,budget,seed)
    return {'results':records,'same_seed':seed,'warning':'Removing Lean measures an ablation; it does not authorize unverified promotion.'}
