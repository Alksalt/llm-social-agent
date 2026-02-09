"""Google Gemini REST provider."""

from __future__ import annotations

import os
import time

import requests

from ..types import LLMRequest, LLMResult, ProviderError


class GeminiProvider:
    name = "gemini"

    def __init__(self) -> None:
        self._api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    def generate(self, request: LLMRequest) -> LLMResult:
        if not self._api_key:
            raise ProviderError("GEMINI_API_KEY/GOOGLE_API_KEY missing")

        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{request.model}:generateContent"
            f"?key={self._api_key}"
        )
        payload = {
            "system_instruction": {"parts": [{"text": request.system}]},
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

        start = time.perf_counter()
        try:
            res = requests.post(url, json=payload, timeout=request.timeout_seconds)
            res.raise_for_status()
            data = res.json()
        except Exception as exc:
            raise ProviderError(str(exc)) from exc

        latency_ms = int((time.perf_counter() - start) * 1000)
        candidates = data.get("candidates", [])
        text = ""
        if candidates:
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))

        usage = data.get("usageMetadata", {})
        tokens_in = int(usage.get("promptTokenCount", 0) or 0)
        tokens_out = int(usage.get("candidatesTokenCount", 0) or 0)

        return LLMResult(
            text=text.strip(),
            provider=self.name,
            model=request.model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            raw={"responseId": data.get("responseId")},
        )
