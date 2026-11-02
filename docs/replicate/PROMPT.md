# Build lagar for your country

This prompt turns a coding agent into the builder of a lagar-style project for one country: the country's law collected from official sources into one Markdown file per norm, a static JSON API built from that corpus, and, if wanted, an app, a landing page and an agent tool server on top. [lagar](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/README.md) does this for Sweden. The country decides what is collected and how it is organised; lagar's architecture, parsing approach and security rules decide how it is built.

## How to use this prompt

Paste this whole file into your coding agent, in an empty folder or in a copy of lagar. The agent follows the phases below in order and stops at every gate until you answer.

Instructions for the agent:

- Read this whole prompt once before you say anything. Once the Phase 1 gate is passed, copy Phase 0 into your project instructions file (the file your agent reads at the start of every session) so the rules survive across sessions; in a copy of lagar, replace that file's Swedish content instead of adding a second file.
- **Resuming.** If `docs/replication/onboarding.md`, `docs/country-profile.md` or `docs/replication/plan.md` already exists, read them first. Skip every question they already answer, tell the person what you found, and continue from the first phase that is not finished. A phase is finished only when its file carries a `Confirmed: <date>` line written after the person's approval; in the plan, a milestone is finished only when it carries a `Done: <date>` line.
- The phases are gates. Phase 1 ends with saved answers, Phase 2 with an approved country profile, Phase 3 with an approved plan. Do not move past a gate without the person's explicit approval.
- The references at the end (A, B, C) are contracts, not suggestions. Each one summarises what must be true and links to the file in lagar that shows a working example. The links point to one fixed lagar version so they always match this prompt; read the linked file when you implement that part.
- If your agent can run helpers in parallel, use them for research and for independent collectors. Hand each helper the relevant rules from Phase 0 and Reference B. Helpers share each host's rate limit: never send two helpers to the same host at once.

## Phase 0: Ground rules

These rules hold for the whole project, in every phase and every session.

1. **Talk in the person's language.** Ask and report in the person's language. Everything written into the repository is in English (code, identifiers, frontmatter keys, file names, commits, docs) except the legal texts themselves and the app's UI strings.
2. **Never machine-translate legal text.** Not in the corpus, not in the app, not in a summary presented as the law. A text that is not published in a supported language is a gap, not a translation job. A translation the state itself publishes may be collected, marked `authoritative: false`.
3. **Never invent legal text.** If a source cannot be read (a scanned PDF without OCR, a broken page), record a gap. Never fill it from memory.
4. **Collect politely and legally.** Honour robots.txt (including its `Crawl-delay`) and each site's terms of use, rate-limit every host, identify the collector with a User-Agent that carries the repository URL, and never bypass a block, captcha, login, firewall or paywall. When a source forbids automation, its terms conflict with each other or with the law (generic portal terms against a statute that frees official texts from copyright), or its terms cannot be read, stop and ask the person.
5. **Gates first.** Writing the answers, the profile and the plan is how the gates work, and the project instructions file carries these rules; apart from those files, do not write anything until the person has confirmed the onboarding answers (Phase 1), the country profile (Phase 2) and the plan (Phase 3).
6. **Respect the country's structure.** Layers, document types, divisions and identifiers come from the country profile. Never carry Swedish structure (three fixed scopes, ministries, SFS numbers, Swedish stop words) into another country.
7. **Prove it.** Every milestone ends with the tests and checks named in Reference A passing, and you show the person the result.
8. **Small steps.** One focused change per commit, Conventional Commits messages, each commit building and passing tests.
9. **Ask when unsure.** When a decision changes what gets built and nothing here settles it, ask the person one clear question instead of guessing.

## Phase 1: Onboarding

Ask these questions one at a time, in this order. Before each one, say in one sentence why it matters. Wait for the answer before the next question. When the person says "you decide", propose a concrete answer and ask them to confirm it.

1. **Country.** Which country's law the project covers. One project covers one country.
2. **Languages.** Two separate answers:
   - the languages in which the country's legal text is authoritative (some countries have several, for example Switzerland, Belgium, Canada or Finland), which decides what the collectors keep. This is a first answer: Phase 2 checks it per layer and division, and when the research differs you update `docs/replication/onboarding.md` and ask the person to confirm again;
   - the app's UI languages as BCP 47 tags with the regional variant where it matters (`pt-PT`, not `pt-BR`), which one is the default, and the fallback language when the device's language is not supported. English is always the base set of strings.
3. **Experience level.** Whether the person is a developer or not. A developer gets short status updates and technical detail; someone non-technical gets plain explanations, more frequent check-ins, and step-by-step help with anything they must do themselves (creating the GitHub repository, enabling GitHub Pages). The rules and the architecture are the same for both.
4. **Starting point.**
   - *Reuse lagar:* copy lagar, keep its structure and generic code, and remove everything Swedish (Reference C).
   - *From zero:* build a new repository from this prompt and its references alone.
5. **Features.** Always built: the collectors, the corpus, the static API, the corpus audit and the reports. Optional, the person picks any of:
   - the app (Compose Multiplatform; which of Android, iOS and web);
   - the landing page (GitHub Pages by default, Vercel if the person prefers);
   - the MCP server, so other agents can search the corpus;
   - sync workflows that collect changes on a schedule and merge them automatically;
   - amendment history, one git commit per amendment on a separate branch.
6. **Project identity.** The project name, the GitHub owner (user or organisation) that will host it, the licence for the code (lagar uses MIT; legal texts are usually public domain or under the source's terms), and the contact URL for the collectors' User-Agent. GitHub is required: the CI, the sync workflows and the security rules are written for GitHub Actions. Also ask whether commit messages may mention an assistant or carry a co-author line. Derive identifiers from the name: a Python package name in snake_case (`gesetze_ch` for `gesetze-ch`) and a Kotlin package in lowercase without separators.

Write the answers to `docs/replication/onboarding.md` (one heading per question, the answer, and the date), read them back to the person in a short summary, and ask them to confirm. That confirmation is the Phase 1 gate; record it as a `Confirmed: <date>` line at the end of the file.

## Phase 2: Legal-structure research

You research the country's legal organization; the person confirms it. Use official sources first: the legislature, the government's legal gazette, the courts, national statistics or mapping agencies, and the country's legal information portal. Cite a URL for every claim and mark anything you could not verify as **unverified**. If your agent can browse in parallel, give each layer to a separate helper.

Research these, in this order:

1. **Hierarchy of norms.** Every level from the constitution down to local rules, with how each ranks against the others: constitutional law, statutes, ordinances or decrees, agency regulations, regional and municipal rules, case law (which courts publish guiding or precedent decisions), treaties, and supranational law. Ranks may tie; when the order between two layers is contested, record that with a source. Case law is not a level of the hierarchy; give it a rank only to order listings, and say so.
   - **Supranational check, always answered:** does a supranational body's law apply directly in the country? It gets a layer only when it does (EU law in a member state). Law that arrives through treaties (a non-member's bilateral agreements, the EEA, the European Convention on Human Rights) stays in the treaty layer.
   - Choose layers by legal rank and issuer, not by website: two types published by one source can sit in different layers, and one layer can need several sources.
2. **Administrative divisions.** The levels below the nation that issue their own binding rules: there can be any number of levels (Sweden has län and kommun; a federation may have states, districts and municipalities). A level that exists but issues no rules is not a division here. For each level: its name in every official language, its parent level, the official code list, its code pattern, the date the list is valid for (lists change through mergers and reforms), and an authoritative source for the list. When a level has no official code list, propose a scheme, mark it **unverified**, and ask the person. Research a source for coordinates only when the app and its location suggestion were chosen.
3. **Languages of the law.** Which languages each layer, and each division where it differs, is authoritative in. A country can have several authoritative languages, and one norm can exist in more than one; record which sources publish which language. Also record official translations the state publishes (binding nowhere, or binding only in some divisions), and treaties whose binding text is in a foreign language.
4. **Official sources per layer.** For each layer: the host, how it is accessed (API, open-data dump, HTML pages, PDF), the identifier scheme (national numbering, ELI, ECLI or others; verify that the country actually uses each one), the signal for incremental updates (change date, feed, sitemap), the robots.txt rules for the paths you need (including `Crawl-delay`), the terms of use and the copyright basis of official texts, and which text is binding.
   - **Which text is binding.** Many countries publish both an official gazette (often the binding text, one act or amendment at a time) and a consolidated collection (current text, often not binding). Record which one each source is, which one the person should read, and set `authoritative` per collection and language, not per host.
   - Read robots.txt and the terms yourself; do not assume. A robots.txt that is missing (any 4xx) or empty allows everything; one that cannot be fetched (5xx, timeout) disallows everything until it can (RFC 9309); a redirect that ends on an HTML page is not a robots file, so record it and ask. When the terms cannot be found, or the page renders only with JavaScript, record that: the source blocks the gate until the person has decided.
   - When text is reachable only through a JavaScript application, its undocumented internal endpoints or a headless browser, record that and ask the person; never assume it is allowed. A bot challenge or firewall page (a WAF interstitial) is a block. Another official publication of the same text (a regional act also printed in the national gazette) is a separate source, not a workaround, but still ask before relying on it.
   - When one host disallows a path that another official host of the same publisher allows and serves with the same bytes, record both, and ask the person before planning to use the allowed one.
   - **Divisions with many publishers** (states, cantons, thousands of municipalities): do not research every one before the gate. Describe the platform families (shared systems, an index portal, one website each), sample two or three of each, and leave the per-division registry (a data file per division layer, like lagar's `counties.json` and `municipalities.json`) to Phase 4.
   - When a norm appears in two sources (a regional constitution also published nationally), name the one the corpus takes it from; the other is not collected again.
5. **Case-law privacy.** Whether anonymised versions of decisions are published and which publications may be stored. Only anonymised case law is ever collected.
6. **Gaps.** Layers or divisions with no machine-readable source, a source that forbids automation, one behind a login, paywall, captcha or bot challenge, or terms that are unreadable or in conflict. Record each one with the reason and the URL; never plan a workaround.

Write the result in two files:

- `docs/country-profile.md`: the readable version, one section per item above, every claim with its URL.
- `collector/data/country-profile.json`: the machine-readable version that the collectors, the audit, the API builder and the app read. Top-level keys:
  - `country`: name and ISO 3166-1 code.
  - `languages`: `legal` (a list of `{code, binding}`, ISO 639-1 codes, where `binding` is `all` or `{layers, divisions}`: the layer ids and division codes in which the language is authoritative), `translations` (codes of languages that are binding nowhere but in which the state publishes official translations; a language binding in some divisions stays in `legal`, and is a translation elsewhere), `ui` (app languages), `default_ui`, `fallback_ui`.
  - `divisions`: a list, one entry per level, each `{level, key, name, parent, code_pattern, count, as_of, source, coordinates_source}`, from the largest to the smallest: `key` is the frontmatter key for its code, named after the level (`canton_code`, `parish_code`; lagar's are `region_code` and `municipality_code`), `name` a map from language to name, `parent` the level above or null, `coordinates_source` null unless the location suggestion was chosen.
  - `layers`: a list of `{id, name, rank, rank_note, division, types}`, with English ids chosen for this country (a supranational id such as `eu` only when the check above says so, one id per division level), `name` a map from legal language to name, `rank` from 1 (highest, ties allowed) and `rank_note` (null, or why the rank is contested or only orders listings), `division` (the `key` of the division level whose codes group this layer, or null).
  - `types`: a closed map from document type (English, snake_case) to its layer.
  - `id_scheme`: the id prefix per type and how the official number becomes the id, with one example per type.
  - `frontmatter`: a map from each key this country uses beyond the universal ones (Reference A, Corpus) to `{status, layers, pattern}`, where `status` is `required` or `optional` within `layers`; plus `cross_field`, a list of rules between keys (a parish code starts with its municipality code).
  - `sources`: a list of `{layers, host, access, id_scheme, update_signal, robots, crawl_delay, terms, licence, authoritative}`, where `layers` is a list, `robots` is `{url, status, rules}`, `terms` is `{url, verdict, decision}` with a verdict of `allows`, `forbids`, `conflict`, `not_found` or `unreadable` and `decision` the person's answer, with its date, for any verdict other than `allows`, `licence` is the copyright basis of the texts with its URL, and `authoritative` maps each collection or language the source serves to true or false.
  - `case_law_privacy`: `{published_anonymised, may_store, never_fetch, urls}`.
  - `gaps`: a list of `{layers, reason, url}`.

lagar's Swedish version of this structure is in [`collector/lagar/vocabulary.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/vocabulary.py) and [`docs/schema/frontmatter.schema.json`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/schema/frontmatter.schema.json); use them as a worked example, not as a template to copy.

Present the profile to the person as a short summary at their experience level (plain words, no patterns or JSON for someone non-technical): the layers in rank order, the divisions, the sources with their access method, which text is binding, the gaps, and every question research left for them (terms, mirrors, internal endpoints, codes you proposed). Ask them to approve it or correct it. No code is written until the person approves the profile; when they correct something, update both files and ask again. Record the approval as a `Confirmed: <date>` line in `docs/country-profile.md`.

## Phase 3: Plan

Turn the onboarding answers and the approved profile into ordered milestones. Write the plan to `docs/replication/plan.md`: for each milestone, what it builds, the files it creates or changes, and a **Done when** line naming the checks from Reference A that must pass. Keep this order; leave out the optional milestones the person did not choose.

1. **Skeleton and contracts.** The repository layout (or the cleaned copy, Reference C), the licence, lint and pre-commit configuration, the read-only CI workflows, `docs/api.md` written for this country, the frontmatter schema and the closed vocabulary from the profile. Done when: CI is green on an empty corpus and the schema tests pass.
2. **First collector and corpus.** The shared HTTP client and robots.txt handling, then the collector for the highest-ranked layer with a machine-readable source (usually the constitution and the statutes), a small first run (`--limit`), the manifests and the audit. Done when: collector tests pass, the audit is clean, and the person has read a few documents and compared them with the official source.
3. **Static API.** The builder, listings, documents and per-layer search for that corpus. Done when: API tests pass and the size report is printed.
4. **More layers.** One milestone per further layer or source family, in the profile's rank order, with PDF text and OCR only where a source needs them. Done when: each collector's tests pass and its gaps are recorded.
5. **Reports.** Progress against targets, statistics, the sources log, and a hand-written `COVERAGE.md`.
6. Optional, in this order when chosen: **Sync workflows**, **MCP server**, **App** (design tokens and i18n first, then the shell, home, hierarchy, search, reader, saved items and settings), **Landing page**, **Amendment history**.

Explain the plan to the person at their experience level, including anything they must do themselves (create the GitHub repository, enable GitHub Pages, add a deploy secret). Wait for them to approve the plan before Phase 4, and record the approval as a `Confirmed: <date>` line in `docs/replication/plan.md`.

## Phase 4: Build

Build the approved plan one milestone at a time.

- Work test-first where code is involved: write the test from the contract, see it fail, make it pass. Fixtures come from real source responses, saved small, never invented.
- Commit in small steps with Conventional Commits messages (`feat(collector):`, `fix(api):`, `data(<layer>):`, `chore(ci):`, `docs:`, `test:`); stage explicit files; each commit builds and passes tests. Whether commit messages mention an assistant or carry a co-author line is the person's choice, recorded in the onboarding answers; follow it.
- Use issues and pull requests if the person wants them; otherwise commit to the main branch only after the milestone's checks pass.
- At the end of each milestone, run its **Done when** checks, show the person the result (counts, a sample document, the test summary) in the depth their experience level calls for, and add a `Done: <date>` line to that milestone in `docs/replication/plan.md`.
- When a source forbids automation, blocks the collector (403, captcha, login, firewall) or changes so that the collector no longer matches it, stop that collector, record a gap with the reason and URL, and ask the person how to continue. Never work around it.
- When the person asks for something this prompt does not cover, or a decision would change the profile or the plan, update the relevant file and confirm with them before building it.
- Large first collections run in the background or in batches with `--limit`, resuming from the state file; never delete state to start over without asking.

When every chosen milestone is done, give the person a final summary: what is collected per layer, the gaps, how to run each part locally, and how the sync workflows (if built) keep it current.

## Reference A: Architecture contracts

Each contract says what must be true and links to lagar's working version. Build what the contract says with the country profile's values; read the linked file for detail and proven edge cases. Parts marked *optional* are built only when chosen in Phase 1.

### Layout

One repository, one folder per part, everything in English:

- `collector/`: Python collectors (`collector/<project>/*.py` modules, thin entry scripts such as `collect.py`, `audit.py`, `plan.py`, `stats.py`), `collector/data/` for configuration, the country profile and committed sync markers, `collector/tests/` with fixtures.
- `corpus/`: one Markdown file per norm, one folder per layer and type.
- `sources/`: committed manifests of every source file read (`sources/cache/` holds the bytes and is git-ignored).
- `api/`: the static API builder and its tests. `mcp/`: the MCP server (optional). `app/`: the app (optional). `landing/`: the landing page (optional).
- `docs/`: the API contract (`docs/api.md`), the frontmatter schema (`docs/schema/`), the country profile, the onboarding answers.
- Root: `README.md`, `LICENSE`, generated reports (`PROGRESS.md`, `STATISTICS.md`, a sources log), a hand-written `COVERAGE.md`, `.editorconfig`, `.gitignore`, the lint configuration and `.pre-commit-config.yaml`.

Example: [lagar's README, with its command list](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/README.md).

### Corpus

- One YAML-fronted Markdown file per norm. The body is the legal text as Markdown, with headings for chapters and sections exactly as the source structures them.
- A **closed vocabulary**: every `type` belongs to exactly one `layer`, both from the country profile; an unknown type is an error, not a new folder. See [`vocabulary.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/vocabulary.py).
- **Universal keys**, required in every document in every country, with these formats:
  - `id`: lowercase, pattern `^[a-z0-9_]+-[0-9a-z-]+$`, built from the type's prefix and the official number (`sfs-1999-175` in lagar), with the language code appended when the profile has more than one legal or translation language (`sr-101-de`, `sr-101-fr`), so every id is unique;
  - `title`, `type`, `layer`, `number` (the official number as printed, or null), `issued` (`YYYY-MM-DD` or null);
  - `in_force`, `repealed` (dates or null), `amended_by` (list of numbers);
  - `language` (a code from the profile's `languages.legal` or `languages.translations`; a norm published in several languages gets one document per language, all with the same `number`, which is what links them);
  - `authoritative` (true only when this text, in this collection and language, is the legally binding one: a consolidated text or an official translation is usually `false`);
  - `source` (the URL read), `source_sha256` (64 lowercase hex characters of the exact bytes read), `fetched_at` (`YYYY-MM-DDTHH:MM:SSZ`, UTC).
- **One optional universal key**: `text_source`, `ocr` when the text came from OCR, otherwise null or absent.
- **Country-specific keys** come only from the profile's `frontmatter` and `divisions` (one code key per division level, named after it), with its cross-field rules. lagar's own list (`ministry`, `eli`, `ecli`, `celex`, `amended_through`, `reprinted_by`, `amendments`, `issuer`, `court`, `region_code`, `municipality_code`) is an example of the kind of keys a country has, not a starting list.
- The path follows from type and id: one folder per type (for example `corpus/<layer>/<type-plural>/<id>.md`), never chosen by hand. See [`writer.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/writer.py).
- Frontmatter is a small YAML subset (quoted strings, null, booleans, flow lists of strings, block lists of flat mappings) with a writer and a reader that are exact inverses, tested by round trip. See [`frontmatter.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/frontmatter.py).
- The schema is a JSON Schema file plus a stdlib validator for cross-field rules: [`frontmatter.schema.json`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/schema/frontmatter.schema.json), [`schema.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/schema.py).

### Collectors

- Python standard library only, run as `python3 -I` (isolated mode). No third-party packages, so nothing to pin and nothing to audit.
- One shared HTTP client ([`http.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/http.py)):
  - at least 1 second between requests to a host, or the host's robots.txt `Crawl-delay` when that is longer (`--rate` can raise it; never lower it below either);
  - up to 3 retries on 429, 500, 502, 503 and 504, with exponential backoff and `Retry-After` honoured;
  - a 403, or a `Retry-After` over 300 seconds, raises `Blocked` and stops the run: never retry around a block;
  - 30-second timeout; a User-Agent like `<project>-collector/0.1 (+<repository URL>)`.
- robots.txt is read once per host and applied before every request, with RFC 9309 matching (`*` wildcards, `$` anchors, longest match wins, agent groups). A robots.txt answered with 404 or 410 allows everything (lagar treats any other 4xx as an error, and so should you until the person decides); an unreachable one (5xx, timeout) blocks the host. The robots.txt `Crawl-delay` for the collector's agent sets the minimum spacing when it is longer than 1 s. A disallowed URL becomes a gap with the reason. Keep this in its own module that every collector imports. lagar has two halves of it: RFC 9309 matching in the `Robots` class of [`municipal.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/municipal.py), and `Crawl-delay` in the `_Robots` class of [`agency.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/agency.py); a new country needs both in one class.
- **Resumable and idempotent:** state in `collector/data/<name>-state.json` (git-ignored) with `done`, `failed`, `blocked`; written atomically (temporary file, fsync, rename); a corrupt state file is an error, never silently reset. `done` is keyed to the source's change stamp so unchanged items are skipped and a rerun writes nothing new.
- **Incremental sync:** a committed marker (`collector/data/<name>-sync.json`) records the last change date read; on failure the marker is held back so the next run retries.
- **Manifests:** every source file read gets an entry in a committed `sources/<name>-manifest.json` with URL, size, content type, retrieval time, SHA-256 and how its text was obtained, plus a `gaps` list. Source bytes (PDFs especially) are never committed.
- **Adapters:** one module per source family, sharing the run loop; configurable adapters for the common shapes (a list of PDF links, one HTML page per rule) so a new issuer is a data entry, not new code. See [`agency_generic.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/agency_generic.py).
- A `--limit`, `--dry-run` or `--report` option on every collector so a run can be tried small and reported.

### Parsing

- HTML to Markdown with a stdlib converter that keeps headings, lists, tables and links: [`htmlmd.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/htmlmd.py).
- PDF text through poppler's `pdftotext`, then a classifier that rejects unusable text layers (no text, unreadable encoding, letter-spaced text) as gaps: [`pdftext.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/pdftext.py).
- OCR only for scanned PDFs: `pdftoppm` plus `tesseract` with the language model of the document's `language` (check that tesseract has one for every legal language; a language without a model makes its scans gaps), low-confidence lines dropped, and the document marked `text_source: ocr`: [`ocr.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/ocr.py). Measure OCR accuracy by reading text-layer PDFs again with OCR and comparing (word recall and precision): [`ocrcalibration.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/ocrcalibration.py).
- Patterns in the country's language (dates such as "issued on", entry into force, amendment headers) live in the module of the source that needs them, with a test per pattern taken from a real document.
- Never guess text. A page or PDF that cannot be read is a gap with its reason.

### Audit and reports

- `audit.py` checks every document: schema errors, duplicate ids, paths that do not match type and id, empty or broken text, unresolved cross-references. It writes a JSON report and exits non-zero on schema errors, duplicates or path mismatches; CI and a pre-commit hook run it. See [`audit.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/audit.py).
- `plan.py` writes `PROGRESS.md` and a progress chart against `collector/data/targets.json` (expected counts per layer and type, with the source of each target): [`progress.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/progress.py).
- `stats.py` writes `STATISTICS.md` and `collector/data/statistics.json` (documents, sections and words per type, issuers, divisions covered, source hosts, how each text was obtained): [`corpusstats.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/corpusstats.py).
- A sources log lists every official source of the country with its status (collected, partial, gap and why): [`agencies.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/agencies.py).
- `COVERAGE.md` is written by hand: what is covered, what is not, and why.

### Static API

The app and other tools read only the API, never the corpus. The full contract is [`docs/api.md`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/api.md); generalise it with the profile:

- Version prefix `v1`; every key always present, `null` when unknown; listings paged at 50 items.
- `index.json`: API version, build time, every layer with its counts and series.
- `<layer>/index-<page>.json`, `<layer>/<type>/index-<page>.json`: listing items with id, title, number, type, dates and the division codes.
- `<layer>/by-code/index.json` and `<layer>/by-code/<code>/index-<page>.json` for each division layer; any other grouping (lagar's `by-ministry`) only when the profile has that key.
- `docs/<id>.json`: `meta` (all frontmatter) and the body.
- Full-text search per layer ([`searchindex.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/api/searchindex.py)): an inverted index sharded by the first two characters of each term (`search/<group>/shards/<key>.json`); postings carry field bits title=1, number=2, body=4; text lowercased with diacritic folding and one stop-word set per legal language, applied by each document's `language`, and official numbers kept as one token; in a country with several languages, the index records each document's language so a search can be filtered to one language instead of returning every language version of the same norm; a per-layer size budget (40 000 000 bytes in lagar) above which the group indexes titles and numbers only. The app's normalisation must be byte-for-byte the same as the builder's, with a shared test vector.
- Built with `python3 -I api/build.py --corpus corpus --out build/api/v1`, served per machine; a size report prints the size per layer. See [`build.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/api/build.py).

### App

*Optional.* Compose Multiplatform, Kotlin, with a shared module and thin hosts for the platforms chosen in Phase 1.

- Versions of Kotlin, Compose Multiplatform, the Android Gradle plugin, Gradle and Ktor are the latest stable, pinned in one version catalog: [`libs.versions.toml`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/app/gradle/libs.versions.toml).
- Data behind repository interfaces with an HTTP implementation (Ktor), a bundled sample and a cache; the app depends only on the API contract. See [`data/`](https://github.com/jacksonmafra-umain/lagar/tree/46a8e7d3f386bbbec82917a9725fe03220268ab5/app/shared/src/commonMain/kotlin/app/lagar/data).
- Scopes come from the profile: the nation plus one scope for each division level that issues rules. The home screen, the hierarchy view and search filters are driven by the profile's layers and divisions, never by hard-coded names. lagar's screens and navigation: [`architecture.md`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/architecture.md), [`screens.md`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/screens.md).
- Internationalisation from the first screen: Compose resources, English in `values/`, one folder per UI language, the profile's fallback for an unsupported device language, no hard-coded user-facing strings: [`i18n.md`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/i18n.md).
- Design tokens (colors, typography, spacing, radii) in the frontmatter of `DESIGN.md`, generated into Kotlin by a Gradle plugin: [`DESIGN.md`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/DESIGN.md), [`build-logic`](https://github.com/jacksonmafra-umain/lagar/tree/46a8e7d3f386bbbec82917a9725fe03220268ab5/app/build-logic). One color per layer, chosen for the country; light and dark themes; every text color meets WCAG AA contrast.
- Anonymous: no accounts, bookmarks and settings stay on the device.
- On the web, each screen has its own address in the URL fragment so reloads and shared links work.

### Landing page

*Optional.* Static HTML, CSS and a little JavaScript in `landing/`, in every UI language, showing the corpus statistics from `statistics.json` and the sources log. Deployed with GitHub Pages by default (a workflow with `pages: write` only on the deploy job), or Vercel if the person chose it. See [`landing/`](https://github.com/jacksonmafra-umain/lagar/tree/46a8e7d3f386bbbec82917a9725fe03220268ab5/landing).

### MCP server

*Optional.* A stdio JSON-RPC 2.0 server over the built API (local folder or published URL), stdlib only, with tools to search, get a document, list layers, list documents and read the reports. Its descriptions name the country and tell callers that legal text must not be machine-translated. See [`server.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/mcp/lagarmcp/server.py).

### Sync workflows

*Optional.* One scheduled GitHub Actions workflow per source family ([example](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/.github/workflows/sync-sfs.yml)):

- runs the collector with `--changed-since` the committed marker, then the audit and every report;
- commits to a `data/<name>-sync` branch and opens a pull request; with no changes it opens nothing;
- merges itself once the collector tests and the audit pass, after merging `main` again and regenerating only the report files on conflict; any other conflict fails the job for a person to fix: [`merge-sync-pr.sh`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/.github/scripts/merge-sync-pr.sh);
- `concurrency` without cancellation, a timeout, and only `contents: write` and `pull-requests: write`.

### Amendment history

*Optional.* A script that writes a `git fast-import` stream with one commit per amendment, dated at entry into force, on a separate branch that is never pushed without the person's approval: [`history.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/history.py).

### Continuous integration

Separate workflows for collectors (lint, tests), API (tests, audit, full build, size report), tools (MCP server) and app (lint, tests, a build per platform), each triggered by its paths, each with `permissions: contents: read`: [`workflows/`](https://github.com/jacksonmafra-umain/lagar/tree/46a8e7d3f386bbbec82917a9725fe03220268ab5/.github/workflows).

## Reference B: Security rules

Every rule says how it is checked. Put the checks in tests, CI or a pre-commit hook so they hold after you are gone.

### Collectors

- Read robots.txt for every host before fetching and skip disallowed URLs, recording them as gaps. Check: a test with a robots.txt fixture that disallows a path, asserting no request is made and a gap is written.
- Read each source's terms of use during Phase 2; when they forbid automated access, conflict, cannot be found or cannot be read, do not build that collector until the person has decided. Check: the source entry in the country profile records the terms URL and verdict, and the person's decision for any verdict other than `allows`.
- Rate-limit every host to at most one request per second (at least 1 s between requests), or its robots.txt `Crawl-delay` when longer. Check: a test with a fake clock asserting the spacing, including a robots.txt fixture with a longer `Crawl-delay`.
- Never bypass a 403, captcha, bot challenge, login, firewall or paywall; stop the run and record the block. Check: a test asserting that a 403 raises the block error and stops the run.
- Identify the collector honestly with a User-Agent that carries the repository URL. Check: a test on the client's default headers.

### App privacy

- No accounts, no sign-in, no analytics, no crash reporting or tracking SDKs. Check: the version catalog has no analytics or tracking dependency, and a reviewer confirms it on every dependency change.
- Bookmarks, notes and settings stay on the device; the only network traffic is reading the static API. Check: the HTTP client is created in one place with the API base URL, and a test asserts it.
- No permissions the app does not use (location only if the location suggestion is built, and only when the person taps it). Check: the Android manifest and iOS `Info.plist` are reviewed in the app milestone.

### Repository and CI

- No secrets in the repository; deploy tokens live only in GitHub Actions secrets. Check: a secret scan (for example `git log -p | grep -iE "token|secret|password"` reviewed) before the first push, and GitHub's push protection enabled.
- Every workflow declares `permissions:`; read-only by default, write scopes only on the job that needs them. Check: a test or lint step that fails when a workflow lacks a `permissions:` block.
- Every third-party action is pinned to a full commit SHA with the version in a comment. Check: a test that fails on `uses:` lines with a tag instead of a 40-character SHA.
- Dependency versions are pinned (the version catalog for the app; collectors have none). Check: no `+` or `latest` versions in Gradle files.
- Pull requests from forks never deploy and never receive secrets. Check: deploy jobs have an `if:` that excludes forks.
- Pre-commit hooks: merge-conflict markers, large files (over 1 MB outside `corpus/`), JSON and YAML syntax, lint, and the corpus audit. Check: `.pre-commit-config.yaml` lists them and CI runs the same checks.

### Legal-text integrity

- Every document records the URL and the SHA-256 of the exact bytes it was built from, and every source file read has a manifest entry. Check: the audit fails a document without `source` or with a malformed `source_sha256`.
- Prefer authoritative sources, and mark `authoritative` true only when the source says its text is binding. Check: every entry in the profile's `sources` has a `sources[].authoritative` map covering each collection and language it serves, and a test per collector asserts the flag.
- No machine translation and no invented text, anywhere. Check: the corpus `language` is always a code from `languages.legal` or `languages.translations`; `authoritative` is true only when the document's layer or division is in its language's `binding` and its collection is marked binding in `sources[].authoritative`; and every gap is recorded instead of filled.
- Only anonymised case law; full judgments with personal data and their attachments are never fetched. Check: a test per case-law collector asserting which URLs it requests.

## Reference C: Reusing lagar

Use this path when the person chose *Reuse lagar* in Phase 1. Copy lagar's files at the pinned version into a new repository (not a fork): download `https://github.com/jacksonmafra-umain/lagar/archive/46a8e7d3f386bbbec82917a9725fe03220268ab5.tar.gz`, unpack it into the new folder, and start the git history there (for someone non-technical, do these steps for them and explain each one). A copy of a later lagar will not match the lists below. Then work through the lists in order, one commit per list item group, each commit building. The paths are lagar's at the pinned version. Never delete the onboarding answers in docs/replication or the country profile.

### Untangle

Some generic modules import from Swedish ones. Before deleting anything, move the shared pieces into generic modules and point every import at them, so the copy still builds after each deletion:

- `StateError`, `_save_state` (the atomic state writer) and the state loading from `collector/lagar/sfs.py` into a state module;
- `NETWORK_ERRORS` and the User-Agent constant from `collector/lagar/sfs.py` and `collector/lagar/caselaw.py` into `collector/lagar/http.py`;
- `personal_numbers` from `collector/lagar/caselaw.py` into a privacy helper that the municipal and case-law collectors share;
- `PRINT_ONLY_NOTE` from `collector/lagar/riksdagen.py`, used by `collector/lagar/audit.py` and `collector/lagar/corpusstats.py`: move it if the country has print-only documents, otherwise drop its use;
- the `Robots` class from `collector/lagar/municipal.py` and the `_Robots` class (with its `Crawl-delay`) from `collector/lagar/agency.py` into one robots module;
- the shared parsing helpers that `collector/lagar/agency_generic.py` imports from `collector/lagar/agency.py`, so the adapter classes there can go.

Run the collector tests after each move.

### Delete

- The Swedish corpus and its records: `corpus/`, every file in `sources/` (`sources/*.json`), the sync markers `collector/data/*-sync.json`, and the generated reports `PROGRESS.md`, `progress.svg`, `STATISTICS.md`, `AGENCIES.md`, `COVERAGE.md`, `collector/data/statistics.json`, `collector/data/agencies-report.json`, `collector/data/pending-integrity.json`.
- Swedish source adapters: `collector/lagar/riksdagen.py`, `collector/lagar/sfs.py`, `collector/lagar/sfspdf.py`, `collector/lagar/sfsr.py`, `collector/lagar/sfsverify.py`, `collector/lagar/caselaw.py`, `collector/lagar/county.py` (read its data-driven `pages` and `files` layouts first: they are the pattern for a division layer with many publishers, such as states or cantons), `collector/lagar/treaties.py`, the agency adapter classes in `collector/lagar/agency.py`, `collector/lagar/agency_text.py`, `collector/lagar/centroids.py`, and their tests and fixtures in `collector/tests/`. Keep `collector/lagar/eu.py`, `collector/lagar/eucaselaw.py` and `.github/workflows/sync-eu.yml` only for an EU member state, switched to its legal languages.
- Swedish data: `collector/data/counties.json`, `collector/data/municipalities.json`, `collector/data/kommuner.json`, `collector/data/agencies.json`, `collector/data/agency-series.json`, `collector/data/rattskalla.json`, `collector/data/courts.json`, `collector/data/eu-acts.json`, `collector/data/targets.json`, and the app's `app/shared/src/commonMain/composeResources/files/geo/sweden.json`.
- Sweden's sync workflows: `.github/workflows/sync-sfs.yml`, `.github/workflows/sync-case-law.yml`, `.github/workflows/sync-county.yml`, `.github/workflows/sync-so.yml`, `.github/workflows/sync-agency.yml`, `.github/workflows/sync-municipal.yml`, `.github/workflows/sync-agencies.yml` (rewrite them per source family from the country profile if sync was chosen); `.github/workflows/site.yml` unless the person chose Vercel.
- Parts the person did not choose: `app/` and `.github/workflows/app.yml` without the app; `landing/`, `scripts/build-site.sh` and `.github/workflows/site.yml` without the landing page; `mcp/` without the MCP server; `collector/lagar/history.py` and `collector/history.py` without amendment history.
- Design input and lagar's own documents: `design/stitch/`, `docs/specs/`, `docs/replicate/` (this prompt), `docs/screens.md`, `landing/data/sources.json`, `landing/i18n/sv.json`, `NOTICE.md`.

### Replace from the profile

- The layer and type vocabulary in `collector/lagar/vocabulary.py`, the schema in `docs/schema/frontmatter.schema.json` and the cross-field checks in `collector/lagar/schema.py` (country-specific keys, division code patterns, the `court` pattern, the `language` enum).
- Folder and id prefix mapping in `collector/lagar/writer.py`.
- User-Agent strings and repository URLs in every collector module, `README.md`, the MCP server and the app's published API URL.
- Stop words and diacritic folding in `api/searchindex.py` (one stop-word set per legal language, plus the document language in the index when there are several), mirrored in the app's search normalisation, and the OCR language in `collector/lagar/ocr.py` (chosen per document language).
- Every place that assumes one corpus language, in `api/build.py`, the schema's `language` enum and the app.
- The API contract `docs/api.md`: layers, types, number formats, division groupings; drop `by-ministry` unless the country has the key.
- The app: scope names and divisions (lagar's `domain/Scope.kt`), route and tab names (Utforska, Hierarki, Sparade, Tjanster in `ui/navigation/Routes.kt`), `values-sv/` strings replaced by the UI languages, the default and fallback language in `i18n/SupportedLanguage.kt`, the geo file, the layer colors and the flag accent in `DESIGN.md`.
- The landing page copy, languages (`landing/js/lang.js`) and catalog; the MCP server's name, descriptions and instructions.
- `README.md`, `docs/architecture.md`, the project instructions file and `LICENSE` (the person's name and year).
- `collector/collect.py`: its subcommands, one per new collector.
- `api/searchindex.py`'s `BODY_END` (Swedish heading `## Referat`): the heading, per layer, after which this country's text is not indexed, or none.
- `.github/workflows/pages.yml` (it publishes the API under lagar's URL): the person's own URL, or delete it.
- `collector/lagar/agencies.py` (the sources log, built on lagrummet.se and Swedish data files): rewrite it to read the profile's `sources` and `gaps`.
- `collector/lagar/history.py` (built on the Swedish amendment register): rewrite it on this country's amendment data, if amendment history was chosen.

### Keep

The generic machinery, unchanged except for names, and only for the parts the person chose. `collector/lagar/http.py`, `collector/lagar/frontmatter.py`, `collector/lagar/htmlmd.py`, `collector/lagar/pdftext.py`, `collector/lagar/ocr.py`, `collector/lagar/ocrcalibration.py`, `collector/lagar/agency_generic.py`, `collector/lagar/municipal.py` (its strategies; drop the Swedish presets), `collector/lagar/audit.py`, `collector/lagar/progress.py`, `collector/lagar/corpusstats.py`, `api/build.py`, `api/searchindex.py`, `api/size_report.py`, `mcp/`, `scripts/serve_local.py`, `scripts/build-site.sh`, `app/build-logic/`, the app's shell, `.github/scripts/merge-sync-pr.sh`, `.github/workflows/collector.yml`, `.github/workflows/api.yml`, `.github/workflows/tools.yml`, `.github/workflows/app.yml`, `.pre-commit-config.yaml`, `ruff.toml`, `.editorconfig`.

### Rename

- The Python package `collector/lagar/` and the MCP package `mcp/lagarmcp/` to the project's name in snake_case (`gesetze_ch` for `gesetze-ch`), with every import.
- The Kotlin package `app.lagar` and the app id, the Gradle plugin id `app.lagar.design-tokens`, `LagarTheme` and the other `Lagar*` types.
- Workflow names, the User-Agent product name and the landing page title.

### Finish

1. Search the copy for Swedish leftovers, case-insensitively, and resolve every hit or explain it to the person: `riksdagen`, `sfs`, `kommun`, `län`, `lansstyrelsen`, `regeringen`, `domstol`, `swe` (the OCR model and language codes), `sverige`, `sweden`, `svenska`, `lagar`, `jacksonmafra`, `ministry` (the `by-ministry` grouping), `"sv"` (a single hard-coded language), `referat`, `lagrummet`, `rattspraxis`, `etjanst`.
2. Run the collector, API, tools and app checks from Reference A; all must pass on an empty or sample corpus.
3. Start a new git history (`git init` in the copy, one first commit): lagar's history is mostly Swedish corpus commits and would make the copy large for no gain. Keep a line in `README.md` crediting lagar as the origin.
