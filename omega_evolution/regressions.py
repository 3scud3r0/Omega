import math
def gate(baseline,candidate,safety,required_safety,tolerances=None):
    tolerances={} if tolerances is None else tolerances;failures=[]
    if not set(baseline)<=set(candidate):raise ValueError('Missing baseline capability metrics')
    for key,value in baseline.items():
        if not math.isfinite(value) or not math.isfinite(candidate[key]):failures.append(('nonfinite',key))
        elif candidate[key]<value-tolerances.get(key,0):failures.append(('capability_regression',key))
    for key in required_safety:
        if safety.get(key) is not True:failures.append(('safety_failure',key))
    return {'passed':not failures,'failures':tuple(failures)}
