"""Chinese sentence learner: shows English sentences whose Chinese
translation only uses characters the learner already knows."""

import json
from pathlib import Path

from flask import Flask, redirect, render_template, request, url_for

import sentence_cache
from common import HAN, GenerationError, known_characters, to_pinyin
from sources import SOURCES, claude_api, local_llm, openrouter, tatoeba

BASE_DIR = Path(__file__).parent
VOCAB_FILE = BASE_DIR / "data" / "vocab.json"
SETTINGS_FILE = BASE_DIR / "data" / "settings.json"

app = Flask(__name__)
app.jinja_env.filters["pinyin"] = to_pinyin  # suggested pinyin in the vocabulary forms


# ---------- storage ----------

def load_json(path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path, data):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_vocab():
    return load_json(VOCAB_FILE, [])


def form_list(name):
    """Values from a dynamic list: one input per row, empty rows ignored."""
    return [v.strip() for v in request.form.getlist(name) if v.strip()]


def load_settings():
    defaults = {
        "source": "tatoeba",
        "api_key": "",  # Claude
        "openrouter_key": "", "openrouter_model": openrouter.DEFAULT_MODEL,
        "local_url": local_llm.DEFAULT_URL, "local_model": "",
    }
    return {**defaults, **load_json(SETTINGS_FILE, {})}


def save_settings(settings):
    save_json(SETTINGS_FILE, settings)
    SETTINGS_FILE.chmod(0o600)  # the file holds API keys


def mask(key):
    return f"{key[:7]}…{key[-4:]}" if len(key) > 12 else "••••"


# ---------- routes ----------

@app.route("/")
def index():
    return redirect(url_for("generate"))


@app.route("/generate", methods=["GET", "POST"])
def generate():
    entries = load_vocab()
    settings = load_settings()
    result = error = None
    theme = ""
    source = settings["source"]
    if request.method == "POST":
        source = request.form.get("source", source)
        if source not in SOURCES:
            source = "tatoeba"
        theme = request.form.get("theme", "").strip()
        if source != settings["source"]:
            settings["source"] = source
            save_settings(settings)
        try:
            if source == "claude":
                key = sentence_cache.cache_key(source, claude_api.MODEL, theme)
                generate_batch = lambda n: claude_api.generate(entries, theme, settings["api_key"], n)
            elif source == "openrouter":
                model = settings["openrouter_model"]
                key = sentence_cache.cache_key(source, model, theme)
                generate_batch = lambda n: openrouter.generate(entries, theme, settings["openrouter_key"], model, n)
            elif source == "local":
                key = sentence_cache.cache_key(source, settings["local_url"], settings["local_model"], theme)
                generate_batch = lambda n: local_llm.generate(
                    entries, theme, settings["local_url"], settings["local_model"], n
                )
            if source in ("claude", "openrouter", "local"):
                result = sentence_cache.next_sentence(key, entries, generate_batch)
            else:
                last_id = request.form.get("last_id", type=int)
                result = tatoeba.generate(entries, exclude_id=last_id)
        except GenerationError as e:
            error = str(e)
    return render_template(
        "generate.html", tab="generate", result=result, error=error,
        theme=theme, source=source, sources=SOURCES,
        char_count=len(known_characters(entries)),
    )


@app.route("/vocabulary", methods=["GET", "POST"])
def vocabulary():
    entries = load_vocab()
    message = None
    if request.method == "POST":
        if "delete" in request.form:
            text = request.form["delete"]
            entries = [e for e in entries if e["text"] != text]
            save_json(VOCAB_FILE, entries)
            message = f"Removed {text}."
        else:
            text = request.form.get("text", "").strip()
            if not HAN.search(text):
                message = "Entries must contain at least one Chinese character."
            elif any(e["text"] == text for e in entries):
                message = f"{text} is already in your list."
            else:
                before = known_characters(entries)
                entries.append({
                    "text": text,
                    "pinyin": form_list("pinyin"),
                    "meanings": form_list("meaning"),
                })
                save_json(VOCAB_FILE, entries)
                new = "".join(c for c in known_characters(entries) if c not in before)
                message = f"Added {text}." + (f" New characters: {new}" if new else "")
    chars = known_characters(entries)
    return render_template(
        "vocabulary.html", tab="vocabulary", entries=entries,
        chars="".join(chars), char_count=len(chars), message=message,
    )


@app.route("/vocabulary/edit", methods=["POST"])
def edit_entry():
    entries = load_vocab()
    text = request.form.get("text", "")
    for e in entries:
        if e["text"] == text:
            e["pinyin"] = form_list("pinyin")
            e["meanings"] = form_list("meaning")
            save_json(VOCAB_FILE, entries)
            break
    return redirect(url_for("vocabulary", _anchor=f"entry-{text}"))


# Settings key -> (expected prefix, display name) for each hosted provider.
API_KEYS = {
    "api_key": ("sk-ant-", "Claude"),
    "openrouter_key": ("sk-or-", "OpenRouter"),
}


@app.route("/settings", methods=["GET", "POST"])
def settings_page():
    settings = load_settings()
    message = None
    if request.method == "POST":
        form = request.form.get("form")
        if form in API_KEYS:
            prefix, name = API_KEYS[form]
            key = request.form.get("key", "").strip()
            if "remove" in request.form:
                settings[form] = ""
                message = f"{name} API key removed."
            elif not key:
                message = "Paste a key to save it."
            elif not key.startswith(prefix):
                message = f"That doesn't look like a valid {name} API key (they start with {prefix})."
            else:
                settings[form] = key
                message = f"{name} API key saved."
        elif form == "openrouter_model":
            settings["openrouter_model"] = request.form["model"].strip() or openrouter.DEFAULT_MODEL
            message = message or "OpenRouter model saved."
        elif form == "local":
            settings["local_url"] = request.form.get("local_url", "").strip() or local_llm.DEFAULT_URL
            settings["local_model"] = request.form.get("local_model", "").strip()
            message = "Local model settings saved."
        save_settings(settings)
    return render_template(
        "settings.html", tab="settings", message=message, settings=settings,
        masked={k: mask(settings[k]) for k in API_KEYS if settings[k]},
        openrouter_models=openrouter.list_models(),
        openrouter_default=openrouter.DEFAULT_MODEL,
        char_count=len(known_characters(load_vocab())),
    )


if __name__ == "__main__":
    app.run(debug=True)
