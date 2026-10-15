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
    "You write short, natural, grammatical Mandarin sentences for a beginner "
    "learner, each with its exact English translation. Make every sentence "
    "different. Reply with JSON only."
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


# One complete {"chinese": ..., "english": ...} object, for salvaging a reply
# that was cut off before the closing brackets.
ITEM = re.compile(r'\{\s*"chinese"\s*:\s*"(?:[^"\\]|\\.)*"\s*,\s*"english"\s*:\s*"(?:[^"\\]|\\.)*"\s*\}')


def _parse_items(content):
    try:
        return json.loads(content)["sentences"]
    except (json.JSONDecodeError, KeyError, TypeError):
        return [json.loads(m) for m in ITEM.findall(content)]


def _degenerate(chinese):
    """Small models sometimes loop (不，不，不，不…); drop those sentences."""
    han = HAN.findall(chinese)
    return chinese.count("，") > 2 or any(han.count(c) > 2 for c in set(han))


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


def generate(entries, theme="", base_url="", model="", n=1):
    """Return a list of up to n sentences."""
    allowed = "".join(known_characters(entries))
    if not allowed:
        raise GenerationError("Add some vocabulary first.")
    base_url = (base_url or DEFAULT_URL).rstrip("/")

    try:
        if not model:  # use whatever the server is serving
            model = _get(f"{base_url}/models")["data"][0]["id"]

        sentence = {
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
        schema = {
            "type": "object",
            "properties": {"sentences": {"type": "array", "items": sentence, "minItems": n, "maxItems": n}},
            "required": ["sentences"],
            "additionalProperties": False,
        }

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        examples = _examples(entries)
        if examples:
            messages += [
                {"role": "user", "content": f"Write {len(examples)} sentences."},
                {"role": "assistant", "content": json.dumps({"sentences": [
                    {"chinese": s["chinese"], "english": s["english"][0]} for s in examples
                ]}, ensure_ascii=False)},
            ]
        words = random.sample([e["text"] for e in entries], k=min(8 + n, len(entries)))
        request = (
            f"Write {n} new sentence{'s' if n > 1 else ''}, different from the previous ones. "
            "Words you can use: " + "、".join(words)
        )
        if theme:
            request += f". Topic: {theme}"
        messages.append({"role": "user", "content": request})

        response = _post(f"{base_url}/chat/completions", {
            "model": model,
            "messages": messages,
            "max_tokens": 150 * n,
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
        items = _parse_items(response["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError):
        raise GenerationError("The local model returned something unexpected. Try again.")

    note = f"Written by {model} running locally. Small models make mistakes: double-check the grammar."
    sentences, seen = [], set()
    for item in items:
        chinese = item.get("chinese", "") if isinstance(item, dict) else ""
        # The regex already guarantees known characters; double-check in case
        # the server ignored it, and drop repeats.
        if not chinese or chinese in seen or _degenerate(chinese) or set(HAN.findall(chinese)) - set(allowed):
            continue
        seen.add(chinese)
        sentences.append({
            "english": item.get("english", ""),
            "chinese": chinese,
            "pinyin": to_pinyin(chinese),
            "note": note,
        })
    if not sentences:
        raise GenerationError("The local model didn't return a usable sentence. Try again.")
    return sentences
