# ai/fallback_manager.py
# ═══════════════════════════════════════════════════════════════════
# Universal LLM Fallback Manager — Arabic-First Priority
# Every LLM call in Fast Drop goes through this layer.
# Chain: Groq → HuggingFace → Gemini → OpenRouter
# ═══════════════════════════════════════════════════════════════════
import os
import time
import logging
from langsmith import traceable

logger = logging.getLogger("fastdrop.llm")

# ── Provider Client Initializations ─────────────────────────────
_groq_client = None
_openrouter_client = None
_huggingface_client = None
_gemini_configured = False


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


def _get_openrouter_client():
    global _openrouter_client
    if _openrouter_client is None:
        from openai import OpenAI
        _openrouter_client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
            default_headers={
                "HTTP-Referer": "https://fastdrop.app",
                "X-Title": "Fast Drop AI - فاست دروب",
            },
        )
    return _openrouter_client


def _get_huggingface_client():
    global _huggingface_client
    if _huggingface_client is None:
        from huggingface_hub import InferenceClient
        _huggingface_client = InferenceClient(
            api_key=os.getenv("HUGGINGFACE_API_TOKEN"),
        )
    return _huggingface_client


def _ensure_gemini():
    global _gemini_configured
    if not _gemini_configured:
        import google.generativeai as genai
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        _gemini_configured = True


# ── Model Pools ─────────────────────────────────────────────────
GROQ_ARABIC_MODELS = [
    "llama-3.3-70b-versatile",                         # ⭐ Best overall reasoning & Arabic on Groq
    "deepseek-r1-distill-llama-70b",                   # ⭐ Excellent for Arabic reasoning
    "meta-llama/llama-4-maverick-17b-128e-instruct",   # New Llama 4
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "gemma2-9b-it",
]

GROQ_FAST_MODELS = [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",      # Fastest, 14,400 req/day
    "gemma2-9b-it",
    "mixtral-8x7b-32768",
]

GEMINI_MODELS = [
    "gemini-2.5-pro",            # ⭐ Best Gemini model
    "gemini-2.5-flash",          # Fast and excellent Arabic
    "gemini-2.5-flash-lite",     # Fallback
]

HUGGINGFACE_ARABIC_MODELS = [
    "meta-llama/Llama-3.3-70B-Instruct",        # ⭐ Best Llama on HF
    "Qwen/Qwen2.5-72B-Instruct",              # ⭐ Unbeatable multilingual/Arabic
    "CohereForAI/c4ai-command-r-plus-08-2024", # ⭐ Extremely good Arabic/RAG
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "mistralai/Mistral-Small-24B-Instruct-2501",
    "google/gemma-2-27b-it",
]

OPENROUTER_ARABIC_MODELS = [
    "google/gemini-2.5-pro:free",                    # ⭐ Best OpenRouter free
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-r1:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
    "google/gemma-3-27b-it:free",
    "qwen/qwen3-32b:free",
]

RETRYABLE_ERRORS = (429, 500, 502, 503, 504)


# ═══════════════════════════════════════════════
@traceable(run_type="llm", name="Groq_Fallback_Chain")
def call_groq_with_fallback(
    messages: list,
    temperature: float = 0.1,
    max_tokens: int = 500,
    json_mode: bool = False,
    preferred_model: str = None,
    arabic_mode: bool = False,
) -> str:
    """
    Try Groq models in priority order.
    Falls through to OpenRouter if all Groq models fail.

    Args:
        messages: Chat messages [{"role": "...", "content": "..."}]
        arabic_mode: If True, uses Arabic-capable model pool
    """
    from core.rate_limiter import is_safe_to_call, increment_usage

    # Select model pool
    base_models = GROQ_ARABIC_MODELS if arabic_mode else GROQ_FAST_MODELS
    models = ([preferred_model] + base_models) if preferred_model else list(base_models)

    # Deduplicate while preserving order
    seen = set()
    models = [m for m in models if m and not (m in seen or seen.add(m))]

    client = _get_groq_client()
    last_error = None

    for model in models:
        # Pre-emptive rate limit check
        if not is_safe_to_call(model):
            logger.info(f"[Groq SKIP] {model} — rate limit approaching")
            continue

        try:
            kwargs = dict(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            increment_usage(model)
            logger.info(f"[Groq OK] model={model} arabic={arabic_mode}")
            return response.choices[0].message.content

        except Exception as e:
            status = getattr(e, "status_code", None)
            logger.warning(f"[Groq FAIL] model={model} status={status} err={e}")
            last_error = e
            if status in RETRYABLE_ERRORS:
                time.sleep(1)
                continue
            break  # Non-retryable (auth, bad request)

    # All Groq models failed → try OpenRouter (terminal step)
    logger.warning("[Groq EXHAUSTED] → OpenRouter Arabic fallback")
    return call_openrouter_fallback(
        messages, temperature, max_tokens, arabic_mode=arabic_mode
    )


# ═══════════════════════════════════════════════
@traceable(run_type="llm", name="Gemini_Fallback_Chain")
def call_gemini_with_fallback(
    prompt: str = None,
    messages: list = None,
    temperature: float = 0.1,
    json_response: bool = False,
    preferred_model: str = None,
) -> str:
    """
    Try Gemini models in priority order.
    Falls through to HuggingFace if all Gemini fail.
    """
    import google.generativeai as genai
    from core.rate_limiter import is_safe_to_call, increment_usage

    _ensure_gemini()

    # Convert messages to prompt string if needed
    if messages and not prompt:
        prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])

    models = ([preferred_model] + GEMINI_MODELS) if preferred_model else list(GEMINI_MODELS)
    seen = set()
    models = [m for m in models if m and not (m in seen or seen.add(m))]

    for model_name in models:
        if not is_safe_to_call(model_name):
            logger.info(f"[Gemini SKIP] {model_name} — rate limit approaching")
            continue

        try:
            model = genai.GenerativeModel(model_name)
            config = genai.GenerationConfig(
                temperature=temperature,
                response_mime_type="application/json" if json_response else "text/plain",
            )
            response = model.generate_content(prompt, generation_config=config)
            increment_usage(model_name)
            logger.info(f"[Gemini OK] model={model_name}")
            return response.text

        except Exception as e:
            logger.warning(f"[Gemini FAIL] model={model_name} err={e}")
            if "429" in str(e) or "quota" in str(e).lower():
                time.sleep(2)
                continue
            break

    # All Gemini models failed → try HuggingFace fallback
    logger.warning("[Gemini EXHAUSTED] → HuggingFace fallback")
    # If messages weren't provided, wrap the prompt
    if messages is None:
        messages = [{"role": "user", "content": prompt}]
        
    return call_huggingface_fallback(
        messages, temperature, 2000,
    )


# ═══════════════════════════════════════════════
@traceable(run_type="llm", name="HuggingFace_Fallback_Chain")
def call_huggingface_fallback(
    messages: list,
    temperature: float = 0.1,
    max_tokens: int = 500,
    preferred_model: str = None,
    arabic_mode: bool = False,
) -> str:
    """
    HuggingFace Inference API fallback.
    Free tier: ~1000 req/day across all models.
    Best Arabic models: Qwen2.5-72B, Command-R+, Llama-3.1-70B.
    """
    from core.rate_limiter import is_safe_to_call, increment_usage

    base_models = HUGGINGFACE_ARABIC_MODELS
    models = ([preferred_model] + base_models) if preferred_model else list(base_models)
    seen = set()
    models = [m for m in models if m and not (m in seen or seen.add(m))]

    client = _get_huggingface_client()

    for model in models:
        if not is_safe_to_call(model):
            logger.info(f"[HuggingFace SKIP] {model} — rate limit approaching")
            continue

        try:
            response = client.chat_completion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            increment_usage(model)
            logger.info(f"[HuggingFace OK] model={model} arabic={arabic_mode}")
            return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"[HuggingFace FAIL] model={model} err={e}")
            if "429" in str(e) or "rate" in str(e).lower():
                time.sleep(2)
                continue
            continue  # Try next model

    # All HuggingFace models failed → try Groq fallback
    logger.warning("[HuggingFace EXHAUSTED] → Groq Arabic fallback")
    return call_groq_with_fallback(
        messages, temperature, max_tokens, arabic_mode=arabic_mode
    )


# ═══════════════════════════════════════════════
@traceable(run_type="llm", name="OpenRouter_Fallback_Chain")
def call_openrouter_fallback(
    messages: list,
    temperature: float = 0.1,
    max_tokens: int = 500,
    preferred_model: str = None,
    arabic_mode: bool = False,
) -> str:
    """Last resort — cycles through all free OpenRouter models."""
    from core.rate_limiter import increment_usage

    base_models = OPENROUTER_ARABIC_MODELS
    models = ([preferred_model] + base_models) if preferred_model else list(base_models)
    seen = set()
    models = [m for m in models if m and not (m in seen or seen.add(m))]

    client = _get_openrouter_client()

    for model in models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            increment_usage(model)
            logger.info(f"[OpenRouter OK] model={model}")
            return response.choices[0].message.content

        except Exception as e:
            logger.warning(f"[OpenRouter FAIL] model={model} err={e}")
            time.sleep(1)
            continue

    raise RuntimeError(
        "جميع مقدمي خدمات الذكاء الاصطناعي استنفدوا — "
        "ALL providers exhausted. Check API keys and rate limits."
    )
