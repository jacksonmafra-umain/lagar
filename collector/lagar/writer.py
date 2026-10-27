"""Build frontmatter from parsed Riksdagen data and write corpus files."""

import os
import re
import tempfile
from pathlib import Path

from . import frontmatter, schema
from .riksdagen import FUNDAMENTAL_LAWS, amendments, classify, clean_title, to_markdown
from .vocabulary import TYPES

_SFS_NUMBER = re.compile(r"\d{4}:\d+")
_DATE_PREFIX = re.compile(r"^(\d{4}-\d{2}-\d{2})")
_DIRS = {
    "fundamental_law": ("fundamental-laws",),
    "act": ("sfs", "acts"),
    "ordinance": ("sfs", "ordinances"),
    "other_statute": ("sfs", "other"),
}


def _date(value):
    match = _DATE_PREFIX.match((value or "").strip())
    return match.group(1) if match else None


def build_meta(item, parsed, raw_sha256, fetched_at):
    header = parsed.header
    if item.dok_id in FUNDAMENTAL_LAWS:
        title = FUNDAMENTAL_LAWS[item.dok_id]
    else:
        title = clean_title(item.title).removesuffix(";").strip()
    type_ = classify(clean_title(item.title).removesuffix(";").strip(), item.dok_id)
    changed = _SFS_NUMBER.search(header.get("Ändrad", ""))
    ministry = item.ministry or header.get("Departement/myndighet", "").strip() or None
    return {
        "id": item.dok_id.lower(),  # N-series ids arrive as sfs-N2026-1
        "title": title,
        "type": type_,
        "layer": TYPES[type_],
        "number": item.number,
        "issued": item.issued or _date(header.get("Utfärdad")),
        "in_force": _date(header.get("Ikraft")),
        "repealed": _date(header.get("Upphävd")),
        "amended_by": amendments(parsed.body),
        "amended_through": changed.group(0) if changed else None,
        "reprinted_by": _SFS_NUMBER.findall(header.get("Omtryck", "")),
        "ministry": ministry,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": f"https://data.riksdagen.se/dokument/{item.dok_id}",
        "source_sha256": raw_sha256,
        "fetched_at": fetched_at,
    }


def path_for(meta, root):
    name = meta["id"].removeprefix("sfs-") + ".md"
    return Path(root).joinpath(*_DIRS[meta["type"]], name)


def write(meta, body_md, root):
    errors = schema.validate(meta)
    if errors:
        raise ValueError("invalid frontmatter: " + "; ".join(errors))
    path = path_for(meta, root)
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
    return path
