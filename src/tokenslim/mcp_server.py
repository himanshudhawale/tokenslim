"""A dependency-free MCP (Model Context Protocol) server for tokenslim.

This exposes tokenslim as tools that any MCP-compatible agent - Claude Desktop,
Claude Code CLI, Cursor, VS Code, Windsurf, etc. - can discover and call
automatically. It speaks JSON-RPC 2.0 over newline-delimited stdio (the MCP
stdio transport), implemented from scratch so tokenslim keeps its zero-runtime-
dependency promise and the protocol logic stays fully unit-testable offline.

Add to Claude Desktop / Claude Code CLI config::

    {
      "mcpServers": {
        "tokenslim": { "command": "tokenslim", "args": ["mcp"] }
      }
    }
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List, Optional

from . import __version__
from .integrate import slim_messages
from .slim import slim_text
from .tokens import DEFAULT_MODEL, MODELS, count_tokens, estimate_cost

PROTOCOL_VERSION = "2024-11-05"
SERVER_INFO = {"name": "tokenslim", "version": __version__}

_MODEL_SCHEMA = {
    "type": "string",
    "enum": sorted(MODELS),
    "default": DEFAULT_MODEL,
    "description": "Model used for token counting / pricing.",
}

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "count_tokens",
        "description": "Count the tokens in a piece of text for a given model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to count."},
                "model": _MODEL_SCHEMA,
            },
            "required": ["text"],
        },
    },
    {
        "name": "estimate_cost",
        "description": "Estimate the USD cost of a token count (or text) for a model.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to price (alternative to tokens)."},
                "tokens": {"type": "integer", "description": "Token count to price."},
                "model": _MODEL_SCHEMA,
                "as_output": {
                    "type": "boolean",
                    "default": False,
                    "description": "Use output pricing instead of input pricing.",
                },
            },
        },
    },
    {
        "name": "slim_text",
        "description": "Slim text/code (strip comments + redundant whitespace) and report tokens saved before sending it to an LLM.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text/code to slim."},
                "ext": {"type": "string", "description": "File extension for comment syntax, e.g. '.py'."},
                "strip_comments": {"type": "boolean", "default": True},
                "model": _MODEL_SCHEMA,
            },
            "required": ["text"],
        },
    },
    {
        "name": "slim_messages",
        "description": "Slim a whole chat 'messages' array (role/content dicts) and report total tokens saved.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "messages": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "List of {role, content} chat messages.",
                },
                "model": _MODEL_SCHEMA,
            },
            "required": ["messages"],
        },
    },
]

_TOOL_NAMES = {t["name"] for t in TOOLS}


# --- JSON-RPC helpers -------------------------------------------------------
def _result(req_id: Any, result: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def _tool_result(payload: Dict[str, Any], is_error: bool = False) -> Dict[str, Any]:
    return {
        "content": [{"type": "text", "text": json.dumps(payload, indent=2)}],
        "isError": is_error,
    }


# --- Tool dispatch ----------------------------------------------------------
def call_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Run a tool by name. Tool-level failures are returned as isError results."""
    args = arguments or {}
    try:
        if name == "count_tokens":
            model = args.get("model", DEFAULT_MODEL)
            tokens = count_tokens(args["text"], model)
            return _tool_result({"tokens": tokens, "model": model})

        if name == "estimate_cost":
            model = args.get("model", DEFAULT_MODEL)
            if "tokens" in args and args["tokens"] is not None:
                tokens = int(args["tokens"])
            else:
                tokens = count_tokens(args.get("text", ""), model)
            cost = estimate_cost(tokens, model, as_output=bool(args.get("as_output", False)))
            return _tool_result(
                {"tokens": tokens, "model": model, "cost_usd": round(cost, 8),
                 "as_output": bool(args.get("as_output", False))}
            )

        if name == "slim_text":
            model = args.get("model", DEFAULT_MODEL)
            res = slim_text(
                args["text"],
                ext=args.get("ext"),
                strip_comments=bool(args.get("strip_comments", True)),
                model=model,
            )
            return _tool_result(
                {
                    "slim_text": res.text,
                    "original_tokens": res.original_tokens,
                    "slim_tokens": res.slim_tokens,
                    "tokens_saved": res.tokens_saved,
                    "percent_saved": round(res.percent_saved, 2),
                    "cost_saved_usd": round(estimate_cost(res.tokens_saved, model), 8),
                    "model": model,
                }
            )

        if name == "slim_messages":
            model = args.get("model", DEFAULT_MODEL)
            messages = args["messages"]
            slimmed, savings = slim_messages(messages, model=model)
            return _tool_result(
                {
                    "messages": slimmed,
                    "original_tokens": savings.original_tokens,
                    "slim_tokens": savings.slim_tokens,
                    "tokens_saved": savings.tokens_saved,
                    "percent_saved": round(savings.percent_saved, 2),
                    "cost_saved_usd": round(savings.cost_saved, 8),
                    "messages_changed": savings.messages_changed,
                    "model": model,
                }
            )

        return _tool_result({"error": f"Unknown tool: {name}"}, is_error=True)
    except KeyError as exc:
        return _tool_result({"error": f"Missing required argument: {exc}"}, is_error=True)
    except Exception as exc:  # noqa: BLE001 - surface any tool failure to the agent
        return _tool_result({"error": str(exc)}, is_error=True)


# --- Protocol handling ------------------------------------------------------
def handle_message(msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Handle one JSON-RPC message; return a response dict, or None for notifications."""
    method = msg.get("method")
    req_id = msg.get("id")

    if method is None:
        return None

    if method == "initialize":
        requested = (msg.get("params") or {}).get("protocolVersion")
        return _result(
            req_id,
            {
                "protocolVersion": requested or PROTOCOL_VERSION,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": SERVER_INFO,
            },
        )

    if method.startswith("notifications/"):
        return None

    if method == "ping":
        return _result(req_id, {})

    if method == "tools/list":
        return _result(req_id, {"tools": TOOLS})

    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name", "")
        if name not in _TOOL_NAMES:
            return _result(req_id, _tool_result({"error": f"Unknown tool: {name}"}, is_error=True))
        return _result(req_id, call_tool(name, params.get("arguments") or {}))

    if req_id is None:
        return None
    return _error(req_id, -32601, f"Method not found: {method}")


def serve(stdin=None, stdout=None) -> int:
    """Run the stdio server loop until stdin closes."""
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle_message(msg)
        if response is not None:
            stdout.write(json.dumps(response) + "\n")
            stdout.flush()
    return 0


def main(argv: Optional[List[str]] = None) -> int:  # pragma: no cover - thin wrapper
    return serve()


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
