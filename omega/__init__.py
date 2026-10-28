"""Ômega: protótipo de linguagem verificável com aritmética exata."""
__version__ = "2.0.0"

# PyTorch is imported lazily only when exporting a decorated model.
from .certify import certify
