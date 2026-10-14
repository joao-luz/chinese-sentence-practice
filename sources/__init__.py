"""Sentence sources. Each one returns a dict with english, chinese, pinyin
(may be empty) and optionally credit_url / credit_label."""

from . import claude_api, local_llm, tatoeba

SOURCES = {
    "tatoeba": "Tatoeba (offline, free)",
    "local": "Local model (vLLM)",
    "claude": "Claude API (needs API key)",
}
