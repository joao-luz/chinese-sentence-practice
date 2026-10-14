"""Build data/tatoeba/corpus.json from Tatoeba's per-language exports.

Downloads any missing export files, then keeps every Mandarin sentence that
has at least one English translation. Run again to refresh the corpus.
"""

import bz2
import collections
import json
import urllib.request
from pathlib import Path

DIR = Path(__file__).parent / "data" / "tatoeba"
BASE_URL = "https://downloads.tatoeba.org/exports/per_language"
FILES = {
    "cmn_sentences.tsv.bz2": f"{BASE_URL}/cmn/cmn_sentences.tsv.bz2",
    "eng_sentences.tsv.bz2": f"{BASE_URL}/eng/eng_sentences.tsv.bz2",
    "cmn-eng_links.tsv.bz2": f"{BASE_URL}/cmn/cmn-eng_links.tsv.bz2",
}


def download_missing():
    DIR.mkdir(parents=True, exist_ok=True)
    for name, url in FILES.items():
        path = DIR / name
        if not path.exists():
            print(f"Downloading {name} (this can be slow)...")
            partial = path.with_suffix(".part")
            urllib.request.urlretrieve(url, partial)
            partial.rename(path)


def read_sentences(name):
    with bz2.open(DIR / name, "rt", encoding="utf-8") as f:
        for line in f:
            sid, _lang, text = line.rstrip("\n").split("\t", 2)
            yield int(sid), text


def main():
    download_missing()

    links = collections.defaultdict(list)
    with bz2.open(DIR / "cmn-eng_links.tsv.bz2", "rt") as f:
        for line in f:
            cmn_id, eng_id = map(int, line.split())
            links[cmn_id].append(eng_id)

    wanted = {e for ids in links.values() for e in ids}
    english = {sid: text for sid, text in read_sentences("eng_sentences.tsv.bz2") if sid in wanted}

    corpus = []
    for sid, text in read_sentences("cmn_sentences.tsv.bz2"):
        translations = [english[e] for e in links.get(sid, []) if e in english]
        if translations:
            corpus.append({"id": sid, "chinese": text, "english": translations})

    out = DIR / "corpus.json"
    out.write_text(json.dumps(corpus, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(corpus)} sentences to {out}")


if __name__ == "__main__":
    main()
