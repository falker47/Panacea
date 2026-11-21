"""Produce a small Markdown dialect with no links, images or embedded HTML.

Only our own heading, list and inline emphasis markers reach Qt's Markdown
parser. Literal punctuation is encoded, including the characters Qt uses to
auto-link bare URLs and email addresses. No parser is given a resource URL.
"""
from __future__ import annotations

from html import unescape
import re
import string


_MAX_TEXT = 16_384
_LITERAL = str.maketrans({char: f"&#{ord(char)};" for char in string.punctuation})
_FORMATTING = re.compile(r"(\*\*|__|\*|_|`)([^*_`\n]{1,512}?)\1")
_LINK = re.compile(r"!?\[([^\[\]\n]*)\](?:\([^()\n]*(?:\([^()\n]*\)[^()\n]*)*\)|\[[^\]\n]*\])")
_BLOCK = re.compile(r"^(#{1,6}|[-*+]|\d{1,4}[.)])\s+(.+)$")


def _inline(value):
    value = _LINK.sub(r"\1", value)
    parts, start = [], 0
    for match in _FORMATTING.finditer(value):
        parts.append(value[start:match.start()].translate(_LITERAL))
        marker, words = match.groups()
        if marker == "`":
            # Markdown code spans do not decode character references.
            parts.append("`" + words + "`")
        else:
            parts.append(marker + words.translate(_LITERAL) + marker)
        start = match.end()
    parts.append(value[start:].translate(_LITERAL))
    return "".join(parts)


def sanitize_notes(notes: str) -> str:
    if not isinstance(notes, str):
        return ""
    # Decoding here also makes re-sanitizing a previously cached result safe.
    text = unescape(notes[:_MAX_TEXT * 8])[:_MAX_TEXT]
    text = re.sub(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>", "", text)
    text = re.sub(r"<!--.*?(?:-->|$)|</?[a-zA-Z][\w:-]*(?:\s+[^<>]*)?\s*/?>", "", text,
                  flags=re.DOTALL)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f\u202a-\u202e\u2066-\u2069]", "", text.replace("\r\n", "\n").replace("\r", "\n"))
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^\[[^\]]+\]:", line):
            continue
        block = _BLOCK.fullmatch(line)
        if block:
            marker, label = block.groups()
            if marker in "-*+":
                marker = "-"
            lines.append(f"{marker} {_inline(label)}")
        elif line or not lines or lines[-1]:
            lines.append(_inline(line))
    return "\n".join(lines).strip()
