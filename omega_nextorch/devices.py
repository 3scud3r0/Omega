def resolve(name='cpu',precision='float32'):
    import torch
    device=torch.device(name)
    if device.type not in {'cpu','cuda'}:raise ValueError('Unsupported compute device')
    if device.type=='cuda' and not torch.cuda.is_available():raise RuntimeError('Requested CUDA device unavailable')
    dtypes={'float32':torch.float32,'float16':torch.float16,'bfloat16':torch.bfloat16}
    if precision not in dtypes or (device.type=='cpu' and precision=='float16'):raise ValueError('Unsupported precision/device pair')
    return device,dtypes[precision]
def parity(reference,candidate,absolute=1e-6,relative=1e-5):
    import torch
    if reference.shape!=candidate.shape:raise ValueError('Numerical comparison shape mismatch')
    if not torch.isfinite(reference).all() or not torch.isfinite(candidate).all():return {'within_tolerance':False,'nonfinite':True}
    return {'within_tolerance':bool(torch.allclose(reference.double(),candidate.double(),atol=absolute,rtol=relative)),
            'max_absolute_error':float((reference.double()-candidate.double()).abs().max())}
