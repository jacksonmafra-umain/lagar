"""Resumable SFS collector: Riksdagen listing and texts into corpus Markdown."""

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.error
import urllib.robotparser
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .http import Blocked, PoliteClient
from .riksdagen import (
    FUNDAMENTAL_LAWS,
    ListingItem,
    classify,
    parse_listing,
    parse_text,
    to_markdown,
)
from .writer import build_meta, path_for, write

USER_AGENT = "lagar-collector/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
BASE = "https://data.riksdagen.se"
ROBOTS_URL = BASE + "/robots.txt"
LISTING_URL = (
    BASE + "/dokumentlista/?doktyp=sfs&utformat=json&sz=200&p={page}"
    "&sort=datum&sortorder=asc"
)
TEXT_URL = BASE + "/dokument/{dok_id}.text"
PROGRESS_EVERY = 50
DEFAULT_STATE = "collector/data/sfs-state.json"

NETWORK_ERRORS = (
    urllib.error.URLError,  # includes HTTPError
    TimeoutError,
    ConnectionError,
)
DOCUMENT_ERRORS = NETWORK_ERRORS + (UnicodeDecodeError, ValueError)


class ListingError(Exception):
    """The listing (or robots.txt) could not be read; the run cannot continue."""


@dataclass
class RunSummary:
    written: int = 0
    skipped: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py sfs")
    parser.add_argument("--fundamental", action="store_true")
    parser.add_argument("--from", dest="from_date", metavar="YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", metavar="YYYY-MM-DD")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--since", metavar="YYYY-MM-DD")
    parser.add_argument("--rate", type=float, default=1.0, metavar="SECONDS")
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--corpus", default="corpus")
    return parser.parse_args(argv)


def _load_state(path):
    state = {"done": {}, "failed": {}, "blocked": None}
    try:
        loaded = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return state
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
        url = LISTING_URL.format(page=page)
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
    first_line = next((l.strip() for l in text.splitlines() if l.strip()), "")
    return ListingItem(
        dok_id=dok_id,
        number=header.get("SFS nr", "").strip(),
        title=first_line,
        issued=header.get("Utfärdad", "").strip() or None,
        systemdatum="",
        ministry=header.get("Departement/myndighet", "").strip() or None,
    )


def _store(client, dok_id, item, corpus):
    """Fetch, parse and write one document; returns the item that was written."""
    raw = client.get(TEXT_URL.format(dok_id=dok_id))
    text = raw.decode("utf-8")
    parsed = parse_text(text)
    if item is None:
        item = _fundamental_item(dok_id, parsed, text)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_meta(item, parsed, hashlib.sha256(raw).hexdigest(), fetched_at)
    write(meta, to_markdown(meta["title"], parsed.body), corpus)
    return item


def _already_done(state, item, corpus):
    if state["done"].get(item.dok_id) != item.systemdatum:
        return False
    title = item.title.strip().removesuffix(";").strip()
    meta = {"id": item.dok_id, "type": classify(title, item.dok_id)}
    return path_for(meta, corpus).exists()


def _candidates(client, args, state, summary):
    """Yield (dok_id, item_or_None); counts skipped items as a side effect."""
    if args.fundamental:
        for dok_id in FUNDAMENTAL_LAWS:
            yield dok_id, None
        return
    for items in _listing_pages(client, args):
        for item in items:
            if args.since and item.systemdatum[:10] < args.since:
                continue
            if _already_done(state, item, args.corpus):
                summary.skipped += 1
                continue
            yield item.dok_id, item


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    state["blocked"] = None

    def finish_blocked(message):
        summary.blocked = True
        state["blocked"] = message
        _save_state(args.state, state)
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
                stored = _store(client, dok_id, item, args.corpus)
            except Blocked:
                raise
            except DOCUMENT_ERRORS as error:
                summary.failed.append(dok_id)
                state["failed"][dok_id] = f"{type(error).__name__}: {error}"
            else:
                summary.written += 1
                state["done"][dok_id] = stored.systemdatum
                state["failed"].pop(dok_id, None)
            processed += 1
            _save_state(args.state, state)
            if processed % PROGRESS_EVERY == 0:
                print(
                    f"{processed} processed: {summary.written} written, "
                    f"{summary.skipped} skipped, {len(summary.failed)} failed"
                )
    except Blocked as error:
        return finish_blocked(str(error))
    _save_state(args.state, state)
    return summary


def main(argv, client=None):
    if argv and argv[0] == "sfs":
        argv = argv[1:]
    args = parse_args(argv)
    if client is None:
        client = PoliteClient(USER_AGENT, min_interval=args.rate)
    try:
        summary = run(client, args)
    except ListingError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(
        f"done: {summary.written} written, {summary.skipped} skipped, "
        f"{len(summary.failed)} failed" + (", BLOCKED" if summary.blocked else "")
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed))
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
