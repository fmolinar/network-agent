from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class LLMConfig:
    provider: str = "mock"
    model: str = "mock-critic"
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: int = 20

    @classmethod
    def from_env(cls) -> "LLMConfig":
        provider = os.getenv("NETWORK_AGENT_LLM_PROVIDER", "mock").strip().lower()
        model = os.getenv("NETWORK_AGENT_LLM_MODEL", "mock-critic").strip()
        base_url = os.getenv("NETWORK_AGENT_LLM_BASE_URL")

        api_key = os.getenv("NETWORK_AGENT_LLM_API_KEY")
        if not api_key:
            if provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
            elif provider == "anthropic":
                api_key = os.getenv("ANTHROPIC_API_KEY")

        return cls(provider=provider, model=model, base_url=base_url, api_key=api_key)


class LLMCritic:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config

    def critique(self, diagnosis_payload: dict[str, Any]) -> dict[str, Any]:
        provider = self.config.provider.lower()
        if provider == "mock":
            return self._mock_critique(diagnosis_payload)
        if provider == "openai":
            return self._openai_critique(diagnosis_payload)
        if provider == "anthropic":
            return self._anthropic_critique(diagnosis_payload)
        if provider == "ollama":
            return self._ollama_critique(diagnosis_payload)
        return {
            "verdict": "error",
            "confidence": 0.0,
            "notes": [f"unsupported provider: {provider}"],
        }

    def _build_prompt(self, payload: dict[str, Any]) -> str:
        return (
            "You are a network diagnostics critic. Review the diagnosis for consistency and safety. "
            "Return strict JSON with keys: verdict, confidence, notes, suggested_evidence. "
            "verdict must be one of: accept, caution, reject.\n\n"
            f"Input:\n{json.dumps(payload, indent=2, sort_keys=True)}"
        )

    def _post_json(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url=url, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                text = resp.read().decode("utf-8")
                return json.loads(text)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else str(exc)
            return {"error": f"HTTP {exc.code}", "detail": detail}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    def _parse_json_object(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if not text:
            return {}
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start : end + 1]
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict):
                return parsed
            return {"verdict": "caution", "confidence": 0.4, "notes": ["LLM returned non-object JSON"]}
        except Exception:  # noqa: BLE001
            return {
                "verdict": "caution",
                "confidence": 0.4,
                "notes": ["LLM output could not be parsed as JSON"],
            }

    def _openai_critique(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.config.api_key:
            return {"verdict": "error", "confidence": 0.0, "notes": ["OPENAI_API_KEY not configured"]}
        url = self.config.base_url or "https://api.openai.com/v1/chat/completions"
        body = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "Respond only with JSON."},
                {"role": "user", "content": self._build_prompt(payload)},
            ],
        }
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        data = self._post_json(url, headers, body)
        if "error" in data:
            return {"verdict": "error", "confidence": 0.0, "notes": [data.get("error", "unknown error")]}

        try:
            content = data["choices"][0]["message"]["content"]
        except Exception:  # noqa: BLE001
            return {"verdict": "error", "confidence": 0.0, "notes": ["unexpected OpenAI response shape"]}
        return self._parse_json_object(content)

    def _anthropic_critique(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.config.api_key:
            return {"verdict": "error", "confidence": 0.0, "notes": ["ANTHROPIC_API_KEY not configured"]}
        url = self.config.base_url or "https://api.anthropic.com/v1/messages"
        body = {
            "model": self.config.model,
            "max_tokens": 500,
            "temperature": 0,
            "messages": [{"role": "user", "content": self._build_prompt(payload)}],
        }
        headers = {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        data = self._post_json(url, headers, body)
        if "error" in data:
            return {"verdict": "error", "confidence": 0.0, "notes": [data.get("error", "unknown error")]}

        try:
            content = data["content"][0]["text"]
        except Exception:  # noqa: BLE001
            return {"verdict": "error", "confidence": 0.0, "notes": ["unexpected Anthropic response shape"]}
        return self._parse_json_object(content)

    def _ollama_critique(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = self.config.base_url or "http://localhost:11434/api/chat"
        body = {
            "model": self.config.model,
            "stream": False,
            "messages": [{"role": "user", "content": self._build_prompt(payload)}],
            "format": "json",
        }
        headers = {"Content-Type": "application/json"}
        data = self._post_json(url, headers, body)
        if "error" in data:
            return {"verdict": "error", "confidence": 0.0, "notes": [data.get("error", "unknown error")]}

        try:
            content = data["message"]["content"]
        except Exception:  # noqa: BLE001
            return {"verdict": "error", "confidence": 0.0, "notes": ["unexpected Ollama response shape"]}
        return self._parse_json_object(content)

    def _mock_critique(self, payload: dict[str, Any]) -> dict[str, Any]:
        confidence = float(payload.get("diagnosis", {}).get("confidence_score", 0.0))
        if confidence >= 0.75:
            return {
                "verdict": "accept",
                "confidence": 0.9,
                "notes": ["Diagnosis is internally consistent"],
                "suggested_evidence": [],
            }
        return {
            "verdict": "caution",
            "confidence": 0.55,
            "notes": ["Low confidence diagnosis; gather additional evidence"],
            "suggested_evidence": ["routing table", "dns trace", "interface counters"],
        }
