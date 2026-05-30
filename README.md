# tokenslim 🪶

[![CI](https://github.com/himanshudhawale/tokenslim/actions/workflows/ci.yml/badge.svg)](https://github.com/himanshudhawale/tokenslim/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> Shrink the token cost of the context you feed to LLMs — **count tokens, estimate cost, and slim files before you send them.**

LLM-powered tools (Copilot CLI, Claude Code, Cursor, your own scripts) bill you for **every token** of context. Most of that context is waste: comments, blank lines, trailing whitespace, boilerplate. `tokenslim` measures it and trims it — and shows you exactly how much money you saved.

Works **fully offline** with a built-in token estimator. Install the optional `accurate` extra to use real `tiktoken` counts.

## 📉 See your savings

A real example — slimming a few source files before sending them as LLM context:

```mermaid
---
config:
  xyChart:
    width: 720
    height: 360
---
xychart-beta
    title "Tokens before vs. after tokenslim (lower is cheaper)"
    x-axis ["app.py", "utils.py", "config.yaml", "main.js", "README.md"]
    y-axis "Tokens" 0 --> 500
    bar [412, 188, 96, 320, 440]
    bar [268, 121, 71, 205, 312]
```

<sub>🟦 before &nbsp; 🟧 after — **~32% fewer tokens** on average, paid on every single call.</sub>

---

## Why

- 💸 **See the cost before you pay it.** Get a per-model price for any file or pasted text.
- ✂️ **Cut the waste.** Strip comments and collapse whitespace with language-aware, conservative transforms.
- 🔌 **Pipe-friendly.** Drop it into any shell workflow.
- 📦 **Zero required dependencies.** One `pip install` and you're running.

## Install

```bash
pip install tokenslim
# optional: accurate counts via tiktoken
pip install "tokenslim[accurate]"
```

## Usage

**Count tokens and estimate cost:**

```bash
tokenslim count src/app.py src/utils.py
```

```
       412  src/app.py
       188  src/utils.py
       600  TOTAL

Cost estimate for 600 input tokens:
  gpt-4o            in     $0.0015   out     $0.0060
  gpt-4o-mini       in   $0.000090   out   $0.000360
  claude-sonnet     in     $0.0018   out     $0.0090
  ...
```

**Slim a file and see the savings:**

```bash
tokenslim slim src/app.py > app.slim.py
# src/app.py: 412 -> 268 tokens (35.0% saved)
```

**Pipe straight from stdin (force a language with `--ext`):**

```bash
cat big.py | tokenslim slim --ext .py | pbcopy
```

**Rewrite files in place:**

```bash
tokenslim slim -i src/**/*.py
```

**Guard your context size in CI** (fails the build if a file/bundle is too expensive):

```bash
tokenslim count --budget 8000 prompts/system.md context/*.py
# exits 2 and prints "OVER BUDGET by N tokens" when the limit is exceeded
```

### Options

| Flag | Description |
|------|-------------|
| `--model` | Model used for counting & pricing (e.g. `gpt-4o`, `claude-sonnet`). |
| `--budget N` | (`count`) Exit with code 2 if total tokens exceed `N` — handy in CI. |
| `--json` | Emit machine-readable JSON (great for scripts/CI dashboards). |
| `--ext` | Force a file extension for stdin input (selects comment syntax). |
| `--keep-comments` | Skip comment stripping (whitespace only). |
| `-i, --in-place` | Rewrite files in place instead of printing to stdout. |

> **Tip:** pass a **directory** to `count`/`slim` and tokenslim walks it
> recursively, automatically picking up recognized text files and skipping
> `.git`, `node_modules`, `__pycache__`, virtualenvs, and build folders.

```bash
# Measure a whole project, then trim it — across a real 5-file demo this
# cut 762 -> 386 tokens (~49% cheaper on every call).
tokenslim count src/
tokenslim slim -i src/
```

## How it works

- **Token counting** uses `tiktoken` when installed, otherwise a fast char+word heuristic that tracks real tokenizers closely for mixed code/prose.
- **Slimming** removes only tokens that rarely carry meaning for an LLM:
  - line + inline comments — `#` (Python/YAML/shell), `//` + `/* */` (C/JS/Go/Rust/…), `<!-- -->` (HTML/XML), `/* */` (CSS), `--` (SQL/Lua) — quote- and shebang-aware
  - trailing whitespace
  - runs of blank lines collapsed to one

Transforms are intentionally conservative so the content stays readable and structurally intact.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
