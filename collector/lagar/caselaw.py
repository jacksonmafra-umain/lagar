"""Resumable case-law collector: published summaries from Sveriges Domstolar.

Source: the open "Rättspraxis" API (https://rattspraxis.etjanst.domstol.se/api/v1,
OpenAPI spec at /openapi/puh-openapi.yaml). Only the anonymised publications
the courts issue as guiding case law are stored: referat (`case_report`) and
notiser (`case_notice`). Rulings published in full (DOM_ELLER_BESLUT), leave to
appeal and preliminary rulings are skipped, and attachments (/api/v1/bilagor)
are never requested: every request goes to the publication listing.
"""

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

from . import frontmatter, htmlmd
from .http import Blocked, PoliteClient
from .vocabulary import TYPES
from .writer import existing_path, path_for, write

USER_AGENT = "lagar-collector/0.1 (+https://github.com/jacksonmafra-umain/lagar)"
BASE = "https://rattspraxis.etjanst.domstol.se"
ROBOTS_URL = BASE + "/robots.txt"
LISTING_URL = BASE + "/api/v1/publiceringar"
SOURCE_URL = BASE + "/api/v1/publiceringar/{id}"
DEFAULT_STATE = "collector/data/case-law-state.json"
DEFAULT_PAGE_SIZE = 20
PROGRESS_EVERY = 50

# publiceringsform -> corpus type
FORMS = {"REFERAT": "case_report", "NOTIS": "case_notice"}
# avgörandetyp values that are never stored, whatever their publication form.
EXCLUDED_DECISIONS = frozenset({"EJ_VAGLEDANDE", "PROVNINGSTILLSTAND", "FORHANDSAVGORANDE"})

NETWORK_ERRORS = (
    urllib.error.URLError,
    TimeoutError,
    ConnectionError,
    http.client.HTTPException,
)
DOCUMENT_ERRORS = (ValueError, KeyError, TypeError, AttributeError)

# Mirrors the case-law number pattern in docs/schema/frontmatter.schema.json.
_REFERENCE = re.compile(r"[A-ZÅÄÖ]{2,5} \d{4}(:\d+| (s\.|ref\.|not\.|nr|N) \d+)")
_ECLI = re.compile(r"ECLI:[A-Z]{2}:[A-Z0-9.]{1,7}:\d{4}:[A-Za-z0-9.]{1,25}")
_COURT = re.compile(r"[A-ZÅÄÖ0-9]{2,10}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
_SPACE = re.compile(r"\s+")
_SLUG = str.maketrans({"å": "a", "ä": "a", "ö": "o", "é": "e", "ü": "u"})
# A Swedish personal identity number: (YY)YYMMDD, a - or + separator and four digits.
_PERSONNUMMER = re.compile(r"(?<![\d-])(?:\d{2})?(\d{2})(\d{2})(\d{2})[-+](\d{3})(\d)(?![\d-])")


class ListingError(Exception):
    """The listing (or robots.txt) could not be read; the run cannot continue."""


class StateError(Exception):
    """The state file is unreadable; never reset it silently."""


def _iso_date(value):
    try:
        if not _ISO_DATE.fullmatch(value):
            raise ValueError(value)
        date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not an ISO date (YYYY-MM-DD): {value}")
    return value


def _court(value):
    code = value.strip().upper()
    if not _COURT.fullmatch(code):
        raise argparse.ArgumentTypeError(f"not a court code (e.g. HDO, HFD): {value}")
    return code


def _non_negative(value):
    number = int(value)
    if number < 0:
        raise argparse.ArgumentTypeError(f"must not be negative: {value}")
    return number


def _positive(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"must be at least 1: {value}")
    return number


@dataclass
class RunSummary:
    written: int = 0
    unchanged: int = 0
    skipped: int = 0
    excluded: int = 0
    failed: "list[str]" = field(default_factory=list)
    blocked: bool = False
    written_numbers: "list[str]" = field(default_factory=list)
    latest_published: "str | None" = None
    complete: bool = False


def parse_args(argv):
    parser = argparse.ArgumentParser(prog="collect.py case-law")
    parser.add_argument(
        "--court", action="append", type=_court, metavar="CODE",
        help="court code from /api/v1/domstolar (HDO, HFD, ...); repeatable; default all",
    )
    parser.add_argument(
        "--from", dest="from_date", metavar="YYYY-MM-DD", type=_iso_date,
        help="only decisions dated on or after this day",
    )
    parser.add_argument(
        "--to", dest="to_date", metavar="YYYY-MM-DD", type=_iso_date,
        help="only decisions dated on or before this day",
    )
    parser.add_argument(
        "--since", "--changed-since", dest="since", metavar="YYYY-MM-DD", type=_iso_date,
        help="only publications published on or after this day (incremental sync)",
    )
    parser.add_argument("--limit", type=_non_negative, help="stop after N written documents")
    parser.add_argument("--report", metavar="FILE", help="write a JSON run report")
    parser.add_argument("--rate", type=float, default=1.0, metavar="SECONDS")
    parser.add_argument("--page-size", type=_positive, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--state", default=DEFAULT_STATE)
    parser.add_argument("--corpus", default="corpus")
    args = parser.parse_args(argv)
    if args.from_date and args.to_date and args.from_date > args.to_date:
        parser.error("--from is after --to")
    return args


# --- state -----------------------------------------------------------------

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


# --- mapping ---------------------------------------------------------------

def _clean(value):
    return _SPACE.sub(" ", value.replace(" ", " ")).strip() if isinstance(value, str) else ""


def canonical_bytes(item):
    """The publication as the API serialises it: sorted keys, compact, UTF-8.

    `GET /api/v1/publiceringar/{id}` returns exactly these bytes, so the hash
    of a listing entry equals the hash of the single-publication response.
    """
    return json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def references(item):
    """Report references in the schema's form, the API's order kept."""
    found = []
    for raw in list(item.get("referatNummerLista") or []) + [item.get("arbetsdomstolenDomsnummer")]:
        ref = _clean(raw)
        if ref and _REFERENCE.fullmatch(ref) and ref not in found:
            found.append(ref)
    return found


def report_number(item):
    """The reference used as `number`: the ordinal form (NJA 2026:38) when given, else the first."""
    refs = references(item)
    if not refs:
        raise ValueError("no report reference in the schema's form: "
                         + repr(item.get("referatNummerLista")))
    return next((r for r in refs if ":" in r), refs[0])


def corpus_id(number):
    """`NJA 2026 s. 435` -> `nja-2026-s-435`, `RÅ 2010 ref. 5` -> `ra-2010-ref-5`."""
    slug = re.sub(r"[^0-9a-z]+", "-", number.lower().translate(_SLUG)).strip("-")
    return slug


def corpus_type(item):
    """The corpus type, or None when the publication is not stored."""
    form = item.get("publiceringsform")
    if form not in FORMS or item.get("typ") in EXCLUDED_DECISIONS:
        return None
    return FORMS[form]


def _luhn_ok(digits):
    total = 0
    for i, ch in enumerate(digits):
        n = int(ch) * (2 if i % 2 == 0 else 1)
        total += n - 9 if n > 9 else n
    return total % 10 == 0


def personal_numbers(text):
    """Personal identity numbers (valid date and check digit) found in `text`."""
    found = []
    for m in _PERSONNUMMER.finditer(text or ""):
        yy, mm, dd, serial, check = m.groups()
        day = int(dd) - 60 if int(dd) > 60 else int(dd)  # samordningsnummer
        if 1 <= int(mm) <= 12 and 1 <= day <= 31 and _luhn_ok(yy + mm + dd + serial + check):
            found.append(m.group(0))
    return found


def build_meta(item, raw_sha256, fetched_at):
    type_ = corpus_type(item)
    if type_ is None:
        raise ValueError(f"not a referat or notis: {item.get('publiceringsform')}/{item.get('typ')}")
    court = item["domstol"]
    number = report_number(item)
    issued = _clean(item.get("avgorandedatum"))[:10] or None
    ecli = _clean(item.get("ecliNummer"))
    title = _clean(item.get("sammanfattning")) or _clean(item.get("benamning")) or number
    return {
        "id": corpus_id(number),
        "title": title,
        "type": type_,
        "layer": TYPES[type_],
        "number": number,
        "issued": issued,
        "in_force": None,
        "repealed": None,
        "amended_by": [],
        "amended_through": None,
        "reprinted_by": [],
        "ministry": None,
        "eli": None,
        "language": "sv",
        "authoritative": False,
        "source": SOURCE_URL.format(id=urllib.parse.quote(item["id"], safe="")),
        "source_sha256": raw_sha256,
        "fetched_at": fetched_at,
        "issuer": _clean(court.get("domstolNamn")) or None,
        "court": _clean(court.get("domstolKod")),
        "ecli": ecli if _ECLI.fullmatch(ecli) else None,
    }


def _reference_text(value):
    """A referenced publication; some arrive as a JSON list of references."""
    text = _clean(value)
    if text.startswith("["):
        try:
            refs = json.loads(text)
        except ValueError:
            return text
        if isinstance(refs, list) and all(isinstance(r, str) for r in refs):
            return ", ".join(_clean(r) for r in refs if _clean(r))
    return text


def _bullets(values):
    return "\n".join("- " + v for v in values if v)


def to_markdown(meta, item):
    """Body: a facts block, the indexed lists as sections, then the text itself."""
    facts = [
        ("Domstol", meta["issuer"] or meta["court"]),
        ("Avgörandedatum", meta["issued"]),
        ("Målnummer", ", ".join(_clean(m) for m in item.get("malNummerLista") or [] if _clean(m))),
        ("Referat", ", ".join(references(item))),
        ("Benämning", _clean(item.get("benamning"))),
        ("ECLI", _clean(item.get("ecliNummer"))),
    ]
    blocks = ["# " + meta["title"], "  \n".join(f"{k}: {v}" for k, v in facts if v)]

    def section(heading, values):
        text = _bullets(values)
        if text:
            blocks.extend(["## " + heading, text])

    summary = _clean(item.get("sammanfattning"))
    if summary and summary != meta["title"]:
        blocks.extend(["## Sammanfattning", summary])
    lagrum = []
    for entry in item.get("lagrumLista") or []:
        ref, sfs = _clean(entry.get("referens")), _clean(entry.get("sfsNummer"))
        if sfs and sfs not in ref:
            ref = f"{ref} (SFS {sfs})" if ref else f"SFS {sfs}"
        lagrum.append(ref)
    section("Lagrum", lagrum)
    section("Nyckelord", [_clean(v) for v in item.get("nyckelordLista") or []])
    section("Rättsområden", [_clean(v) for v in item.get("rattsomradeLista") or []])
    section("Förarbeten", [_clean(v) for v in item.get("forarbeteLista") or []])
    section("Litteratur", [
        ", ".join(p for p in (_clean(e.get("forfattare")), _clean(e.get("titel"))) if p)
        for e in item.get("litteraturLista") or []
    ])
    section("Hänvisningar", [_reference_text(e.get("fritext")) for e in item.get("hanvisadePubliceringarLista") or []])
    section("Europarättsliga avgöranden", [_clean(v) for v in item.get("europarattsligaAvgorandenLista") or []])
    text = htmlmd.to_markdown(item.get("innehall") or "", heading_offset=2)
    if text:
        blocks.extend(["## " + ("Referat" if meta["type"] == "case_report" else "Notis"), text])
    return "\n\n".join(b for b in blocks if b) + "\n"


# --- listing and run -------------------------------------------------------

def listing_url(court, since, page, page_size):
    params = [("publiceringsformer", ",".join(FORMS).lower())]
    if court:
        params.append(("domstolkod", court))
    if since:
        params.append(("publicerad_fran_och_med", since))
    params += [("page", str(page)), ("pagesize", str(page_size))]
    return LISTING_URL + "?" + urllib.parse.urlencode(params, safe=",")


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
    return parser.can_fetch(USER_AGENT, LISTING_URL)


def _pages(client, court, args):
    """Listing pages, newest decision first (the API's default order)."""
    page = 0
    while True:
        url = listing_url(court, args.since, page, args.page_size)
        try:
            items = json.loads(client.get(url))
        except Blocked:
            raise
        except (*NETWORK_ERRORS, ValueError) as error:
            raise ListingError(f"listing page {page}: {error}") from error
        if not isinstance(items, list) or not all(isinstance(i, dict) for i in items):
            raise ListingError(f"listing page {page}: not a list of publications")
        yield items
        if len(items) < args.page_size:
            return
        page += 1


def _court_candidates(client, court, args):
    previous = None
    for items in _pages(client, court, args):
        for item in items:
            decided = str(item.get("avgorandedatum") or "")[:10]
            if previous is not None and decided > previous:
                # Stopping at --from is only safe when the listing is newest first.
                raise ListingError("listing is not sorted by decision date, newest first")
            previous = decided or previous
            if args.from_date and decided and decided < args.from_date:
                return  # newest first: everything after this is older
            if args.to_date and decided > args.to_date:
                continue
            yield item


def _candidates(client, args):
    for court in args.court or [None]:
        yield from _court_candidates(client, court, args)


def _unchanged(meta, body, corpus):
    """True when the stored file has the same body and frontmatter apart from `fetched_at`.

    The body is compared too, so a mapping change reaches documents whose
    source bytes did not change.
    """
    try:
        stored, stored_body = frontmatter.load(path_for(meta, corpus).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    stored.pop("fetched_at", None)
    return stored_body == body and stored == {k: v for k, v in meta.items() if k != "fetched_at"}


def _stored_source(doc_id, corpus):
    path = existing_path(doc_id, corpus)
    if path is None:
        return None
    try:
        stored, _ = frontmatter.load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return stored.get("source")


def _store(item, corpus):
    """Map and write one publication; returns (meta, written)."""
    raw = canonical_bytes(item)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = build_meta(item, hashlib.sha256(raw).hexdigest(), fetched_at)
    other = _stored_source(meta["id"], corpus)
    if other is not None and other != meta["source"]:
        raise ValueError(f"{meta['number']} is already stored from {other}")
    body = to_markdown(meta, item)
    found = personal_numbers(body)
    if found:
        raise ValueError(f"possible personal identity number in the text ({len(found)} found)")
    if _unchanged(meta, body, corpus):
        return meta, False
    write(meta, body, corpus)
    return meta, True


def _already_done(state, item, corpus):
    if state["done"].get(item.get("id")) != item.get("publiceringstid"):
        return False
    try:
        meta = {"id": corpus_id(report_number(item)), "type": corpus_type(item)}
    except ValueError:
        return False
    return meta["type"] is not None and path_for(meta, corpus).exists()


def next_since(summary, since):
    """Where the next incremental run starts: the newest publication day seen.

    The day itself is collected again (publication times are finer than the
    API's date filter); re-reading it is idempotent. A run that stopped early
    (--limit, a block) never moves past `since`, because the listing is ordered
    by decision date and unseen publications may be older.
    """
    if not summary.complete or not summary.latest_published:
        return since
    day = summary.latest_published[:10]
    return max(day, since) if since else day


def _write_report(path, summary, since=None):
    report = {
        "written": summary.written_numbers,
        "unchanged": summary.unchanged,
        "skipped": summary.skipped,
        "excluded": summary.excluded,
        "failed": summary.failed,
        "blocked": summary.blocked,
        "latest_published": summary.latest_published,
        "next_since": next_since(summary, since),
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(client, args):
    summary = RunSummary()
    state = _load_state(args.state)
    state["blocked"] = None

    def finish(blocked=None):
        if blocked:
            summary.blocked = True
            state["blocked"] = blocked
        _save_state(args.state, state)
        if args.report:
            _write_report(args.report, summary, args.since)
        return summary

    try:
        if not _robots_allows(client):
            return finish("robots.txt disallows /api/v1/publiceringar")
    except Blocked as error:
        return finish(str(error))

    processed = 0
    try:
        for item in _candidates(client, args):
            if args.limit is not None and summary.written >= args.limit:
                break
            pub_id = str(item.get("id") or "")
            published = item.get("publiceringstid")
            if isinstance(published, str):
                summary.latest_published = max(summary.latest_published or "", published)
            if corpus_type(item) is None:
                summary.excluded += 1
                continue
            if _already_done(state, item, args.corpus):
                summary.skipped += 1
                continue
            try:
                meta, changed = _store(item, args.corpus)
            except DOCUMENT_ERRORS as error:
                summary.failed.append(pub_id)
                state["failed"][pub_id] = f"{type(error).__name__}: {error}"
            else:
                if changed:
                    summary.written += 1
                    summary.written_numbers.append(meta["number"])
                else:
                    summary.unchanged += 1
                if isinstance(published, str):
                    state["done"][pub_id] = published
                state["failed"].pop(pub_id, None)
            processed += 1
            _save_state(args.state, state)
            if processed % PROGRESS_EVERY == 0:
                print(
                    f"{processed} processed: {summary.written} written, "
                    f"{summary.skipped} skipped, {len(summary.failed)} failed",
                    flush=True,
                )
        else:
            # A filtered run saw only part of the window; it never moves the marker.
            summary.complete = not (args.court or args.from_date or args.to_date)
    except Blocked as error:
        return finish(str(error))
    return finish()


def main(argv, client=None):
    if argv and argv[0] in ("case-law", "caselaw"):
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
        f"{summary.skipped} skipped, {summary.excluded} excluded, "
        f"{len(summary.failed)} failed" + (", BLOCKED" if summary.blocked else ""),
        flush=True,
    )
    if summary.failed:
        print("failed: " + ", ".join(summary.failed), flush=True)
    if summary.blocked:
        print("blocked: see state file", file=sys.stderr)
        return 2
    return 0
