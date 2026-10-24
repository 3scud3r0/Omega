"""Function-preserving Net2Wider for adjacent affine layers.

Clone incoming neurons and divide their outgoing weights by clone multiplicity.
The identity holds for elementwise activations, with floating-point tolerance.
Noise, layer normalization and coupled activations invalidate this identity.
"""

import copy

import torch
from torch import nn


class Net2NetExpansion:
    @staticmethod
    def widen_pair(incoming, outgoing, new_features, generator=None):
        if incoming.out_features != outgoing.in_features:
            raise ValueError("Layers do not share the same hidden dimension")
        old = incoming.out_features
        if new_features < old:
            raise ValueError("Net2Wider cannot shrink a layer")
        if (
            incoming.weight.device != outgoing.weight.device
            or incoming.weight.dtype != outgoing.weight.dtype
        ):
            raise ValueError("Layer devices/dtypes must match")
        if new_features == old:
            return copy.deepcopy(incoming), copy.deepcopy(outgoing)
        device, dtype = incoming.weight.device, incoming.weight.dtype
        # Draw on CPU so a portable caller generator also works for CUDA models.
        clones = torch.randint(old, (new_features - old,), generator=generator)
        mapping = torch.cat((torch.arange(old), clones)).to(device)
        counts = torch.bincount(mapping, minlength=old).to(dtype)
        first = nn.Linear(
            incoming.in_features,
            new_features,
            bias=incoming.bias is not None,
            device=device,
            dtype=dtype,
        )
        second = nn.Linear(
            new_features,
            outgoing.out_features,
            bias=outgoing.bias is not None,
            device=device,
            dtype=dtype,
        )
        with torch.no_grad():
            first.weight.copy_(incoming.weight[mapping])
            second.weight.copy_(outgoing.weight[:, mapping] / counts[mapping])
            if incoming.bias is not None:
                first.bias.copy_(incoming.bias[mapping])
            if outgoing.bias is not None:
                second.bias.copy_(outgoing.bias)
        first.train(incoming.training)
        second.train(outgoing.training)
        first.weight.requires_grad_(incoming.weight.requires_grad)
        second.weight.requires_grad_(outgoing.weight.requires_grad)
        if first.bias is not None:
            first.bias.requires_grad_(incoming.bias.requires_grad)
        if second.bias is not None:
            second.bias.requires_grad_(outgoing.bias.requires_grad)
        return first, second

    @staticmethod
    def widen_sequential(model, index, new_features, generator=None):
        if not isinstance(model, nn.Sequential) or index < 0 or index + 2 >= len(model):
            raise ValueError("Expected Sequential with Linear, elementwise activation, Linear")
        if not isinstance(model[index], nn.Linear) or not isinstance(model[index + 2], nn.Linear):
            raise ValueError("Expansion requires adjacent affine projections")
        if not isinstance(model[index + 1], (nn.ReLU, nn.GELU, nn.Tanh, nn.Sigmoid, nn.Identity)):
            raise ValueError("Only deterministic elementwise activations preserve Net2Wider")
        first, second = Net2NetExpansion.widen_pair(
            model[index], model[index + 2], new_features, generator
        )
        widened = copy.deepcopy(model)
        widened[index], widened[index + 2] = first, second
        return widened
