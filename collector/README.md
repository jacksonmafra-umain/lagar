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

## Resume

State is kept in `collector/data/sfs-state.json` (git-ignored) and rewritten atomically
after every document: `{"done": {id: systemdatum}, "failed": {id: error}, "blocked": null|msg}`.
A document is skipped when its `systemdatum` matches the state and its corpus file exists.
Per-document errors are recorded under `failed` and the run continues; rerun to retry them.

## Exit codes

- 0: finished (failures are listed, not fatal)
- 1: the listing or robots.txt could not be read
- 2: blocked (HTTP 403 or robots.txt disallow); recorded in the state file

## Tests

```
python3 -I -m unittest discover -s collector/tests -t collector -v
```
