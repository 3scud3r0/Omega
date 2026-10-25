"""External judgments remain hidden from candidate selection feedback."""
def crosscheck(problem,candidate,development_verifier,external_verifier):
    development=development_verifier(problem,candidate);external=external_verifier(problem,candidate)
    if type(development) is not bool or type(external) is not bool:raise ValueError('Boolean independent judgments required')
    return {'development':development,'external':external,'disagreement':development!=external,'accepted':development and external}
def discrepancy(development,external):
    if not development or len(development)!=len(external):raise ValueError('Paired verifier observations required')
    opportunistic=sum(a and not b for a,b in zip(development,external))
    return {'cases':len(development),'opportunistic_cases':opportunistic,'rate':opportunistic/len(development)}
