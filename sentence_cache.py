"""A per-source cache of model-written sentences.

Models are asked for BATCH_SIZE sentences at once. Once only REFILL_AT are left
(the learner has used 8 of a batch of 10), the next batch is fetched in a
background thread, so the learner rarely waits. On a cold cache one sentence is
generated right away and a full batch is fetched in the background.

The cache is saved to disk so restarting the app doesn't waste paid sentences.
Each sentence is re-checked against the learner's current characters before it
is shown, so deleting a word never surfaces a sentence they can't read.
"""

import json
import logging
import threading
from pathlib import Path

from common import HAN, GenerationError, known_characters

BATCH_SIZE = 10
REFILL_AT = 2

CACHE_FILE = Path(__file__).parent / "data" / "sentence_cache.json"

log = logging.getLogger(__name__)
_lock = threading.Lock()
_refilling = set()  # keys with a background refill in progress


def _load():
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(queues):
    CACHE_FILE.parent.mkdir(exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(queues, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(CACHE_FILE)


def cache_key(*parts):
    """Separate queues per source, model and theme, e.g. ("openrouter", model, theme)."""
    return "|".join(str(p).strip().lower() for p in parts)


def _refill(key, generate):
    try:
        batch = generate(BATCH_SIZE)
        with _lock:
            queues = _load()
            queue = queues.setdefault(key, [])
            known = {s["chinese"] for s in queue}
            queue.extend(s for s in batch if s["chinese"] not in known)
            _save(queues)
    except GenerationError as e:
        # Not fatal: the next request finds the cache short and tries again.
        log.warning("Background refill for %s failed: %s", key, e)
    except Exception:
        log.exception("Background refill for %s crashed", key)
    finally:
        with _lock:
            _refilling.discard(key)


def _start_refill(key, generate):
    """Start a background refill unless one is already running for this key.
    Call with _lock held."""
    if key in _refilling:
        return
    _refilling.add(key)
    threading.Thread(target=_refill, args=(key, generate), daemon=True).start()


def next_sentence(key, entries, generate):
    """Return the next sentence for `key`.

    `generate(n)` must return a list of up to n sentences; it is called with
    BATCH_SIZE in the background, or with 1 when the cache is empty.
    """
    allowed = set(known_characters(entries))
    with _lock:
        queues = _load()
        queue = queues.get(key, [])
        sentence = None
        while queue:
            candidate = queue.pop(0)
            if set(HAN.findall(candidate["chinese"])) <= allowed:
                sentence = candidate
                break
        _save(queues)
        if len(queue) <= REFILL_AT:
            _start_refill(key, generate)
        refilling = key in _refilling

    if sentence is None:
        # Cold cache: answer now with a single sentence while the batch loads.
        sentence = generate(1)[0]
    return {**sentence, "cached_left": len(queue), "refilling": refilling}
