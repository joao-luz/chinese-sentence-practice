"""Helpers shared by the app and the sentence sources."""

import re

HAN = re.compile(r"[㐀-䶿一-鿿豈-﫿]")


class GenerationError(Exception):
    """A problem the learner should see as a message on the page."""


def known_characters(entries):
    """Known characters in the order they were learned (dict keys keep order)."""
    return dict.fromkeys(ch for e in entries for ch in HAN.findall(e["text"])).keys()


PUNCTUATION = {"，": ",", "。": ".", "？": "?", "！": "!", "、": ",", "：": ":", "；": ";"}
ATTACH_LEFT = set(PUNCTUATION.values()) | {"”"}  # no space before these
ATTACH_RIGHT = {"“"}                            # no space after these


def to_pinyin(text):
    """Pinyin with tone marks, one syllable per character, punctuation attached."""
    from pypinyin import Style, lazy_pinyin

    # Non-Chinese chunks come back marked with \0 so we can tell them apart.
    tokens = []
    for piece in lazy_pinyin(text, style=Style.TONE, errors=lambda chunk: ["\0" + chunk]):
        if piece.startswith("\0"):
            for word in re.findall(r"[A-Za-z0-9']+|\S", piece[1:]):
                tokens.append(PUNCTUATION.get(word, word))
        else:
            tokens.append(piece)

    out = ""
    for tok in tokens:
        if out and tok not in ATTACH_LEFT and out[-1] not in ATTACH_RIGHT:
            out += " "
        out += tok
    return out
