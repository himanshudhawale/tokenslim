"""Integration helpers: slim whole chat conversations and (optionally) force
slimming on every outbound LLM call.

``slim_messages`` takes the OpenAI/Anthropic-style ``messages`` list (each item a
dict with ``role`` and ``content``) and slims the textual content of each
message, reporting how many tokens were saved across the whole conversation.

``auto_slim`` wraps any callable that accepts ``messages=...`` so that the
context is slimmed *before* it is sent - the "force it on every call" pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Tuple

from .slim import slim_text
from .tokens import DEFAULT_MODEL, estimate_cost


@dataclass
class MessagesSavings:
    """Aggregate savings from slimming a conversation."""

    original_tokens: int
    slim_tokens: int
    model: str
    messages_changed: int = 0
    details: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def tokens_saved(self) -> int:
        return self.original_tokens - self.slim_tokens

    @property
    def percent_saved(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return self.tokens_saved / self.original_tokens * 100.0

    @property
    def cost_saved(self) -> float:
        return estimate_cost(self.tokens_saved, self.model)


def slim_messages(
    messages: List[Dict[str, Any]],
    *,
    model: str = DEFAULT_MODEL,
) -> Tuple[List[Dict[str, Any]], MessagesSavings]:
    """Slim the ``content`` of each chat message conservatively.

    Only string content is touched (whitespace-level transforms that never
    corrupt prose). Non-string content (tool calls, image parts, etc.) is left
    untouched. Returns ``(slimmed_messages, savings)``.
    """
    slimmed: List[Dict[str, Any]] = []
    original_total = 0
    slim_total = 0
    changed = 0
    details: List[Dict[str, Any]] = []

    for msg in messages:
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, str):
            slimmed.append(msg)
            continue
        res = slim_text(content, ext=None, strip_comments=False, model=model)
        original_total += res.original_tokens
        slim_total += res.slim_tokens
        new_msg = dict(msg)
        new_msg["content"] = res.text.rstrip("\n") if content and not content.endswith("\n") else res.text
        slimmed.append(new_msg)
        if res.tokens_saved:
            changed += 1
        details.append(
            {
                "role": msg.get("role"),
                "original_tokens": res.original_tokens,
                "slim_tokens": res.slim_tokens,
                "tokens_saved": res.tokens_saved,
            }
        )

    savings = MessagesSavings(
        original_tokens=original_total,
        slim_tokens=slim_total,
        model=model,
        messages_changed=changed,
        details=details,
    )
    return slimmed, savings


def auto_slim(func: Callable, *, model: str = DEFAULT_MODEL) -> Callable:
    """Wrap a chat-completion callable so its ``messages`` are slimmed first.

    Use it to *force* slimming on every call without changing call sites::

        client.chat.completions.create = auto_slim(client.chat.completions.create)
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if "messages" in kwargs and isinstance(kwargs["messages"], list):
            kwargs["messages"], _ = slim_messages(kwargs["messages"], model=model)
        return func(*args, **kwargs)

    return wrapper
