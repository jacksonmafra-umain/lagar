# Roadmap

What lagar does next, and the recurring work that keeps the corpus healthy and true to its sources. Product items further out are candidates for the owner to decide on; the maintenance and verification work is meant to run whether or not new features land.

Last reviewed: 2026-11-12.

## Where things stand

Figures from `STATISTICS.md`, `PROGRESS.md` and `AGENCIES.md` on 2026-11-12.

| area | state |
| --- | --- |
| Corpus | 54,833 documents; text from the web or an API 32,457, a PDF text layer 20,415, OCR 1,494, none 467 |
| Coverage | SFS 11,428 of 11,567 (98.8 %); 21 of 21 counties; 286 of 290 kommuner; 62 agency series collected, 5 blocked by a WAF, 1 needs an API key |
| Audit | 0 schema errors, 0 duplicate ids, 0 path mismatches; 904 text-quality flags (548 short bodies, 259 print only, 97 replacement characters) |
| SFS against the print | 93.1 % of 682 statutes in their current wording match the official PDF; 47 differ |
| OCR | 95.5 % word recall and 94.2 % precision on text-layer PDFs read again by OCR (lowest source: 74.4 % precision); not yet measured on real paper scans |
| Automation | 8 sync workflows (3 daily, 5 weekly) that test, audit and merge themselves; the landing page deploys from `main` |

## Now: open problems (next two weeks)

| # | problem | done when |
| --- | --- | --- |
| 1 | A sync run that spans a workflow change on `main` cannot push: GitHub refuses to update `.github/workflows/` without the `workflows` permission, which neither the workflow token nor `SYNC_TOKEN` has. The agency sync of 2026-11-12 lost 2.5 hours of work this way. | Sync pushes no longer depend on what changed under `.github/workflows/` meanwhile (token permission or a push that never carries workflow changes), and the agency sync has merged once. |
| 2 | Agency series failing in the weekly run: AFS (overview page returns no regulations), KVFS, KBVFS; NFS 2001:20 and NFS 2000:2 fail to read. | Each one is fixed or recorded as a gap in `agencies.json` with its reason. |
| 3 | The weekly agency sync is close to its time budget (2.5 to 3 hours for 60 series). | The run stays under 4 hours with room to grow, for example by splitting the series over two jobs or skipping unchanged listing pages. |
| 4 | `SYNC_TOKEN` expires silently; when it does, sync pull requests fall back to the workflow token and their checks stop running. | The expiry date is checked by the health workflow (below) and an issue opens 30 days before. |
| 5 | Open issues: Värnamo (0683) municipal regulations (#309), landing page copy review (#53). | Closed. |

## Health and veracity checks

Three kinds of checks: **health** (is the system running and fresh?), **integrity** (is the corpus well formed?), and **veracity** (does the text say what the official source says?). What already runs is marked *exists*; the rest is to build.

### On every sync (automatic)

- Collector tests, corpus audit (schema, duplicate ids, path mismatches) before merging. *exists*
- Statistics, progress and agencies reports regenerated. *exists*
- Per-series and per-source failures listed in the run summary and the commit message. *exists*
- Fail the merge when the number of documents in a layer drops by more than a set share (for example 2 %), so a broken listing page cannot silently delete rules. *to build*

### Weekly: health report (new `health.yml`, scheduled)

`scripts/health.py`, run by `health.yml` on Mondays, reads the state of the other workflows and keeps a single `Health report` issue open while something is wrong (opened or updated on each run, closed when a run is clean). Freshness, token expiry, site and run time *exist*; failure streaks are *to build*:

- **Freshness:** the last successful run of each sync workflow; flag a daily sync older than 3 days and a weekly one older than 10.
- **Failure streaks:** a series, county or kommun that failed in two runs in a row.
- **Token expiry:** the `github-authentication-token-expiration` header that GitHub returns on calls made with `SYNC_TOKEN`; warn 30 days before.
- **Site:** <https://grundlagar.vercel.app> answers 200, its figures match `collector/data/statistics.json`, and the analytics script loads.
- **Run time:** the agency sync's collect step against its 240 minute budget.

### Monthly: veracity sampling

- **Source drift:** pick a random sample per layer (for example 50 documents), fetch the official source again, and compare its SHA-256 with the manifest. A changed hash with no corpus update means a sync missed a change.
- **Dead sources:** check that every `source` URL in the sample still answers; record moved or removed publications.
- **SFS against the print:** run `sfsverify` on the newly cached PDFs and review every statute that moves to `differs`. *the tool exists; the review is to schedule*
- **Text-quality flags:** work the queue down, starting with the 97 replacement characters (encoding errors are always fixable) and the short bodies.

### Quarterly

- **OCR on real scans:** build a ground-truth set of printed and typewritten pages (older county and agency regulations) with checked transcriptions, and measure Tesseract on it, not only on rendered text layers. Compare newer engines (PaddleOCR, docTR, LightOnOCR) on the same set and publish the results per document type; precision matters most, because it catches invented text.
- **OCR calibration:** rerun `ocr_calibration.py` and keep the history, so a Tesseract or model update that lowers accuracy shows up.
- **Coverage review:** new lagrummet.se sources (unclassified entries in `AGENCIES.md`), the 4 kommuner still missing, and the blocked sources (Bolagsverket, Konkurrensverket, PTS, Jordbruksverket, Skatteverket; Boverket's API key): check whether any of them now publishes in a way that can be collected without bypassing anything.
- **Dependencies:** add Dependabot for GitHub Actions and Gradle (there is none today), and update pinned Python, Kotlin, Compose Multiplatform, AGP, Gradle and Ktor versions in small pull requests.
- **Replication prompt:** check `docs/replicate/PROMPT.md` against the current contracts and move its pin.

### Yearly

- Renew `SYNC_TOKEN` and the Vercel token; review their permissions.
- Rebuild the API from scratch and compare with the incremental output.
- Review `COVERAGE.md` by hand against the official lists of författningssamlingar.

## Next: product (owner to decide)

Candidates collected so far, in no fixed order:

- **Search by meaning and by voice:** Swedish models from KBLab (sentence embeddings for search, KB-Whisper for speech), proven in the lagar-search demo.
- **Reading a law as of a date:** point-in-time text, which needs historical text in the API first.
- **Services (Tjänster):** the fourth tab, today a placeholder. Designed in [`docs/specs/2026-11-13-tjanster-design.md`](specs/2026-11-13-tjanster-design.md) (public services linked to the norms they are based on) and planned as 14 issues in [`docs/plans/2026-11-13-tjanster.md`](plans/2026-11-13-tjanster.md); waiting for the owner to start it.
- **The web app:** paused and not deployed; decide whether and when it goes public again.
- **OCR engine:** replace or complement Tesseract once the real-scan benchmark has a winner.

## When something breaks

1. Read the failed step's log (`gh run view <id> --log-failed`); the sync summary lists failed series and sources.
2. A source that changed its page: fix the adapter in a pull request with a test from the new page. A source that blocks automation: record it as a gap with its reason, never bypass it.
3. A sync that lost its run (time limit, push refused): fix the cause first, then run it again with `gh workflow run sync-<name>.yml`.
4. Note the incident and its fix in the health issue, so the next review sees the pattern.
