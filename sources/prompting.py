"""Prompt and retry loop shared by the hosted-model sources (Claude, OpenRouter).

Each source supplies an `ask(system, user)` function that sends one request and
returns the model's JSON reply as a dict (or None if it couldn't be parsed).
Sentences are requested in batches so one request can fill the sentence cache.
"""

import json
import random

from common import HAN, GenerationError, known_characters

MAX_ATTEMPTS = 3

SENTENCE_SCHEMA = {
    "type": "object",
    "properties": {
        "english": {"type": "string"},
        "chinese": {"type": "string"},
        "pinyin": {"type": "string"},
    },
    "required": ["english", "chinese", "pinyin"],
    "additionalProperties": False,
}

BATCH_SCHEMA = {
    "type": "object",
    "properties": {"sentences": {"type": "array", "items": SENTENCE_SCHEMA}},
    "required": ["sentences"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = """You write practice sentences for a beginner learner of Mandarin Chinese (simplified characters).

You are given the learner's vocabulary: the words and expressions they have studied, and the exact set of characters they can read. Produce short, natural English sentences whose most natural Mandarin translation uses ONLY characters from the allowed set. Punctuation (，。？！) is fine.

Requirements:
- The Chinese must be grammatical and idiomatic, the way a teacher would actually say it. Never force an unnatural translation just to fit the character set; pick a different sentence instead.
- The English must translate naturally to exactly that Chinese, so the learner can translate it themselves and check.
- Keep it beginner level: one clause or two short ones.
- Some vocabulary entries are marked PRIORITY: the learner has practised them least. Build the sentences around them: every sentence must use at least one priority entry, and across all the sentences use each priority entry at least once. Other vocabulary can fill in around them.
- When asked for several sentences, make them different from each other: vary the structure (statements, questions, negations) and the words used.
- Give pinyin with tone marks, words separated by spaces.
- Reply with a JSON object {"sentences": [{"english": ..., "chinese": ..., "pinyin": ...}, ...]}."""


def parse_sentences(text):
    """Parse a batch reply into a list of sentence dicts, tolerating a ```json
    fence and malformed items. Returns None if nothing usable came back."""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`").removeprefix("json").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return None
    items = data.get("sentences") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return None
    keys = SENTENCE_SCHEMA["required"]
    sentences = [s for s in items if isinstance(s, dict) and all(isinstance(s.get(k), str) for k in keys)]
    return sentences or None


def generate_with_retries(entries, theme, ask, n=1, priority=()):
    """Ask for n sentences; keep those that only use known characters.
    Retries (naming the bad characters) until at least one is usable.
    `priority` lists the entries the sentences should be built around."""
    allowed = set(known_characters(entries))
    if not allowed:
        raise GenerationError("Add some vocabulary first.")

    priority = list(priority) or random.sample([e["text"] for e in entries], k=min(3, len(entries)))

    def describe(e):
        line = f"- {e['text']}"
        if e.get("meanings"):
            line += f" ({'; '.join(e['meanings'])})"
        return line + ("  <- PRIORITY" if e["text"] in priority else "")

    vocab_lines = "\n".join(describe(e) for e in entries)
    prompt = (
        f"Learner vocabulary:\n{vocab_lines}\n\n"
        f"Allowed characters (exhaustive): {''.join(known_characters(entries))}\n\n"
        f"Priority entries (use each of them at least once): {', '.join(priority)}\n\n"
        f"Write {n} sentence{'s' if n > 1 else ''}."
    )
    if theme:
        prompt += f"\nTheme requested by the learner: {theme}"

    rejected = []
    for _ in range(MAX_ATTEMPTS):
        content = prompt
        if rejected:
            content += "\n\nThese earlier attempts used characters outside the allowed set; do not repeat them:\n" + "\n".join(rejected)
        sentences = ask(SYSTEM_PROMPT, content)
        if not sentences:
            continue
        good, seen = [], set()
        for s in sentences:
            unknown = sorted(set(HAN.findall(s["chinese"])) - allowed)
            if unknown:
                rejected.append(f"{s['chinese']} (unknown: {''.join(unknown)})")
            elif s["chinese"] not in seen:
                seen.add(s["chinese"])
                good.append(s)
        if good:
            return good

    raise GenerationError(
        "Couldn't find a sentence using only your characters. Try again, or add more vocabulary."
    )
