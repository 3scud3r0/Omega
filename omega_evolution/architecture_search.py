import random
def candidates(widths,depths,seed=0,count=16,max_parameters=1000000):
    rng=random.Random(seed);seen=set();result=[]
    choices=[(w,d) for w in widths for d in depths if type(w) is int and type(d) is int and w>0 and d>0 and w*w*d<=max_parameters]
    rng.shuffle(choices)
    for width,depth in choices[:min(count,128)]:
        configuration={'width':width,'depth':depth,'parameter_upper_estimate':width*width*depth,'seed':seed};result.append(configuration)
    return tuple(result)
def compare(proposals,construct,train,evaluate,training,heldout,budget):
    results=[]
    for configuration in proposals:
        model=construct(configuration);train(model,training,budget,configuration['seed'])
        results.append({'configuration':configuration,'heldout':evaluate(model,heldout),'promoted':False})
    return tuple(results)
