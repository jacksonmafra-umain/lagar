"""Small HTML-to-Markdown converter for court publications (stdlib html.parser).

Handles headings, paragraphs, line breaks, bold, italics, lists and simple
tables. Links keep their text only. Unknown tags are dropped and their text
kept; script and style content is dropped.
"""

import re
from html.parser import HTMLParser

_HEADINGS = {f"h{n}": n for n in range(1, 7)}
_BLOCKS = {"p", "div", "blockquote", "li", "tr", "section", "article", "pre"}
_INLINE = {"strong": "**", "b": "**", "em": "*", "i": "*"}
_SKIP = {"script", "style", "head", "title"}
_INVISIBLE = re.compile("[­​‌‍⁠﻿]")
_SPACE = re.compile(r"[ \t\r\n\f\v  -   　]+")
_BREAK = "\x00"  # placeholder for <br>, survives whitespace collapsing


class _Converter(HTMLParser):
    def __init__(self, heading_offset):
        super().__init__(convert_charrefs=True)
        self.shift = heading_offset
        self.blocks = []
        self.parts = []  # inline text of the current block
        self.marks = []  # (tag, marker, index into parts)
        self.heading = None
        self.lists = []  # stack of [kind, counter]
        self.cells = None
        self.skip = 0

    # block handling
    def _flush(self):
        text = "".join(self.parts)
        self.parts, self.marks = [], []
        text = _SPACE.sub(" ", _INVISIBLE.sub("", text))
        text = re.sub(r" ?\x00 ?", _BREAK, text).strip(" " + _BREAK)
        if not text:
            return
        if self.heading:
            text = text.replace(_BREAK, " ").replace("**", "")
            self.blocks.append("#" * min(6, self.heading + self.shift) + " " + text)
            return
        text = text.replace(_BREAK, "\\\n")
        if text.startswith("#"):
            text = "\\" + text
        if self.lists:
            kind, counter = self.lists[-1]
            indent = "   " * (len(self.lists) - 1)
            bullet = f"{counter}." if kind == "ol" else "-"
            text = indent + bullet + " " + text.replace("\n", "\n" + indent + "  ")
            if self.blocks and self.blocks[-1].startswith("\x01"):
                self.blocks[-1] += "\n" + text
            else:
                self.blocks.append("\x01" + text)
            return
        self.blocks.append(text)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
            return
        if self.skip:
            return
        if tag in _HEADINGS:
            self._flush()
            self.heading = _HEADINGS[tag]
        elif tag in ("ul", "ol"):
            self._flush()
            self.lists.append([tag, 0])
        elif tag == "li":
            self._flush()
            if self.lists:
                self.lists[-1][1] += 1
        elif tag == "tr":
            self._flush()
            self.cells = []
        elif tag in ("td", "th"):
            if self.cells is not None:
                self.cells.append(len(self.parts))
        elif tag in _BLOCKS:
            self._flush()
        elif tag == "br":
            self.parts.append(_BREAK)
        elif tag in _INLINE:
            self.marks.append((tag, _INLINE[tag], len(self.parts)))

    def handle_startendtag(self, tag, attrs):
        if tag == "br" and not self.skip:
            self.parts.append(_BREAK)
        elif tag not in _SKIP:
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag in _HEADINGS:
            self._flush()
            self.heading = None
        elif tag in ("ul", "ol"):
            self._flush()
            if self.lists:
                self.lists.pop()
            if not self.lists and self.blocks and self.blocks[-1].startswith("\x01"):
                self.blocks[-1] = "\x02" + self.blocks[-1][1:]  # close: the next list starts anew
        elif tag == "tr":
            if self.cells:
                starts = self.cells + [len(self.parts)]
                cells = ["".join(self.parts[a:b]).strip() for a, b in zip(starts, starts[1:])]
                self.parts = [" | ".join(c for c in cells if c.strip())]
                self.marks = []
            self.cells = None
            self._flush()
        elif tag in ("td", "th") and self.cells is not None:
            self.parts.append(" ")
        elif tag in _BLOCKS:
            self._flush()
        elif tag in _INLINE:
            for i in range(len(self.marks) - 1, -1, -1):
                if self.marks[i][0] == tag:
                    _, marker, start = self.marks.pop(i)
                    inner = "".join(self.parts[start:])
                    core = _INVISIBLE.sub("", inner)
                    stripped = _SPACE.sub(" ", core).strip(" " + _BREAK)
                    if stripped:
                        lead = " " if _SPACE.match(core) else ""
                        trail = " " if _SPACE.match(core[-1:]) else ""
                        self.parts[start:] = [lead + marker + stripped + marker + trail]
                    break

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)

    def result(self):
        self._flush()
        return "\n\n".join(b.lstrip("\x01\x02") for b in self.blocks)


def to_markdown(html, heading_offset=0):
    """Markdown for an HTML fragment; headings are moved down by `heading_offset` levels."""
    converter = _Converter(heading_offset)
    converter.feed(html or "")
    converter.close()
    return converter.result()
