"""Stage-based provider routing with fallback."""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from ..config import parse_route
from ..models import log_llm_call
from .providers.anthropic_provider import AnthropicProvider
from .providers.gemini_provider import GeminiProvider
from .providers.openai_provider import OpenAIProvider
from .types import LLMRequest, LLMResult, ProviderError


class LLMRouter:
    def __init__(
        self,
        config: Dict[str, Any],
        conn,
        models_reference: Dict[str, Any] | None = None,
        providers: Mapping[str, Any] | None = None,
    ) -> None:
        self.config = config
        self.conn = conn
        self.models_reference = models_reference or {}
        self.providers = dict(providers or self._default_providers())

    def _default_providers(self) -> Dict[str, Any]:
        available: Dict[str, Any] = {}
        for provider_cls in (OpenAIProvider, AnthropicProvider, GeminiProvider):
            try:
                provider = provider_cls()
            except Exception:
                continue
            available[provider.name] = provider
        return available

    def _routes_for_stage(self, stage: str) -> list[str]:
        from_models = self.models_reference.get("routing", {}).get(stage)
        if isinstance(from_models, list) and from_models:
            return [str(r) for r in from_models]
        cfg_routes = self.config.get("routing", {}).get(stage, [])
        return [str(r) for r in cfg_routes]

    def _estimate_cost(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
        key = f"{provider}:{model}"
        pricing = self.config.get("pricing", {}).get(key)
        if not pricing:
            return 0.0
        in_price = float(pricing.get("input_per_1k", 0.0))
        out_price = float(pricing.get("output_per_1k", 0.0))
        return ((tokens_in / 1000.0) * in_price) + ((tokens_out / 1000.0) * out_price)

    def generate(self, stage: str, prompt: str, system: str, meta: Dict[str, Any] | None = None) -> LLMResult:
        llm_cfg = self.config.get("llm", {})
        temperature = float(llm_cfg.get("temperature", 0.4))
        max_tokens = int(llm_cfg.get("max_tokens", 700))
        timeout_seconds = int(llm_cfg.get("timeout_seconds", 30))

        routes = self._routes_for_stage(stage)
        if not routes:
            raise ProviderError(f"No routes configured for stage '{stage}'")

        errors: list[str] = []
        for route in routes:
            provider_name, model = parse_route(route)
            provider = self.providers.get(provider_name)
            if not provider:
                errors.append(f"{route}: provider not available")
                continue

            try:
                result = provider.generate(
                    LLMRequest(
                        stage=stage,
                        prompt=prompt,
                        system=system,
                        model=model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        timeout_seconds=timeout_seconds,
                        meta=meta or {},
                    )
                )
                cost_usd = self._estimate_cost(
                    provider=result.provider,
                    model=result.model,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                )
                log_llm_call(
                    self.conn,
                    stage=stage,
                    provider=result.provider,
                    model=result.model,
                    tokens_in=result.tokens_in,
                    tokens_out=result.tokens_out,
                    cost_usd=cost_usd,
                    latency_ms=result.latency_ms,
                    meta=meta,
                )
                return result
            except Exception as exc:
                errors.append(f"{route}: {exc}")

        raise ProviderError("All provider routes failed: " + " | ".join(errors))
