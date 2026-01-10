import os
import json
import urllib.request

OPENAI_API_KEY = os.environ.get("AI_INTEGRATIONS_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_BASE_URL = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

class LLMError(RuntimeError):
    pass

def call_llm(messages, temperature=0.2, max_tokens=1800):
    if not OPENAI_API_KEY:
        raise LLMError("OPENAI_API_KEY is not set")

    url = f"{OPENAI_BASE_URL}/chat/completions"
    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise LLMError(f"LLM call failed: {e}")

    try:
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)
    except Exception as e:
        raise LLMError(f"Bad LLM response: {e} | raw={data}")
