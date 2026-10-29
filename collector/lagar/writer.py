"""Build frontmatter from parsed Riksdagen data and write corpus files."""

import os
import re
import tempfile
import urllib.parse
from pathlib import Path

from . import frontmatter, schema
from .riksdagen import FUNDAMENTAL_LAWS, amendments, item_type, statute_title
from .vocabulary import TYPES

_SFS_NUMBER = re.compile(r"\bN?\d{4}:\d+")
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_ID_JUNK = re.compile(r"[^0-9a-z-]+")
# type -> (folder under the corpus root, id prefix left out of the file name)
_DIRS = {
    "fundamental_law": (("fundamental-laws",), "sfs-"),
    "act": (("sfs", "acts"), "sfs-"),
    "ordinance": (("sfs", "ordinances"), "sfs-"),
    "other_statute": (("sfs", "other"), "sfs-"),
    "agency_regulation": (("agency", "regulations"), ""),
    "case_report": (("case-law", "reports"), ""),
    "case_notice": (("case-law", "notices"), ""),
    "eu_regulation": (("eu", "regulations"), "eu-"),
    "eu_directive": (("eu", "directives"), "eu-"),
    "eu_decision": (("eu", "decisions"), "eu-"),
    "county_regulation": (("region", "county-regulations"), ""),
    "municipal_regulation": (("municipality", "regulations"), ""),
}


def _date(value):
    match = _DATE_PREFIX.match((value or "").strip())
    return match.group(1) if match else None


def corpus_id(dok_id):
    """Corpus id for a Riksdagen dok_id: old prints carry spaces and dots, a few lack the sfs- prefix."""
    slug = _ID_JUNK.sub("-", dok_id.lower()).strip("-")  # N-series ids arrive as sfs-N2026-1
    return slug if slug.startswith("sfs-") else "sfs-" + slug


def build_meta(item, parsed, raw_sha256, fetched_at):
    header = parsed.header
    if item.dok_id in FUNDAMENTAL_LAWS:
        title = FUNDAMENTAL_LAWS[item.dok_id]
    else:
        title = statute_title(item.title)
    type_ = item_type(item)
    changed = _SFS_NUMBER.search(header.get("Ändrad", ""))
    ministry = item.ministry or header.get("Departement/myndighet", "").strip() or None
    return {
        "id": corpus_id(item.dok_id),
        "title": title,
        "type": type_,
        "layer": TYPES[type_],
        "number": item.number,
        "issued": item.issued or _date(header.get("Utfärdad")),
        # Riksdagen texts have no entry-into-force header (`Ikraft` is never sent);
        # the SFSR register collector fills it, see keep_register_fields.
        "in_force": None,
        "repealed": _date(header.get("Upphävd")),
        "amended_by": [n for n in amendments(parsed.body) if n != item.number],
        "amended_through": changed.group(0) if changed else None,
        "reprinted_by": _SFS_NUMBER.findall(header.get("Omtryck", "")),
        "ministry": ministry,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": "https://data.riksdagen.se/dokument/" + urllib.parse.quote(item.dok_id),
        "source_sha256": raw_sha256,
        "fetched_at": fetched_at,
    }


def path_for(meta, root):
    folders, prefix = _DIRS[meta["type"]]
    return Path(root).joinpath(*folders, meta["id"].removeprefix(prefix) + ".md")


def existing_path(doc_id, root):
    """The stored file for `doc_id` under any type folder, or None."""
    found = [
        p for p in (path_for({"id": doc_id, "type": t}, root) for t in _DIRS) if p.exists()
    ]
    if len(found) > 1:
        raise ValueError(f"{doc_id} is stored more than once: {', '.join(map(str, found))}")
    return found[0] if found else None


# Fields filled by the SFSR register collector (sfsr.py), not from the Riksdagen text.
REGISTER_FIELDS = ("in_force", "amendments")


def keep_register_fields(meta, root):
    """Copy register-derived fields from the stored file into a freshly built `meta`.

    The Riksdagen text has no entry-into-force date and no amendment register, so
    a rewrite from it must not erase what the register collector stored.
    """
    path = existing_path(meta["id"], root)
    if path is None:
        return meta
    try:
        stored, _ = frontmatter.load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return meta
    merged = dict(meta)
    if merged.get("in_force") is None and stored.get("in_force") is not None:
        merged["in_force"] = stored["in_force"]
    if "amendments" in stored and "amendments" not in merged:
        merged["amendments"] = stored["amendments"]
    return merged


def _stale_paths(meta, root):
    """Existing files for the same id under another type folder."""
    current = path_for(meta, root)
    found = []
    for type_ in _DIRS:
        other = path_for({**meta, "type": type_}, root)
        if other != current and other.exists():
            found.append(other)
    return found


def write(meta, body_md, root):
    errors = schema.validate(meta)
    if errors:
        raise ValueError("invalid frontmatter: " + "; ".join(errors))
    path = path_for(meta, root)
    stale = _stale_paths(meta, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "---\n" + frontmatter.dump(meta) + "---\n" + body_md
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    for old in stale:
        old.unlink()
    return path
