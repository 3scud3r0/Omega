def compare(configurations,training_ids,heldout_cases,evaluate,budget):
    cases=tuple(heldout_cases)
    if not cases or any(case['id'] in set(training_ids) for case in cases):raise ValueError('Held-out planner cases required')
    results=[]
    for configuration in configurations:
        if len(results)>=128:raise ValueError('Planner candidate budget exceeded')
        observations=evaluate(configuration,cases,budget)
        results.append({'configuration':configuration,'observations':observations})
    return {'candidates':tuple(results),'heldout_ids':tuple(c['id'] for c in cases),'promoted':False}
