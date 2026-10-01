from __future__ import annotations

import pytest

from app.services import ai


def _provider(code: str) -> ai.Provider:
    return next(provider for provider in ai.PROVIDERS if provider.code == code)


def test_extract_usage_openai_dialect() -> None:
    provider = _provider("openai")
    assert ai._extract_usage(provider, {"usage": {"prompt_tokens": 10, "completion_tokens": 5}}) == {
        "prompt_tokens": 10,
        "completion_tokens": 5,
    }
    assert ai._extract_usage(provider, {}) == {"prompt_tokens": 0, "completion_tokens": 0}


def test_extract_usage_anthropic_dialect() -> None:
    provider = _provider("anthropic")
    assert ai._extract_usage(provider, {"usage": {"input_tokens": 7, "output_tokens": 3}}) == {
        "prompt_tokens": 7,
        "completion_tokens": 3,
    }


def test_accumulate_stream_usage_openai() -> None:
    out: dict = {}
    ai._accumulate_stream_usage(_provider("openai"), {"usage": {"prompt_tokens": 2, "completion_tokens": 9}}, out)
    assert out == {"prompt_tokens": 2, "completion_tokens": 9}


def test_accumulate_stream_usage_anthropic() -> None:
    out: dict = {}
    ai._accumulate_stream_usage(_provider("anthropic"), {"type": "message_start", "message": {"usage": {"input_tokens": 4}}}, out)
    ai._accumulate_stream_usage(_provider("anthropic"), {"type": "message_delta", "usage": {"output_tokens": 6}}, out)
    assert out == {"prompt_tokens": 4, "completion_tokens": 6}


def test_estimate_cost_uses_model_pricing() -> None:
    from app.services import ai_pricing

    # 1000 input + 1000 output on gpt-4o-mini = 0.00015 + 0.0006.
    assert ai_pricing.estimate_cost_usd("gpt-4o-mini", 1000, 1000) == pytest.approx(0.00075)
    # Longest key wins: a dated gpt-4o name still matches gpt-4o, not gpt-4o-mini.
    assert ai_pricing.estimate_cost_usd("gpt-4o-2024-08-06", 1000, 0) == pytest.approx(0.0025)
    # Unknown models cost 0 rather than guessing.
    assert ai_pricing.estimate_cost_usd("mystery-model", 1000, 1000) == 0.0
    assert ai_pricing.estimate_cost_usd(None, 100, 100) == 0.0
