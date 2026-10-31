"""Optional fixed WebGPU sieve; exact native CPU verification is authoritative.

No automatic driver installation, remote service or performance assertion.
WGSL is compiled by wgpu-native to the adapter backend (e.g. Vulkan/Metal).
The shader never runs arbitrary candidate source; candidates are bounded data.
"""
from pathlib import Path
import struct

from .runtime import SOURCE_ROOT, call
from .certificates import certify_claim, verify_claim


class GPUUnavailable(RuntimeError):
    pass


class GPUExecutionError(RuntimeError):
    pass


def _packed(rows,kind):
    flat = [int(value) for row in rows for value in row]
    return struct.pack('<'+kind*len(flat),*flat)


def _dispatch(plan):
    if not plan['gpu_eligible']:
        raise ValueError('GPU sieve domain: 32 nodes, reduced signed Q15 rational lanes')
    try:
        import wgpu
    except ImportError as exc:
        raise GPUUnavailable('Optional wgpu package is not installed') from exc
    try:
        adapter = wgpu.gpu.request_adapter_sync(power_preference='high-performance')
        if adapter is None:
            raise GPUUnavailable('No WebGPU adapter')
        device = adapter.request_device_sync(required_limits={})
    except Exception as exc:
        raise GPUUnavailable('WebGPU adapter/device is unavailable') from exc
    path = SOURCE_ROOT/'omega_gpu/parallel_induction.wgsl'
    shader = device.create_shader_module(code=path.read_text())
    inputs = [struct.pack('<4I',*plan['metadata']),_packed(plan['nodes'],'i'),
              _packed(plan['descriptors'],'I'),_packed(plan['samples'],'i')]
    buffers = []
    try:
        for data in inputs:
            buffers.append(device.create_buffer_with_data(data=data,usage=wgpu.BufferUsage.STORAGE))
        output = device.create_buffer(size=int(plan['metadata'][0])*16,
                                      usage=wgpu.BufferUsage.STORAGE|wgpu.BufferUsage.COPY_SRC)
        buffers.append(output)
        pipeline = device.create_compute_pipeline(layout='auto',compute={'module':shader,'entry_point':'main'})
        group = device.create_bind_group(layout=pipeline.get_bind_group_layout(0),entries=[
            {'binding':index,'resource':{'buffer':buffer,'offset':0,'size':buffer.size}}
            for index,buffer in enumerate(buffers)])
        encoder = device.create_command_encoder()
        compute = encoder.begin_compute_pass()
        compute.set_pipeline(pipeline)
        compute.set_bind_group(0,group)
        compute.dispatch_workgroups((int(plan['metadata'][0])+63)//64)
        compute.end()
        device.queue.submit([encoder.finish()])
        raw = bytes(device.queue.read_buffer(output))
        rows = [list(struct.unpack_from('<4I',raw,offset)) for offset in range(0,len(raw),16)]
        info = dict(adapter.info)
        return {'rows':rows,'adapter':info,'physical_gpu_claimed':str(info.get('adapter_type','')).lower() not in {'cpu','unknown',''},
                'shader_format':'WGSL','backend':str(info.get('backend_type','unknown'))}
    finally:
        for buffer in buffers:
            buffer.destroy()
        device.destroy()


def dispatch(plan):
    """Run the fixed driver adapter in a bounded trusted tool process."""
    import json
    import sys
    import tempfile
    from omega_platform.budget import Budget
    from omega_platform.sandbox import trusted
    from omega_security.encoding import canonical,decode
    with tempfile.TemporaryDirectory(prefix='omega-webgpu-') as tmp:
        path = Path(tmp)/'plan.json'
        path.write_bytes(canonical(plan,max_bytes=4*1024**2,max_nodes=100000))
        outcome = trusted([sys.executable,Path(__file__).with_name('_gpu_worker.py'),path],
                          budget=Budget(wall_seconds=30,cpu_seconds=20,memory_bytes=4*1024**3,
                                        file_bytes=512*1024**2),check=False)
    if not outcome.ok:
        raise GPUExecutionError('WebGPU worker failed or exceeded its OS budget')
    result = decode(outcome.stdout.encode(),max_bytes=1024**2,max_nodes=20000)
    if result.get('status') == 'unavailable':
        raise GPUUnavailable(result.get('reason','WebGPU unavailable'))
    if result.get('status') != 'computed':
        raise GPUExecutionError(result.get('reason','WebGPU computation failed'))
    return result['result']


def sieve(programs, observations, *, backend='cpu', max_admitted=8):
    if backend not in {'cpu','gpu','auto'}:
        raise ValueError('Sieve backend cpu, gpu or auto')
    if type(max_admitted) is not int or not 1 <= max_admitted <= 16:
        raise ValueError('Kernel admission budget 1..16')
    if type(observations) is not list or not 1 <= len(observations) <= 16:
        raise ValueError('Kernel-verified sieve observation budget 1..16')
    request = {'programs':programs,'observations':observations}
    plan = call('sieve',dict(request,pack_only=1)) if backend != 'cpu' else call('sieve',request)
    actual = 'cpu'
    gpu = None
    unavailable = None
    if backend != 'cpu':
        try:
            gpu = dispatch(plan)
            actual = 'webgpu'
        except (GPUUnavailable,ValueError) as exc:
            if backend == 'gpu':
                raise
            unavailable = str(exc)
            plan = call('sieve',request)
    survivors = list(plan['fits'])
    cpu_results = list(plan['results'])
    cpu_fits = set(plan['fits'])
    proposed_count = len(survivors)
    if gpu is not None:
        # GPU may reject candidates due to its narrower intermediate domain.
        # CPU remains authoritative: a spurious GPU "fit" never becomes proof.
        survivors = [i for i,row in enumerate(gpu['rows']) if row[0]==0 and row[1]==0]
        if any(i >= len(programs) for i in survivors):
            raise GPUExecutionError('GPU candidate index outside the submitted batch')
        proposed_count = len(survivors)
        survivors = survivors[:max_admitted]
        cpu_results = [None]*len(programs)
        cpu_fits = set()
        if survivors:
            checked = call('sieve',{'programs':[programs[i] for i in survivors],'observations':observations})
            for local,index in enumerate(survivors):
                cpu_results[index] = checked['results'][local]
                if local in checked['fits']:
                    cpu_fits.add(index)
    survivors = survivors[:max_admitted]
    admitted = []
    rejected = []
    for index in survivors:
        if index not in cpu_fits:
            rejected.append({'index':index,'reason':'GPU/CPU disagreement'})
            continue
        certificate = certify_claim({'format':'omega-epistemic-claim-1',
                                     'dag':programs[index],'observations':observations})
        result = verify_claim(certificate)
        if result['accepted']:
            admitted.append({'index':index,'certificate':certificate,'verification':result})
        else:
            rejected.append({'index':index,'reason':'kernel rejected'})
    return {'format':'omega-verified-parallel-sieve-1','backend':actual,'gpu':gpu,
            'gpu_unavailable_reason':unavailable,'cpu_results':cpu_results,
            'cpu_evaluated_candidates':len(programs) if gpu is None else len(survivors),
            'admission_limit':max_admitted,'selection_limited':proposed_count>max_admitted,
            'admitted':admitted,'rejected':rejected,'scope':'finite observation agreement; no general correctness or speed claim'}
