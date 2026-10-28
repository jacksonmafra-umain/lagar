# Landing page design

Date: 2026-10-28
Status: approved

## Intent

lagar needs a public front door. Today the only ways in are the GitHub repository and local builds. The landing page tells any resident of Sweden, not lawyers, what lagar is in a few seconds: Swedish law in its current wording, in one place, without getting lost in amendments and versions. Then it sends them into the web app.

The page is also where the project explains itself: why it exists, where its data comes from and that it is open source. The native apps are not in the stores yet; the page says they will come later, without store badges.

Background documents:

- `CLAUDE.md`: hard rules (English everywhere, i18n, micro commits, no assistant mention).
- `DESIGN.md`: the design system the page reuses.
- `NOTICE.md`, `COVERAGE.md`: legal notice and source list the page summarises.
- `app/README.md`: how the wasmJs web app is built and that it works under any path prefix.

## Audience and success

- Audience: any resident of Sweden who needs to read a law, in Swedish or English.
- Success: a first-time visitor understands what lagar is and reaches the web app with one click. A curious visitor finds the motivation, the sources and the repository without hunting.

## Goals

1. A single static landing page in Swedish (default) and English.
2. The Compose wasmJs web app published under `/app/` on the same domain.
3. A build script that assembles both into one static output folder.
4. Deploys to Vercel: a preview per pull request, production on merge to `main`.
5. Work tracked as labelled GitHub issues and PRs, merged to `main`, with micro commits.

## Non-goals

- No framework, bundler or Node build for the landing page.
- No hosted JSON API in this work. The web app reads `api/v1/` next to itself; on Vercel, `landing/vercel.json` proxies `/app/api/v1/*` to the API published on GitHub Pages.
- No custom domain yet: the first release lives on the project's `*.vercel.app` address.
- No analytics, cookies, newsletter, contact form or accounts.
- No app store badges until the apps are published.

## Anti-goals

- The page must never read as an official government or agency service: no crown, no agency logos, no flag-yellow hero, no wording like "officiell". A visible note says it is an independent project.
- No machine translation of legal text. Only UI and project copy is translated.
- No claims of completeness or legal authority. The page repeats the `NOTICE.md` point: texts are informational and do not replace Svensk författningssamling.

## Visual design (decided)

Direction A from the mockups: the landing page matches the app.

- Colors from `DESIGN.md`: navy `primary` `#004373` for headings and the primary button, `surface` `#f8f9fc` background, `on-surface` text, `outline-variant` borders, and the gold `tertiary-container` `#d0a700` only as a thin accent rule. Dark mode from `colors-dark` in `DESIGN.md`, following `prefers-color-scheme`.
- Typography: Source Serif 4 for headlines, Inter for everything else. Fonts self-hosted (copied from the app's bundled fonts), not loaded from Google Fonts, so the page makes no third-party requests.
- Sober tone: no imagery beyond simple layer-colored accents, no animation beyond subtle hover states.
- Tokens are CSS custom properties on `:root`. Whether they are generated from the `DESIGN.md` frontmatter or hand-copied with a comment pointing to it is left to the builder; generation is preferred if it is cheap.

## Page structure

One page, top to bottom:

1. Header: wordmark "lagar", language toggle (SV / EN).
2. Hero: headline, one-line lead, primary button "Öppna lagar" / "Open lagar" linking to `/app/`, secondary link to the GitHub repository, the note "Oberoende projekt. Inte en myndighetstjänst." / "Independent project. Not a government service."
3. Why lagar: the motivation (draft below).
4. What is inside: SFS acts and ordinances today, with the planned layers (agency regulations, case law, EU law, regional and municipal regulations, public services) marked as coming. Numbers stay out of the copy unless the builder wires them to `PROGRESS.md`; a hand-typed count goes stale.
5. Sources and references: links listed below.
6. Open source: MIT licence, repository link, how the corpus is built (one Markdown file per norm, static JSON API), sister project leis. One line that Android and iOS apps are planned.
7. Footer: legal notice (texts informational, not a replacement for SFS; statutes not copyrighted under Upphovsrättslagen 9 §), licence, repository, attribution line from `NOTICE.md`.

## Motivation draft (owner to edit)

English:

> Swedish law is public, but reading it is harder than it should be. An act is amended again and again, and the wording that applies today is spread across the original text and every change since. Official sources are complete but built for people who already know where to look.
>
> lagar puts the current wording of each law in one clean place, readable on a phone, free and without an account. Every law is a plain text file in an open repository, built from official open data, so anyone can check where a text came from, reuse it, or help improve it.

Swedish:

> Svensk lag är offentlig, men den är svårare att läsa än den borde vara. En lag ändras om och om igen, och den lydelse som gäller i dag är utspridd över originaltexten och alla ändringar sedan dess. De officiella källorna är fullständiga men byggda för den som redan vet var man ska leta.
>
> lagar samlar den gällande lydelsen av varje lag på ett ställe, lätt att läsa i mobilen, gratis och utan konto. Varje lag är en vanlig textfil i ett öppet arkiv, byggd från officiella öppna data, så att vem som helst kan se var en text kommer ifrån, återanvända den eller hjälpa till att förbättra den.

Production goes live with this draft (owner decision); the owner's edit and a native read of the Swedish follow as a later issue.

## Sources and references

- Riksdagen open data: `https://data.riksdagen.se/`
- Svensk författningssamling (official publication): `https://svenskforfattningssamling.se/`
- Lagrummet, the public legal information portal: `https://lagrummet.se/`
- Upphovsrättslagen (1960:729) 9 § on Riksdagen.
- Repository: `https://github.com/jacksonmafra-umain/lagar`
- Sister project leis (Brazil): `https://github.com/jacksonfdam/leis`

All external links open normally (no tracking parameters).

## i18n

- Swedish is the default. English is the second language.
- Language resolution: an explicit choice (stored in `localStorage`) wins; otherwise `navigator.language` `en*` gives English and everything else gives Swedish, matching the app rule.
- Strings live in one place per language (for example `landing/i18n/sv.json` and `en.json`, or `data-*` attributes resolved by a small script). The Swedish text is in the HTML by default so the page works and indexes without JavaScript; the script swaps to English.
- `<html lang>` updates with the language.
- The landing page's language choice does not carry into the web app: the app keeps resolving its language from the system locale and its own setting. Passing the choice through (for example a query parameter the app reads) is a separate app issue, not part of this work.
- Whether English also gets its own URL (`/en/`) for sharing and indexing is left to the builder; a query parameter or path is fine, a hash is not.

## Layout in the repo and build

- `landing/`: hand-written landing page (`index.html`, CSS, the toggle script, fonts, favicon, `vercel.json` if needed).
- `scripts/build-site.sh` (name is the builder's call): runs `./gradlew :webApp:wasmJsBrowserDistribution` from `app/`, copies `landing/` into `build/landing/`, then copies `app/webApp/build/dist/wasmJs/productionExecutable/` into `build/landing/app/`. The output is plain static files.
- The repository's top-level `api/` folder must never be uploaded as the Vercel project root: Vercel would treat it as serverless functions. Deploying the assembled output folder avoids this.
- `.wasm` must be served as `application/wasm` (Vercel does this by default; verify).

## Deploy

- One Vercel project named `lagar` under the owner's Umain Vercel account `jacksonmafra-umain` (owner decision), never the personal `jacksonfdam` account. Before any `vercel` command, check `vercel whoami` reports the Umain account; stop and ask if not.
- The assembled folder is deployed as a static site. The builder picks between `vercel deploy` of the output folder and `vercel build` + `vercel deploy --prebuilt`.
- GitHub Actions workflow (`.github/workflows/site.yml`): on pull requests that touch `landing/`, `DESIGN.md`, `app/` or the build script, build and deploy a preview and post its URL on the PR; on push to `main`, deploy production. It needs JDK 21 for the Gradle build and the secrets `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, which the owner adds.
- The same script also runs locally, so the owner can deploy from their machine with the CLI logged in to the Umain account.
- Previews keep Vercel's default deployment protection (only the owner can open them). Pull requests from forks cannot read the secrets: the workflow skips the deploy for them cleanly and does not use `pull_request_target`.

## Quality bar

- Valid HTML, works without JavaScript (Swedish), keyboard reachable, visible focus, contrast AA in both themes, `prefers-reduced-motion` respected.
- Works at phone width with no horizontal scroll.
- Lighthouse accessibility and best practices at 100 is the target, not a gate.
- Meta description, Open Graph tags and a favicon in both languages.

## Work breakdown (for the plan)

Issues with `type:` and `area:` labels, assigned to the owner, each closed by a PR into `main`. Suggested split:

1. Landing page content and layout in Swedish (`area: design` plus a new `area: site` label).
2. English translation and language toggle.
3. Build script assembling the landing page and the web app.
4. Vercel project and deploy workflow (`area: ci`).
5. README and `docs/screens.md` / docs links to the live site.
6. Copy review: owner edits the motivation and a native speaker reads the Swedish. Production does not wait for it (owner decision); it is a later issue.

## Calls made without the owner

- Swedish as default language, matching the app.
- A visible "independent project" note.
- Self-hosted fonts, no third-party requests, no analytics.
- `landing/` as the folder name, `/app/` as the web app path, `*.vercel.app` address first.
- Both local and GitHub Actions deploys; Actions needs the owner to add the Vercel secrets.
- Motivation copy as drafted above, pending the owner's edit.
- Previews stay protected (owner-only); fork PRs get no preview.
- Landing language choice is not passed to the web app in this work.

## Changes during implementation

- The source folder is `landing/`, not `site/`: the `Pages` workflow uses a top-level `site/` as its build output, so a tracked `site/` would leak into the GitHub Pages deploy.
- The web app now reads the real API (`api/v1/` relative to its page), so the "sample data" note was dropped and `landing/vercel.json` proxies `/app/api/v1/*` to `https://jacksonmafra-umain.github.io/lagar/api/v1/`. If GitHub Pages is down, the app on Vercel cannot load data.
- The Vercel project `lagar` lives under the owner's account `jacksonmafra-1855` (personal scope, Hobby), owner decision. Production: <https://lagar-three.vercel.app>. Vercel's Git integration is disconnected; only the `Site` workflow deploys, and only when all three Vercel secrets are set.
