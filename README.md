# Chinese Sentence Learner

A small Flask app that shows English sentences whose Chinese translation uses
only the characters you know. Plain HTML/CSS frontend with no libraries; the
vocabulary page uses a little vanilla JS (`static/js/`) for its edit overlay.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python build_tatoeba.py   # downloads Tatoeba data, builds the corpus
.venv/bin/python app.py
```

Open http://localhost:5000.

- **Generate sentence**: pick a source, get an English sentence to translate,
  click "Show answer" to check.
  - **Tatoeba**: free and offline. Picks a real sentence from Tatoeba's
    Mandarin–English pairs that uses only your characters.
  - **Local model**: a small model running on your own computer through vLLM
    (see below). Free and offline, but slower and makes more mistakes.
  - **OpenRouter**: one API key for hundreds of models, some free (IDs ending
    in `:free`, with tight rate limits). Pick the model in Settings; the
    default is a free one.
  - **Claude API**: writes a new sentence for you, optionally on a theme.
    Needs an API key.
- The three model sources (local, OpenRouter, Claude) keep a cache of
  sentences: each request asks for a batch of 10, and once 8 of a batch are
  used the next 10 are fetched in the background. The first sentence on an
  empty cache is generated on the spot. There's one cache per source, model
  and theme, saved in `data/sentence_cache.json`, and every cached sentence is
  re-checked against your current characters before it's shown.
- **Balanced practice**: every generated sentence is recorded in
  `data/history.json`, and the app counts how often each vocabulary entry has
  been used. New sentences are built around the least-used entries (the model
  is told to use each of them; Tatoeba prefers sentences containing them), so
  over time every entry gets practised about equally.
- **History**: the sentences you've been shown, newest first, with the entries
  each one practises, and the usage count of every entry.
- **My vocabulary**: add, edit or remove characters, words and expressions.
  Each entry has pinyin and a list of the meanings you know; click **Edit**
  to change them.
- **Settings**: save or remove your OpenRouter and Claude API keys, choose the
  OpenRouter model, and set the local model server.

## Local model (vLLM on the CPU)

vLLM lives in its own environment, `.venv-vllm` (about 3 GB, mostly PyTorch):

```bash
uv venv --python 3.12 .venv-vllm
VIRTUAL_ENV=.venv-vllm uv pip install \
  "https://github.com/vllm-project/vllm/releases/download/v0.31.0/vllm-0.31.0+cpu-cp38-abi3-manylinux_2_39_x86_64.whl" \
  --torch-backend cpu
```

Then, in a separate terminal:

```bash
./serve_local_llm.sh                    # Qwen/Qwen3-0.6B, ~9 s per sentence
./serve_local_llm.sh Qwen/Qwen3-1.7B    # ~28 s per sentence, needs ~5 GB RAM
```

The first start downloads the model and compiles it (5–10 minutes); later
starts are faster. The Chinese is constrained to your known characters with
vLLM's structured outputs, so the model can't use characters you don't know,
but small models still produce odd sentences and loose translations.

Data lives in `data/`: `vocab.json` (your vocabulary), `settings.json` (API
key and last source, not committed), and `tatoeba/corpus.json` (built by
`build_tatoeba.py`; run it again to refresh).

Sentences from Tatoeba are licensed CC BY 2.0 FR; each one links back to its
page on tatoeba.org.
