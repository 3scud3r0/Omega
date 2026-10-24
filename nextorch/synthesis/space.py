"""Shape-safe DAG search space: residual MLP, diagonal SSM and linear attention."""

from dataclasses import asdict, dataclass

import torch
from torch import nn

from nextorch.verifier.mup import MuPScaleCoordinator

OPERATIONS = ("mlp", "ssm", "linear_attention")


@dataclass(frozen=True)
class GraphNode:
    op: str
    parents: tuple[int, ...]


@dataclass(frozen=True)
class Architecture:
    input_dim: int
    output_dim: int
    width: int
    nodes: tuple[GraphNode, ...]

    def __post_init__(self):
        if min(self.input_dim, self.output_dim, self.width) <= 0 or not self.nodes:
            raise ValueError("Architecture dimensions and node list must be nonempty")
        # State 0 is the input projection; node i produces state i + 1.
        for i, node in enumerate(self.nodes):
            if (
                node.op not in OPERATIONS
                or not node.parents
                or len(set(node.parents)) != len(node.parents)
            ):
                raise ValueError("Invalid DAG node")
            if min(node.parents) < 0 or max(node.parents) > i:
                raise ValueError("DAG parents must precede their child")

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(
            data["input_dim"],
            data["output_dim"],
            data["width"],
            tuple(GraphNode(n["op"], tuple(n["parents"])) for n in data["nodes"]),
        )

    def build(self):
        return DAGNetwork(self)


class ResidualMLP(nn.Module):
    def __init__(self, width):
        super().__init__()
        self.norm = nn.LayerNorm(width)
        self.layers = nn.Sequential(
            nn.Linear(width, 2 * width), nn.GELU(), nn.Linear(2 * width, width)
        )

    def forward(self, x):
        return x + self.layers(self.norm(x)) / 2


class DiagonalSSM(nn.Module):
    """Stable diagonal state-space recurrence, causal along the sequence axis."""

    def __init__(self, width):
        super().__init__()
        self.decay_logit = nn.Parameter(torch.zeros(width))
        self.input_layer = nn.Linear(width, width)
        self.output_layer = nn.Linear(width, width)

    def forward(self, x):
        single = x.ndim == 2
        sequence = x.unsqueeze(1) if single else x
        state = torch.zeros_like(sequence[:, 0])
        decay = self.decay_logit.sigmoid()
        outputs = []
        for item in sequence.unbind(1):
            state = decay * state + (1 - decay) * torch.tanh(self.input_layer(item))
            outputs.append(item + self.output_layer(state))
        result = torch.stack(outputs, 1)
        return result[:, 0] if single else result


class LinearAttention(nn.Module):
    """Noncausal positive-kernel attention with linear sequence complexity."""

    def __init__(self, width):
        super().__init__()
        self.qkv = nn.Linear(width, 3 * width)
        self.output_layer = nn.Linear(width, width)

    def forward(self, x):
        single = x.ndim == 2
        seq = x.unsqueeze(1) if single else x
        q, k, v = self.qkv(seq).chunk(3, -1)
        q, k = nn.functional.elu(q) + 1, nn.functional.elu(k) + 1
        kv = k.transpose(-2, -1) @ v
        normalizer = (q * k.sum(1, keepdim=True)).sum(-1, keepdim=True).clamp_min(1e-8)
        out = seq + self.output_layer((q @ kv) / normalizer)
        return out[:, 0] if single else out


class DAGNetwork(nn.Module):
    def __init__(self, architecture):
        super().__init__()
        self.architecture = architecture
        self.input_layer = nn.Linear(architecture.input_dim, architecture.width)
        types = dict(zip(OPERATIONS, (ResidualMLP, DiagonalSSM, LinearAttention)))
        self.blocks = nn.ModuleList(types[n.op](architecture.width) for n in architecture.nodes)
        self.policy_head = nn.Linear(architecture.width, architecture.output_dim)
        MuPScaleCoordinator.apply_mup_coordinates(self, architecture.width)

    def encode(self, x):
        if x.ndim not in (2, 3) or x.shape[-1] != self.architecture.input_dim:
            raise ValueError("Expected [batch, (sequence), input_dim]")
        states = [self.input_layer(x)]
        for node, block in zip(self.architecture.nodes, self.blocks):
            merged = torch.stack([states[p] for p in node.parents]).mean(0)
            states.append(block(merged))
        return states[-1].mean(1) if x.ndim == 3 else states[-1]

    def forward(self, x):
        return self.policy_head(self.encode(x))
