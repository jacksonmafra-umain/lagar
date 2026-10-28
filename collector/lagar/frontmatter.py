"""Minimal YAML-subset frontmatter: dump and load (exact inverses).

Values are scalars (string, null, true, false), flow lists of strings, or block
lists of flat mappings whose values are scalars:

    amendments:
      - number: "1965:280"
        title: null
"""

import re

from . import schema

_STRING = r'"(?:[^"\\]|\\.)*"'
_SCALAR = rf"(?:{_STRING}|null|true|false)"
_LIST = rf"\[(?:{_STRING}(?:, {_STRING})*)?\]"
_KEY = re.compile(r"[a-z0-9_]+")
_LINE = re.compile(rf"^({_KEY.pattern}): ({_SCALAR}|{_LIST})$")
_BLOCK = re.compile(rf"^({_KEY.pattern}):$")
_ITEM_FIRST = re.compile(rf"^  - ({_KEY.pattern}): ({_SCALAR})$")
_ITEM_NEXT = re.compile(rf"^    ({_KEY.pattern}): ({_SCALAR})$")
_STRING_RE = re.compile(_STRING)
_ESCAPES = {"\\": "\\", '"': '"', "n": "\n", "r": "\r", "t": "\t"}
_ESCAPED_CHARS = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\r": "\\r", "\t": "\\t"}
# Control characters without an escape would make the file unreadable or ambiguous.
_BAD_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _quote(value):
    if _BAD_CONTROL.search(value):
        raise ValueError(f"control character in string: {value!r}")
    escaped = "".join(_ESCAPED_CHARS.get(ch, ch) for ch in value)
    return f'"{escaped}"'


def _unquote(token):
    inner = token[1:-1]
    out = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\":
            i += 1
            if i >= len(inner) or inner[i] not in _ESCAPES:
                raise ValueError(f"unsupported escape in {token!r}")
            out.append(_ESCAPES[inner[i]])
        else:
            out.append(ch)
        i += 1
    return "".join(out)


def _scalar(value):
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _quote(value)
    if isinstance(value, list):
        if not all(isinstance(v, str) for v in value):
            raise ValueError("lists may only contain strings")
        return "[" + ", ".join(_quote(v) for v in value) + "]"
    raise ValueError(f"unsupported value type: {type(value).__name__}")


def _check_key(key):
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise ValueError(f"key cannot be read back by load(): {key!r}")


def _ordered(mapping, order):
    return [k for k in order if k in mapping] + [k for k in mapping if k not in order]


def _mapping_list(key, items, order):
    lines = [f"{key}:\n"]
    for item in items:
        if not item:
            raise ValueError(f"{key}: empty mapping cannot be read back")
        for i, sub in enumerate(_ordered(item, order)):
            _check_key(sub)
            value = item[sub]
            if isinstance(value, (list, dict)):
                raise ValueError(f"{key}.{sub}: mapping values must be scalars")
            lines.append(f"{'  - ' if i == 0 else '    '}{sub}: {_scalar(value)}\n")
    return "".join(lines)


def dump(meta):
    """Keys follow the schema's property order, unknown keys last in their own order."""
    props = schema._load_schema()["properties"]
    out = []
    for key in _ordered(meta, list(props)):
        _check_key(key)
        value = meta[key]
        if isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            order = list(props.get(key, {}).get("items", {}).get("properties", {}))
            out.append(_mapping_list(key, value, order))
        else:
            out.append(f"{key}: {_scalar(value)}\n")
    return "".join(out)


def _parse_value(token):
    if token == "null":
        return None
    if token == "true":
        return True
    if token == "false":
        return False
    if token.startswith("["):
        return [_unquote(t) for t in _STRING_RE.findall(token)]
    return _unquote(token)


def load(text):
    """Return (meta, body) for a file produced by `write`; ValueError otherwise."""
    if not text.startswith("---\n"):
        raise ValueError("missing frontmatter opening '---'")
    rest = text[4:]
    meta = {}
    block = None  # list of mappings being read
    pos = 0
    while True:
        end = rest.find("\n", pos)
        if end == -1:
            raise ValueError("missing frontmatter closing '---'")
        line = rest[pos:end]
        pos = end + 1
        if block is not None:
            first, more = _ITEM_FIRST.match(line), _ITEM_NEXT.match(line)
            if first:
                block.append({first.group(1): _parse_value(first.group(2))})
                continue
            if more and block:
                if more.group(1) in block[-1]:
                    raise ValueError(f"duplicate key in list item: {more.group(1)}")
                block[-1][more.group(1)] = _parse_value(more.group(2))
                continue
            if not block:
                raise ValueError(f"empty block list before line: {line!r}")
            block = None
        if line == "---":
            return meta, rest[pos:]
        match = _LINE.match(line) or _BLOCK.match(line)
        if not match:
            raise ValueError(f"unsupported frontmatter line: {line!r}")
        if match.group(1) in meta:
            raise ValueError(f"duplicate key: {match.group(1)}")
        if match.re is _BLOCK:
            block = meta[match.group(1)] = []
        else:
            meta[match.group(1)] = _parse_value(match.group(2))
