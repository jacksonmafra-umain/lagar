# Replication prompt design: lagar for any country

Date: 2026-11-02
Status: draft
Issue: #748

## Intent

lagar turns one country's law into one Markdown file per norm, a static JSON API and an app. The approach is not Swedish; only the data, the sources and the legal structure are. The owner wants anyone, in any country, to be able to build the same thing for their own legal system without reverse-engineering this repository.

The deliverable is **one self-contained prompt** that a person pastes into any coding agent. The prompt interviews the person, researches the country's legal organization, gets that research confirmed, and then builds the project with lagar's architecture, parsing approach and security rules. The country's structure decides *what* is collected and how it is organised; lagar's conventions decide *how* it is built.

Background documents (read before planning):

- `CLAUDE.md`: commands, hard rules, data flow.
- `docs/api.md`: the static API contract.
- `docs/schema/frontmatter.schema.json`, `collector/lagar/vocabulary.py`, `collector/lagar/schema.py`: corpus schema and closed vocabulary.
- `docs/architecture.md`, `docs/i18n.md`, `docs/screens.md`, `DESIGN.md`: app structure, i18n, design system.
- `collector/lagar/http.py`, `pdftext.py`, `ocr.py`, `htmlmd.py`, `writer.py`, `frontmatter.py`, `audit.py`; `api/build.py`, `api/searchindex.py`; `mcp/lagarmcp/`; `.github/workflows/`, `.github/scripts/merge-sync-pr.sh`; `.pre-commit-config.yaml`.

The local master spec (`lagar-implementation-prompt.md`) must not be read into, quoted in or paraphrased into the prompt. Everything the prompt says comes from tracked files.

## Goals

1. `docs/replicate/PROMPT.md`: one Markdown file, in English, that works with any coding agent. No tool names, slash commands or features specific to one agent product; where a step benefits from parallel helpers or persistent instructions, it says so in plain terms ("if your agent can run helpers in parallel, ...", "write these rules into the agent's project instructions file").
2. The prompt runs in **phases with explicit gates**, and never writes project code before the person confirms the country profile and the feature list.
3. The prompt carries enough architectural detail to build the project **from zero**, and enough mapping detail to **adapt a copy of lagar** without missing a Swedish leftover. Detailed contracts are not inlined: the prompt summarises each one and links to the file in lagar's public repository (`https://github.com/jacksonmafra-umain/lagar`, MIT) for the full text (owner decision). Links are pinned to a commit or tag (my call), so a replica reads the version the prompt was written against even as lagar moves on.
4. Short pointers from `README.md` and `CLAUDE.md` to the prompt, plus a line in `CLAUDE.md` that architecture changes must be reflected in it.

## The prompt's phases

### Phase 0: ground rules

Stated first and binding for the whole run: the security rules (below), "never machine-translate legal text", "never write code before the gates", "ask when a source forbids automation", and conversation in the person's language while everything written into the repository is in English except legal text and UI strings.

### Phase 1: onboarding questionnaire

One question at a time, each with a short explanation of why it matters. Decided questions:

1. **Country.**
2. **Languages.** Two separate answers: the app's UI languages, and the language or languages in which legal text is authoritative (some countries have several, for example Switzerland, Belgium, Canada, Finland). The default UI language and the fallback for an unsupported system locale are asked here too.
3. **Experience level.** Developer or non-technical. This changes only how much the agent explains and how often it checks in; rules and architecture are identical.
4. **Starting point.**
   - *Reuse lagar:* copy the lagar repository, keep its structure and generic code, and wipe everything Swedish (see "Reuse path").
   - *From zero:* build a fresh repository from the prompt's description alone.
5. **Features.** Always built: collectors, corpus, static API, corpus audit and reports. Optional, chosen here: the Compose Multiplatform app (and which of Android, iOS, web), the landing page, the MCP server, scheduled sync workflows with auto-merge, and metadata-only amendment history.
6. **Project identity.** Project name, GitHub owner, licence, and contact URL for the collectors' User-Agent.

The answers are written to `docs/replication/onboarding.md` in the new project so a later session can resume. That folder is distinct from lagar's `docs/replicate/` (where the prompt lives), and the reuse-path wipe never touches it; the wipe removes `docs/replicate/` and lagar's own `docs/specs/` and `docs/plans/` from the copy (my call).

### Phase 2: legal-structure research (agent-led)

The agent researches; the person confirms. The agent produces a **country profile**, `docs/country-profile.md` plus machine-readable data files, covering:

- **Hierarchy of norms:** every level from the constitution down to municipal rules, including agency regulations, case law (which courts publish guiding decisions), treaties and supranational law (EU or any regional body that applies), with how each ranks against the others.
- **Administrative divisions:** the levels that issue their own norms (for example län and kommun in Sweden; states and municipalities in a federation), their official codes and an authoritative source for the list and coordinates.
- **Official sources per layer:** host, access method (API, open-data dump, HTML, PDF), identifier scheme (national numbering, ELI, ECLI), update signal for incremental sync, robots.txt status, terms of use, and whether the text there is authoritative.
- **Case-law privacy:** whether anonymised versions exist, and which publications may be stored.
- **Gaps:** layers with no machine-readable or permitted source, recorded as gaps rather than worked around.

The agent cites a URL for every claim and marks anything it could not verify. The gate: the person approves the profile, or corrects it, before Phase 3.

### Phase 3: plan

The agent turns the profile and feature list into ordered milestones (the shape lagar followed: skeleton and contracts, first collector and corpus, API, then each optional feature), each with a definition of done and the tests that prove it. The person approves the plan.

### Phase 4: build

Milestone by milestone, with the verification each milestone names, microcommits in Conventional Commits form, and a short status report to the person at each milestone. When a source turns out to forbid automation or block the collector, the agent stops, records a gap and asks.

## What the prompt specifies (fixed across countries)

Each item is written as a contract the agent implements, with the lagar file to copy from in the reuse path.

- **Layout:** `collector/`, `corpus/`, `sources/`, `api/`, `app/`, `mcp/`, `landing/`, `docs/`, `scripts/`, root reports.
- **Corpus:** one YAML-fronted Markdown file per norm; a closed `type` vocabulary mapped to `layer`s; English keys; path derived from type and id; a minimal YAML subset with exact dump/load inverses. Keys split in two (my call, from `frontmatter.schema.json`):
  - *Universal, required everywhere:* `id`, `title`, `type`, `layer`, `number`, `issued`, `in_force`, `repealed`, `amended_by`, `language`, `authoritative`, `source`, `source_sha256`, `fetched_at`, with lagar's formats (id pattern, 64-hex SHA-256, UTC timestamp). `text_source` stays optional (`ocr` or null), as in lagar.
  - *Country profile:* everything tied to one legal system, which the profile declares as required, optional or absent: `ministry`, `eli`, `ecli`, `amended_through`, `reprinted_by`, `amendments`, `issuer`, `court`, division codes and their patterns, and cross-field checks such as lagar's `<code>FS` number rule. The audit, the API listings (for example `by-ministry`) and the app models follow the profile.
- **Collectors:** Python standard library only, run with `python3 -I`; a shared polite HTTP client (minimum interval, retries with backoff on 429/5xx honouring Retry-After, a block on 403 or a long Retry-After that stops the run, timeout, descriptive User-Agent with the repository URL); robots.txt read per host with RFC 9309 wildcard matching, disallowed URLs recorded as gaps; resumable state written atomically and never reset silently; idempotent writes keyed to the source's change stamp; committed incremental markers; committed SHA-256 source manifests with the source bytes never committed.
- **Parsing:** HTML to Markdown with a stdlib converter; PDF text through poppler's `pdftotext` with classification of unusable text layers; OCR only for scanned PDFs, with the country's tesseract language model, low-confidence lines dropped, the document marked `text_source: ocr`, and OCR accuracy measured against text-layer PDFs; never guessed text. Country-language date and header patterns live in one module per source.
- **Audit and reports:** schema, duplicate ids, path mismatches and text quality checks that fail CI; generated progress (against a targets file), statistics and sources reports.
- **Static API:** the contract in `docs/api.md` generalised: `index.json`, paged listings per layer, type and division, `docs/<id>.json`, and a per-layer search index sharded by term prefix, with field bits and a size budget that falls back to titles and numbers. Tokenising, stop words and diacritic folding come from the profile's languages and are mirrored exactly in the app.
- **App (optional):** Compose Multiplatform with a shared module and thin platform hosts; repository interfaces over HTTP, bundled sample and cache; scopes derived from the profile's divisions (national plus each level with normative power); Compose resources with English base strings plus each UI language; design tokens generated from `DESIGN.md` frontmatter, with layer colours re-chosen for the country and AA contrast kept; anonymous, with bookmarks and settings on the device.
- **MCP server (optional):** stdio JSON-RPC over the built API with search, get-document, list-layers, list-documents and get-report tools.
- **Sync workflows (optional):** one scheduled workflow per source family committing to a `data/<name>-sync` branch, opening a PR, and merging itself once collector tests and the audit pass, regenerating only report files on conflict.

## Security rules (fixed across countries)

Grouped as agreed with the owner; the prompt states each as a rule plus how it is checked.

- **Collectors:** honour robots.txt and terms of use, rate-limit every host, never bypass a block, captcha, login, WAF or paywall, record a gap instead, and ask the person when a source forbids automation.
- **App privacy:** no accounts, no analytics or tracking, no data leaves the device except API reads.
- **Repository and CI:** no secrets in the repository; least-privilege `permissions:` per workflow, write scopes only where a job needs them; every third-party action pinned to a full commit SHA; dependency versions pinned in a version catalog; no deploys from fork PRs; pre-commit hooks for merge conflicts, large files, lint and the corpus audit.
- **Legal-text integrity:** SHA-256 of every source byte stream, authoritative sources preferred and marked, no machine translation, only anonymised case law, never invented text.

## Reuse path

The prompt carries a checklist of everything Swedish in lagar, so the agent wipes or replaces it and a final search proves nothing is left:

- **Delete:** `corpus/`, the entries of `sources/*.json`, state files, sync markers, generated reports, the Swedish source adapters (Riksdagen, SFSR, Domstolarna, Länsstyrelsen, municipal, SÖ, agency series), the Swedish data files in `collector/data/`, the geo file, `design/stitch/`.
- **Replace from the profile:** layer and type vocabulary, schema code patterns and cross-field checks, User-Agent and repository URLs, stop words and folding, OCR language, scope and tab names, route names, strings, layer colours, landing page copy and catalogue, published API URL, MCP descriptions.
- **Keep:** the generic modules (HTTP client, robots parser, frontmatter, writer, schema validator, `pdftext`, `ocr`, `htmlmd`, audit, reports, API builder and search index mechanics, MCP server, app shell, token generator, workflows and merge script).
- **Rename:** package and module names (`app.lagar`, `lagarmcp`), project name.

The copy starts a new git history (my call): lagar's history is mostly Swedish corpus commits and would make a wiped copy large for no gain.

## Non-goals

- A generator script or CLI. The deliverable is a prompt.
- Hosting, maintaining or supporting replicas.
- One multi-country app or a shared corpus across countries.
- Translating legal text, in the corpus or in the app.
- The architecture features in `docs/architecture.md` that lagar has not built (reading a law as of a past date, version comparison, inline notes).

## Anti-goals

The prompt fails, even if a project comes out, when:

- the agent scrapes against robots.txt or terms of use, or works around a block;
- legal text is machine-translated or guessed;
- code is written before the country profile and features are confirmed;
- Swedish structure leaks into another country (three hard-coded scopes in a federation, `ministry` forced where it means nothing, Swedish stop words, a Swedish flag accent);
- owner-specific details of lagar (accounts, domains, tokens) end up in a replica;
- the prompt names or depends on one agent product.

## Constraints

- **GitHub is required** (owner decision): repository, CI, sync auto-merge, least-privilege `permissions:`, SHA-pinned actions and `gh` are written for GitHub Actions only. The onboarding asks for the GitHub owner, not a host. The landing page defaults to GitHub Pages, with Vercel as an option the person can pick (my call), so no third-party account is needed.

- English throughout the prompt. It instructs the agent to talk with the person in the person's language.
- Size: aim for a prompt an agent can read in one pass (my call: under about 60 KB); detail goes into contracts and checklists, not prose.
- Tracked lagar files are the only source; nothing from the local master spec.
- Commit and PR rules for replicas: microcommits and Conventional Commits are fixed; whether commits mention an assistant is the replica owner's choice, not something the prompt imposes.

## Verification

- A fresh agent runs the prompt for two contrasting countries, one unitary and one federal with several authoritative languages, through Phase 2 only, and the country profiles are checked for leftover Swedish assumptions and unsourced claims. This is part of the deliverable: at most one revise-and-rerun round, results summarised in the PR description, profiles not committed (my call).
- A checklist pass of the reuse path against the current tree: every Swedish file named above exists and nothing Swedish is missing from the list.
- The prompt has no reference to the local master spec and no agent product names.

## Left to the builder

- The prompt's internal section order and wording, as long as the phases and gates hold.
- How much of each contract is inline versus a pointer to a lagar file for the reuse path.
- The exact format of the country profile data files (JSON is the default).
- Which two countries the dry run uses.
