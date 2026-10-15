"""Generate sentences with the Claude API."""

import anthropic

from common import GenerationError

from .prompting import BATCH_SCHEMA, generate_with_retries, parse_sentences

MODEL = "claude-opus-5-5"


def generate(entries, theme="", api_key=None, n=1):
    """Return a list of up to n sentences."""
    if not api_key:
        raise GenerationError("No Claude API key set. Add one in the Settings tab.")
    client = anthropic.Anthropic(api_key=api_key)

    def ask(system, user):
        response = client.beta.messages.create(
            model=MODEL,
            max_tokens=8000,  # room for a batch of sentences plus thinking
            output_config={
                "effort": "low",
                "format": {"type": "json_schema", "schema": BATCH_SCHEMA},
            },
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        if response.stop_reason == "refusal":
            raise GenerationError("The model declined this request. Try again.")
        return parse_sentences(next((b.text for b in response.content if b.type == "text"), ""))

    try:
        return generate_with_retries(entries, theme, ask, n)
    except anthropic.AuthenticationError:
        raise GenerationError("The API key was rejected. Check it in the Settings tab.")
    except anthropic.RateLimitError:
        raise GenerationError("Rate limited by the API. Wait a moment and try again.")
    except anthropic.APIConnectionError:
        raise GenerationError("Couldn't reach the Claude API. Check your internet connection.")
    except anthropic.APIStatusError as e:
        raise GenerationError(f"API error ({e.status_code}): {e.message}")
