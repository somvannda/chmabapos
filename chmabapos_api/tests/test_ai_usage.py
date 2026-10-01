from __future__ import annotations

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
