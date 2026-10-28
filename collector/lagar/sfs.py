"""Resumable SFS collector: Riksdagen listing and texts into corpus Markdown."""

import argparse
import hashlib
import http.client
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path

from . import frontmatter
from .http import Blocked, PoliteClient
from .riksdagen import (
    FUNDAMENTAL_LAWS,
    ListingItem,
    item_type,
    parse_listing,
    parse_text,
    statute_title,
    to_markdown,
)
from .writer import build_meta, corpus_id, keep_register_fields, path_for, write

USER_AGENT = "lagar-collector/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
BASE = "https://data.riksdagen.se"
ROBOTS_URL = BASE + "/robots.txt"
LISTING_URL = (
    BASE + "/dokumentlista/?doktyp=sfs&utformat=json&sz=200&p={page}"
    "&sort={sort}&sortorder={order}"
)
TEXT_URL = BASE + "/dokument/{dok_id}.text"
PROGRESS_EVERY = 50
DEFAULT_STATE = "collector/data/sfs-state.json"

NETWORK_ERRORS = (
    urllib.error.URLError,  # includes HTTPError
    TimeoutError,
    ConnectionError,
    http.client.HTTPException,
)
# Per-document failures: recorded and skipped so one bad document never stalls a run.
DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError, KeyError, TypeError)


class ListingError(Exception):
    """The listing (or robots.txt) could not be read; the run cannot continue."""


class StateError(Exception):
    """The state file is unreadable; never reset it silently."""


_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_TIMESTAMP = re.compile(r"(\d{4}-\d{2}-\d{2})( \d{2}:\d{2}:\d{2})?", re.ASCII)


def _iso_date(value):
    try:
        if not _ISO_DATE.fullmatch(value):
            raise ValueError(value)
        date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO date (YYYY-MM-DD): {value}")
    return value


def _timestamp(value):
    """A Riksdagen `systemdatum` bound: `YYYY-MM-DD` or `YYYY-MM-DD HH:MM:SS`."""
    match = _TIMESTAMP.fullmatch(value)
    try:
        if not match:
            raise ValueError(value)
        datetime.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"not a timestamp (YYYY-MM-DD[ HH:MM:SS]): {value}"
        )
    return value


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


@dataclass
class RunSummary:
    written: int = 0
    unchanged: int = 0
    skipped: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False
    written_numbers: "list[str]" = field(default_factory=list)
    latest_systemdatum: "str | None" = None
    retry_from: "str | None" = None  # oldest systemdatum of a network failure


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py sfs")
    parser.add_argument("--fundamental", action="store_true")
    parser.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD", type=_iso_date)
    parser.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD", type=_iso_date)
    parser.add_argument("--limit", type=_non_negative)
    parser.add_argument("--since", metavar="YYYY-MM-DD", type=_iso_date)
    parser.add_argument(
        "--changed-since", metavar="TIMESTAMP", type=_timestamp,
        help="only documents whose systemdatum is at or after TIMESTAMP, newest first",
    )
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=float, default=1.0, metavar="SECONDS")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--corpus", default="corpus")
    args = parser.parse_args(argv)
    if args.changed_since and (
        args.fundamental or args.since or args.from_date or args.to_date
    ):
        parser.error(
            "--changed-since cannot be combined with --fundamental, --since, --from or --to"
        )
    return args


def _load_state(path):
    state = {"done": {}, "failed": {}, "blocked": None}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
    except (ValueError, OSError):
        raise StateError(f"state file corrupt: {path}") from None
    valid = isinstance(loaded, dict) and all(
        isinstance(loaded.get(k, {}), dict)
        and all(isinstance(v, str) for v in loaded.get(k, {}).values())
        for k in ("done", "failed")
    )
    if valid and not isinstance(loaded.get("blocked"), (str, type(None))):
        valid = False
    if not valid:
        raise StateError(f"state file corrupt: {path}")
    for key in state:
        if key in loaded:
            state[key] = loaded[key]
    return state


def _save_state(path, state):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2, sort_keys=True)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def _robots_allows(client):
    """True when allowed; False when robots.txt disallows the API paths."""
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
    return all(
        parser.can_fetch(USER_AGENT, BASE + path)
        for path in ("/dokument", "/dokumentlista")
    )


def _listing_pages(client, args):
    page, pages = 1, 1
    while page <= pages:
        if args.changed_since:
            url = LISTING_URL.format(page=page, sort="systemdatum", order="desc")
        else:
            url = LISTING_URL.format(page=page, sort="datum", order="asc")
        if args.from_date:
            url += f"&from={args.from_date}"
        if args.to_date:
            url += f"&tom={args.to_date}"
        try:
            items, pages = parse_listing(client.get(url))
        except Blocked:
            raise
        except (*NETWORK_ERRORS, ValueError, KeyError, TypeError) as error:
            raise ListingError(f"listing page {page}: {error}") from error
        yield items
        page += 1


def _fundamental_item(dok_id, parsed, text):
    header = parsed.header
    first_line = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return ListingItem(
        dok_id=dok_id,
        number=header.get("SFS nr", "").strip(),
        title=statute_title(first_line),
        issued=header.get("Utfärdad", "").strip() or None,
        systemdatum="",
        ministry=header.get("Departement/myndighet", "").strip() or None,
    )


def _unchanged(meta, corpus):
    """True when the stored file has the same frontmatter apart from `fetched_at`.

    The body derives from the source bytes, which `source_sha256` covers.
    """
    path = path_for(meta, corpus)
    try:
        stored, _ = frontmatter.load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    stored.pop("fetched_at", None)
    return stored == {k: v for k, v in meta.items() if k != "fetched_at"}


def _store(client, dok_id, item, corpus):
    """Fetch, parse and write one document; returns (item, written).

    A document whose stored frontmatter matches apart from `fetched_at` is left
    untouched, so a re-run does not churn the corpus.
    """
    raw = client.get(TEXT_URL.format(dok_id=urllib.parse.quote(dok_id)))
    if raw.lstrip().startswith(b"<dokumentstatus"):
        # Digitised OCR prints come back as status XML wrapping styled HTML; record them as a coverage gap.
        raise ValueError("digitised print with no plain text")
    text = raw.decode("utf-8")
    parsed = parse_text(text)
    if item is None:
        item = _fundamental_item(dok_id, parsed, text)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_meta(item, parsed, hashlib.sha256(raw).hexdigest(), fetched_at)
    meta = keep_register_fields(meta, corpus)
    if _unchanged(meta, corpus):
        return item, False
    write(meta, to_markdown(meta["title"], parsed.body), corpus)
    return item, True


def _already_done(state, item, corpus):
    if state["done"].get(item.dok_id) != item.systemdatum:
        return False
    meta = {"id": corpus_id(item.dok_id), "type": item_type(item)}
    return path_for(meta, corpus).exists()


def _candidates(client, args, state, summary):
    """Yield (dok_id, item_or_None); counts skipped items as a side effect."""
    if args.fundamental:
        for dok_id in FUNDAMENTAL_LAWS:
            yield dok_id, None
        return
    previous = None
    for items in _listing_pages(client, args):
        for item in items:
            if args.changed_since:
                if previous is not None and item.systemdatum > previous:
                    # Stopping early is only safe when the listing really is newest first.
                    raise ListingError("listing is not sorted by systemdatum, newest first")
                previous = item.systemdatum
                if item.systemdatum < args.changed_since:
                    return  # newest first: everything after this is older
                summary.latest_systemdatum = max(
                    summary.latest_systemdatum or "", item.systemdatum
                )
            if args.since and item.systemdatum[:10] < args.since:
                continue
            if _already_done(state, item, args.corpus):
                summary.skipped += 1
                continue
            yield item.dok_id, item


def _write_report(path, summary):
    report = {
        "written": summary.written_numbers,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "failed": summary.failed,
        "blocked": summary.blocked,
        "latest_systemdatum": summary.latest_systemdatum,
        "retry_from": summary.retry_from,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    state["blocked"] = None

    def finish_blocked(message):
        summary.blocked = True
        state["blocked"] = message
        _save_state(args.state, state)
        if args.report:
            _write_report(args.report, summary)
        return summary

    try:
        if not _robots_allows(client):
            return finish_blocked("robots.txt disallows /dokument or /dokumentlista")
    except Blocked as error:
        return finish_blocked(str(error))

    processed = 0
    try:
        for dok_id, item in _candidates(client, args, state, summary):
            if args.limit is not None and summary.written >= args.limit:
                break
            try:
                stored, changed = _store(client, dok_id, item, args.corpus)
            except Blocked:
                raise
            except DOCUMENT_ERRORS as error:
                summary.failed.append(dok_id)
                if isinstance(error, NETWORK_ERRORS) and item and item.systemdatum:
                    summary.retry_from = min(summary.retry_from or item.systemdatum, item.systemdatum)
                state["failed"][dok_id] = f"{type(error).__name__}: {error}"
            else:
                if changed:
                    summary.written += 1
                    summary.written_numbers.append(stored.number)
                else:
                    summary.unchanged += 1
                if stored.systemdatum:
                    state["done"][dok_id] = stored.systemdatum
                else:
                    # --fundamental has no listing systemdatum; an empty marker
                    # would never match a later listing run anyway.
                    state["done"].pop(dok_id, None)
                state["failed"].pop(dok_id, None)
            processed += 1
            _save_state(args.state, state)
            if args.limit is not None and summary.written >= args.limit:
                break
            if processed % PROGRESS_EVERY == 0:
                print(
                    f"{processed} processed: {summary.written} written, "
                    f"{summary.skipped} skipped, {len(summary.failed)} failed",
                    flush=True,
                )
    except Blocked as error:
        return finish_blocked(str(error))
    _save_state(args.state, state)
    if args.report:
        _write_report(args.report, summary)
    return summary


def main(argv, client=None):
    if argv and argv[0] == "sfs":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate)
    try:
        summary = run(client, args)
    except (ListingError, StateError) as error:
        print(f"error: {error}", file=sys.stderr, flush=True)
        return 1
    print(
        f"done: {summary.written} written, {summary.unchanged} unchanged, "
        f"{summary.skipped} skipped, "
        f"{len(summary.failed)} failed" + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
