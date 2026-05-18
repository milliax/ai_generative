from unittest.mock import MagicMock, patch
import pytest
from shared.llm_client import call_llm, LLMError


def _fake_completion_response(content: str):
    resp = MagicMock()
    resp.choices = [MagicMock()]
    resp.choices[0].message.content = content
    return resp


def test_call_llm_uses_env_model(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-1.5-flash")
    with patch("shared.llm_client.completion") as mock_completion:
        mock_completion.return_value = _fake_completion_response("hello")
        out = call_llm([{"role": "user", "content": "hi"}])
    assert out == "hello"
    assert mock_completion.call_args.kwargs["model"] == "gemini/gemini-1.5-flash"


def test_call_llm_explicit_model_overrides_env(monkeypatch):
    monkeypatch.setenv("LLM_MODEL", "gemini/gemini-1.5-flash")
    with patch("shared.llm_client.completion") as mock_completion:
        mock_completion.return_value = _fake_completion_response("x")
        call_llm([{"role": "user", "content": "hi"}], model="gpt-4o-mini")
    assert mock_completion.call_args.kwargs["model"] == "gpt-4o-mini"


def test_call_llm_retries_on_transient_error(monkeypatch):
    monkeypatch.setattr("shared.llm_client.time.sleep", lambda _: None)  # speed up
    fail_then_pass = [Exception("rate limit"), _fake_completion_response("ok")]
    with patch("shared.llm_client.completion", side_effect=fail_then_pass) as mock_completion:
        out = call_llm([{"role": "user", "content": "hi"}], max_retries=2)
    assert out == "ok"
    assert mock_completion.call_count == 2


def test_call_llm_raises_after_max_retries(monkeypatch):
    monkeypatch.setattr("shared.llm_client.time.sleep", lambda _: None)
    with patch("shared.llm_client.completion", side_effect=Exception("boom")):
        with pytest.raises(LLMError):
            call_llm([{"role": "user", "content": "hi"}], max_retries=2)
