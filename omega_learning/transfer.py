def evaluate(model,domains,evaluator,training_domains):
    training=frozenset(training_domains);results={}
    for domain,cases in domains.items():
        if domain in training:raise ValueError('Transfer domain overlaps training')
        results[domain]=evaluator(model,cases)
    if not results:raise ValueError('Unseen domains required')
    return results
def gains(baseline,candidate):
    if set(baseline)!=set(candidate):raise ValueError('Domain metrics mismatch')
    return {domain:candidate[domain]-baseline[domain] for domain in baseline}
