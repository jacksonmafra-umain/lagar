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

To be written.

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
