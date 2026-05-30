"""Command-line interface for tokenslim."""

from __future__ import annotations

import argparse
import os
import sys
from typing import List, Sequence

from . import __version__
from .slim import slim_text
from .tokens import DEFAULT_MODEL, MODELS, cost_table, count_tokens, estimate_cost


def _read_inputs(paths: Sequence[str]) -> list[tuple[str, str]]:
    """Return a list of ``(label, text)`` from files or stdin.

    If *paths* is empty, read from stdin and label it ``"<stdin>"``.
    """
    if not paths:
        data = sys.stdin.read()
        return [("<stdin>", data)]

    items: list[tuple[str, str]] = []
    for path in paths:
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

    grand_total = 0
    for label, text in items:
        tokens = count_tokens(text, args.model)
        grand_total += tokens
        print(f"{tokens:>10,}  {label}")

    if len(items) > 1:
        print(f"{grand_total:>10,}  TOTAL")

    print()
    print(f"Cost estimate for {grand_total:,} input tokens:")
    for est in cost_table(grand_total):
        print(f"  {est.model:<16} in {_fmt_cost(est.input_cost):>12}   out {_fmt_cost(est.output_cost):>12}")
    return 0


def cmd_slim(args: argparse.Namespace) -> int:
    items = _read_inputs(args.paths)
    if not items:
        print("tokenslim: no input", file=sys.stderr)
        return 1

    total_before = 0
    total_after = 0
    writing_stdout = not args.in_place and len(items) == 1

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

        if args.in_place and label != "<stdin>":
            with open(label, "w", encoding="utf-8") as fh:
                fh.write(res.text)
        elif writing_stdout:
            sys.stdout.write(res.text)

        if args.in_place or not writing_stdout:
            print(
                f"{label}: {res.original_tokens:,} -> {res.slim_tokens:,} tokens "
                f"({res.percent_saved:.1f}% saved)",
                file=sys.stderr,
            )

    saved = total_before - total_after
    pct = (saved / total_before * 100.0) if total_before else 0.0
    in_saved = estimate_cost(saved, args.model)
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
    p_count.set_defaults(func=cmd_count)

    p_slim = sub.add_parser("slim", help="Slim text/code and report tokens saved.")
    p_slim.add_argument("paths", nargs="*", help="Files to slim (default: stdin).")
    p_slim.add_argument("--model", **common_model)
    p_slim.add_argument("--ext", help="Force a file extension for stdin (e.g. .py).")
    p_slim.add_argument("--keep-comments", action="store_true", help="Do not strip comments.")
    p_slim.add_argument("-i", "--in-place", action="store_true", help="Rewrite files in place.")
    p_slim.set_defaults(func=cmd_slim)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
