"""Record of every generated sentence, and how often each vocabulary entry
has been used, so generation can favour the entries practised least.

Each record has an id, the sentence (english, chinese, pinyin, note), its
source, when it was generated, and when the learner was shown it ("shown" is
None while it waits in the sentence cache).

Usage counts include sentences still waiting in the cache: they will be shown
soon, so counting them stops the next batch from repeating the same words.
Which entries a sentence uses is worked out against the *current* vocabulary
every time, so adding 名字 later also counts the 名字 in older sentences.
"""

import json
import random
import threading
import time
from pathlib import Path

HISTORY_FILE = Path(__file__).parent / "data" / "history.json"
SENTENCE_FIELDS = ("english", "chinese", "pinyin", "note", "credit_url")

_lock = threading.Lock()


def _load():
    try:
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save(records):
    HISTORY_FILE.parent.mkdir(exist_ok=True)
    tmp = HISTORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(records, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(HISTORY_FILE)


def record(sentences, source, shown=False):
    """Add generated sentences; returns them with their new "history_id"."""
    now = time.time()
    out = []
    with _lock:
        records = _load()
        next_id = max((r["id"] for r in records), default=0) + 1
        for s in sentences:
            records.append({
                "id": next_id,
                **{k: s.get(k, "") for k in SENTENCE_FIELDS},
                "source": source,
                "generated": now,
                "shown": now if shown else None,
            })
            out.append({**s, "history_id": next_id})
            next_id += 1
        _save(records)
    return out


def mark_shown(history_id):
    with _lock:
        records = _load()
        for r in records:
            if r["id"] == history_id and r["shown"] is None:
                r["shown"] = time.time()
                _save(records)
                break


def shown_sentences():
    """Sentences the learner has seen, newest first."""
    return sorted((r for r in _load() if r["shown"]), key=lambda r: r["shown"], reverse=True)


def entries_used(chinese, entries):
    """Vocabulary entries in a sentence, matching the longest entry first:
    没关系 counts as 没关系, not as 没."""
    texts = sorted({e["text"] for e in entries}, key=len, reverse=True)
    found, i = [], 0
    while i < len(chinese):
        match = next((t for t in texts if chinese.startswith(t, i)), None)
        if match:
            found.append(match)
            i += len(match)
        else:
            i += 1
    return found


def usage_counts(entries):
    """How many generated sentences use each entry (0 for unused ones)."""
    counts = {e["text"]: 0 for e in entries}
    for r in _load():
        for text in set(entries_used(r["chinese"], entries)):
            counts[text] += 1
    return counts


def preferred(entries, k):
    """The k least-used entries, ties broken at random, so that over time every
    entry is practised about equally."""
    counts = usage_counts(entries)
    ranked = sorted(counts, key=lambda t: (counts[t], random.random()))
    return ranked[:min(k, len(ranked))]
