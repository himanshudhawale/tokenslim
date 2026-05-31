from tokenslim.integrate import auto_slim, slim_messages


def test_slim_messages_reduces_and_preserves_structure():
    msgs = [
        {"role": "system", "content": "You are a helpful assistant." + "\n" * 40},
        {"role": "user", "content": "Question one" + "   \n" * 20 + "Question two"},
    ]
    slimmed, savings = slim_messages(msgs)
    assert len(slimmed) == 2
    assert slimmed[0]["role"] == "system"
    assert savings.tokens_saved > 0
    assert savings.percent_saved > 0
    assert savings.cost_saved >= 0


def test_slim_messages_leaves_non_string_content_untouched():
    msgs = [
        {"role": "user", "content": [{"type": "image_url", "url": "x"}]},
        {"role": "assistant", "content": "ok   \n\n\n"},
    ]
    slimmed, savings = slim_messages(msgs)
    assert slimmed[0]["content"] == [{"type": "image_url", "url": "x"}]
    assert savings.messages_changed >= 0


def test_auto_slim_wraps_and_slims_messages():
    captured = {}

    def fake_create(*, messages, model="gpt-4o"):
        captured["messages"] = messages
        return "ok"

    wrapped = auto_slim(fake_create)
    result = wrapped(messages=[{"role": "user", "content": "hi   \n\n\n\n"}])
    assert result == "ok"
    # The content passed through should be slimmed (trailing blank lines gone).
    assert captured["messages"][0]["content"].count("\n") < 3


def test_auto_slim_passes_through_without_messages():
    def fake(**kwargs):
        return kwargs

    wrapped = auto_slim(fake)
    out = wrapped(model="gpt-4o")
    assert out == {"model": "gpt-4o"}
