from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class AgentLLMConfig:
    provider: str = "none"
    model: str = "llama3.2"
    base_url: str | None = None
    api_key: str | None = None
    timeout_seconds: int = 30

    @classmethod
    def from_env(cls) -> "AgentLLMConfig":
        provider = os.getenv("NETWORK_AGENT_AGENT_LLM_PROVIDER", "none").strip().lower()
        model = os.getenv("NETWORK_AGENT_AGENT_LLM_MODEL", "llama3.2").strip()
        base_url = os.getenv("NETWORK_AGENT_AGENT_LLM_BASE_URL")
        api_key = os.getenv("NETWORK_AGENT_AGENT_LLM_API_KEY")

        # Backward-compatible fallback to existing generic LLM env vars.
        if model == "llama3.2":
            model = os.getenv("NETWORK_AGENT_LLM_MODEL", model).strip()
        if not base_url:
            base_url = os.getenv("NETWORK_AGENT_LLM_BASE_URL")
        if not api_key:
            api_key = os.getenv("NETWORK_AGENT_LLM_API_KEY")

        return cls(provider=provider, model=model, base_url=base_url, api_key=api_key)


class AgentLLMConnector:
    def __init__(self, config: AgentLLMConfig) -> None:
        self.config = config

    def ask_json(self, system_prompt: str, user_prompt: str, task: str) -> dict[str, Any]:
        provider = self.config.provider.lower()
        if provider in {"none", ""}:
            return {}
        if provider == "mock":
            return self._mock_response(task)
        if provider == "ollama":
            return self._ollama_json(system_prompt, user_prompt)
        if provider in {"openai", "openai_compatible"}:
            return self._openai_json(system_prompt, user_prompt)
        return {}

    def _post_json(self, url: str, headers: dict[str, str], body: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError:
            return {}
        except Exception:  # noqa: BLE001
            return {}

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
        except Exception:  # noqa: BLE001
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _openai_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        url = self.config.base_url or "http://localhost:1234/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        body = {
            "model": self.config.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        data = self._post_json(url, headers, body)
        try:
            return self._parse_json_object(data["choices"][0]["message"]["content"])
        except Exception:  # noqa: BLE001
            return {}

    def _ollama_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        url = self.config.base_url or "http://localhost:11434/api/chat"
        body = {
            "model": self.config.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
        }
        data = self._post_json(url, {"Content-Type": "application/json"}, body)
        try:
            return self._parse_json_object(data["message"]["content"])
        except Exception:  # noqa: BLE001
            return {}

    def _mock_response(self, task: str) -> dict[str, Any]:
        if task == "planner":
            return {
                "category": "connectivity",
                "selected_checks": ["ping", "traceroute", "logs"],
                "rationale": "mock llm planner response",
            }
        if task == "generator":
            return {
                "problem_summary": "LLM-assisted diagnosis.",
                "candidate_causes_ranked": [
                    {
                        "title": "Likely path instability from intermediate hop drops",
                        "confidence": 0.73,
                        "required_evidence": ["traceroute", "packet_loss_pct"],
                        "remediation_steps": [
                            "Verify gateway health counters",
                            "Compare path quality from another host",
                            "Escalate with upstream ISP if persistent",
                        ],
                    }
                ],
                "confidence_score": 0.73,
                "required_evidence": ["traceroute", "packet_loss_pct"],
                "remediation_plan": [
                    "Verify gateway health counters",
                    "Compare path quality from another host",
                    "Escalate with upstream ISP if persistent",
                ],
            }
        return {}
