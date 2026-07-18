"""Backward-compatible wrappers — prefer app.generation.llm."""

from app.generation.llm import call_llm as call_ollama
from app.generation.llm import llm_status as ollama_status

__all__ = ["call_ollama", "ollama_status"]
