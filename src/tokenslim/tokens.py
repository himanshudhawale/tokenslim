"""Token counting and cost estimation.

Uses :mod:`tiktoken` when it is installed for accurate counts, and falls back
to a fast, dependency-free heuristic otherwise so the tool always works
offline.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Approximate USD pricing per 1,000,000 tokens (input / output).
# Prices are illustrative and easy to update; the tool's value is the
# *relative* savings it reports, not exact billing.
MODELS: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
    "claude-sonnet": {"input": 3.00, "output": 15.00},
    "claude-haiku": {"input": 0.80, "output": 4.00},
    "claude-opus": {"input": 15.00, "output": 75.00},
}

DEFAULT_MODEL = "gpt-4o-mini"

_WORD_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


@dataclass
class CostEstimate:
    """Cost estimate for a given token count under a model."""

    model: str
    tokens: int
    input_cost: float
    output_cost: float

    @property
    def total_input_only(self) -> float:
        return self.input_cost


def _heuristic_count(text: str) -> int:
    """Estimate tokens without any external dependency.

    Combines a character-based estimate (~4 chars/token) with a token-like
    word/punctuation split and averages them, which tracks real tokenizers
    reasonably well for mixed code and prose.
    """
    if not text:
        return 0
    char_estimate = len(text) / 4.0
    piece_estimate = len(_WORD_RE.findall(text))
    return max(1, round((char_estimate + piece_estimate) / 2))


def count_tokens(text: str, model: str = DEFAULT_MODEL) -> int:
    """Count tokens in *text*, using ``tiktoken`` if available.

    Falls back to a heuristic estimate when ``tiktoken`` is not installed or
    does not recognise *model*.
    """
    if not text:
        return 0
    try:  # pragma: no cover - exercised only when tiktoken is installed
        import tiktoken

        try:
            enc = tiktoken.encoding_for_model(model)
        except KeyError:
            enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        return _heuristic_count(text)


def estimate_cost(
    tokens: int,
    model: str = DEFAULT_MODEL,
    *,
    as_output: bool = False,
) -> float:
    """Return the USD cost of *tokens* for *model*.

    By default the input price is used; pass ``as_output=True`` for the
    output price.
    """
    pricing = MODELS.get(model)
    if pricing is None:
        raise KeyError(f"Unknown model: {model!r}. Known: {', '.join(MODELS)}")
    rate = pricing["output" if as_output else "input"]
    return tokens / 1_000_000 * rate


def cost_table(tokens: int) -> list[CostEstimate]:
    """Return a per-model cost estimate for *tokens* (input pricing)."""
    table = []
    for model, pricing in MODELS.items():
        table.append(
            CostEstimate(
                model=model,
                tokens=tokens,
                input_cost=tokens / 1_000_000 * pricing["input"],
                output_cost=tokens / 1_000_000 * pricing["output"],
            )
        )
    return table
