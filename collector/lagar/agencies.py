"""Processing log of Swedish legal sources: AGENCIES.md and its JSON report.

The list of agency regulation series (författningssamlingar) and other legal
sources comes from lagrummet.se's `rattskalla` sitemap. It is fetched only with
`--refresh` (robots.txt checked, one request each, collector User-Agent) and
cached in `collector/data/rattskalla.json`, so the report is rebuilt offline.
Agency names, statuses and reasons for gaps are curated in
`collector/data/agencies.json`; document counts come from the corpus, county
and kommun configuration from `counties.json` and `municipalities.json`, the
kommun list from the app's bundled geo file.
"""

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

from . import progress
from .agency import _Robots
from .caselaw import NETWORK_ERRORS, USER_AGENT
from .http import Blocked, PoliteClient

SITEMAP_URL = "https://www.lagrummet.se/rattskalla-sitemap.xml"
SITEMAP_HOST = "https://www.lagrummet.se"
PAGE_PREFIX = SITEMAP_HOST + "/rattskalla/"
DEFAULT_CACHE = "collector/data/rattskalla.json"
DEFAULT_CURATED = "collector/data/agencies.json"
DEFAULT_REPORT = "collector/data/agencies-report.json"
DEFAULT_COUNTIES = "collector/data/counties.json"
DEFAULT_MUNICIPALITIES = "collector/data/municipalities.json"
DEFAULT_MUNICIPAL_MANIFEST = "sources/municipal-manifest.json"
DEFAULT_GEO = "app/shared/src/commonMain/composeResources/files/geo/sweden.json"
MIN_RATE = 1.0

STATUSES = {
    "collected": "collected",
    "collected_pdf": "collected: metadata and PDF links (text only in PDF, not extracted)",
    "partial": "partly collected",
    "blocked": "not collected: blocked by a WAF",
    "api_key": "not collected: API key needed",
    "robots": "not collected: robots.txt disallows",
    "no_adapter": "not collected: no adapter yet",
    "out_of_scope": "out of scope",
    "unclassified": "unclassified: new or unknown sitemap page",
}
_ORDER = list(STATUSES)
_NS = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
_COUNTY_SLUG = re.compile(r"^.+-lans-forfattningssamling-(\d{2})fs$")
_YEAR = re.compile(r"(\d{4}):\d+")


def parse_sitemap(raw):
    """[{slug, lastmod}] for every page under /rattskalla/, without the index page itself."""
    root = ET.fromstring(raw)
    pages = []
    for url in root.iter(f"{_NS}url"):
        loc = (url.findtext(f"{_NS}loc") or "").strip()
        if not loc.startswith(PAGE_PREFIX):
            continue
        slug = loc[len(PAGE_PREFIX):].strip("/")
        if slug:
            lastmod = (url.findtext(f"{_NS}lastmod") or "").strip()[:10] or None
            pages.append({"slug": slug, "lastmod": lastmod})
    return sorted(pages, key=lambda p: p["slug"])


def fetch_sitemap(client, now):
    """Fetch the sitemap politely; raise Blocked if robots.txt disallows it."""
    robots = _Robots(client, SITEMAP_HOST)
    if not robots.allows(SITEMAP_URL):
        raise Blocked(f"robots.txt disallows {SITEMAP_URL}")
    return {"source": SITEMAP_URL, "fetched_at": now, "pages": parse_sitemap(client.get(SITEMAP_URL))}


def tally_corpus(corpus):
    """Counts the report needs, from documents that pass schema validation."""
    counts = {"series": {}, "years": {}, "kommun": {}, "court": {}, "court_name": {}, "type": {}}
    for meta in progress._valid_metas(corpus):
        layer, number = meta["layer"], str(meta.get("number") or "")
        counts["type"][meta["type"]] = counts["type"].get(meta["type"], 0) + 1
        key = progress._series_key(meta)
        if key:
            counts["series"][key] = counts["series"].get(key, 0) + 1
            year = _YEAR.search(number)
            if year:
                counts["years"].setdefault(key, set()).add(int(year.group(1)))
        if layer == "municipality":
            code = meta["id"][:4]
            counts["kommun"][code] = counts["kommun"].get(code, 0) + 1
        if layer == "case_law" and meta.get("court"):
            court = meta["court"]
            counts["court"][court] = counts["court"].get(court, 0) + 1
            counts["court_name"].setdefault(court, meta.get("issuer") or court)
    return counts


def _years(counts, key):
    years = counts["years"].get(key)
    if not years:
        return None
    return str(min(years)) if min(years) == max(years) else f"{min(years)}–{max(years)}"


def _page_url(slug):
    return PAGE_PREFIX + slug + "/"


def build_report(sitemap, curated, counts, targets, counties, municipalities, municipal_manifest, geo):
    series_status = {}
    agencies, shared, sources, unclassified, county_slugs = [], [], [], [], {}
    target_by_series = {t["series"]: t["target"] for t in targets if t.get("series")}
    for page in sitemap["pages"]:
        slug = page["slug"]
        if slug in curated["series"]:
            entry = curated["series"][slug]
            documents = counts["series"].get(("agency", entry["series"]), 0)
            status = entry.get("status") or ("collected" if documents else "no_adapter")
            agencies.append({"series": entry["series"], "agency": entry["agency"], "status": status,
                             "documents": documents, "target": target_by_series.get(entry["series"]),
                             "note": entry.get("note"), "lagrummet": _page_url(slug)})
            series_status.setdefault(entry["series"], status)
        elif slug in curated["shared"]:
            shared.append({**curated["shared"][slug], "lagrummet": _page_url(slug)})
        elif slug in curated["sources"]:
            sources.append({**curated["sources"][slug], "lagrummet": _page_url(slug)})
        elif _COUNTY_SLUG.match(slug):
            county_slugs[_COUNTY_SLUG.match(slug).group(1)] = _page_url(slug)
        else:
            unclassified.append({"slug": slug, "status": "unclassified", "lagrummet": _page_url(slug)})
    agencies.sort(key=lambda a: (_ORDER.index(a["status"]), a["series"], a["agency"]))
    seen, unique_shared = set(), []
    for entry in sorted(shared, key=lambda s: (s["agency"], s["published_in"])):
        if (entry["agency"], entry["published_in"]) not in seen:
            seen.add((entry["agency"], entry["published_in"]))
            unique_shared.append({**entry, "status": series_status.get(entry["published_in"], "no_adapter")})
    sources.sort(key=lambda s: (_ORDER.index(s["status"]), s["layer"], s["name"]))

    county_rows = []
    for region in geo["regions"]:
        code = region["code"]
        config = counties["counties"].get(code)
        key = ("region", f"{code}FS")
        documents = counts["series"].get(key, 0)
        if config is None:
            status, text = "no_adapter", None
        else:
            status = "partial" if documents else "no_adapter"
            text = "HTML text" if config["layout"] == "pages" else "PDF links only"
        county_rows.append({"code": code, "county": region["name"], "series": f"{code}FS", "status": status,
                            "documents": documents, "years": _years(counts, key), "text": text,
                            "landing": config["landing"] if config else None,
                            "lagrummet": county_slugs.get(code)})

    gaps = {}
    for gap in municipal_manifest.get("gaps", []):
        gaps.setdefault(gap["municipality_code"], {}).setdefault(gap["reason"], 0)
        gaps[gap["municipality_code"]][gap["reason"]] += 1
    regions = {r["code"]: r["name"] for r in geo["regions"]}
    configured, missing = [], {}
    for kommun in sorted(geo["kommuner"], key=lambda k: k["code"]):
        config = municipalities["kommuner"].get(kommun["code"])
        if config is None:
            missing.setdefault(kommun["regionCode"], []).append(kommun["name"])
            continue
        documents = counts["kommun"].get(kommun["code"], 0)
        notes = [f"{n} documents not fetched: {reason}" for reason, n in sorted(gaps.get(kommun["code"], {}).items())]
        configured.append({"code": kommun["code"], "kommun": kommun["name"], "collection": config["collection"],
                           "status": "partial" if documents else "no_adapter", "documents": documents,
                           "note": "; ".join(notes) or None})
    missing_rows = [{"region_code": code, "county": regions[code], "kommuner": names}
                    for code, names in sorted(missing.items())]

    courts = [{"code": code, "court": counts["court_name"][code], "documents": n}
              for code, n in sorted(counts["court"].items(), key=lambda item: (-item[1], item[0]))]
    layers = {
        "sfs": sum(counts["type"].get(t, 0) for t in progress.SFS_TYPES),
        "fundamental": counts["type"].get("fundamental_law", 0),
        "eu": sum(n for t, n in counts["type"].items() if t.startswith("eu_")),
        "case_law": sum(counts["court"].values()),
    }
    summary = {}
    for entry in agencies:
        summary[entry["status"]] = summary.get(entry["status"], 0) + 1
    return {
        "sitemap": {"source": sitemap["source"], "fetched_at": sitemap["fetched_at"],
                    "pages": len(sitemap["pages"])},
        "summary": {"series": len(agencies), "by_status": summary,
                    "shared": len(unique_shared), "kommuner": len(geo["kommuner"]),
                    "kommuner_configured": len(configured)},
        "agency_series": agencies,
        "shared_series": unique_shared,
        "counties": county_rows,
        "municipalities": {"configured": configured, "not_configured": missing_rows},
        "courts": courts,
        "layers": layers,
        "other_sources": sources,
        "unclassified": unclassified,
    }


def _cell(value):
    return "-" if value is None else str(value).replace("|", "\\|")


def render_markdown(report):
    sm, summary = report["sitemap"], report["summary"]
    out = [
        "# Agencies and sources",
        "",
        "Which Swedish legal sources the corpus processes and which it does not, with the reason for each "
        "gap. Generated by `collector/agencies.py` from lagrummet.se's "
        f"[rättskällor sitemap]({sm['source']}) (fetched {sm['fetched_at'][:10]}, {sm['pages']} pages), "
        "the corpus and the collector configuration; do not edit by hand. Per-series counts are in "
        "[PROGRESS.md](PROGRESS.md) and the details of each gap in [COVERAGE.md](COVERAGE.md). "
        "More agency series are tracked in "
        "[#115](https://github.com/jacksonmafra-umain/lagar/issues/115).",
        "",
        "## Summary",
        "",
        f"{summary['series']} agency regulation series, {summary['shared']} agencies that publish in another "
        f"agency's series, {summary['kommuner_configured']} of {summary['kommuner']} kommuner configured.",
        "",
        "| agency series | count |",
        "| --- | ---: |",
    ]
    out += [f"| {STATUSES[s]} | {summary['by_status'][s]} |" for s in _ORDER if s in summary["by_status"]]
    layers = report["layers"]
    out += [
        "",
        f"Other layers in the corpus: {layers['fundamental']} fundamental laws, {layers['sfs']} SFS statutes, "
        f"{layers['case_law']} case-law documents from {len(report['courts'])} courts, {layers['eu']} EU documents "
        "(a curated list, from the Publications Office Cellar).",
        "",
        "## Agency regulation series",
        "",
        "| series | agency | status | documents | target | note |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for a in report["agency_series"]:
        out.append(f"| [{_cell(a['series'])}]({a['lagrummet']}) | {_cell(a['agency'])} | {STATUSES[a['status']]} | "
                   f"{a['documents']} | {_cell(a['target'])} | {_cell(a['note'])} |")
    out += [
        "",
        "## Agencies publishing in another series",
        "",
        "Their regulations are collected when the series they publish in is.",
        "",
        "| agency | published in | status of that series |",
        "| --- | --- | --- |",
    ]
    out += [f"| [{_cell(s['agency'])}]({s['lagrummet']}) | {s['published_in']} | {STATUSES[s['status']]} |"
            for s in report["shared_series"]]
    out += [
        "",
        "## County regulations (Länsstyrelserna)",
        "",
        "| code | county | series | status | documents | years | text |",
        "| --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for c in report["counties"]:
        county = f"[{c['county']}]({c['landing']})" if c["landing"] else c["county"]
        out.append(f"| {c['code']} | {county} | {c['series']} | {STATUSES[c['status']]} | {c['documents']} | "
                   f"{_cell(c['years'])} | {_cell(c['text'])} |")
    m = report["municipalities"]
    out += [
        "",
        "## Municipal regulations (kommuner)",
        "",
        f"{len(m['configured'])} of {summary['kommuner']} kommuner have a collector configuration "
        "(`collector/data/municipalities.json`); the others are not collected: no configuration yet.",
        "",
        "| code | kommun | collection | status | documents | note |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    out += [f"| {k['code']} | {k['kommun']} | {_cell(k['collection'])} | {STATUSES[k['status']]} | {k['documents']} | "
            f"{_cell(k['note'])} |" for k in m["configured"]]
    out += ["", "Not configured yet, per county:", ""]
    out += [f"- {row['county']} ({len(row['kommuner'])}): {', '.join(row['kommuner'])}" for row in m["not_configured"]]
    out += [
        "",
        "## Courts (case law)",
        "",
        "Referat and notiser from Sveriges Domstolar's rättspraxis API; rulings published in full, "
        "attachments and non-guiding decisions are left out by design.",
        "",
        "| code | court | documents |",
        "| --- | --- | ---: |",
    ]
    out += [f"| {c['code']} | {c['court']} | {c['documents']} |" for c in report["courts"]]
    out += [
        "",
        "## SFS, EU and other sources",
        "",
        "| source | layer | status | note |",
        "| --- | --- | --- | --- |",
    ]
    out += [f"| [{_cell(s['name'])}]({s['lagrummet']}) | {s['layer']} | {STATUSES[s['status']]} | {_cell(s.get('note'))} |"
            for s in report["other_sources"]]
    if report["unclassified"]:
        out += ["", "## Unclassified sitemap pages", "",
                "Pages the curated list in `collector/data/agencies.json` does not know yet:", ""]
        out += [f"- [{u['slug']}]({u['lagrummet']})" for u in report["unclassified"]]
    return "\n".join(out) + "\n"


def _read_json(path, default=None):
    path = Path(path)
    if not path.exists() and default is not None:
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv, client=None):
    parser = argparse.ArgumentParser(prog="agencies.py", description="Write AGENCIES.md and its JSON report.")
    parser.add_argument("--refresh", action="store_true", help="fetch the lagrummet.se sitemap again")
    parser.add_argument("--rate", type=float, default=2.0, help=f"seconds between requests (at least {MIN_RATE})")
    parser.add_argument("--cache", default=DEFAULT_CACHE)
    parser.add_argument("--curated", default=DEFAULT_CURATED)
    parser.add_argument("--corpus", default="corpus")
    parser.add_argument("--targets", default=progress.DEFAULT_TARGETS)
    parser.add_argument("--counties", default=DEFAULT_COUNTIES)
    parser.add_argument("--municipalities", default=DEFAULT_MUNICIPALITIES)
    parser.add_argument("--municipal-manifest", default=DEFAULT_MUNICIPAL_MANIFEST)
    parser.add_argument("--geo", default=DEFAULT_GEO)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--out", default="AGENCIES.md")
    args = parser.parse_args(argv)
    if args.rate < MIN_RATE:
        parser.error(f"--rate must be at least {MIN_RATE}")
    if args.refresh:
        client = client or PoliteClient(USER_AGENT, min_interval=args.rate)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            sitemap = fetch_sitemap(client, now)
        except (Blocked, *NETWORK_ERRORS) as error:
            print(f"sitemap not fetched: {error}", file=sys.stderr)
            return 1
        _write_json(args.cache, sitemap)
    sitemap = _read_json(args.cache)
    report = build_report(
        sitemap, _read_json(args.curated), tally_corpus(args.corpus), _read_json(args.targets),
        _read_json(args.counties), _read_json(args.municipalities),
        _read_json(args.municipal_manifest, {}), _read_json(args.geo),
    )
    _write_json(args.report, report)
    Path(args.out).write_text(render_markdown(report), encoding="utf-8")
    for status in _ORDER:
        if status in report["summary"]["by_status"]:
            print(f"{STATUSES[status]}: {report['summary']['by_status'][status]}")
    return 0
