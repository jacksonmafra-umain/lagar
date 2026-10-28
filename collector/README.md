# lagar collector

Collects Swedish statutes (SFS) from Riksdagen open data into `corpus/` Markdown files.
Python standard library only.

## Usage

Run from the repository root (`-I` ignores `PYTHONPATH`, so use the entry script):

```
python3 -I collector/collect.py sfs --fundamental
python3 -I collector/collect.py sfs [--from YYYY-MM-DD --to YYYY-MM-DD] [--limit N] \
    [--since YYYY-MM-DD] [--rate SECONDS] [--state collector/data/sfs-state.json] \
    [--corpus corpus]
```

- `--fundamental` fetches only the four fundamental laws (always refetched).
- `--since` keeps listing items whose `systemdatum` is on or after the date.
- `--limit` stops after N written documents.
- `--rate` is the minimum interval between requests (default 1.0 s).

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

## Exit codes

- 0: finished (failures are listed, not fatal)
- 1: the listing or robots.txt could not be read, or the state file is corrupt
- 2: blocked (HTTP 403 or robots.txt disallow); recorded in the state file

## Tests

```
python3 -I -m unittest discover -s collector/tests -t collector -v
```
