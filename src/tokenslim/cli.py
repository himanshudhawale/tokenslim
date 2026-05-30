"""Command-line interface for tokenslim."""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Sequence

from . import __version__
from .slim import is_text_ext, slim_text
from .tokens import DEFAULT_MODEL, MODELS, cost_table, count_tokens, estimate_cost

# Directories never worth walking into.
_IGNORE_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "env",
                ".mypy_cache", ".pytest_cache", "dist", "build", ".idea", ".vscode"}


def _expand_paths(paths: Sequence[str]) -> list[str]:
    """Expand *paths*: directories are walked recursively for text files.

    Files given explicitly are always included regardless of extension; files
    discovered by walking a directory are filtered to recognized text types.
    """
    out: list[str] = []
    seen: set[str] = set()

    def _add(path: str) -> None:
        norm = os.path.normpath(path)
        if norm not in seen:
            seen.add(norm)
            out.append(path)

    for path in paths:
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                dirs[:] = [d for d in dirs if d not in _IGNORE_DIRS]
                for name in sorted(files):
                    if is_text_ext(os.path.splitext(name)[1]):
                        _add(os.path.join(root, name))
        else:
            _add(path)
    return out


def _read_inputs(paths: Sequence[str]) -> list[tuple[str, str]]:
    """Return a list of ``(label, text)`` from files, directories, or stdin.

    If *paths* is empty, read from stdin and label it ``"<stdin>"``.
    """
    if not paths:
        data = sys.stdin.read()
        return [("<stdin>", data)]

    items: list[tuple[str, str]] = []
    for path in _expand_paths(paths):
        if not os.path.isfile(path):
            print(f"tokenslim: warning: skipping '{path}' (not a file)", file=sys.stderr)
            continue
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            items.append((path, fh.read()))
    return items


def _fmt_cost(value: float) -> str:
    if value == 0:
        return "$0"
    if value < 0.01:
        return f"${value:.6f}"  # show more precision for tiny amounts
    return f"${value:,.4f}"


def cmd_count(args: argparse.Namespace) -> int:
    items = _read_inputs(args.paths)
    if not items:
        print("tokenslim: no input", file=sys.stderr)
        return 1

    per_file = [(label, count_tokens(text, args.model)) for label, text in items]
    grand_total = sum(tokens for _, tokens in per_file)
    over_budget = args.budget is not None and grand_total > args.budget

    if args.json:
        payload = {
            "model": args.model,
            "files": [{"path": label, "tokens": tokens} for label, tokens in per_file],
            "total_tokens": grand_total,
            "cost": {
                est.model: {"input": est.input_cost, "output": est.output_cost}
                for est in cost_table(grand_total)
            },
        }
        if args.budget is not None:
            payload["budget"] = args.budget
            payload["over_budget"] = over_budget
        print(json.dumps(payload, indent=2))
        return 2 if over_budget else 0

    for label, tokens in per_file:
        print(f"{tokens:>10,}  {label}")

    if len(per_file) > 1:
        print(f"{grand_total:>10,}  TOTAL")

    print()
    print(f"Cost estimate for {grand_total:,} input tokens:")
    for est in cost_table(grand_total):
        print(f"  {est.model:<16} in {_fmt_cost(est.input_cost):>12}   out {_fmt_cost(est.output_cost):>12}")

    if args.budget is not None:
        if over_budget:
            over = grand_total - args.budget
            print(
                f"\ntokenslim: OVER BUDGET by {over:,} tokens "
                f"({grand_total:,} > {args.budget:,})",
                file=sys.stderr,
            )
            return 2
        print(
            f"\ntokenslim: within budget ({grand_total:,} <= {args.budget:,})",
            file=sys.stderr,
        )
    return 0


def cmd_slim(args: argparse.Namespace) -> int:
    items = _read_inputs(args.paths)
    if not items:
        print("tokenslim: no input", file=sys.stderr)
        return 1

    total_before = 0
    total_after = 0
    writing_stdout = not args.in_place and not args.json and len(items) == 1
    records = []

    for label, text in items:
        ext = os.path.splitext(label)[1] if label != "<stdin>" else (args.ext or None)
        res = slim_text(
            text,
            ext=ext,
            strip_comments=not args.keep_comments,
            model=args.model,
        )
        total_before += res.original_tokens
        total_after += res.slim_tokens
        records.append(
            {
                "path": label,
                "original_tokens": res.original_tokens,
                "slim_tokens": res.slim_tokens,
                "tokens_saved": res.tokens_saved,
                "percent_saved": round(res.percent_saved, 2),
            }
        )

        if args.in_place and label != "<stdin>":
            with open(label, "w", encoding="utf-8") as fh:
                fh.write(res.text)
        elif writing_stdout:
            sys.stdout.write(res.text)

        if not args.json and (args.in_place or not writing_stdout):
            print(
                f"{label}: {res.original_tokens:,} -> {res.slim_tokens:,} tokens "
                f"({res.percent_saved:.1f}% saved)",
                file=sys.stderr,
            )

    saved = total_before - total_after
    pct = (saved / total_before * 100.0) if total_before else 0.0
    in_saved = estimate_cost(saved, args.model)

    if args.json:
        print(
            json.dumps(
                {
                    "model": args.model,
                    "files": records,
                    "total_original_tokens": total_before,
                    "total_slim_tokens": total_after,
                    "total_tokens_saved": saved,
                    "percent_saved": round(pct, 2),
                    "cost_saved_per_call": in_saved,
                },
                indent=2,
            )
        )
        return 0

    print(
        f"\nTotal: {total_before:,} -> {total_after:,} tokens "
        f"({pct:.1f}% saved, ~{_fmt_cost(in_saved)} per call on {args.model})",
        file=sys.stderr,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tokenslim",
        description="Count tokens, estimate LLM cost, and slim context before you send it.",
    )
    parser.add_argument("--version", action="version", version=f"tokenslim {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    common_model = dict(
        default=DEFAULT_MODEL,
        choices=sorted(MODELS),
        help="Model used for token counting/pricing (default: %(default)s).",
    )

    p_count = sub.add_parser("count", help="Count tokens and show cost estimates.")
    p_count.add_argument("paths", nargs="*", help="Files to count (default: stdin).")
    p_count.add_argument("--model", **common_model)
    p_count.add_argument(
        "--budget",
        type=int,
        metavar="N",
        help="Fail (exit code 2) if total tokens exceed N. Useful in CI.",
    )
    p_count.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_count.set_defaults(func=cmd_count)

    p_slim = sub.add_parser("slim", help="Slim text/code and report tokens saved.")
    p_slim.add_argument("paths", nargs="*", help="Files to slim (default: stdin).")
    p_slim.add_argument("--model", **common_model)
    p_slim.add_argument("--ext", help="Force a file extension for stdin (e.g. .py).")
    p_slim.add_argument("--keep-comments", action="store_true", help="Do not strip comments.")
    p_slim.add_argument("-i", "--in-place", action="store_true", help="Rewrite files in place.")
    p_slim.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")
    p_slim.set_defaults(func=cmd_slim)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
