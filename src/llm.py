import json
import ssl
import urllib.request
from pathlib import Path

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "qwen/qwen3.5-flash-02-23"

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


def load_prompt(name: str = "extraction") -> str:
    """Load a prompt from the prompts/ directory."""
    path = _PROMPT_DIR / f"{name}.md"
    return path.read_text(encoding="utf-8")


def call_openrouter(image_b64: str, mime_type: str, api_key: str) -> dict:
    """Call OpenRouter Vision API (OpenAI-compatible)."""
    prompt = load_prompt("extraction")
    data_url = f"data:{mime_type};base64,{image_b64}"

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": data_url}},
            ]
        }],
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
    # Clean markdown fences if present
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    text = text.strip()

    return json.loads(text)


def call_openrouter_text(prompt: str, api_key: str) -> str:
    """Call OpenRouter text API (no image). Returns raw text response."""
    payload = {
        "model": OPENROUTER_MODEL,
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
