"""Nextorch: neural synthesis and proof-gated latent reasoning."""

from .config import NextorchConfig, seed_everything
from .core import ManifoldAnalyzer, OrangeBridge
from .engine import NextorchReasoner
from .evolution import NextorchEngine
from .formal import FormalVerificationGateway
from .interpretability import IntegratedSAE
from .model import NextorchModel

__version__ = "0.1.0"
__all__ = [
    "NextorchModel",
    "NextorchConfig",
    "seed_everything",
    "ManifoldAnalyzer",
    "OrangeBridge",
    "NextorchReasoner",
    "NextorchEngine",
    "FormalVerificationGateway",
    "IntegratedSAE",
]
