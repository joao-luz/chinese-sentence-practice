"""Generate sentences through OpenRouter (https://openrouter.ai), which gives
one API key access to many models, some of them free."""

import json
import time
import urllib.error
import urllib.request

from common import GenerationError

from .prompting import BATCH_SCHEMA, generate_with_retries, parse_sentences

API_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"
TIMEOUT = 120  # seconds; reasoning models can take a while

_models_cache = {"time": 0.0, "models": []}


def _request(path, body=None, api_key=""):
    headers = {
        "Content-Type": "application/json",
        # Optional attribution headers OpenRouter uses to identify the app.
        "HTTP-Referer": "http://localhost:5000",
        "X-Title": "Chinese Sentence Learner",
    }
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{API_URL}{path}", data, headers)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.load(r)


def _error_message(e):
    """Turn an OpenRouter HTTP error into something the learner can act on."""
    try:
        detail = json.loads(e.read())["error"]["message"]
    except (ValueError, KeyError, TypeError):
        detail = e.reason
    return {
        401: "OpenRouter rejected the API key. Check it in the Settings tab.",
        402: "Your OpenRouter account is out of credits. Pick a free model (ending in :free) or add credits.",
        404: f"No OpenRouter provider can serve this model with JSON output. Pick another model in Settings. ({detail})",
        429: "OpenRouter rate limit reached (free models have tight limits). Wait a moment and try again.",
    }.get(e.code, f"OpenRouter error ({e.code}): {detail}")


def generate(entries, theme="", api_key="", model="", n=1):
    """Return a list of up to n sentences."""
    if not api_key:
        raise GenerationError("No OpenRouter API key set. Add one in the Settings tab.")
    model = model or DEFAULT_MODEL

    def ask(system, user):
        response = _request("/chat/completions", {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": 8000,  # room for 10 sentences plus any reasoning
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "sentences", "strict": True, "schema": BATCH_SCHEMA},
            },
            # Only route to providers that actually honour response_format.
            "provider": {"require_parameters": True},
        }, api_key)
        if "error" in response:  # some failures arrive as 200 with an error body
            raise GenerationError(f"OpenRouter error: {response['error'].get('message', response['error'])}")
        try:
            return parse_sentences(response["choices"][0]["message"]["content"] or "")
        except (KeyError, IndexError):
            return None

    try:
        sentences = generate_with_retries(entries, theme, ask, n)
    except urllib.error.HTTPError as e:
        raise GenerationError(_error_message(e))
    except (urllib.error.URLError, ConnectionError):
        raise GenerationError("Couldn't reach OpenRouter. Check your internet connection.")
    except TimeoutError:
        raise GenerationError("The model on OpenRouter took too long to answer. Try again or pick a faster model.")
    return [{**s, "note": f"Written by {model} via OpenRouter."} for s in sentences]


def list_models():
    """Models that support JSON output, free ones first. Cached for an hour;
    returns [] if OpenRouter can't be reached (the settings page still works)."""
    if time.time() - _models_cache["time"] < 3600:
        return _models_cache["models"]
    try:
        data = _request("/models")["data"]
    except (urllib.error.URLError, ConnectionError, TimeoutError, ValueError, KeyError):
        return _models_cache["models"]
    models = []
    for m in data:
        # :batch variants are for OpenRouter's offline batch API, not live requests.
        if m["id"].endswith(":batch") or "structured_outputs" not in m.get("supported_parameters", []):
            continue
        pricing = m.get("pricing", {})
        try:
            cost_in = float(pricing.get("prompt", 0)) * 1e6
            cost_out = float(pricing.get("completion", 0)) * 1e6
        except ValueError:
            continue
        if cost_in < 0 or cost_out < 0:  # negative = variable/router pricing
            continue
        free = cost_in == 0 and cost_out == 0
        label = "free" if free else f"${cost_in:.2f} / ${cost_out:.2f} per million tokens (in / out)"
        models.append({"id": m["id"], "label": label, "free": free})
    models.sort(key=lambda m: (not m["free"], m["id"]))
    _models_cache.update(time=time.time(), models=models)
    return models
