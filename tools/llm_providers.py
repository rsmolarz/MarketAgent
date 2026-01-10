"""
LLM Provider Adapters for Regime Council

Provides unified interface for GPT, Claude, and Gemini.
"""
import os
import json
import requests
from typing import Dict, Any


class LLMProviderError(Exception):
    pass


def _post_json(url: str, headers: Dict[str, str], payload: Dict[str, Any], timeout: int = 45) -> Dict[str, Any]:
    r = requests.post(url, headers=headers, json=payload, timeout=timeout)
    if r.status_code >= 400:
        raise LLMProviderError(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.json()


class GPTProvider:
    """OpenAI GPT provider (uses Replit AI integrations if available)."""
    
    def __init__(self, model: str = "gpt-4o-mini"):
        self.model = os.getenv("COUNCIL_GPT_MODEL", model)
        self.api_key = os.getenv("AI_INTEGRATIONS_OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
        self.base_url = os.getenv("AI_INTEGRATIONS_OPENAI_BASE_URL") or "https://api.openai.com/v1"

    def call(self, system: str, user: str) -> str:
        if not self.api_key:
            raise LLMProviderError("Missing OPENAI_API_KEY")
        url = f"{self.base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": 1500,
        }
        data = _post_json(url, headers, payload)
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "").strip()
        return json.dumps(data)


class ClaudeProvider:
    """Anthropic Claude provider."""
    
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = os.getenv("COUNCIL_CLAUDE_MODEL", model)
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")

    def call(self, system: str, user: str) -> str:
        if not self.api_key:
            raise LLMProviderError("Missing ANTHROPIC_API_KEY")
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 1500,
            "temperature": 0.2,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        data = _post_json(url, headers, payload)
        blocks = data.get("content", [])
        text = "".join([b.get("text", "") for b in blocks if b.get("type") == "text"])
        return text.strip() or json.dumps(data)


class GeminiProvider:
    """Google Gemini provider."""
    
    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = os.getenv("COUNCIL_GEMINI_MODEL", model)
        self.api_key = os.getenv("GEMINI_API_KEY", "")

    def call(self, system: str, user: str) -> str:
        if not self.api_key:
            raise LLMProviderError("Missing GEMINI_API_KEY")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        headers = {"Content-Type": "application/json"}
        payload = {
            "contents": [{
                "role": "user",
                "parts": [{"text": f"SYSTEM:\n{system}\n\nUSER:\n{user}"}]
            }],
            "generationConfig": {"temperature": 0.2, "maxOutputTokens": 1500}
        }
        data = _post_json(url, headers, payload)
        cands = data.get("candidates", [])
        if not cands:
            return json.dumps(data)
        parts = cands[0].get("content", {}).get("parts", [])
        text = "".join([p.get("text", "") for p in parts])
        return text.strip() or json.dumps(data)
