"""LLM provider interface."""

from __future__ import annotations

from typing import Protocol

from ..types import LLMRequest, LLMResult


class LLMProvider(Protocol):
    name: str

    def generate(self, request: LLMRequest) -> LLMResult:
        ...
