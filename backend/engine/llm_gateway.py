"""External & On-Premise Local LLM Gateway (Ollama & OpenAI-Compatible APIs).

Zero external dependencies: uses Python standard library urllib.request.
Falls back cleanly to offline deterministic mode whenever provider == 'builtin'
or if the configured endpoint is unreachable.
"""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from backend.models import LlmConfig


def _post_json(url: str, payload: dict[str, Any], headers: dict[str, str], timeout: int) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _extract_json_block(text: str) -> dict[str, Any]:
    """Extract first JSON object from LLM text response (handling markdown fences)."""
    cleaned = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1)
    else:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start != -1 and end > start:
            cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def test_llm_connection(cfg: LlmConfig) -> dict[str, Any]:
    """Verify reachability of configured Ollama or OpenAI-compatible LLM server."""
    if cfg.provider == "builtin":
        return {
            "ok": True,
            "provider": "builtin",
            "message": "오프라인 내장 엔진(결정론적 파서 + SSOT 규칙 생성기)이 활성화되어 있습니다.",
        }

    base = cfg.base_url.rstrip("/")
    try:
        if cfg.provider == "ollama":
            req = urllib.request.Request(f"{base}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=min(cfg.timeout_sec, 8)) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                return {
                    "ok": True,
                    "provider": "ollama",
                    "message": f"Ollama 연결 성공 ({len(models)}개 모델 감지)",
                    "available_models": models[:10],
                }

        # OpenAI-compatible (OpenAI, vLLM, LiteLLM, LM Studio)
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        data = _post_json(
            f"{base}/chat/completions",
            {
                "model": cfg.model,
                "messages": [{"role": "user", "content": "Reply with OK"}],
                "max_tokens": 8,
                "temperature": 0.0,
            },
            headers,
            timeout=min(cfg.timeout_sec, 12),
        )
        reply = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "ok": True,
            "provider": "openai_compat",
            "message": f"LLM 엔드포인트 연결 성공 (모델: {cfg.model}, 응답: {reply.strip()[:24]})",
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": cfg.provider,
            "message": f"연결 실패 ({exc.__class__.__name__}: {exc}). 오프라인 내장 엔진으로 자동 폴백됩니다.",
        }


def call_llm_json(cfg: LlmConfig, system_prompt: str, user_prompt: str) -> tuple[dict[str, Any] | None, str]:
    """Call configured external/local LLM expecting JSON output. Returns (json_dict_or_None, engine_label)."""
    if cfg.provider == "builtin":
        return None, "Offline Built-in Engine"

    base = cfg.base_url.rstrip("/")
    try:
        if cfg.provider == "ollama":
            data = _post_json(
                f"{base}/api/chat",
                {
                    "model": cfg.model,
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": cfg.temperature},
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                },
                {"Content-Type": "application/json"},
                timeout=cfg.timeout_sec,
            )
            content = data.get("message", {}).get("content", "")
            return _extract_json_block(content), f"Ollama ({cfg.model})"

        # OpenAI-compatible
        headers = {"Content-Type": "application/json"}
        if cfg.api_key:
            headers["Authorization"] = f"Bearer {cfg.api_key}"
        data = _post_json(
            f"{base}/chat/completions",
            {
                "model": cfg.model,
                "temperature": cfg.temperature,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
            headers,
            timeout=cfg.timeout_sec,
        )
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return _extract_json_block(content), f"LLM ({cfg.model})"
    except Exception:
        return None, f"Offline Fallback ({cfg.provider} unreachable)"
