"""Generate sentences with a local model served by vLLM (OpenAI-compatible API).

Small models can't reliably stick to a character list on their own, so the
Chinese field is constrained with a regex: vLLM's structured outputs make it
impossible for the model to emit a character the learner doesn't know.
"""

import json
import random
import re
import urllib.error
import urllib.request

from common import HAN, GenerationError, known_characters, to_pinyin
from . import tatoeba

DEFAULT_URL = "http://localhost:8000/v1"
TIMEOUT = 300  # seconds; CPU inference is slow
FEW_SHOT = 4
ALLOWED_PUNCTUATION = "，。？！"

SYSTEM_PROMPT = (
    "You write one short, natural, grammatical Mandarin sentence for a beginner "
    "learner, then its exact English translation. Reply with JSON only."
)


def _post(url, body):
    req = urllib.request.Request(
        url, json.dumps(body).encode(), {"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _get(url):
    with urllib.request.urlopen(url, timeout=10) as r:
        return json.load(r)


def _examples(entries):
    """Real Tatoeba sentences the learner can read, used as few-shot examples."""
    try:
        pool = [
            s for s in tatoeba.matching(entries)
            if len(s["chars"]) >= 4 and not re.search(r"[A-Za-z]", s["chinese"])
        ]
    except GenerationError:  # corpus not built yet
        return []
    return random.sample(pool, k=min(FEW_SHOT, len(pool)))


def generate(entries, theme="", base_url="", model=""):
    allowed = "".join(known_characters(entries))
    if not allowed:
        raise GenerationError("Add some vocabulary first.")
    base_url = (base_url or DEFAULT_URL).rstrip("/")

    try:
        if not model:  # use whatever the server is serving
            model = _get(f"{base_url}/models")["data"][0]["id"]

        schema = {
            "type": "object",
            "properties": {
                "chinese": {
                    "type": "string",
                    "pattern": f"^[{allowed}{ALLOWED_PUNCTUATION}]{{3,16}}$",
                },
                "english": {"type": "string", "maxLength": 150},
            },
            "required": ["chinese", "english"],
            "additionalProperties": False,
        }

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for s in _examples(entries):
            messages += [
                {"role": "user", "content": "New sentence."},
                {"role": "assistant", "content": json.dumps(
                    {"chinese": s["chinese"], "english": s["english"][0]}, ensure_ascii=False
                )},
            ]
        words = random.sample([e["text"] for e in entries], k=min(8, len(entries)))
        request = "New sentence, different from the previous ones. Words you can use: " + "、".join(words)
        if theme:
            request += f". Topic: {theme}"
        messages.append({"role": "user", "content": request})

        response = _post(f"{base_url}/chat/completions", {
            "model": model,
            "messages": messages,
            "max_tokens": 150,
            # Qwen3 thinks by default; that's slow on a CPU and not needed here.
            "chat_template_kwargs": {"enable_thinking": False},
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "sentence", "schema": schema},
            },
        })
    except urllib.error.HTTPError as e:
        raise GenerationError(f"Local model server error ({e.code}): {e.read().decode()[:200]}")
    except (urllib.error.URLError, ConnectionError):
        raise GenerationError(
            f"Can't reach the local model at {base_url}. Start it with ./serve_local_llm.sh"
        )
    except TimeoutError:
        raise GenerationError("The local model took too long to answer.")

    try:
        result = json.loads(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, json.JSONDecodeError):
        raise GenerationError("The local model returned something unexpected. Try again.")

    # The regex already guarantees this; double-check in case the server ignored it.
    if set(HAN.findall(result["chinese"])) - set(allowed):
        raise GenerationError("The local model used characters you don't know. Try again.")

    return {
        "english": result["english"],
        "chinese": result["chinese"],
        "pinyin": to_pinyin(result["chinese"]),
        "note": f"Written by {model} running locally. Small models make mistakes: double-check the grammar.",
    }
