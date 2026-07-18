from app import config
from app.generation import llm as llm_mod


def test_llm_provider_default():
    assert config.LLM_PROVIDER
    assert config.HF_MODEL
    assert config.OLLAMA_MODEL


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setattr(config, "LLM_PROVIDER", "nope")
    with __import__("pytest").raises(llm_mod.LLMError):
        llm_mod.call_llm("hi")
