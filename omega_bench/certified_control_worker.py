"""Fixed FP32 benchmark worker. It executes only the built-in controller fixture."""
from fractions import Fraction as Q
import json
from pathlib import Path
import resource
import sys
import time


def main(path):
    import torch
    from .certified_control import controller
    torch.set_num_threads(1)
    data=json.loads(Path(path).read_text())
    model,graph=controller()
    if graph!=data['graph']:raise ValueError('Benchmark model identity mismatch')
    total=0;calls=0
    def control(inputs):
        nonlocal total,calls
        start=time.perf_counter_ns()
        x=torch.tensor([float(Q(x)) for x in inputs],dtype=torch.float32)
        with torch.no_grad():y=model(x)
        total+=time.perf_counter_ns()-start;calls+=1
        return [str(Q(float(z))) for z in y]
    # Warm the fixed model before internal timing.
    control(['0','0']);total=calls=0
    bank=[control(row) for row in data['inputs']]
    theta,velocity=map(Q,data['initial']);trajectory=[]
    for _ in range(data['steps']):
        u=Q(control([str(theta),str(velocity)])[0]);trajectory.append(list(map(str,(theta,velocity,u))))
        theta,velocity=theta+Q(1,50)*velocity,velocity+Q(1,50)*(10*theta+u)
    print(json.dumps({'bank':bank,'trajectory':trajectory},sort_keys=True))
    print('OMEGA_METRICS '+json.dumps({'control_ns':total,'calls':calls,'peak_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}),file=sys.stderr)


if __name__=='__main__':main(sys.argv[1])
