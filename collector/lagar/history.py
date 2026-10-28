"""Metadata-only history of statutes as a `git fast-import` stream.

One commit for the statute itself and one per amendment in its register
(`amendments` in the frontmatter, see sfsr.py). Each commit writes the
statute's metadata as it stood after that event: identity, entry into force,
and the amendments applied so far. Historical text is never reconstructed;
the files on the history branch hold frontmatter only.

Commit dates, in order of preference:

1. the amendment's entry into force from the register (`in_force`);
2. the publication date of the amending act in the SFS PDF manifest
   (`sources/sfs-pdf-manifest.json`, from 2018 on);
3. 1 January of the amending act's SFS year, when neither is known.

The statute's own commit uses its `in_force`, else its `issued` date. An
amendment dated before its statute's own commit is moved to that date, and a
date before 1970 is stored as 1970-01-01 because git cannot record earlier
dates. Each commit body states the date used and where it came from.
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from . import frontmatter
from .sfsr import PILOT, doc_id
from .sfspdf import number_key
from .writer import existing_path

DEFAULT_BRANCH = "history/pilot"
DEFAULT_AUTHOR = "lagar history <history@lagar.invalid>"
DEFAULT_PDF_MANIFEST = "sources/sfs-pdf-manifest.json"
GIT_EPOCH = date(1970, 1, 1)
SNAPSHOT_KEYS = ("id", "title", "type", "layer", "number", "issued", "in_force")


@dataclass
class Event:
    when: date
    statute: str
    index: int  # -1 for the statute itself, else its position in the register
    subject: str
    notes: "list[str]"


def _iso(value):
    try:
        return date.fromisoformat(value) if value else None
    except (TypeError, ValueError):
        return None


def load_published(path):
    """SFS number -> publication date from the SFS PDF manifest (may be missing)."""
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    published = {}
    for entry in loaded.get("entries", []):
        when = _iso(entry.get("published"))
        if when and isinstance(entry.get("number"), str):
            published[entry["number"]] = when
    return published


def _amendment_date(amendment, published):
    when = _iso(amendment.get("in_force"))
    if when:
        raw = amendment.get("in_force_raw")
        detail = f' (register value "{raw}")' if raw and raw != amendment["in_force"] else ""
        return when, f"entry into force from the SFS register{detail}"
    reason = "the SFS register gives no entry into force"
    if amendment.get("in_force_raw"):
        reason = f'the SFS register entry into force "{amendment["in_force_raw"]}" is not a date'
    when = published.get(amendment["number"])
    if when:
        return when, f"publication date from the SFS PDF manifest; {reason}"
    year = int(amendment["number"].lstrip("N").split(":", 1)[0])
    return date(year, 1, 1), f"start of the SFS year; {reason} and no issue date is known"


def _base_date(meta):
    when = _iso(meta.get("in_force"))
    if when:
        return when, "entry into force from the SFS register"
    when = _iso(meta.get("issued"))
    if when:
        return when, "issue date; no entry into force is known"
    raise ValueError(f"{meta['number']}: neither in_force nor issued is set")


def events_for(meta, published):
    if meta.get("amendments") is None:
        raise ValueError(f"{meta['number']}: no amendment register in the corpus; run collect.py sfsr first")
    base_when, base_source = _base_date(meta)
    title = meta["title"]
    events = [Event(base_when, meta["number"], -1, f"{title}: in force",
                    [f"Date: {base_when}, {base_source}."])]
    for index, amendment in enumerate(meta["amendments"]):
        when, source = _amendment_date(amendment, published)
        notes = []
        body = [amendment.get("title"), amendment.get("scope") and "Scope: " + amendment["scope"]]
        notes.append("\n".join(line for line in body if line))
        notes.append(f"Date: {when}, {source}.")
        if when < base_when:
            notes.append(f"Moved to {base_when}, the statute's own date, to keep the order.")
            when = base_when
        events.append(Event(when, meta["number"], index,
                            f"{title}: amended by SFS {amendment['number']}", [n for n in notes if n]))
    return events


def _snapshot(meta, applied):
    snap = {k: meta.get(k) for k in SNAPSHOT_KEYS}
    ordered = [a for i, a in enumerate(meta["amendments"]) if i in applied]
    snap["amended_through"] = ordered[-1]["number"] if ordered else None
    snap["amendments"] = ordered
    return "---\n" + frontmatter.dump(snap) + "---\n"


def _timestamp(when):
    if when < GIT_EPOCH:
        return 0, f"Stored as 1970-01-01: git cannot record the real date {when}."
    moment = datetime(when.year, when.month, when.day, tzinfo=timezone.utc)
    return int(moment.timestamp()), None


def _data(text):
    raw = text.encode("utf-8")
    return b"data %d\n" % len(raw) + raw + b"\n"


def load_statutes(corpus, numbers):
    statutes = []
    for number in numbers:
        path = existing_path(doc_id(number), corpus)
        if path is None:
            raise ValueError(f"{number}: not in the corpus")
        meta, _ = frontmatter.load(path.read_text(encoding="utf-8"))
        statutes.append((Path(path).relative_to(Path(corpus).parent).as_posix(), meta))
    return statutes


def plan(statutes, published):
    """[(event, path, file_text)] in commit order."""
    by_number = {meta["number"]: (path, meta) for path, meta in statutes}
    events = [e for _, meta in statutes for e in events_for(meta, published)]
    events.sort(key=lambda e: (e.when, number_key(e.statute), e.index))
    applied = {number: set() for number in by_number}
    steps = []
    for event in events:
        path, meta = by_number[event.statute]
        if event.index >= 0:
            applied[event.statute].add(event.index)
        steps.append((event, path, _snapshot(meta, applied[event.statute])))
    return steps


def stream(steps, branch, author):
    out = [b"reset refs/heads/" + branch.encode() + b"\n"]
    for mark, (event, path, text) in enumerate(steps, start=1):
        seconds, clamp = _timestamp(event.when)
        notes = [*event.notes, *([clamp] if clamp else [])]
        message = event.subject + "\n\n" + "\n\n".join(notes) + "\n"
        stamp = f"{author} {seconds} +0000\n".encode()
        out.append(b"commit refs/heads/" + branch.encode() + b"\n")
        out.append(b"mark :%d\n" % mark)
        out.append(b"author " + stamp + b"committer " + stamp)
        out.append(_data(message))
        if mark > 1:
            out.append(b"from :%d\n" % (mark - 1))
        out.append(b"M 100644 inline " + path.encode("utf-8") + b"\n")
        out.append(_data(text))
        out.append(b"\n")
    return b"".join(out)


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="history.py")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--number", action="append", metavar="YYYY:N")
    which.add_argument("--pilot", action="store_true",
                       help="Regeringsformen, Brottsbalken and Miljöbalken")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--pdf-manifest", default=DEFAULT_PDF_MANIFEST)
    parser.add_argument("--branch", default=DEFAULT_BRANCH)
    parser.add_argument("--author", default=DEFAULT_AUTHOR, metavar='"NAME <EMAIL>"')
    parser.add_argument("--out", metavar="FILE", help="write the stream here instead of stdout")
    parser.add_argument("--dry-run", action="store_true",
                        help="list the commits instead of writing the stream")
    return parser.parse_args(argv)


def main(argv, stdout=None):
    args = parse_args(argv)
    stdout = stdout or sys.stdout
    numbers = list(PILOT) if args.pilot else list(dict.fromkeys(args.number))
    try:
        steps = plan(load_statutes(args.corpus, numbers), load_published(args.pdf_manifest))
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if args.dry_run:
        for event, path, _ in steps:
            print(f"{event.when}  {path}  {event.subject}", file=stdout)
        print(f"{len(steps)} commits on {args.branch}", file=stdout)
        return 0
    data = stream(steps, args.branch, args.author)
    if args.out:
        Path(args.out).write_bytes(data)
    else:
        stdout.buffer.write(data)
        stdout.flush()
    return 0
