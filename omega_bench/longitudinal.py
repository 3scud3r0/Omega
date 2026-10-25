from .harness import run
def generations(versions,cases,load_solver,verifier,budget,seed=0):
    cases=tuple(cases);records=[]
    for version in versions:
        solver=load_solver(version);measurement=run(cases,solver,verifier,budget,seed)
        previous=records[-1]['measurement']['accuracy'] if records else None
        current=measurement['accuracy']
        records.append({'version':version,'measurement':measurement,'delta_accuracy':current-previous if current is not None and previous is not None else None,'fixed_seed':seed})
    return tuple(records)
