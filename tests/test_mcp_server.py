import json

from tokenslim.mcp_server import call_tool, handle_message


def test_initialize_returns_server_info():
    resp = handle_message(
        {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05"}}
    )
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "tokenslim"
    assert resp["result"]["protocolVersion"] == "2024-11-05"
    assert "tools" in resp["result"]["capabilities"]


def test_initialize_defaults_protocol_when_absent():
    resp = handle_message({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp["result"]["protocolVersion"]


def test_notifications_return_none():
    assert handle_message({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_ping():
    resp = handle_message({"jsonrpc": "2.0", "id": 5, "method": "ping"})
    assert resp["result"] == {}


def test_tools_list_has_all_tools():
    resp = handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    names = {t["name"] for t in resp["result"]["tools"]}
    assert names == {"count_tokens", "estimate_cost", "slim_text", "slim_messages"}
    for tool in resp["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_unknown_method_returns_error():
    resp = handle_message({"jsonrpc": "2.0", "id": 9, "method": "does/not/exist"})
    assert resp["error"]["code"] == -32601


def test_tools_call_count_tokens():
    resp = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "count_tokens", "arguments": {"text": "hello world"}},
        }
    )
    assert resp["result"]["isError"] is False
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["tokens"] >= 1


def test_tools_call_slim_text_saves_tokens():
    payload = json.loads(
        call_tool("slim_text", {"text": "x = 1  # comment\n\n\n\n", "ext": ".py"})["content"][0]["text"]
    )
    assert payload["tokens_saved"] > 0
    assert "# comment" not in payload["slim_text"]


def test_tools_call_estimate_cost():
    payload = json.loads(
        call_tool("estimate_cost", {"tokens": 1_000_000, "model": "gpt-4o"})["content"][0]["text"]
    )
    assert payload["cost_usd"] == 2.5


def test_tools_call_slim_messages():
    msgs = [
        {"role": "system", "content": "You are helpful." + "\n" * 30},
        {"role": "user", "content": "Hello there" + "\n" * 30},
    ]
    payload = json.loads(
        call_tool("slim_messages", {"messages": msgs})["content"][0]["text"]
    )
    assert payload["tokens_saved"] > 0
    assert len(payload["messages"]) == 2


def test_unknown_tool_is_error():
    resp = handle_message(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "nope", "arguments": {}},
        }
    )
    assert resp["result"]["isError"] is True


def test_missing_required_arg_is_error():
    result = call_tool("count_tokens", {})
    assert result["isError"] is True
