"""Stdlib-only validator for corpus frontmatter.

Implements the JSON Schema keywords used by docs/schema/frontmatter.schema.json
(type, required, enum, const, pattern, format, items, maxItems,
additionalProperties, properties, allOf, if/then/else) plus the cross-field
rules in `_cross_checks`: `layer` must equal the layer of `type`, and the
regional codes must agree with the number.
"""

import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from .vocabulary import TYPES

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "schema" / "frontmatter.schema.json"

# RFC 3986 scheme, a non-empty remainder, and no whitespace or control characters.
_URI = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*:([^\s\x00-\x1f\x7f]+)")

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "boolean": lambda v: isinstance(v, bool),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}


def _load_schema():
    with open(SCHEMA_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def _format_ok(fmt, value):
    if fmt == "date":
        try:
            return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)) and bool(date.fromisoformat(value))
        except ValueError:
            return False
    if fmt == "date-time":
        if not value.endswith("Z"):
            return False
        try:
            datetime.fromisoformat(value[:-1] + "+00:00")
            return True
        except ValueError:
            return False
    if fmt == "uri":
        match = _URI.fullmatch(value)
        if not match:
            return False
        rest = match.group(1)
        if rest.startswith("//"):  # hierarchical URI needs an authority
            return bool(urlparse(value).netloc)
        return True
    return True


def _valid(value, schema):
    errors = []
    _check(value, schema, "frontmatter", errors)
    return not errors


def _check(value, schema, path, errors):
    types = schema.get("type")
    if types is not None:
        names = [types] if isinstance(types, str) else types
        if not any(_TYPE_CHECKS[n](value) for n in names):
            errors.append(f"{path}: expected {' or '.join(names)}, got {type(value).__name__}")
            return
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} is not one of {schema['enum']}")
        return
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: {value!r} is not {schema['const']!r}")
        return
    if isinstance(value, str):
        if "pattern" in schema and not re.compile(schema["pattern"], re.ASCII).fullmatch(value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")
        if "format" in schema and not _format_ok(schema["format"], value):
            errors.append(f"{path}: {value!r} is not a valid {schema['format']}")
    if isinstance(value, list) and "maxItems" in schema and len(value) > schema["maxItems"]:
        errors.append(f"{path}: must have at most {schema['maxItems']} items, got {len(value)}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        prefix = "" if path == "frontmatter" else path + "."
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{prefix}{key}: required key is missing")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{prefix}{key}: unknown key")
        for key, sub in props.items():
            if key in value:
                _check(value[key], sub, prefix + key, errors)
    for sub in schema.get("allOf", ()):
        _check(value, sub, path, errors)
    if "if" in schema:
        branch = schema.get("then") if _valid(value, schema["if"]) else schema.get("else")
        if branch is not None:
            _check(value, branch, path, errors)


def validate(frontmatter):
    """Return a list of human-readable errors; empty means valid."""
    if not isinstance(frontmatter, dict):
        return [f"frontmatter: expected object, got {type(frontmatter).__name__}"]
    errors = []
    _check(frontmatter, _load_schema(), "frontmatter", errors)
    errors.extend(_cross_checks(frontmatter))
    return errors


def _cross_checks(meta):
    errors = []
    type_, layer = meta.get("type"), meta.get("layer")
    if type_ in TYPES and isinstance(layer, str) and layer != TYPES[type_]:
        errors.append(f"layer: {layer!r} does not match type {type_!r} (expected {TYPES[type_]!r})")
    region, kommun, number = meta.get("region_code"), meta.get("municipality_code"), meta.get("number")
    if type_ == "county_regulation" and isinstance(region, str) and isinstance(number, str):
        if not number.startswith(region + "FS "):
            errors.append(f"region_code: {region!r} does not match the series of number {number!r}")
    if isinstance(region, str) and isinstance(kommun, str) and not kommun.startswith(region):
        errors.append(f"municipality_code: {kommun!r} is not in region {region!r}")
    return errors
