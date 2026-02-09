# models.md — Model menu & routing defaults (Telegram Social Agent)

This project supports multiple LLM providers per pipeline stage (summarize → draft → check → publish).
Routing is configured in `settings.yaml` so you can swap models per stage without code changes.

## Pricing conventions
- Prices below are **USD per 1M tokens** (MTok) for **standard** API usage unless explicitly marked Batch.
- Always treat pricing as “config input”, not hard-coded logic.

---

## OpenAI (Responses API)

### Top 3 (recommended “serious” tiers)
1) **gpt-5.2-pro**  
   - Input: **$21.00 / MTok**  
   - Output: **$168.00 / MTok**

2) **gpt-5.2**  
   - Input: **$1.75 / MTok**  
   - Output: **$14.00 / MTok**

3) **gpt-5.1**  
   - Input: **$1.25 / MTok**  
   - Output: **$10.00 / MTok**

### Cheap tiers (for summaries/checks)
- **gpt-5-mini**: Input **$0.25**, Output **$2.00**
- **gpt-5-nano**: Input **$0.05**, Output **$0.40**

---

## Anthropic (Claude API)

### Top 3 (recommended “serious” tiers)
1) **claude-opus-4.6**  
   - Base input: **$5 / MTok**  
   - Output: **$25 / MTok**

2) **claude-opus-4.5**  
   - Base input: **$5 / MTok**  
   - Output: **$25 / MTok**

3) **claude-sonnet-4-5**  
   - Base input: **$3 / MTok**  
   - Output: **$15 / MTok**

### Cheap tier (for summaries/checks)
- **claude-haiku-4-5**  
  - Base input: **$1 / MTok**  
  - Output: **$5 / MTok**

> Note: Claude also has prompt caching and batch discounts; keep those optional and config-driven.

---

## Google (Gemini API)

### Top 3 (recommended “serious” tiers)
1) **gemini-3-pro-preview**  
   - Input: **$2.00 / MTok** (<= 200K prompt) | **$4.00 / MTok** (> 200K)  
   - Output: **$12.00 / MTok** (<= 200K) | **$18.00 / MTok** (> 200K)

2) **gemini-2.5-pro**  
   - Input: **$1.25 / MTok** (<= 200K) | **$2.50 / MTok** (> 200K)  
   - Output: **$10.00 / MTok** (<= 200K) | **$15.00 / MTok** (> 200K)

3) **gemini-3-flash-preview**  
   - Input: **$0.50 / MTok** (text/image/video)  
   - Output: **$3.00 / MTok** (incl. thinking tokens)

### Cheap tier (optional)
- **gemini-2.5-flash-lite**  
  - Input: **$0.10 / MTok** (text/image/video)  
  - Output: **$0.40 / MTok**

---

## Routing defaults (matches your preferences)

### Principles
- **Writer**: premium-but-not-insane (Sonnet 4.5 or GPT-5.2)
- **Summary**: cheap (Haiku 4.5 or GPT-5-mini)
- **Check**: cheapest acceptable (OpenAI nano by default), because you manually review anyway

### Suggested `settings.yaml` routing (example)
```yaml
routing:
  summarize:
    - anthropic:claude-haiku-4-5
    - openai:gpt-5-mini
    - gemini:gemini-3-flash-preview

  draft_x:
    - anthropic:claude-sonnet-4-5
    - openai:gpt-5.2
    - gemini:gemini-3-pro-preview

  draft_linkedin:
    - anthropic:claude-sonnet-4-5
    - openai:gpt-5.2
    - gemini:gemini-3-pro-preview

  draft_threads:
    - anthropic:claude-sonnet-4-5
    - openai:gpt-5.2
    - gemini:gemini-3-flash-preview

  check:
    - openai:gpt-5-nano
    - anthropic:claude-haiku-4-5
    - gemini:gemini-2.5-flash-lite
