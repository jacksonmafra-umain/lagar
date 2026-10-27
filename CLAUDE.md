# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

Pre-bootstrap: no code, build files or tests exist yet. The repo currently holds only planning and design input:

- `lagar-implementation-prompt.md` — **the master spec**, local-only: it is excluded from git (`.git/info/exclude`) and may be missing in other clones. When present, read it before any work; it defines the monorepo layout, corpus schema, static API contract, app stack, CI workflows and milestones (M0–M12). Follow its milestone order. When missing, rely on this file, `docs/` and `DESIGN.md`, and ask the owner for anything they don't cover. Never commit it or quote it in tracked files.
- `docs/architecture.md` — app information architecture: normative-layer hierarchy, context engine, 4-tab shell (Utforska / Hierarki / Sparade / Tjänster), onboarding and navigation flows. Some features it describes go beyond the spec (reading a law as of a past date, version comparator, inline notes, GPS kommun detection); the static API in the spec does not yet expose historical text, so check with the owner before building those.
- `DESIGN.md` — the chosen design system ("Nordic Juridisk Klarhet"): M3 color roles (light + dark), layer colors, typography, radii, spacing, Liquid Glass elevation spec, Compose implementation notes. Started from `design/stitch/nordic_juridisk_klarhet/DESIGN.md` but has since been extended (dark mode, accessible layer text colors); the root file is canonical, the Stitch copy is the untouched export.
- `design/stitch/` — Google Stitch export (`code.html` + `screen.png` per screen).

When commands (Gradle, Python collector, API generator) are added, update this file with them.

## What lagar is

Swedish legislation, case law, EU law, municipal regulations and public services as one YAML-fronted Markdown file per norm (`corpus/`), built by a Python collector, turned into a static JSON API on GitHub Pages (`api/`), and consumed by a Compose Multiplatform app (`app/`: Android, iOS, wasmJs SPA). Sister project of the Brazilian corpus <https://github.com/jacksonfdam/leis>; reuse its ideas (closed type vocabulary, resumable rate-limited collectors, SHA-256 source snapshots, generated progress files, `git fast-import` history reconstruction).

Planned data flow: `collector/` (Python, `python3 -I`, stdlib first) → `corpus/*.md` + `sources/` snapshots → `api/` generator → `/api/v1/*.json` → app. The app depends only on the API contract (`docs/api.md`), never on the corpus directly. Corpus history is rebuilt on a dedicated branch as one commit per amendment, dated at entry into force.

## Hard rules from the spec

- Everything in English (code, identifiers, frontmatter keys, file names, commits, docs). Only legal texts and Swedish UI strings are in Swedish. Never machine-translate legal text in the app.
- No mention of any AI/assistant/tool in commits, trailers, PRs, README, comments or file headers.
- Micro commits, Conventional Commits (`feat(collector):`, `fix(app):`, `data(sfs):`, `chore(ci):`, `docs:`, `test:`); each commit builds and passes tests.
- i18n from day one: Compose resources, `values/` = English base, `values-sv/` = Swedish, app defaults to Swedish when system locale unsupported. No hardcoded user-facing strings.
- Collectors: rate-limited, resumable, idempotent, honour `robots.txt`, descriptive User-Agent with repo URL, never bypass blocks/captchas/paywalls (record as coverage gap). Case law: anonymised versions only.
- Pin latest stable Kotlin / CMP / AGP / Gradle / Ktor via a version catalog.
- No user accounts or BankID sign-in for now (owner decision). The app is anonymous; bookmarks and settings stay on the device. The Swedish Stitch screen still shows BankID — ignore that element.
- Stop and ask the owner when: the Stitch export is missing or ambiguous, `gh` is authed to an account other than the owner's Umain account (`jacksonmafra-umain`), a source forbids automation, or Stitch conflicts with accessibility/i18n.

## Design input caveats

- Most screens in `design/stitch/` are from the Brazilian **leis.org** project (`lang="pt-BR"`, Brazilian states/municipalities, Portuguese labels). Treat them as layout/component references only; translate concepts to the Swedish model (Nationell / Region / Kommun scopes, Swedish layer names). Only `lagar_normhierarki_f_rgsystem/` is Swedish.
- `design/stitch/juris_glass_system/DESIGN.md` is an alternative system; the root `DESIGN.md` (Nordic Juridisk Klarhet) is the one to implement.
- Layer colors live in the `layers:` frontmatter of `DESIGN.md` (base values match the spec's fallback palette); every chromatic accent maps to a normative layer. Each layer has `base` (light icons/borders/tints), `text` (light-mode text, AA-safe) and `dark` (all dark-mode uses). Never put text in a `base` color — six bases fail contrast. Badges/surfaces use 10–12% alpha of the layer color (14–16% in dark), 20% alpha border.
- The spec's `layer` field has one `sfs` value, but the palette splits SFS acts and ordinances: pick the color from `type`.
- Typography: Inter for UI chrome, Source Serif 4 for legal text; § numbers bold Inter.
- Theme lives in `app/shared/.../designsystem/` (`LagarTheme`, `LagarColors`, `LagarTypography`, `LagarSpacing`, shapes), light + dark; write `docs/design.md` inventory before UI code.
