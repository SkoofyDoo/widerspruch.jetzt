from __future__ import annotations

from langchain.chat_models import init_chat_model


llm = init_chat_model(
    model_provider="Ollama",
    model = "qwen3:8b",
    temperature = 0.1
)

