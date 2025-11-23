
"""
LLM client wrapper.

This module provides a small, clean interface for the rest of the codebase
to talk to an LLM (currently OpenAI, but designed so we can swap providers).

Key ideas:
- The rest of the app should NOT directly import or depend on the OpenAI SDK.
- All provider-specific logic lives here.
"""
from typing import Optional
import os

from openai import OpenAI, BadRequestError
from .config_loader import get_config
from ..tools.data_tools import log_cost_entry

_config = get_config()
_llm_cfg = _config.get("llm", {})

_PROVIDER = _llm_cfg.get("provider", "openai")
_MODEL = _llm_cfg.get("model", "gpt-5-mini")
_TEMPERATURE = float(_llm_cfg.get("temperature", 0.7))

if _PROVIDER != "openai":
    raise ValueError(f"Unsupported LLM provider in config, {_PROVIDER}")

_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not _OPENAI_API_KEY:
    raise EnvironmentError(
        "OPENAI_API_KEY is not set. "
        "Make sure you have a .env file with OPENAI_API_KEY=... and that it is loaded."
    )

_openai_client = OpenAI(api_key=_OPENAI_API_KEY)

def _extract_output_text(response) -> str:
    """
    Best-effort extraction of text from Responses API.
    Uses response.output_text if available, otherwise falls back
    to manually walking response.output.
    """
    reply_text = getattr(response, "output_text", None)
    if reply_text:
        return reply_text.strip()

    chunks = []
    for out in getattr(response, "output", []) or []:
        content = getattr(out, "content", None) or []
        for c in content:
            # adapt to your actual response shape; this mirrors your old logic
            text = getattr(c, "text", None)
            if text:
                # sometimes text might be a plain string or have .value, adjust if needed
                if hasattr(text, "value"):
                    chunks.append(text.value)
                else:
                    chunks.append(str(text))
    return "\n".join(chunks).strip()

def generate_text(prompt: str,
                  system_prompt: Optional[str] = None,
                  model: Optional[str] = None,
                  temperature: Optional[str] = None) -> str:
    """
    Call the LLM to generate plain text.

    - Uses default model/temperature from config if not provided.
    - Logs token usage and estimated cost in the database.
    """
    model_name = model or _MODEL
    temp_value = float(temperature) if temperature is not None else _TEMPERATURE

    # Build input for Responses API
    if system_prompt:
        input_payload = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ]
    else:
        input_payload = [
            {"role": "user", "content": prompt},
        ]

    try:
        response = _openai_client.responses.create(
            model=model_name,
            input=input_payload,
            temperature=temp_value,
        )
    except BadRequestError as e:
        # Some models/endpoints do not accept temperature; retry without it.
        if getattr(e, "param", None) == "temperature":
            response = _openai_client.responses.create(
                model=model_name,
                input=input_payload,
            )
        else:
            raise

    # --- Extract text ---
    text = _extract_output_text(response)
    
    # --- Usage & cost logging ---
    usage = getattr(response, "usage", None)
    if usage is not None:
        tokens_in = getattr(usage, "input_tokens", 0) or 0
        tokens_out = getattr(usage, "output_tokens", 0) or 0

        pricing_cfg = _config.get("pricing", {})
        model_pricing = pricing_cfg.get(model_name, {})

        input_price = float(model_pricing.get("input_per_1k", 0.0))
        output_price = float(model_pricing.get("output_per_1k", 0.0))

        in_k = tokens_in / 1000.0
        out_k = tokens_out / 1000.0
        estimated_cost = in_k * input_price + out_k * output_price

        log_cost_entry(
            model=model_name,
            tokens_in=int(tokens_in),
            tokens_out=int(tokens_out),
            estimated_cost=estimated_cost,
        )

    return text
