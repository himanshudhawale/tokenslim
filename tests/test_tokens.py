import pytest

from tokenslim.tokens import count_tokens, estimate_cost, cost_table, MODELS


def test_count_empty():
    assert count_tokens("") == 0


def test_count_nonempty_positive():
    assert count_tokens("hello world this is a test") > 0


def test_count_scales_with_length():
    short = count_tokens("a short string")
    long = count_tokens("a short string " * 50)
    assert long > short


def test_estimate_cost_known_model():
    cost = estimate_cost(1_000_000, "gpt-4o")
    assert cost == pytest.approx(MODELS["gpt-4o"]["input"])


def test_estimate_cost_output_pricing():
    cost = estimate_cost(1_000_000, "gpt-4o", as_output=True)
    assert cost == pytest.approx(MODELS["gpt-4o"]["output"])


def test_estimate_cost_unknown_model():
    with pytest.raises(KeyError):
        estimate_cost(100, "no-such-model")


def test_cost_table_covers_all_models():
    table = cost_table(1000)
    assert {e.model for e in table} == set(MODELS)
    assert all(e.input_cost >= 0 for e in table)
