"""AI model client adapters.

Provider is selected by AI_PROVIDER. Supported values:
- anthropic/claude: ANTHROPIC_API_KEY
- openai: OPENAI_API_KEY
- deepseek: DEEPSEEK_API_KEY
- gemini: GEMINI_API_KEY
- doubao: DOUBAO_API_KEY
- qianwen/tongyi: QIANWEN_API_KEY or DASHSCOPE_API_KEY
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

DEFAULT_TIMEOUT = 30
DEFAULT_MAX_TOKENS = 1024

PROVIDER_DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "claude": "claude-sonnet-4-20250514",
    "openai": "gpt-4.1-mini",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-1.5-flash",
    "doubao": "doubao-seed-1-6-250615",
    "qianwen": "qwen-plus",
    "tongyi": "qwen-plus",
}

OPENAI_COMPATIBLE_BASE_URLS = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "deepseek": "https://api.deepseek.com/chat/completions",
    "doubao": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
    "qianwen": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
    "tongyi": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
}


def _provider() -> str:
    return os.environ.get("AI_PROVIDER", "anthropic").strip().lower()


def _model(provider: str) -> str:
    return os.environ.get("AI_MODEL", PROVIDER_DEFAULT_MODELS.get(provider, "gpt-4.1-mini"))


def _api_key(provider: str) -> str:
    env_names = {
        "anthropic": ["ANTHROPIC_API_KEY"],
        "claude": ["ANTHROPIC_API_KEY"],
        "openai": ["OPENAI_API_KEY"],
        "deepseek": ["DEEPSEEK_API_KEY"],
        "gemini": ["GEMINI_API_KEY"],
        "doubao": ["DOUBAO_API_KEY"],
        "qianwen": ["QIANWEN_API_KEY", "DASHSCOPE_API_KEY"],
        "tongyi": ["QIANWEN_API_KEY", "DASHSCOPE_API_KEY"],
    }.get(provider, [])
    for name in env_names:
        value = os.environ.get(name)
        if value:
            return value
    raise ValueError(f"Missing API key for AI_PROVIDER={provider}")


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"AI API HTTP {e.code}: {detail[:300]}") from e
    except urllib.error.URLError as e:
        raise ConnectionError(f"AI API connection failed: {e}") from e


def _call_anthropic(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> str:
    try:
        from anthropic import APIError, APITimeoutError, Anthropic, RateLimitError
    except ImportError as e:
        raise RuntimeError("anthropic package is required for AI_PROVIDER=anthropic") from e

    client = Anthropic(api_key=_api_key("anthropic"), timeout=DEFAULT_TIMEOUT)
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
    except RateLimitError as e:
        raise RuntimeError(f"API rate limited: {e}") from e
    except APITimeoutError as e:
        raise TimeoutError(f"API timeout after {DEFAULT_TIMEOUT}s") from e
    except APIError as e:
        raise RuntimeError(f"API error: {e}") from e

    text = "".join(block.text for block in response.content if block.type == "text")
    if not text:
        raise RuntimeError("AI API returned empty content")
    return text


def _call_openai_compatible(
    provider: str,
    system_prompt: str,
    user_prompt: str,
    model: str,
    max_tokens: int,
) -> str:
    url = os.environ.get("AI_BASE_URL", OPENAI_COMPATIBLE_BASE_URLS[provider])
    data = _post_json(
        url,
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2,
        },
        {
            "Authorization": f"Bearer {_api_key(provider)}",
            "Content-Type": "application/json",
        },
    )
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError("AI API returned empty content")
    return content


def _call_gemini(system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> str:
    url = os.environ.get(
        "AI_BASE_URL",
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={_api_key('gemini')}",
    )
    data = _post_json(
        url,
        {
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.2},
        },
        {"Content-Type": "application/json"},
    )
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    content = "".join(part.get("text", "") for part in parts)
    if not content:
        raise RuntimeError("AI API returned empty content")
    return content


def call_ai_model(system_prompt: str, user_prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    provider = _provider()
    model = _model(provider)
    if provider in {"anthropic", "claude"}:
        return _call_anthropic(system_prompt, user_prompt, model, max_tokens)
    if provider == "gemini":
        return _call_gemini(system_prompt, user_prompt, model, max_tokens)
    if provider in OPENAI_COMPATIBLE_BASE_URLS:
        return _call_openai_compatible(provider, system_prompt, user_prompt, model, max_tokens)
    raise ValueError(f"Unsupported AI_PROVIDER={provider}")


def call_claude(system_prompt: str, user_prompt: str, model: str | None = None, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
    """Backward-compatible Claude entry point used by older code."""
    selected_model = model or _model("anthropic")
    return _call_anthropic(system_prompt, user_prompt, selected_model, max_tokens)
