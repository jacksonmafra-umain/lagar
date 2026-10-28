"""Amendment register (SFSR) of Regeringskansliets rättsdatabaser into the corpus.

For each statute already in the corpus, reads the server-rendered register page
`https://rkrattsbaser.gov.se/sfsr?bet=<number>` and stores, in the statute's
frontmatter, the base statute's entry into force (`in_force`) and one
`amendments` entry per "Ändring, SFS ..." box. Every fetched page is hashed
into a committed manifest (`sources/sfsr-manifest.json`); the HTML itself is
never committed.
"""

import argparse
import hashlib
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from . import frontmatter, writer
from .http import Blocked, PoliteClient
from .sfs import NETWORK_ERRORS, USER_AGENT, StateError, _save_state
from .sfspdf import number_key

BASE = "https://rkrattsbaser.gov.se"
ROBOTS_URL = BASE + "/robots.txt"
REGISTER_URL = BASE + "/sfsr?bet={number}"
DEFAULT_MANIFEST = "sources/sfsr-manifest.json"
DEFAULT_STATE = "collector/data/sfsr-state.json"
DEFAULT_RATE = 2.0
MANIFEST_VERSION = 1
# Regeringsformen, Brottsbalken, Miljöbalken: the pilot agreed in issue #7.
PILOT = ("1974:152", "1962:700", "1998:808")

DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError)

_NUMBER = re.compile(r"N?\d{4}:\d+", re.ASCII)
_AMENDMENT_HEADER = re.compile(r"Ändring, SFS (\S+)")
_HEADER_NUMBER = re.compile(r"SFS-nummer · (\S+)")
_LEADING_DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(?![\d-])", re.ASCII)

# Register labels and the amendment keys they fill.
_AMENDMENT_FIELDS = {
    "Rubrik": "title",
    "Omfattning": "scope",
    "Förarbeten": "preparatory_works",
    "CELEX-nr": "celex",
}


@dataclass
class Register:
    number: str
    title: "str | None"
    fields: "dict[str, str]"
    amendments: "list[dict]"
    other_entries: "list[str]" = field(default_factory=list)

    @property
    def in_force(self):
        return parse_in_force(self.fields.get("Ikraft"))[0]


def _text(parts):
    return " ".join("".join(parts).split())


def parse_in_force(raw):
    """Return (iso_date_or_None, raw_or_None) for a register `Ikraft` value.

    The register mostly holds a plain date, sometimes followed by a note such
    as "överg.best." (transitional provisions apply). A value that does not
    start with a valid date (entry into force set by a later decision, or on a
    condition) keeps its raw text and gets no date.
    """
    raw = " ".join((raw or "").split()) or None
    if raw is None:
        return None, None
    match = _LEADING_DATE.match(raw)
    if not match:
        return None, raw
    try:
        date.fromisoformat(match.group(1))
    except ValueError:
        return None, raw
    return match.group(1), raw


class _RegisterParser(HTMLParser):
    """Boxes of the register page: `result-inner-box` for the statute itself,
    `result-inner-sub-box-container` per register entry (amendment)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.boxes = []  # (label_or_None, value_text, raw_text)
        self.entries = []  # {"header": str, "boxes": [...]}
        self._stack = []  # role per open div
        self._entry = None
        self._header = None
        self._box = None  # {"label": [...], "value": [...]}
        self._bold_depth = 0
        self._label_done = False

    def handle_starttag(self, tag, attrs):
        classes = (dict(attrs).get("class") or "").split()
        if tag == "div":
            role = None
            if "result-inner-sub-box-container" in classes:
                role = "entry"
                self._entry = {"header": None, "boxes": []}
            elif "result-inner-sub-box-header" in classes and self._entry is not None:
                role = "header"
                self._header = []
            elif "result-inner-sub-box" in classes or "result-inner-box" in classes:
                role = "box"
                self._box = {"label": [], "value": []}
                self._label_done = False
            self._stack.append(role)
        elif tag == "span" and self._box is not None and "bold" in classes and not self._label_done:
            self._bold_depth += 1

    def handle_endtag(self, tag):
        if tag == "span" and self._bold_depth:
            self._bold_depth -= 1
            if not self._bold_depth:
                self._label_done = True
            return
        if tag != "div" or not self._stack:
            return
        role = self._stack.pop()
        if role == "header":
            self._entry["header"] = _text(self._header)
            self._header = None
        elif role == "box":
            label, value = _text(self._box["label"]), _text(self._box["value"])
            box = (label[:-1].strip(), value) if label.endswith(":") else (None, _text([label, " ", value]))
            if self._entry is not None:
                self._entry["boxes"].append(box)
            else:
                self.boxes.append(box)
            self._box = None
        elif role == "entry":
            self.entries.append(self._entry)
            self._entry = None

    def handle_data(self, data):
        if self._header is not None:
            self._header.append(data)
        elif self._box is not None:
            (self._box["label"] if self._bold_depth else self._box["value"]).append(data)


def _labelled(boxes):
    fields = {}
    for label, value in boxes:
        if label and label not in fields:
            fields[label] = value
    return fields


def _amendment(number, fields):
    if not _NUMBER.fullmatch(number):
        raise ValueError(f"unexpected amendment number: {number!r}")
    in_force, raw = parse_in_force(fields.get("Ikraft"))
    entry = {"number": number}
    for label, key in _AMENDMENT_FIELDS.items():
        entry[key] = fields.get(label) or None
    entry["in_force"] = in_force
    entry["in_force_raw"] = raw
    return entry


def parse_register(html):
    """Parse one register page; ValueError when it is not a single-statute page."""
    parser = _RegisterParser()
    parser.feed(html)
    parser.close()
    number = None
    title = None
    for label, value in parser.boxes:
        if label is None:
            match = _HEADER_NUMBER.search(value)
            if match and number is None:
                number = match.group(1)
            elif title is None and not match:
                title = value or None
    if number is None:
        raise ValueError("not a register entry page (no SFS number)")
    amendments, other = [], []
    for entry in parser.entries:
        header = entry["header"] or ""
        match = _AMENDMENT_HEADER.fullmatch(header)
        if match:
            amendments.append(_amendment(match.group(1), _labelled(entry["boxes"])))
        else:
            other.append(header)
    return Register(number, title, _labelled(parser.boxes), amendments, other)


def apply_register(meta, register):
    """Return `meta` with the register's entry into force and amendment list."""
    updated = dict(meta)
    if register.in_force is not None:
        updated["in_force"] = register.in_force
    updated["amendments"] = register.amendments
    return updated


def doc_id(number):
    return "sfs-" + number.lower().replace(":", "-")


# --- manifest and state ----------------------------------------------------


def load_manifest(path):
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (ValueError, OSError):
        raise StateError(f"manifest corrupt: {path}") from None
    entries = loaded.get("entries") if isinstance(loaded, dict) else None
    if not isinstance(entries, list) or not all(
        isinstance(e, dict) and isinstance(e.get("number"), str) for e in entries
    ):
        raise StateError(f"manifest corrupt: {path}")
    return {entry["number"]: entry for entry in entries}


def save_manifest(path, entries):
    _save_state(path, {
        "version": MANIFEST_VERSION,
        "source": BASE,
        "entries": [entries[n] for n in sorted(entries, key=number_key)],
    })


def _load_state(path):
    state = {"failed": {}, "blocked": None}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (ValueError, OSError):
        raise StateError(f"state file corrupt: {path}") from None
    failed = loaded.get("failed", {}) if isinstance(loaded, dict) else None
    if not isinstance(failed, dict) or not all(isinstance(v, str) for v in failed.values()):
        raise StateError(f"state file corrupt: {path}")
    state["failed"] = failed
    return state


# --- network ---------------------------------------------------------------


class ListingError(Exception):
    """robots.txt could not be read; the run cannot continue."""


def _robots_allows(client):
    try:
        raw = client.get(ROBOTS_URL)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return True
        raise ListingError(f"robots.txt: HTTP {error.code}") from error
    except NETWORK_ERRORS as error:
        raise ListingError(f"robots.txt: {error}") from error
    parser = urllib.robotparser.RobotFileParser()
    parser.parse(raw.decode("utf-8", errors="replace").splitlines())
    return parser.can_fetch(USER_AGENT, BASE + "/sfsr")


def _process(client, number, corpus):
    """Fetch and apply one register page; returns (manifest_entry, written)."""
    path = writer.existing_path(doc_id(number), corpus)
    if path is None:
        raise ValueError("statute is not in the corpus")
    meta, body = frontmatter.load(path.read_text(encoding="utf-8"))
    url = REGISTER_URL.format(number=urllib.parse.quote(number, safe=":"))
    raw = client.get(url)
    retrieved_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    register = parse_register(raw.decode("utf-8"))
    if register.number != number:
        raise ValueError(f"register page shows {register.number!r}, expected {number}")
    updated = apply_register(meta, register)
    written = updated != meta
    if written:
        writer.write(updated, body, corpus)
    entry = {
        "number": number,
        "url": url,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "retrieved_at": retrieved_at,
        "amendments": len(register.amendments),
        "other_entries": register.other_entries,
    }
    return entry, written


# --- run -------------------------------------------------------------------


@dataclass
class RunSummary:
    written: "list[str]" = field(default_factory=list)
    unchanged: "list[str]" = field(default_factory=list)
    skipped: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False


def _sfs_number(value):
    if not _NUMBER.fullmatch(value):
        raise argparse.ArgumentTypeError(f"not an SFS number (YYYY:N): {value}")
    return value


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py sfsr")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--number", type=_sfs_number, action="append", metavar="YYYY:N",
                       help="statute to read (repeatable)")
    which.add_argument("--pilot", action="store_true",
                       help="Regeringsformen, Brottsbalken and Miljöbalken")
    which.add_argument("--all", action="store_true", help="every statute in the corpus")
    parser.add_argument("--refresh", action="store_true",
                        help="fetch again even when the manifest already has the statute")
    parser.add_argument("--limit", type=int, metavar="N", help="stop after N statutes")
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=float, default=DEFAULT_RATE, metavar="SECONDS")
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 0:
        parser.error("--limit must not be negative")
    if args.rate < DEFAULT_RATE:
        parser.error(f"--rate must be at least {DEFAULT_RATE} seconds")
    return args


def _corpus_numbers(corpus):
    numbers = []
    for path in sorted(Path(corpus).rglob("*.md")):
        try:
            meta, _ = frontmatter.load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        number = meta.get("number")
        if meta.get("layer") in ("fundamental", "sfs") and isinstance(number, str) \
                and _NUMBER.fullmatch(number) and meta.get("id") == doc_id(number):
            numbers.append(number)
    return sorted(set(numbers), key=number_key)


def _candidates(args):
    if args.pilot:
        return list(PILOT)
    if args.all:
        return _corpus_numbers(args.corpus)
    return list(dict.fromkeys(args.number))


def _write_report(path, summary):
    report = {
        "written": summary.written,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "blocked": summary.blocked,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    summary = RunSummary()
    entries = load_manifest(args.manifest)
    state = _load_state(args.state)
    state["blocked"] = None
    fetched = 0
    try:
        if not _robots_allows(client):
            state["blocked"] = "robots.txt disallows /sfsr"
            summary.blocked = True
            return summary
        for number in _candidates(args):
            if args.limit is not None and fetched >= args.limit:
                break
            if number in entries and not args.refresh:
                summary.skipped += 1
                continue
            try:
                entry, written = _process(client, number, args.corpus)
            except Blocked:
                raise
            except DOCUMENT_ERRORS as error:
                summary.failed.append(number)
                state["failed"][number] = f"{type(error).__name__}: {error}"
                continue
            finally:
                fetched += 1
            entries[number] = entry
            state["failed"].pop(number, None)
            (summary.written if written else summary.unchanged).append(number)
            save_manifest(args.manifest, entries)
            _save_state(args.state, state)
    except Blocked as error:
        state["blocked"] = str(error)
        summary.blocked = True
    finally:
        _save_state(args.state, state)
        if args.report:
            _write_report(args.report, summary)
    return summary


def main(argv, client=None):
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate)
    try:
        summary = run(client, args)
    except (ListingError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {len(summary.written)} written, {len(summary.unchanged)} unchanged, "
        f"{summary.skipped} skipped, {len(summary.failed)} failed"
        + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
