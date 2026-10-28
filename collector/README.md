# lagar collector

Collects Swedish statutes (SFS) from Riksdagen open data into `corpus/` Markdown files, and
records a SHA-256 manifest of the authoritative SFS PDFs.
Python standard library only.

## Usage

Run from the repository root (`-I` ignores `PYTHONPATH`, so use the entry script):

```
python3 -I collector/collect.py sfs --fundamental
python3 -I collector/collect.py sfs [--from YYYY-MM-DD --to YYYY-MM-DD] [--limit N] \
    [--since YYYY-MM-DD] [--rate SECONDS] [--state collector/data/sfs-state.json] \
    [--corpus corpus] [--report FILE]
python3 -I collector/collect.py sfs --changed-since "YYYY-MM-DD[ HH:MM:SS]" [--report FILE]
```

- `--fundamental` fetches only the four fundamental laws (always refetched).
- `--since` keeps listing items whose `systemdatum` is on or after the date.
- `--changed-since` pages the listing newest-first by `systemdatum` and stops at the first
  document older than the bound, so an incremental sync reads only the pages it needs. It
  cannot be combined with `--fundamental` or `--since`.
- `--report` writes a JSON summary: written SFS numbers, unchanged/skipped counts, failed ids,
  `blocked` and the newest `systemdatum` seen (`latest_systemdatum`).
- `--limit` stops after N written documents.
- `--rate` is the minimum interval between requests (default 1.0 s).

A refetched document whose source SHA-256 matches the stored file is left untouched (counted as
unchanged), so reruns never churn `fetched_at`.

## Scheduled sync

`.github/workflows/sync-sfs.yml` runs daily, and on manual dispatch with an optional earlier
`since`. It starts from `main`, or from the `data/sfs-sync` branch while a sync pull request is
open, and collects with `--changed-since` from the marker in `collector/data/sfs-sync.json`.

When the corpus changed, the workflow:
- refreshes the audit and progress reports;
- moves the marker to the newest `systemdatum` seen, or to `retry_from` when a document failed
  with a network error;
- adds one `data(sfs):` commit to `data/sfs-sync`, opening a pull request if none is open.

The marker only moves inside that commit, so a failed run, a rejected push or an abandoned pull
request never skips documents: the next run collects them again. A run that finds nothing new
commits nothing. Failures are listed in the run summary and in the commit body.

Two GitHub constraints apply. The workflow needs "Allow GitHub Actions to create and approve pull
requests" enabled in the repository settings. Pull requests opened with the default token do not
trigger other workflows.

## Listing cap

Riksdagen serves at most 10,000 listing results (50 pages of 200); page 51 answers HTTP 400.
A full run therefore needs date windows, e.g. `--to 2016-12-31` and then `--from 2016-12-22`
(overlap is harmless: finished documents are skipped).

## Resume

State is kept in `collector/data/sfs-state.json` (git-ignored) and rewritten atomically
after every document: `{"done": {id: systemdatum}, "failed": {id: error}, "blocked": null|msg}`.
A document is skipped when its `systemdatum` matches the state and its corpus file exists.
Per-document errors are recorded under `failed` and the run continues; rerun to retry them.
Digitised OCR prints that have no plain-text version are recorded there too, as a coverage gap.

Items sharing a date may shift between listing pages during a long run; a rerun picks up any miss.

## Authoritative PDFs

The SFS published on <https://svenskforfattningssamling.se> is the authoritative version. The
`sfspdf` command records a SHA-256 manifest of its PDFs; it never changes `corpus/`.

```
python3 -I collector/collect.py sfspdf --year YYYY [--year YYYY ...] [--limit N] [--cache DIR] \
    [--manifest sources/sfs-pdf-manifest.json] [--state collector/data/sfspdf-state.json] \
    [--rate SECONDS] [--report FILE]
python3 -I collector/collect.py sfspdf --rss [--report FILE]
```

- `--year` walks the year index (`regulations/<year>/index.html`, 15 acts per page, newest
  first) through its "next" links; `--rss` reads only the RSS feed of recent acts, for an
  incremental run.
- Each act's detail page (`doc/<year><number>.html`) is read for its PDF links. An act can have
  several files, for example a correction sheet (rättelseblad). Every PDF is downloaded once and
  hashed; a response that does not start with `%PDF-`, a detail page showing another number and a
  link off the site are recorded as failures.
- The manifest `sources/sfs-pdf-manifest.json` is committed. Entries are sorted by year and
  number; each has `number`, `detail_url`, `published` and `files` (`url`, `bytes`, `sha256`,
  `content_type`, `retrieved_at`). Numbers already in the manifest are skipped, so reruns
  fetch only new acts.
- PDF bytes are never committed. `--cache DIR` keeps them as `DIR/<year>/<file>.pdf`; use the
  git-ignored `sources/cache/`.
- `--limit` stops after N new entries. The manifest is saved every 25 entries and when the run
  ends, including on an error or interrupt.
- `--report` writes `{"recorded": [...], "skipped": n, "failed": [...], "blocked": bool}`.
- The state file (git-ignored) keeps `failed` (number to error) and `blocked`.

The site has no robots.txt (HTTP 404); one is honoured if it appears. The PDFs are signed by
the publisher, but the signature is not verified or recorded. `Last-Modified` and `ETag` change
nightly, so they are not used. A full crawl of 2018 to today is about 30,000 requests.

## Exit codes

- 0: finished (failures are listed, not fatal)
- 1: the listing or robots.txt could not be read, or the state file is corrupt
- 2: blocked (HTTP 403 or robots.txt disallow); recorded in the state file

## Tests

```
python3 -I -m unittest discover -s collector/tests -t collector -v
```
