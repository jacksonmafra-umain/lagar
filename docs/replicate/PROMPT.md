# Build lagar for your country

This prompt turns a coding agent into the builder of a lagar-style project for one country: the country's law collected from official sources into one Markdown file per norm, a static JSON API built from that corpus, and, if wanted, an app, a landing page and an agent tool server on top. [lagar](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/README.md) does this for Sweden. The country decides what is collected and how it is organised; lagar's architecture, parsing approach and security rules decide how it is built.

## How to use this prompt

Paste this whole file into your coding agent, in an empty folder or in a copy of lagar. The agent follows the phases below in order and stops at every gate until you answer.

Instructions for the agent:

- Read this whole prompt once before you say anything. Copy Phase 0 into your project instructions file (the file your agent reads at the start of every session) so the rules survive across sessions.
- **Resuming.** If `docs/replication/onboarding.md` or `docs/country-profile.md` already exists, read them first. Skip every question they already answer, tell the person what you found, and continue from the first phase that is not finished.
- The phases are gates. Phase 1 ends with saved answers, Phase 2 with an approved country profile, Phase 3 with an approved plan. Do not move past a gate without the person's explicit approval.
- The references at the end (A, B, C) are contracts, not suggestions. Each one summarises what must be true and links to the file in lagar that shows a working example. The links point to one fixed lagar version so they always match this prompt; read the linked file when you implement that part.
- If your agent can run helpers in parallel, use them for research and for independent collectors. Hand each helper the relevant rules from Phase 0 and Reference B.

## Phase 0: Ground rules

These rules hold for the whole project, in every phase and every session.

1. **Talk in the person's language.** Ask and report in the person's language. Everything written into the repository is in English (code, identifiers, frontmatter keys, file names, commits, docs) except the legal texts themselves and the app's UI strings.
2. **Never machine-translate legal text.** Not in the corpus, not in the app, not in a summary presented as the law. A text that is not published in a supported language is a gap, not a translation job.
3. **Never invent legal text.** If a source cannot be read (a scanned PDF without OCR, a broken page), record a gap. Never fill it from memory.
4. **Collect politely and legally.** Honour robots.txt and each site's terms of use, rate-limit every host, identify the collector with a User-Agent that carries the repository URL, and never bypass a block, captcha, login, firewall or paywall. When a source forbids automation, stop and ask the person.
5. **Gates first.** Do not write project code until the person has confirmed the onboarding answers (Phase 1), the country profile (Phase 2) and the plan (Phase 3).
6. **Respect the country's structure.** Layers, document types, divisions and identifiers come from the country profile. Never carry Swedish structure (three fixed scopes, ministries, SFS numbers, Swedish stop words) into another country.
7. **Prove it.** Every milestone ends with the tests and checks named in Reference A passing, and you show the person the result.
8. **Small steps.** One focused change per commit, Conventional Commits messages, each commit building and passing tests.
9. **Ask when unsure.** When a decision changes what gets built and nothing here settles it, ask the person one clear question instead of guessing.

## Phase 1: Onboarding

Ask these questions one at a time, in this order. Before each one, say in one sentence why it matters. Wait for the answer before the next question. When the person says "you decide", propose a concrete answer and ask them to confirm it.

1. **Country.** Which country's law the project covers. One project covers one country.
2. **Languages.** Two separate answers:
   - the languages in which the country's legal text is authoritative (some countries have several, for example Switzerland, Belgium, Canada or Finland), which decides what the collectors keep;
   - the app's UI languages, which one is the default, and the fallback language when the device's language is not supported. English is always the base set of strings.
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
6. **Project identity.** The project name, the GitHub owner (user or organisation) that will host it, the licence for the code (lagar uses MIT; legal texts are usually public domain or under the source's terms), and the contact URL for the collectors' User-Agent. GitHub is required: the CI, the sync workflows and the security rules are written for GitHub Actions.

Write the answers to `docs/replication/onboarding.md` (one heading per question, the answer, and the date), read them back to the person in a short summary, and ask them to confirm. That confirmation is the Phase 1 gate.

## Phase 2: Legal-structure research

You research the country's legal organization; the person confirms it. Use official sources first: the legislature, the government's legal gazette, the courts, national statistics or mapping agencies, and the country's legal information portal. Cite a URL for every claim and mark anything you could not verify as **unverified**. If your agent can browse in parallel, give each layer to a separate helper.

Research these, in this order:

1. **Hierarchy of norms.** Every level from the constitution down to local rules, with how each ranks against the others: constitutional law, statutes, ordinances or decrees, agency regulations, regional and municipal rules, case law (which courts publish guiding or precedent decisions), treaties, and supranational law. Supranational law (for example EU law in a member state) gets a layer only when a body's law applies directly in the country.
2. **Administrative divisions.** The levels below the nation that issue their own binding rules: there can be any number of levels (Sweden has län and kommun; a federation may have states, districts and municipalities). For each level: its name in the official language, the official code list and its code pattern, and an authoritative source for the list and for coordinates (used by the app's location suggestion).
3. **Languages of the law.** Which languages each layer is authoritative in. A country can have several authoritative languages, and one norm can exist in more than one; record which sources publish which language.
4. **Official sources per layer.** For each layer: the host, how it is accessed (API, open-data dump, HTML pages, PDF), the identifier scheme (national numbering, ELI, ECLI or others), the signal for incremental updates (change date, feed, sitemap), the robots.txt rules for the paths you need, the terms of use, and whether the text there is the authoritative one. Read robots.txt and the terms yourself; do not assume.
5. **Case-law privacy.** Whether anonymised versions of decisions are published and which publications may be stored. Only anonymised case law is ever collected.
6. **Gaps.** Layers or divisions with no machine-readable source, a source that forbids automation, or one behind a login, paywall or captcha. Record each one with the reason and the URL; never plan a workaround.

Write the result in two files:

- `docs/country-profile.md`: the readable version, one section per item above, every claim with its URL.
- `collector/data/country-profile.json`: the machine-readable version that the collectors, the audit, the API builder and the app read. Top-level keys:
  - `country`: name and ISO 3166-1 code.
  - `languages`: `legal` (authoritative languages, ISO 639-1), `ui` (app languages), `default_ui`, `fallback_ui`.
  - `divisions`: a list, one entry per level, each `{level, name, code_pattern, source}`, from the largest to the smallest.
  - `layers`: a list of `{id, name, rank, types}`, with English ids (`fundamental`, `statute`, `agency`, `case_law`, a supranational id such as `eu`, one per division level, and so on), names in the legal languages, and `rank` from 1 (highest).
  - `types`: a closed map from document type (English, snake_case) to its layer.
  - `frontmatter`: for each country-specific frontmatter key (Reference A, Corpus), `required`, `optional` or `absent`, plus any key this country adds, with its pattern.
  - `sources`: a list of `{layer, host, access, id_scheme, update_signal, robots, terms, authoritative}`.
  - `case_law_privacy`: what is published anonymised and what may be stored.
  - `gaps`: a list of `{layer, reason, url}`.

lagar's Swedish version of this structure is in [`collector/lagar/vocabulary.py`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/collector/lagar/vocabulary.py) and [`docs/schema/frontmatter.schema.json`](https://github.com/jacksonmafra-umain/lagar/blob/46a8e7d3f386bbbec82917a9725fe03220268ab5/docs/schema/frontmatter.schema.json); use them as a worked example, not as a template to copy.

Present the profile to the person as a short summary: the layers in rank order, the divisions, the sources with their access method, and the gaps. Ask them to approve it or correct it. No code is written until the person approves the profile; when they correct something, update both files and ask again.

## Phase 3: Plan

To be written.

## Phase 4: Build

To be written.

## Reference A: Architecture contracts

To be written.

## Reference B: Security rules

To be written.

## Reference C: Reusing lagar

To be written.
