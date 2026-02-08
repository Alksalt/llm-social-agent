"""Shared LLM data structures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class LLMRequest:
    stage: str
    prompt: str
    system: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: int
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: int = 0
    raw: Dict[str, Any] = field(default_factory=dict)


class ProviderError(RuntimeError):
    """Provider failed to return a valid generation."""
