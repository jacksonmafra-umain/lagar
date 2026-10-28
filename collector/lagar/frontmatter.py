"""Minimal YAML-subset frontmatter: dump and load (exact inverses)."""

import re

from . import schema

_STRING = r'"(?:[^"\\]|\\.)*"'
_SCALAR = rf"(?:{_STRING}|null|true|false)"
_LIST = rf"\[(?:{_STRING}(?:, {_STRING})*)?\]"
_LINE = re.compile(rf"^([a-z0-9_]+): ({_SCALAR}|{_LIST})$")
_STRING_RE = re.compile(_STRING)
_ESCAPES = {"\\": "\\", '"': '"', "n": "\n"}


def _quote(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
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


def dump(meta):
    order = schema._load_schema()["required"]
    keys = [k for k in order if k in meta] + [k for k in meta if k not in order]
    return "".join(f"{key}: {_scalar(meta[key])}\n" for key in keys)


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
    pos = 0
    while True:
        end = rest.find("\n", pos)
        if end == -1:
            raise ValueError("missing frontmatter closing '---'")
        line = rest[pos:end]
        pos = end + 1
        if line == "---":
            return meta, rest[pos:]
        match = _LINE.match(line)
        if not match:
            raise ValueError(f"unsupported frontmatter line: {line!r}")
        if match.group(1) in meta:
            raise ValueError(f"duplicate key: {match.group(1)}")
        meta[match.group(1)] = _parse_value(match.group(2))
