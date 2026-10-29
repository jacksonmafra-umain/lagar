# App screens and features

Inventory of every screen in the Compose Multiplatform app (`app/`). For each one it gives the route, the design references and the features, with their status. Code paths are relative to `app/shared/src/commonMain/kotlin/app/lagar/`.

**Design references.** [`DESIGN.md`](../DESIGN.md) is the canonical design system: tokens, glass tiers, typography and components. [`docs/architecture.md`](architecture.md) defines the screens and flows. The Stitch exports in `design/stitch/` are layout references only; most of them come from the Brazilian project, so their concepts are mapped to the Swedish Nationell / Region / Kommun model. There is no sign-in, so BankID and profile elements are not built.

**Status values:**
- **Done:** built and matching the reference.
- **Partial:** built, but incomplete or off-spec.
- **Missing:** not built.
- **Blocked:** needs data or an API endpoint that does not exist yet.

The number after each gap is its GitHub issue.

## Layout check

Checked on 2026-10-29 in the web app run offline with `python3 -I scripts/serve_local.py` (full local API), at 375x812 against the Stitch screens and `DESIGN.md`, and at 1440x900 against the wide-layout rows below. Stitch's Portuguese text, Brazilian data, BankID and profile elements are not counted, nor are gaps already listed with an issue. The desktop reference `lagar_multi_jurisdiction_design_system_portal` is not in `design/stitch/`, so the wide layouts were checked against this file and `DESIGN.md` only. Tablet (#35) was not checked.

| Screen | Result | Issues |
| --- | --- | --- |
| Splash | Matches, with the known corpus-size gap | |
| Welcome (step 1) | Matches | |
| Scope (step 2), Locality (step 3) | Matches; back arrow at the top left (fixed) | #128 |
| Utforska, Nationell | Matches, with known gaps | |
| Utforska, Region and Kommun | Matches; the search hint follows the scope (fixed) | #130 |
| Scope sheet, Drawer | Matches; the drawer button uses a menu icon (fixed) | #134 |
| Search results | Matches; the active scope is shown with a scoped empty state, the document the query names ranks first and case-law titles no longer carry "-----" separators (fixed) | #126, #127, #135 |
| Advanced search | Matches; the scope chip moves under the title on narrow windows (fixed) | #131 |
| Hierarki, wide home hierarchy | Matches; counts are digit-grouped and include the SFS other statutes (fixed) | #125, #133 |
| By ministry | Matches | |
| Layer list | Matches; the header badge no longer touches the top edge of the bar (fixed) | #129 |
| Reader | Matches; the table of contents opens over the dimmed reader, validity markers show as labels on the § card and the ministry is shown without its unit code (fixed) | #123, #124, #132 |
| Sparade | Matches, with the known repealed gap | |
| Tjänster | Matches | |
| Settings | Matches; Swedish and English complete on the screens visited | |
| Wide top bar, wide home, reader panes, two-column search and advanced search (1440x900) | Match the layout; the content fixes above apply there too | |

The API now has case law (16,390 documents), so rows below marked "Blocked: no case-law data" (#38) need a fresh look.

## Cross-cutting design work

| Topic | Status | Issue |
| --- | --- | --- |
| Glass tier 1 on article cards and input frames, tier 2 on sticky bars, tier 3 on the drawer and sheets, reduce-transparency support | Done | #23 |
| Input, button and checkbox shapes, search focus glow, web `⌘K` hint | Done | #24 |
| Repealed treatment (grey, strikethrough, history icon) everywhere | Partial: only the layer list is correct | #21 |
| Bookmark icon in the document's layer colour | Missing | #22 |
| Desktop layout (window ≥ 1024dp): top bar navigation, max content width, wide home | Done | #79 |
| Desktop layouts of onboarding, search, advanced search, the layer list and the reader | Done | #35 |
| Tablet two-pane layout (768–1023dp) | Missing | #35 |
| `docs/design.md` component inventory up to date | Done | #25 |
| Swedish and English strings, no hardcoded UI text | Done | |

## Shell

The app shell has four tabs (Utforska, Hierarki, Sparade, Tjänster) in a glass bottom bar. The glass top bar holds the title, a scope chip, search and the drawer button. Pushed screens use a back top bar. Code: `ui/shell/`.

On windows at least 1024dp wide (`ShellDimens.WideBreakpoint`, exposed as `LocalWideLayout`) the bottom bar gives way to a wide top bar (`WideTopBar.kt`): wordmark, scope switch, the tabs plus "Sök & filter" (opens the advanced search), search, theme toggle and the drawer button. Reference: Stitch `lagar_multi_jurisdiction_design_system_portal` (desktop), without BankID, the profile and any official-portal framing.

| Feature | Status | Issue |
| --- | --- | --- |
| Wide top bar with navigation; content capped at 1280dp on Utforska, Hierarki and Sparade | Done | #79 |
| Back top bar of the pushed screens lines its content up with the wide top bar | Done | #35 |
| Scope switch in the bar from 1360dp, Nationell / Region / Kommun plus "Institutionellt" shown disabled | Done | #79 |
| Search field with ⌘K in the bar | Partial: search button | #24 |

### Drawer

Code: `ui/shell/Drawer.kt`. Reference: Stitch `menu_lateral_drawer_perfil_e_navega_o`, without the profile and sign-out.

| Feature | Status | Issue |
| --- | --- | --- |
| Header, six entries, About block with data build date | Done | |
| Opened from a menu icon button in the top bar and the wide top bar (no profile avatar, the app has no accounts) | Done | #134 |
| Each scope as a direct switch (Region / Kommun without a stored locality, and the active scope, open the scope sheet), Saved count badge, "Switch scope" / "Navigate" / "About" section headings | Done | #31 |
| "Most popular" and "Official gazettes" entries | Blocked: no usage data, no gazette source | #38 |

### Scope sheet

A modal sheet opened from the scope chip, the drawer or the location card. Code: `ui/home/ScopeSheet.kt`. References: Stitch `home_troca_de_mbito_e_localidade` and `modal_troca_de_localiza_o_estado_e_munic_pio`.

| Feature | Status | Issue |
| --- | --- | --- |
| Scope cards with Active and count badges, region and kommun pickers, changes applied on Done | Done | |
| Glass overlay (tier 3; opaque fallback, since a modal sheet's window has no backdrop to blur) | Done | #23 |
| "Use my location" in the locality pickers: suggests the nearest kommun offline from bundled SCB centroids, coarse permission only, nothing stored but the chosen kommun | Done | #30 |
| Linked kommun status card | Blocked: no municipal data | #38 |

## Onboarding

### Splash

Route: `Splash`. Code: `ui/onboarding/SplashScreen.kt`. Reference: Stitch `splash_loading_leis.org`.

| Feature | Status | Issue |
| --- | --- | --- |
| Loads the API index, then routes to onboarding or home | Done | |
| Stitch glass logo card | Done | #23 |
| Corpus-size line | Missing | |

### Welcome (step 1)

Route: `OnboardingWelcome`. Code: `ui/onboarding/WelcomeScreen.kt`. Reference: Stitch `onboarding_boas_vindas_leis.org`, architecture §4 flow 1.

| Feature | Status | Issue |
| --- | --- | --- |
| Introduction, three scope cards with live document counts, step progress | Done | |
| Skip at the top right, as in Stitch; stores the defaults (Nationell, no locality) and leaves like the last step | Done | #29 |
| Choice of main focus (Medborgare, Student, Jurist), stored on the device and changeable in Settings; it only orders the home key-law groups | Done | #29 |

### Scope (step 2)

Route: `OnboardingScope`. Code: `ui/onboarding/ScopeStepScreen.kt`, `ScopeCard.kt`. Reference: Stitch `onboarding_sele_o_de_mbito`.

| Feature | Status | Issue |
| --- | --- | --- |
| Selectable Nationell, Region and Kommun cards with layer colours and counts | Done | |
| Skip at the top right, and a "stored on this device" note | Done | #29 |
| Back arrow at the top left, returning to the welcome step | Done | #128 |

### Locality (step 3)

Route: `OnboardingLocality`. Code: `ui/onboarding/LocalityStepScreen.kt`, `LocalityPickers.kt`. Reference: Stitch `onboarding_localiza_o_e_munic_pio`.

| Feature | Status | Issue |
| --- | --- | --- |
| Searchable region and kommun pickers for all 21 regions and 290 kommuner, both optional | Done | |
| Skip at the top right | Done | #29 |
| Back arrow at the top left, returning to the scope step | Done | #128 |
| Kommun suggested from the device location (offline nearest SCB centroid, coarse permission; pre-selected for the user to confirm, with denied, unavailable, timeout and abroad messages) | Done | #30 |
| Linked kommun summary (council, document count) | Blocked: no municipal data | #38 |

### Desktop layout

All three steps share `OnboardingScaffold` (`ui/onboarding/StepHeader.kt`). From 1024dp the frame is capped at 1040dp (`ShellDimens.FormMaxWidth`): the title, text and (on step 1) the Lagar card form a left column beside the choices, and the primary action follows the choices instead of spanning the window.

| Feature | Status | Issue |
| --- | --- | --- |
| Two-column steps capped at the form width | Done | #35 |

## Utforska (home)

Route: `Utforska`. Code: `ui/home/`. References: Stitch `home_legislativa_leis_federais_brasil` (Nationell) and `home_legislativa_leis_estaduais_rs` (Region), the feed card on `lagar_normhierarki_f_rgsystem`, and architecture §4 flow 2.

| Feature | Status | Issue |
| --- | --- | --- |
| Hero with search field, advanced-search link and layer chips | Done | |
| Search examples under the hero field by scope: national laws for Nationell, county regulation words for Region, municipal regulation words for Kommun | Done | #130 |
| Key laws: Regeringsformen card, plus accordions for acts and ordinances | Done | |
| Key-law groups ordered by the main focus: hierarchy order for Medborgare and Student, acts and ordinances first for Jurist | Done | #29 |
| Explore feed with Recent and Favourites tabs, bookmark toggle and "Show more" | Done | |
| Loads only the first listing page of each level it shows, not the whole catalog; search loads the catalog on its first query | Done | |
| Feed card shows the in-force date and "Ändrad senast genom SFS …" | Done; each line is hidden while its field is `null` (the collector does not fill `in_force` yet). Saved items in the Favourites tab carry neither field | |
| Case-law items in the feed | Blocked: no case-law data | #38 |
| Popular tab | Blocked: the app is anonymous and collects no usage data | |
| Region and Kommun homes: the chosen län's or kommun's documents from the per-locality listings (`<layer>/by-code/`), with "Regulations in force" (newest five in force, document count), the Recent and Favourites feed and "Show more" to the locality's list; "no regulations collected yet for <locality>" when it has none, and a prompt to choose one when unset. The location card stays | Done | #99 |

### Wide layout

Code: `ui/home/WideHome.kt`, `HierarchySection.kt`, `RecentWithPreview.kt`. Reference: Stitch `lagar_multi_jurisdiction_design_system_portal` (desktop).

| Feature | Status | Issue |
| --- | --- | --- |
| Hero with document total, scope row with counts (Institutionellt disabled), location pill and data build date | Done | #79 |
| Wide search bar, advanced-search button and quick picks (Grundlagar, Brottsbalken, Miljöbalken, Rättegångsbalken) | Done | #79 |
| Norm hierarchy: total, distribution bar, 3-column grid of the nine layers with counts or "coming soon"; SFS other statutes counted under SFS acts | Done | #79, #125 |
| Recent and Favourites list next to a live preview of the selected document (header, opening sections, bookmark, open full text) | Done | #79 |
| Region and Kommun: "Regulations in force" for the chosen län or kommun above the list, which shows that locality's documents ("Show more" opens its list); the choose-a-locality or "no regulations collected yet" state when there are none | Done | #99 |
| Footer with the independent-project disclaimer | Done | #79 |
| GPS location, inline advanced-search panel, case-law / most-read / real-time tabs, version history, notes and linked precedents in the preview | Left out: no data, or owner decision | |

## Search

### Search results

Route: `Search(text, types, from, to, mode, status, inForceFrom, inForceTo, vacatioLegis, sort)`. Code: `ui/search/SearchScreen.kt`, `data/SearchService.kt`, `data/FullTextIndex.kt`. Reference: architecture §4 flow 4.

| Feature | Status | Issue |
| --- | --- | --- |
| Live search over titles and numbers, accent-insensitive; result count; empty, prompt and error states | Done | |
| Query survives process death through the route arguments | Done | |
| Static search index (`search/`): loads the manifest, then for each layer group of the scope its `docs.json` and only the shards of the query terms, cached by `built_at`, and merges the groups' hits (search versions 1 and 2); every term must match, the word being typed matches as a prefix; falls back to the whole catalog when the API has no index | Done | #37, #105 |
| Ranking (title, then number, then body; more matched fields first), sorting by relevance, newest or number, and matched words highlighted in titles | Done | #32 |
| Documents the query names first: title (with or without its number) or number equal to the query, then titles starting with it; a definite query word also matches its base ("miljöbalken" finds and ranks Miljöbalk (1998:808) first) | Done | #127 |
| Full-text mode (body text) with a "Found in the text" note on body-only matches | Done | #37 |
| Snippets of the matching text | Not planned: needs each result's document (`docs/<id>.json`), too costly per result; the note above says where it matched | #37 |
| Region and Kommun scopes: only the chosen län's or kommun's documents, by the `region_code` and `municipality_code` columns of `docs.json` (or listing items on the catalog path); a prompt to choose a locality when it is unset | Done | #99 |
| Searched scope as a chip beside the result count ("Region: Skåne län", ellipsized; opens the scope sheet); a Region or Kommun search without results says it covered only the län or kommun and offers "Sök i Nationell" | Done | #126 |
| Desktop: results in two equal-height columns within the 1280dp content width; the list stays full width so the whole window scrolls | Done | #35 |

### Advanced search

Route: `AdvancedSearch`. Code: `ui/search/AdvancedSearchScreen.kt`, `DateField.kt`. Reference: Stitch `busca_avan_ada_leis_municipais`.

| Feature | Status | Issue |
| --- | --- | --- |
| Text field, issue-date range, mode (all, title, number, full text), status (all, in force, repealed) | Done | #37 |
| Document types from the index `series` of the scope, so new vocabulary types appear once they have data | Done | #32 |
| Calendar date picker (M3, tier 3 glass) with dates shown in the app language, collapsible filter sections with an "Active" badge, scope change from the form and the header chip | Done | #32 |
| Header scope chip moves under the title when both do not fit (phones with a long locality), ellipsized when too long for its line | Done | #131 |
| Vacatio legis filter and in-force date range; documents without `in_force` (most SFS today) never match them. `docs.json` has no `in_force` yet, so these filters read the catalog | Done | #32 |
| Glass footer bar | Done | #23 |
| Desktop: text, scope, mode and types beside the date, in-force and status filters, capped at 1040dp, search button under the right column | Done | #35 |

## Hierarki

Route: `Hierarki`. Code: `ui/hierarki/`. References: Stitch `lagar_normhierarki_f_rgsystem` (Swedish) and architecture §4 flow 3.

| Feature | Status | Issue |
| --- | --- | --- |
| Toggle between layers and pyramid views | Done | |
| Distribution bar and legend; total, bar and legend count the SFS other statutes under SFS acts | Done | #125 |
| Nine layer rows with counts (Region and Kommun count every collected län and kommun; SFS acts include the other statutes, noted on their row); empty layers open a "coming soon" sheet | Done | #99, #125 |
| Authority badge (Överordnad, Riksdag, Regering, Verk, Prejudikat, Unionsakt, Regional, Kommunal, Service) and real examples on each layer row | Done | #34 |
| Browse SFS acts and ordinances by ministry: "By ministry" pill on their rows, from the API's per-ministry index | Done | #34 |
| Browse agency, case law and other layers by issuer or court | Blocked: no data in those layers, and no per-issuer index yet | #38 |

### By ministry

Route: `Ministries(layer, type)`. Code: `ui/hierarki/MinistriesScreen.kt`. Reference: architecture §4 flow 3.

| Feature | Status | Issue |
| --- | --- | --- |
| Ministries of one SFS series with document counts (glass tier 1 cards), unassigned count, empty and error states | Done | #34 |
| Opens the layer list filtered to the ministry (`LayerList(layer, type, ministry, ministryName)`) | Done | #34 |

## Layer list

Route: `LayerList(layer, type?, ministry?, ministryName?, code?, codeName?)`. Code: `ui/list/`.

| Feature | Status | Issue |
| --- | --- | --- |
| Paged list with prefetch, loading and error rows, layer badge and total | Done | |
| Repealed rows struck through, with the history badge | Done | |
| Empty state for a layer or series with no documents | Done | #33 |
| Series switch (all, acts, ordinances, other statutes) inside the list, from the layer's `series` in `index.json` | Done | #33 |
| Header (badge, count, series switch) padded clear of the back top bar's edges | Done | #129 |
| Names, levels and colours for the case law, EU, agency, county and municipal types, ready for when those layers have data | Done | #77 |
| One län's or kommun's documents (`code`, from the per-locality listings), opened from "Show more" on the Region and Kommun homes | Done | #99 |
| Desktop: two equal-height columns within the 1280dp content width, prefetch counted in rows | Done | #35 |

## Reader

Route: `Reader(id, anchor)`; `anchor` is an outline anchor (`k3p1` is 3 kap. 1 §) scrolled to once the text loads. Web links: `?doc=<id>&p=<anchor>`. Code: `ui/reader/`. References: DESIGN.md (Legal Text Cards, Typography) and architecture §4 flow 5.

| Feature | Status | Issue |
| --- | --- | --- |
| Metadata header: layer badge, citation, title, issue date, ministry, status, amended through, source link | Done | |
| Source Serif 4 legal text, bold Inter § numbers, reading column width | Done | |
| § cards with the layer indicator, bookmark toggle, text selection | Done | |
| Riksdagen's "Upphör att gälla U:…" and "Träder i kraft I:…" markers on a § shown as a label above its text ("Upphör att gälla …", "Träder i kraft …" with the date or condition as published) | Done | #124 |
| Save a single § or chapter: one 48dp actions button per § card and chapter heading opens a menu (save or remove, add or edit note, share link); a saved section shows the filled bookmark in the layer colour | Done | #28 |
| Repealed banner and strikethrough | Missing | #21 |
| Table of contents sheet: chapters and § chips, jump to a chapter or §; opens half-expanded over the dimmed reader on phones | Done | #26, #123 |
| Amendment list under the header (register list, else `amended_by`; reprints), numbers link to documents the API has | Done | #26 |
| Share links to the document and to each § (platform share sheet; Web Share API or clipboard on the web); `?doc=&p=` links open the reader at that § | Done | #26 |
| Cross-reference links: SFS citations (`lagen (1962:700)`, `(SFS 1998:808)`, `Lag (1994:458).`) and case-law references (`NJA 2026:38`, `HFD 2026 ref. 43`) open the cited document when the API has it | Done | #27 |
| Private notes on the document (under the header) and on each § or chapter (under its text), edited in a sheet, stored on the device only | Done | #28 |
| Desktop (≥ 1024dp): table of contents as a 300dp pane left of the text instead of a sheet | Done | #35 |
| Desktop (≥ 1280dp, `ShellDimens.ReaderInspectorBreakpoint`): facts, source link and amendments in an inspector pane right of the text; the text keeps the badge, number and title | Done | #35 |
| Tablet: frosted bottom sheet for the normative tree, sliding metadata drawer | Missing | #35 |
| Reading the text as of a past date, version comparator | Blocked: the API has no historical text; owner decision pending | #7 |

## Sparade

Route: `Sparade`. Code: `ui/sparade/SparadeScreen.kt`. Reference: architecture §4 (saved articles and notes).

| Feature | Status | Issue |
| --- | --- | --- |
| Bookmarked documents stored on the device, remove action, empty state | Done | |
| Repealed state kept on bookmarks | Missing | #21 |
| Saved single provisions (label, document, excerpt) that open the reader at their §, and notes on documents and provisions | Done | #28 |
| Grouping by level in hierarchy order, filter (all, documents, provisions, notes), search within saved items, undo snackbar after removing | Done | #28 |

## Tjänster

Route: `Tjanster`. Code: `ui/tjanster/TjansterScreen.kt`. Reference: architecture §4 (notices and gazettes), layer 9.

| Feature | Status | Issue |
| --- | --- | --- |
| "Coming soon" empty state | Done | |
| Public services and official notices | Blocked: no source or collector yet | #38 |

## Settings

Route: `Settings`, opened from the drawer. Code: `ui/settings/SettingsScreen.kt`. Reference: architecture §3 (global context).

| Feature | Status | Issue |
| --- | --- | --- |
| Language (system, Svenska, English), theme (system, light, dark), About with credits, licence and data build date | Done | |
| Reduce transparency (system, on, off); System follows iOS Reduce Transparency and the web `prefers-reduced-transparency` query, Android has no such setting | Done | #23 |
| Main focus (Medborgare, Student, Jurist), as chosen in onboarding | Done | #29 |

## Data and release

| Topic | Status | Issue |
| --- | --- | --- |
| Release builds and the web app read the published API | Done | #10 |
| Scheduled sync of new and amended statutes | Missing | #20 |
