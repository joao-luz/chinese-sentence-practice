"""Generate sentences with the Claude API."""

import json
import random

import anthropic

from common import HAN, GenerationError, known_characters

MODEL = "claude-opus-5-5"
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

SYSTEM_PROMPT = """You write practice sentences for a beginner learner of Mandarin Chinese (simplified characters).

You are given the learner's vocabulary: the words and expressions they have studied, and the exact set of characters they can read. Produce ONE short, natural English sentence whose most natural Mandarin translation uses ONLY characters from the allowed set. Punctuation (，。？！) is fine.

Requirements:
- The Chinese must be grammatical and idiomatic, the way a teacher would actually say it. Never force an unnatural translation just to fit the character set; pick a different sentence instead.
- The English must translate naturally to exactly that Chinese, so the learner can translate it themselves and check.
- Keep it beginner level: one clause or two short ones.
- Give pinyin with tone marks, words separated by spaces."""


def generate(entries, theme="", api_key=None):
    allowed = known_characters(entries)
    if not allowed:
        raise GenerationError("Add some vocabulary first.")
    if not api_key:
        raise GenerationError("No API key set. Add one in the Settings tab.")

    # Nudge variety: suggest a few random words to build around.
    focus = random.sample([e["text"] for e in entries], k=min(3, len(entries)))
    vocab_lines = "\n".join(
        f"- {e['text']}" + (f" ({e['meaning']})" if e.get("meaning") else "")
        for e in entries
    )
    prompt = (
        f"Learner vocabulary:\n{vocab_lines}\n\n"
        f"Allowed characters (exhaustive): {''.join(allowed)}\n\n"
        f"Try to build the sentence around some of these: {', '.join(focus)}"
    )
    if theme:
        prompt += f"\nTheme requested by the learner: {theme}"

    client = anthropic.Anthropic(api_key=api_key)
    rejected = []
    try:
        for _ in range(MAX_ATTEMPTS):
            content = prompt
            if rejected:
                content += "\n\nThese earlier attempts used characters outside the allowed set; do not repeat them:\n" + "\n".join(rejected)
            response = client.beta.messages.create(
                model=MODEL,
                max_tokens=4000,
                output_config={
                    "effort": "low",
                    "format": {"type": "json_schema", "schema": SENTENCE_SCHEMA},
                },
                betas=["server-side-fallback-2026-07-01"],
                fallbacks="default",
                system=SYSTEM_PROMPT,
                messages=[{"role": "user", "content": content}],
            )
            if response.stop_reason == "refusal":
                raise GenerationError("The model declined this request. Try again.")
            text = next((b.text for b in response.content if b.type == "text"), "")
            try:
                result = json.loads(text)
            except json.JSONDecodeError:
                continue

            unknown = sorted(set(HAN.findall(result["chinese"])) - set(allowed))
            if not unknown:
                return result
            rejected.append(f"{result['chinese']} (unknown: {''.join(unknown)})")
    except anthropic.AuthenticationError:
        raise GenerationError("The API key was rejected. Check it in the Settings tab.")
    except anthropic.RateLimitError:
        raise GenerationError("Rate limited by the API. Wait a moment and try again.")
    except anthropic.APIConnectionError:
        raise GenerationError("Couldn't reach the Claude API. Check your internet connection.")
    except anthropic.APIStatusError as e:
        raise GenerationError(f"API error ({e.status_code}): {e.message}")

    raise GenerationError(
        "Couldn't find a sentence using only your characters. Try again, or add more vocabulary."
    )
