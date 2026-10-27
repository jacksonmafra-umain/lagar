# Bootstrap design: first corpus and first app, in parallel

Date: 2026-10-27
Status: approved

## Intent

Get lagar from "docs only" to something real on both sides at once:

- **Corpus track:** actual Swedish legislation collected from official open data into `corpus/` as Markdown, one file per norm.
- **App track:** the Compose Multiplatform app running with the lagar design system, showing laws in the reader.

The owner wants visible results first. CI and broad test suites come last. The two tracks meet at the static JSON API contract, so neither waits on the other.

Background documents (read them before planning):

- `CLAUDE.md`: project state, hard rules, design caveats.
- `DESIGN.md`: canonical design system (light and dark tokens, layer colors, glass, Compose notes).
- `docs/architecture.md`: normative hierarchy, context engine, 4-tab shell, navigation flows.
- `design/stitch/`: Stitch export. Most screens are Brazilian leis.org layouts and are layout references only; `lagar_normhierarki_f_rgsystem/` is the Swedish screen.
- `lagar-implementation-prompt.md` (local-only master spec, may be absent): sections 1–5 define the layout, corpus schema, API and app stack this design follows.

## Goals

1. Monorepo skeleton in the layout from the master spec: `corpus/`, `collector/`, `api/`, `app/` (`shared`, `androidApp`, `iosApp`, `webApp`), `docs/`, plus licence/NOTICE, `.editorconfig`, `.gitattributes`, `.gitignore`, README skeleton.
2. `docs/api.md`: the static API contract, written first, because both tracks code against it.
3. **Corpus track**
   - Frontmatter schema (`docs/schema/` JSON Schema) and the closed type vocabulary (`collector/lagar/vocabulary.py`).
   - SFS collector against Riksdagen open data (`data.riksdagen.se`, document type `sfs`): list, metadata and text, written as `corpus/...` Markdown with the spec's frontmatter.
   - The four fundamental laws first (Regeringsformen 1974:152, Tryckfrihetsförordningen 1949:105, Yttrandefrihetsgrundlagen 1991:1469, Successionsordningen 1810:0926) under `corpus/fundamental-laws/`, layer `fundamental`.
   - Then about 100 SFS documents end to end, then a full run of all SFS acts and ordinances.
   - Rate-limited (conservative default, configurable), resumable via a state file, idempotent, incremental (`--since`), descriptive User-Agent with the repo URL, honours `robots.txt`.
4. **App track**
   - KMP/CMP project with a Gradle version catalog pinned to the latest stable Kotlin, Compose Multiplatform, AGP, Gradle, Ktor, Koin, kotlinx.serialization/coroutines/datetime.
   - Targets: `androidTarget`, `iosArm64`, `iosSimulatorArm64`, `wasmJs` (web served under `/lagar/`). Android is the first target checked visually; the others must build and run.
   - Design system in `app/shared/.../designsystem/` (`LagarTheme`, `LagarColors` light/dark, layer palette, `LagarTypography`, `LagarSpacing`, shapes) generated from the `DESIGN.md` frontmatter, not hand-copied. Inter and Source Serif 4 bundled.
   - i18n from the first screen: `values/strings.xml` (English base) and `values-sv/strings.xml`; Swedish when the system locale is unsupported; manual override.
   - Screens in this order:
     1. 4-tab shell: Utforska, Hierarki, Sparade, Tjänster.
     2. Utforska: the Swedish Stitch screen (layer distribution chart and the nine layers with counts and layer colors, from `index.json`). Hierarki: the norm pyramid from the same data.
     3. Layer list: paginated listing of one layer/series.
     4. Reader: metadata header, in-force/repealed status, Markdown body in Source Serif 4, link to the official source.
     5. Minimal settings: language (System / Svenska / English) and theme (System / Light / Dark), reachable from the side drawer.
   - Sparade and Tjänster show designed empty states in this round.
   - Data layer behind an interface with two implementations: bundled sample JSON (fixtures that follow `docs/api.md`) and a Ktor client for the real API. A single configuration switch chooses which.
5. **Meeting point:** a minimal `api/` generator (Python) that turns `corpus/` into the `index.json`, paginated listings and `docs/<id>.json` files from the contract. Served locally by any static server, it lets the app switch from sample data to the real corpus.

## Non-goals (this round)

- CI workflows and broad test suites (owner decision: last). Small tests that keep a piece working while it is built are fine.
- User accounts, BankID or any sign-in (owner decision). The app is anonymous; settings stay on the device.
- Authoritative SFS PDF snapshots from `svenskforfattningssamling.se`, Git LFS in `sources/`, and `authoritative: true` documents.
- History reconstruction (one commit per amendment), `history.json`, the amendment timeline in the reader, reading a law as of a past date, the version comparator.
- `plan.py`, `audit.py`, `PROGRESS.md`, `progress.svg`, `COVERAGE.md`.
- Agency regulations, case law, EU law, regions, municipalities, services layer.
- Search, onboarding, splash, location/GPS, bookmarks and offline cache, inline notes.
- GitHub Pages deployment (the repo itself is created and pushed).

## Anti-goals

- Inventing screens, colors, type or spacing that contradict `DESIGN.md` or the Swedish Stitch screen. Brazilian Stitch screens must not leak Brazilian concepts or Portuguese text into the app.
- Hardcoded user-facing strings, or sentences built by string concatenation.
- Machine-translating legal text. Legal content is shown in its original language.
- Hammering Riksdagen: no parallel request storms, no ignoring errors by retrying in a tight loop, no bypassing any block.
- Text in a layer's `base` color (six of them fail contrast); use the `text` token in light mode and `dark` in dark mode.
- Any mention of AI or tooling in commits, docs, code or README.

## Constraints

- Everything written is English; only legal texts and Swedish UI strings are Swedish.
- Micro commits, Conventional Commits, each commit builds. Commits are authored by the owner's git identity with no attribution trailers.
- Python: standard library first, run with `python3 -I`.
- The app depends only on the API contract, never on `corpus/` files directly.
- `lagar-implementation-prompt.md` stays local-only and is never committed or quoted.

## Decided by the owner

- Corpus and app are built in parallel.
- CI and tests last.
- No BankID or sign-in for now.
- `DESIGN.md` (root) is the design source of truth; `docs/architecture.md` describes the navigation.
- Screens without a Stitch design (layer list, reader, settings, Swedish drawer) are designed by the builder from `DESIGN.md` components and the Swedish Stitch screen's patterns. The Swedish Stitch screen is the **Utforska** tab: layer distribution chart plus the nine-layer list with counts. Hierarki shows the norm pyramid built from the same data.
- Corpus files land on `main` as one commit per collector batch (`data(sfs): add …`); the later history reconstruction replaces this history on its own branch.
- Create the public GitHub repo `jacksonmafra-umain/lagar` (after checking `gh auth status` is on that account) and push regularly.

## Calls made by the designer (owner may override)

- Fundamental laws plus ~100 SFS documents as the first end-to-end batch before the full run.
- Utforska/Hierarki → list → reader as the first app screens, with Sparade and Tjänster as empty states.
- Sample JSON fixtures as the app's first data source, so the app does not wait for the collector.
- The minimal `api/` generator is part of this round, as the meeting point of the two tracks.
- Official PDF snapshots deferred; `source_sha256` holds the hash of the fetched Riksdagen response.
- Design specs live in `docs/specs/`.
- Top bar of the Swedish Stitch screen: search, `⌘K` field and notifications are hidden until those features exist; the profile icon opens the side drawer with settings (no account); the dark-mode toggle stays and switches theme.
- All nine layers are always listed: `index.json` includes every layer with its count (0 when empty), and empty layers show a designed "coming soon" state instead of being hidden.
- "Full SFS set" means everything Riksdagen's `sfs` document type returns: base acts and ordinances in their consolidated form, repealed ones included and marked `repealed`. Amending acts are not separate files; they appear in `amended_by`. The four fundamental laws live only under `fundamental-laws/`.

## Left to the builder

- Exact JSON field names in `docs/api.md`, within the spec's endpoint list (`/api/v1/index.json`, `/api/v1/<layer>/index-<page>.json`, `/api/v1/docs/<id>.json`) and the frontmatter schema.
- How to tell acts from ordinances in Riksdagen metadata, and how to map Riksdagen fields to the frontmatter.
- Default rate limit value, state-file format, page size.
- How the token generator reads `DESIGN.md` (Gradle task or script) as long as the frontmatter is the single source.
- Markdown renderer for CMP (must support wasmJs) and backdrop-blur library (e.g. Haze), with the solid fallback described in `DESIGN.md`.
- Navigation library and typed routes, module boundaries inside `shared`.
- Splitting the work into separate sessions or worktrees per track.

## Done when

- `corpus/` holds the four fundamental laws and the full SFS set from Riksdagen, valid against the JSON Schema.
- The app runs on Android with the lagar theme in light and dark, in Swedish and English, and shows Utforska → list → reader from sample data.
- iOS simulator and wasmJs builds run the same screens.
- The `api/` generator output, served locally, can replace the sample data and the reader shows a real law from the corpus.
