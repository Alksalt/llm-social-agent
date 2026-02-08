"""OpenAI Responses API provider."""

from __future__ import annotations

import os
import time
from typing import Any, Dict

from ..types import LLMRequest, LLMResult, ProviderError


class OpenAIProvider:
    name = "openai"

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        self._client = None
        if api_key:
            try:
                from openai import OpenAI
            except Exception as exc:  # pragma: no cover - depends on installed package
                raise ProviderError(f"openai package unavailable: {exc}") from exc
            self._client = OpenAI(api_key=api_key)

    def generate(self, request: LLMRequest) -> LLMResult:
        if self._client is None:
            raise ProviderError("OPENAI_API_KEY missing")

        start = time.perf_counter()
        try:
            response = self._client.responses.create(
                model=request.model,
                temperature=request.temperature,
                max_output_tokens=request.max_tokens,
                input=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.prompt},
                ],
                timeout=request.timeout_seconds,
            )
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        text = getattr(response, "output_text", "") or ""
        usage = getattr(response, "usage", None)

        tokens_in = int(getattr(usage, "input_tokens", 0) or 0)
        tokens_out = int(getattr(usage, "output_tokens", 0) or 0)

        return LLMResult(
            text=text.strip(),
            provider=self.name,
            model=request.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            raw={"id": getattr(response, "id", None)},
        )
