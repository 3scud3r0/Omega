from .harness import run
def by_domain(cases,training_domains,solver,verifier,budget,seed=0):
    training=frozenset(training_domains);groups={}
    for case in cases:
        if case['domain'] in training:raise ValueError('Generalization corpus includes a training domain')
        groups.setdefault(case['domain'],[]).append(case)
    return {domain:run(rows,solver,verifier,budget,seed) for domain,rows in sorted(groups.items())}
