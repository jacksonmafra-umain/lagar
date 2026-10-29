# lagar collector

Collects Swedish statutes (SFS) from Riksdagen open data into `corpus/` Markdown files,
records a SHA-256 manifest of the authoritative SFS PDFs, adds each statute's amendment
register from SFSR, writes a metadata-only amendment history for git, and collects the
published case law of the Swedish courts.
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

## Amendment register (SFSR)

Riksdagen texts carry no entry-into-force date and only mention amending acts inline. The SFS
register (SFSR) of Regeringskansliets rättsdatabaser lists every amending act of a statute. The
`sfsr` command reads it for statutes already in the corpus:

```
python3 -I collector/collect.py sfsr --pilot | --number YYYY:N [--number ...] | --all \
    [--refresh] [--limit N] [--corpus corpus] [--manifest sources/sfsr-manifest.json] \
    [--state collector/data/sfsr-state.json] [--rate SECONDS] [--report FILE]
```

- The source is `https://rkrattsbaser.gov.se/sfsr?bet=<number>`, one server-rendered HTML page
  per statute, read with `html.parser`. The site has no robots.txt (one is honoured if it
  appears); `--rate` defaults to, and may not go below, 2 s between requests.
- `--pilot` reads Regeringsformen (1974:152), Brottsbalken (1962:700) and Miljöbalken
  (1998:808); `--all` reads every statute in the corpus in number order. A statute that is not
  in the corpus is recorded as failed without a request.
- Only the frontmatter changes; the body is kept byte for byte. `in_force` gets the statute's
  own `Ikraft` (left as it is when the register has none) and `amendments` gets one entry per
  "Ändring, SFS ..." box, in register order: `number`, `title` (Rubrik), `scope`
  (Omfattning), `preparatory_works` (Förarbeten), `celex` (CELEX-nr), `in_force` and
  `in_force_raw`. Whitespace is collapsed; missing fields are `null`.
- `Ikraft` values: `in_force` is the date the value starts with, `in_force_raw` the value as
  written. `1983-07-01 överg.best.` (transitional provisions apply) gives `1983-07-01`; a value
  that does not start with a date, such as an entry into force set by a later government
  decision, gives `in_force: null` and keeps the text. Missing values (most entries before
  about 1982) give `null` for both.
- Register entries with another header than "Ändring" are not stored; they are listed in the
  manifest entry's `other_entries`. A page that shows another statute, or is not a single
  register entry (for example a search result), is recorded as failed.
- The committed manifest `sources/sfsr-manifest.json` keeps, per statute, `number`, `url`,
  `bytes`, `sha256` and `retrieved_at` of the fetched page, the number of amendments and
  `other_entries`. Statutes already in it are skipped unless `--refresh` is given, so a bulk
  run can be resumed. The HTML is not stored.
- `--report` writes `{"written": [...], "unchanged": [...], "skipped": n, "failed": [...],
  "blocked": bool}`. The state file (git-ignored) keeps `failed` (number to error) and
  `blocked`; an HTTP 403 or a robots.txt disallow stops the run (exit code 2).

The `sfs` collector never erases this data: when it rewrites a statute from Riksdagen it keeps
the stored `in_force` and `amendments`. A new successor site (`beta.rkrattsbaser.gov.se`) is
being built, so the page layout may change.

## Amendment history

`collector/history.py` turns the register into history: one commit for each statute and one
per amendment, dated at entry into force, as a `git fast-import` stream. The files on the
history branch hold frontmatter only (identity, `in_force`, `amended_through` and the
amendments applied so far). Historical text is not reconstructed: no open source has it.

```
python3 -I collector/history.py --pilot --dry-run          # list the commits
python3 -I collector/history.py --pilot --out build/history.fi
git fast-import --quiet < build/history.fi                 # creates history/pilot
```

- Commit dates: the amendment's entry into force; else its publication date in
  `sources/sfs-pdf-manifest.json` (acts from 2018 on); else 1 January of its SFS year. The
  statute's own commit uses its `in_force`, else `issued`. Each commit body names the date and
  its source.
- An amendment dated before its statute's own commit moves to that date. Dates before 1970
  are stored as 1970-01-01 (git cannot record earlier dates); the body keeps the real date.
  Amendments that enter into force in the future get future commit dates.
- Commits from several statutes are merged into one branch in date order. The stream starts
  with `reset`, so it always builds the branch from scratch; to rebuild an existing branch
  run `git fast-import --force`. `--branch` and `--author` change the defaults
  (`history/pilot`, `lagar history <history@lagar.invalid>`).
- Statutes without `amendments` in the corpus are refused: run `collect.py sfsr` first.

The branch is not pushed by any workflow.

## Case law

The `case-law` command (alias `caselaw`) collects the anonymised summaries that the courts
publish as guiding case law, from the open API of Sveriges Domstolar (dataset "Rättspraxis från
Sveriges Domstolar", CC0):

```
python3 -I collector/collect.py case-law [--court CODE ...] [--from YYYY-MM-DD] [--to YYYY-MM-DD] \
    [--since YYYY-MM-DD] [--limit N] [--page-size N] [--rate SECONDS] \
    [--state collector/data/case-law-state.json] [--corpus corpus] [--report FILE]
```

- Source: `GET https://rattspraxis.etjanst.domstol.se/api/v1/publiceringar?publiceringsformer=referat,notis`
  (OpenAPI spec at `/openapi/puh-openapi.yaml`), paged with `page` (from 0) and `pagesize`
  (default 20), newest decision first. Each listing entry is the whole publication, so the listing
  is the only endpoint requested.
- Only referat (`case_report`, `corpus/case-law/reports/`) and notiser (`case_notice`,
  `corpus/case-law/notices/`) are stored. Rulings published in full (`DOM_ELLER_BESLUT`), leave to
  appeal (`PROVNINGSTILLSTAND`), preliminary rulings (`FORHANDSAVGORANDE`) and non-guiding decisions
  (`EJ_VAGLEDANDE`) are skipped and counted as `excluded`. Attachments (`/api/v1/bilagor/...`) are
  never requested; tests assert that every request goes to the listing.
- The texts are the courts' anonymised publications. As a safeguard, a publication whose text
  contains a personal identity number (valid date and check digit) is recorded as failed and not
  written.
- `--court` takes the codes of `GET /api/v1/domstolar` (`HDO` Högsta domstolen, `HFD` Högsta
  förvaltningsdomstolen, `ADO`, `MIOD`, ...); repeat it for several courts. `--from`/`--to` bound
  the decision date (`avgorandedatum`); the run stops at the first decision older than `--from`.
  `--since` (alias `--changed-since`) asks the API for publications published on or after the day
  (`publicerad_fran_och_med`), for an incremental sync.
- Mapping: `number` is the report reference, the ordinal form (`NJA 2026:38`) when the API gives
  one, else the first reference (`HFD 2026 ref. 43`, `HFD 2026 not. 24`, `NJA 2019 s. 2`); `id` is
  its slug (`nja-2026-38`, `hfd-2026-ref-43`, `ra-2010-ref-5`). `title` is the summary
  (`sammanfattning`, the report's headline), `issued` the decision date, `court` the court code,
  `issuer` the court name, `ecli` the ECLI when it has the standard form. `source` is
  `/api/v1/publiceringar/{id}` and `source_sha256` hashes the publication as the API serialises it
  (sorted keys, compact UTF-8 JSON), which is byte for byte the response of that URL.
- Body: a facts block (court, decision date, case numbers, all references, name, ECLI), then
  sections for Lagrum (with SFS numbers), Nyckelord, Rättsområden, Förarbeten, Litteratur,
  Hänvisningar and Europarättsliga avgöranden when present, then the text (`innehall`, HTML
  converted to Markdown, headings moved down two levels) under `## Referat` or `## Notis`.
- A publication without a reference in the schema's form (`[A-ZÅÄÖ]{2,5} YYYY:N` or
  `YYYY s./ref./not./nr/N N`), or with a reference already stored from another publication, is
  recorded as failed.
- State (git-ignored) is `{"done": {publication id: publiceringstid}, "failed": {id: error},
  "blocked": null|msg}`; a publication is skipped when its `publiceringstid` matches and its file
  exists. A document whose frontmatter (apart from `fetched_at`) and body are unchanged is left
  untouched. After a mapping change, delete the state file and rerun to rewrite affected files.
- `--limit` stops after N written documents (unchanged ones do not count). `--report` writes
  `{"written": [...], "unchanged": n, "skipped": n, "excluded": n, "failed": [...], "blocked": bool,
  "latest_published": "..."}`.
- The site has no robots.txt (HTTP 404); one is honoured if it appears. An HTTP 403 stops the run
  (exit code 2). Entries may shift between pages while the courts publish; a rerun picks up any miss.

## Exit codes

- 0: finished (failures are listed, not fatal)
- 1: the listing or robots.txt could not be read, or the state file is corrupt
- 2: blocked (HTTP 403 or robots.txt disallow); recorded in the state file

These apply to `sfs` and `case-law`.

## Tests

```
python3 -I -m unittest discover -s collector/tests -t collector -v
```
