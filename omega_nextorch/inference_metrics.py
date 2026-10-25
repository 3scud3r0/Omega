import statistics,time,resource
def measure(model,inputs,repetitions=10,energy_reader=None):
    import torch
    if not 1<=repetitions<=1000:raise ValueError('Invalid inference measurement budget')
    use_cuda=any(p.is_cuda for p in model.parameters());timings=[];training=model.training;model.eval()
    initial_energy=energy_reader() if energy_reader else None
    try:
        with torch.no_grad():
            for _ in range(repetitions):
                if use_cuda:torch.cuda.synchronize()
                started=time.perf_counter();model(inputs)
                if use_cuda:torch.cuda.synchronize()
                timings.append(time.perf_counter()-started)
    finally:model.train(training)
    final_energy=energy_reader() if energy_reader else None
    return {'median_seconds':statistics.median(timings),'repetitions':repetitions,
            'process_max_rss_kib':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            'cuda_allocated_bytes':torch.cuda.memory_allocated() if use_cuda else None,
            'energy_joules':final_energy-initial_energy if energy_reader else None}
