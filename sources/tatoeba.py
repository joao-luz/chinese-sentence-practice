"""Pick sentences from the Tatoeba corpus (built by build_tatoeba.py)."""

import json
import random
from pathlib import Path

from common import HAN, GenerationError, known_characters, to_pinyin

CORPUS_FILE = Path(__file__).parent.parent / "data" / "tatoeba" / "corpus.json"
MIN_CHARS = 3  # prefer sentences longer than 谢谢！ or 是吗？

_cache = {"mtime": None, "sentences": []}


def _load():
    """Load the corpus once, reloading if the file is rebuilt."""
    if not CORPUS_FILE.exists():
        raise GenerationError(
            "The Tatoeba corpus isn't built yet. Run: .venv/bin/python build_tatoeba.py"
        )
    mtime = CORPUS_FILE.stat().st_mtime
    if _cache["mtime"] != mtime:
        raw = json.loads(CORPUS_FILE.read_text(encoding="utf-8"))
        _cache["sentences"] = [
            {**s, "chars": frozenset(HAN.findall(s["chinese"]))} for s in raw
        ]
        _cache["mtime"] = mtime
    return _cache["sentences"]


def matching(entries):
    allowed = set(known_characters(entries))
    return [s for s in _load() if s["chars"] and s["chars"] <= allowed]


def generate(entries, exclude_id=None, priority=()):
    """Pick a sentence, preferring ones that use the first priority entry
    (the least practised) that any candidate sentence contains."""
    if not entries:
        raise GenerationError("Add some vocabulary first.")
    candidates = matching(entries)
    longer = [s for s in candidates if len(s["chars"]) >= MIN_CHARS]
    pool = [s for s in (longer or candidates) if s["id"] != exclude_id] or candidates
    if not pool:
        raise GenerationError("No Tatoeba sentences use only your characters yet. Add more vocabulary.")
    for text in priority:
        with_entry = [s for s in pool if text in s["chinese"]]
        if with_entry:
            pool = with_entry
            break
    s = random.choice(pool)
    return {
        "id": s["id"],
        "english": s["english"][0],
        "other_english": s["english"][1:],
        "chinese": s["chinese"],
        "pinyin": to_pinyin(s["chinese"]),
        "credit_url": f"https://tatoeba.org/en/sentences/show/{s['id']}",
        "credit_label": f"Tatoeba sentence #{s['id']} (CC BY 2.0 FR)",
        "pool_size": len(candidates),
    }
