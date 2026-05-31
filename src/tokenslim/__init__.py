"""tokenslim — shrink the token cost of context you send to LLMs."""

from .tokens import count_tokens, estimate_cost, MODELS
from .slim import slim_text, SlimResult
from .integrate import slim_messages, auto_slim, MessagesSavings

__version__ = "0.2.0"

__all__ = [
    "__version__",
    "count_tokens",
    "estimate_cost",
    "MODELS",
    "slim_text",
    "SlimResult",
    "slim_messages",
    "auto_slim",
    "MessagesSavings",
]
