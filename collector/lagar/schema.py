"""Stdlib-only validator for corpus frontmatter.

Implements the JSON Schema keywords used by docs/schema/frontmatter.schema.json
(type, required, enum, pattern, format, items, additionalProperties, properties)
plus the rule that `layer` must equal the layer of `type`.
"""

import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse

from .vocabulary import TYPES

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "docs" / "schema" / "frontmatter.schema.json"

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
        parsed = urlparse(value)
        return bool(parsed.scheme) and bool(parsed.netloc or parsed.path) and " " not in value
    return True


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
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")
        if "format" in schema and not _format_ok(schema["format"], value):
            errors.append(f"{path}: {value!r} is not a valid {schema['format']}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{i}]", errors)
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{key}: required key is missing")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    errors.append(f"{key}: unknown key")
        for key, sub in props.items():
            if key in value:
                _check(value[key], sub, key, errors)


def validate(frontmatter):
    """Return a list of human-readable errors; empty means valid."""
    errors = []
    _check(frontmatter, _load_schema(), "frontmatter", errors)
    type_, layer = frontmatter.get("type"), frontmatter.get("layer")
    if type_ in TYPES and isinstance(layer, str) and layer != TYPES[type_]:
        errors.append(f"layer: {layer!r} does not match type {type_!r} (expected {TYPES[type_]!r})")
    return errors
