"""Anthropic Messages API provider."""

from __future__ import annotations

import os
import time
from typing import Any, Dict

import requests

from ..types import LLMRequest, LLMResult, ProviderError


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY")

    def generate(self, request: LLMRequest) -> LLMResult:
        if not self._api_key:
            raise ProviderError("ANTHROPIC_API_KEY missing")

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": request.model,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
        }

        start = time.perf_counter()
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=request.timeout_seconds)
            res.raise_for_status()
            data = res.json()
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        content = data.get("content", [])
        text = ""
        if content and isinstance(content, list):
            text = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and item.get("type") == "text"
            )

        usage = data.get("usage", {})
        tokens_in = int(usage.get("input_tokens", 0) or 0)
        tokens_out = int(usage.get("output_tokens", 0) or 0)

        return LLMResult(
            text=text.strip(),
            provider=self.name,
            model=request.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            raw={"id": data.get("id")},
        )
