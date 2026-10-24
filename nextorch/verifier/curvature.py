"""Matrix-free Hessian diagnostics. The caller supplies a scalar differentiable loss."""

import torch


def _hvp(loss, parameters):
    params = tuple(p for p in parameters if p.requires_grad)
    if loss.ndim != 0 or not params:
        raise ValueError("Need a scalar loss and trainable parameters")
    grads = torch.autograd.grad(loss, params, create_graph=True, allow_unused=True)

    def product(vectors):
        terms = [(g * v).sum() for g, v in zip(grads, vectors) if g is not None and g.requires_grad]
        if not terms:
            return tuple(torch.zeros_like(p) for p in params)
        second = torch.autograd.grad(sum(terms), params, retain_graph=True, allow_unused=True)
        return tuple(torch.zeros_like(p) if h is None else h for h, p in zip(second, params))

    return params, product


def hutchinson_trace(loss, parameters, samples=16, seed=42):
    if samples <= 0:
        raise ValueError("samples must be positive")
    params, product = _hvp(loss, parameters)
    generator = torch.Generator(device=params[0].device).manual_seed(seed)
    values = []
    for _ in range(samples):
        vectors = [
            torch.randint(0, 2, p.shape, generator=generator, device=p.device).to(p.dtype) * 2 - 1
            for p in params
        ]
        values.append(sum((v * h).sum() for v, h in zip(vectors, product(vectors))))
    return float(torch.stack(values).mean())


def dominant_hessian_eigenvalue(loss, parameters, iterations=20):
    if iterations <= 0:
        raise ValueError("iterations must be positive")
    params, product = _hvp(loss, parameters)
    vectors = [torch.randn_like(p) for p in params]
    norm = torch.sqrt(sum(v.square().sum() for v in vectors)).clamp_min(1e-12)
    vectors = [v / norm for v in vectors]
    value = torch.zeros((), device=params[0].device)
    for _ in range(iterations):
        hv = product(vectors)
        value = sum((v * h).sum() for v, h in zip(vectors, hv))
        norm = torch.sqrt(sum(h.square().sum() for h in hv))
        if norm < 1e-12:
            return 0.0
        vectors = [h.detach() / norm.detach() for h in hv]
    return float(value)
