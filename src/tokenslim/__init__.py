"""tokenslim — shrink the token cost of context you send to LLMs."""

from .tokens import count_tokens, estimate_cost, MODELS
from .slim import slim_text, SlimResult

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "count_tokens",
    "estimate_cost",
    "MODELS",
    "slim_text",
    "SlimResult",
]
