"""The slimming engine: reduce token count of text/code with safe transforms.

The transforms are conservative — they remove tokens that almost never carry
meaning for an LLM (trailing whitespace, repeated blank lines, comments when
requested) while preserving the structure of the content.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .tokens import count_tokens

# File extension -> language family used to pick comment syntax.
_HASH_COMMENT = {".py", ".rb", ".sh", ".bash", ".zsh", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".r", ".pl"}
_SLASH_COMMENT = {
    ".js", ".jsx", ".ts", ".tsx", ".java", ".c", ".h", ".cpp", ".hpp", ".cc",
    ".cs", ".go", ".rs", ".swift", ".kt", ".kts", ".scala", ".php", ".m", ".mm",
    ".scss", ".less",
}
# Block-comment-only languages (/* ... */) with no line-comment form.
_BLOCK_ONLY = {".css"}
# HTML/XML style block comments (<!-- ... -->).
_HTML_COMMENT = {".html", ".htm", ".xml", ".svg", ".vue"}
# SQL/Lua style: "--" line comments (SQL also supports /* */ blocks).
_DASH_COMMENT = {".sql", ".lua"}


@dataclass
class SlimResult:
    """Result of slimming a piece of text."""

    text: str
    original_tokens: int
    slim_tokens: int
    model: str

    @property
    def tokens_saved(self) -> int:
        return self.original_tokens - self.slim_tokens

    @property
    def percent_saved(self) -> float:
        if self.original_tokens == 0:
            return 0.0
        return self.tokens_saved / self.original_tokens * 100.0


def _strip_hash_comments(text: str) -> str:
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("#!"):
            # Preserve shebang lines verbatim.
            out.append(line)
            continue
        if stripped.startswith("#"):
            continue
        # Inline comment: drop from an unquoted '#' to end of line.
        out.append(_remove_inline(line, "#"))
    return "\n".join(out)


def _strip_slash_comments(text: str) -> str:
    # Remove block comments /* ... */ first.
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("//"):
            continue
        out.append(_remove_inline(line, "//"))
    return "\n".join(out)


def _strip_block_only_comments(text: str) -> str:
    """Languages such as CSS that only have ``/* ... */`` block comments."""
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def _strip_html_comments(text: str) -> str:
    """HTML/XML ``<!-- ... -->`` comments."""
    return re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)


def _strip_dash_comments(text: str) -> str:
    """SQL/Lua ``--`` line comments (plus ``/* */`` blocks for SQL)."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    out = []
    for line in text.splitlines():
        stripped = line.lstrip()
        if stripped.startswith("--"):
            continue
        out.append(_remove_inline(line, "--"))
    return "\n".join(out)


def _remove_inline(line: str, marker: str) -> str:
    """Remove an inline comment starting at *marker*, ignoring markers that
    appear inside simple quotes. Conservative: if a quote is open, keep line."""
    in_single = in_double = False
    i = 0
    while i < len(line):
        ch = line[i]
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double and line.startswith(marker, i):
            return line[:i].rstrip()
        i += 1
    return line


def _collapse_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text)


def _trim_trailing_ws(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines())


def slim_text(
    text: str,
    *,
    ext: str | None = None,
    strip_comments: bool = True,
    model: str = "gpt-4o-mini",
) -> SlimResult:
    """Slim *text* and return a :class:`SlimResult` with before/after tokens.

    ``ext`` selects comment syntax (e.g. ``".py"``). When omitted, comment
    stripping is skipped and only whitespace transforms are applied.
    """
    original_tokens = count_tokens(text, model)
    result = text

    if strip_comments and ext:
        ext = ext.lower()
        if ext in _HASH_COMMENT:
            result = _strip_hash_comments(result)
        elif ext in _SLASH_COMMENT:
            result = _strip_slash_comments(result)
        elif ext in _BLOCK_ONLY:
            result = _strip_block_only_comments(result)
        elif ext in _HTML_COMMENT:
            result = _strip_html_comments(result)
        elif ext in _DASH_COMMENT:
            result = _strip_dash_comments(result)

    result = _trim_trailing_ws(result)
    result = _collapse_blank_lines(result)
    result = result.strip("\n") + "\n" if result.strip() else ""

    slim_tokens = count_tokens(result, model)
    return SlimResult(
        text=result,
        original_tokens=original_tokens,
        slim_tokens=slim_tokens,
        model=model,
    )
