import json
import ssl
import urllib.request
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

_PROMPT_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


def load_prompt(name: str = "extraction") -> str:
    """Load a prompt from the prompts/ directory."""
    path = _PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def _clean_json_markdown(text: str) -> str:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1]
    if cleaned.endswith("```"):
        cleaned = cleaned.rsplit("```", 1)[0]
    return cleaned.strip()


def call_vision(image_b64: str, mime_type: str, api_key: str, model: str) -> dict:
    """Call OpenRouter Vision API (OpenAI-compatible)."""
    prompt = load_prompt("extraction")
    data_url = f"data:{mime_type};base64,{image_b64}"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        "temperature": 0.0,
        "max_tokens": 1000,
    }

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    ssl_ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=60, context=ssl_ctx) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    text = result["choices"][0]["message"]["content"]
    return json.loads(_clean_json_markdown(text))


def call_text(prompt: str, api_key: str, model: str) -> str:
    """Call OpenRouter text API (no image). Returns raw text response."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 200,
    }

    req = urllib.request.Request(
        OPENROUTER_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    ssl_ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=30, context=ssl_ctx) as resp:
        result = json.loads(resp.read().decode("utf-8"))

    return result["choices"][0]["message"]["content"].strip()
