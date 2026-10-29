# App screens and features

Inventory of every screen in the Compose Multiplatform app (`app/`). For each one it gives the route, the design references and the features, with their status. Code paths are relative to `app/shared/src/commonMain/kotlin/app/lagar/`.

**Design references.** [`DESIGN.md`](../DESIGN.md) is the canonical design system: tokens, glass tiers, typography and components. [`docs/architecture.md`](architecture.md) defines the screens and flows. The Stitch exports in `design/stitch/` are layout references only; most of them come from the Brazilian project, so their concepts are mapped to the Swedish Nationell / Region / Kommun model. There is no sign-in, so BankID and profile elements are not built.

**Status values:**
- **Done:** built and matching the reference.
- **Partial:** built, but incomplete or off-spec.
- **Missing:** not built.
- **Blocked:** needs data or an API endpoint that does not exist yet.

The number after each gap is its GitHub issue.

## Cross-cutting design work

| Topic | Status | Issue |
| --- | --- | --- |
| Glass tier 1 on article cards and input frames, tier 2 on sticky bars, tier 3 on the drawer and sheets, reduce-transparency support | Done | #23 |
| Input, button and checkbox shapes, search focus glow, web `⌘K` hint | Done | #24 |
| Repealed treatment (grey, strikethrough, history icon) everywhere | Partial: only the layer list is correct | #21 |
| Bookmark icon in the document's layer colour | Missing | #22 |
| Tablet two-pane and desktop tri-pane layouts | Missing | #35 |
| `docs/design.md` component inventory up to date | Done | #25 |
| Swedish and English strings, no hardcoded UI text | Done | |

## Shell

The app shell has four tabs (Utforska, Hierarki, Sparade, Tjänster) in a glass bottom bar. The glass top bar holds the title, a scope chip, search and the drawer button. Pushed screens use a back top bar. Code: `ui/shell/`.

### Drawer

Code: `ui/shell/Drawer.kt`. Reference: Stitch `menu_lateral_drawer_perfil_e_navega_o`, without the profile and sign-out.

| Feature | Status | Issue |
| --- | --- | --- |
| Header, six entries, About block with data build date | Done | |
| Each scope as a direct switch (Region / Kommun without a stored locality, and the active scope, open the scope sheet), Saved count badge, "Switch scope" / "Navigate" / "About" section headings | Done | #31 |
| "Most popular" and "Official gazettes" entries | Blocked: no usage data, no gazette source | #38 |

### Scope sheet

A modal sheet opened from the scope chip, the drawer or the location card. Code: `ui/home/ScopeSheet.kt`. References: Stitch `home_troca_de_mbito_e_localidade` and `modal_troca_de_localiza_o_estado_e_munic_pio`.

| Feature | Status | Issue |
| --- | --- | --- |
| Scope cards with Active and count badges, region and kommun pickers, changes applied on Done | Done | |
| Glass overlay (tier 3; opaque fallback, since a modal sheet's window has no backdrop to blur) | Done | #23 |
| Use my location | Missing | #30 |
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

### Locality (step 3)

Route: `OnboardingLocality`. Code: `ui/onboarding/LocalityStepScreen.kt`, `LocalityPickers.kt`. Reference: Stitch `onboarding_localiza_o_e_munic_pio`.

| Feature | Status | Issue |
| --- | --- | --- |
| Searchable region and kommun pickers for all 21 regions and 290 kommuner, both optional | Done | |
| Skip at the top right | Done | #29 |
| Kommun suggested from the device location | Missing | #30 |
| Linked kommun summary (council, document count) | Blocked: no municipal data | #38 |

## Utforska (home)

Route: `Utforska`. Code: `ui/home/`. References: Stitch `home_legislativa_leis_federais_brasil` (Nationell) and `home_legislativa_leis_estaduais_rs` (Region), the feed card on `lagar_normhierarki_f_rgsystem`, and architecture §4 flow 2.

| Feature | Status | Issue |
| --- | --- | --- |
| Hero with search field, advanced-search link and layer chips | Done | |
| Key laws: Regeringsformen card, plus accordions for acts and ordinances | Done | |
| Key-law groups ordered by the main focus: hierarchy order for Medborgare and Student, acts and ordinances first for Jurist | Done | #29 |
| Explore feed with Recent and Favourites tabs, bookmark toggle and "Show more" | Done | |
| Loads only the first listing page of each level it shows, not the whole catalog; search loads the catalog on its first query | Done | |
| Feed card shows the in-force date and "Ändrad senast genom SFS …" | Done; each line is hidden while its field is `null` (the collector does not fill `in_force` yet). Saved items in the Favourites tab carry neither field | |
| Case-law items in the feed | Blocked: no case-law data | #38 |
| Popular tab | Blocked: the app is anonymous and collects no usage data | |
| Region and Kommun homes (constitution, key rules, feed) | Blocked: empty layers; shows "coming soon" | #38 |

## Search

### Search results

Route: `Search(text, types, from, to, mode, status)`. Code: `ui/search/SearchScreen.kt`. Reference: architecture §4 flow 4.

| Feature | Status | Issue |
| --- | --- | --- |
| Live on-device search over titles and numbers, accent-insensitive; result count; empty, prompt and error states | Done | |
| Query survives process death through the route arguments | Done | |
| Sorting and highlighted matches | Missing | #32 |
| Full-text search with snippets | Blocked: no search index in the API | #37 |
| Region and Kommun scopes | Blocked: no data | #38 |

### Advanced search

Route: `AdvancedSearch`. Code: `ui/search/AdvancedSearchScreen.kt`, `DateField.kt`. Reference: Stitch `busca_avan_ada_leis_municipais`.

| Feature | Status | Issue |
| --- | --- | --- |
| Text field, issue-date range, document types, mode (all, title, number), status (all, in force, repealed) | Done | |
| Calendar date picker, collapsible filter sections, scope change from the form | Missing | #32 |
| Vacatio legis filter and in-force date range | Missing; `in_force` is now in listing items (still `null` until the collector fills it) | #32 |
| Glass footer bar | Done | #23 |

## Hierarki

Route: `Hierarki`. Code: `ui/hierarki/`. References: Stitch `lagar_normhierarki_f_rgsystem` (Swedish) and architecture §4 flow 3.

| Feature | Status | Issue |
| --- | --- | --- |
| Toggle between layers and pyramid views | Done | |
| Distribution bar and legend | Done | |
| Nine layer rows with counts; empty layers open a "coming soon" sheet | Done | |
| Authority badge and real examples on each layer row | Missing | #34 |
| Browse by issuing body (ministry, agency) | Missing; `ministry` is now in listing items | #34 |

## Layer list

Route: `LayerList(layer, type?)`. Code: `ui/list/`.

| Feature | Status | Issue |
| --- | --- | --- |
| Paged list with prefetch, loading and error rows, layer badge and total | Done | |
| Repealed rows struck through, with the history badge | Done | |
| Empty state for a layer or series with no documents | Done | #33 |
| Series switch (all, acts, ordinances, other statutes) inside the list, from the layer's `series` in `index.json` | Done | #33 |
| Names, levels and colours for the case law, EU, agency, county and municipal types, ready for when those layers have data | Done | #77 |

## Reader

Route: `Reader(id, anchor)`; `anchor` is an outline anchor (`k3p1` is 3 kap. 1 §) scrolled to once the text loads. Web links: `?doc=<id>&p=<anchor>`. Code: `ui/reader/`. References: DESIGN.md (Legal Text Cards, Typography) and architecture §4 flow 5.

| Feature | Status | Issue |
| --- | --- | --- |
| Metadata header: layer badge, citation, title, issue date, ministry, status, amended through, source link | Done | |
| Source Serif 4 legal text, bold Inter § numbers, reading column width | Done | |
| § cards with the layer indicator, bookmark toggle, text selection | Done | |
| Repealed banner and strikethrough | Missing | #21 |
| Table of contents sheet: chapters and § chips, jump to a chapter or § | Done | #26 |
| Amendment list under the header (register list, else `amended_by`; reprints), numbers link to documents the API has | Done | #26 |
| Share links to the document and to each § (platform share sheet; Web Share API or clipboard on the web); `?doc=&p=` links open the reader at that § | Done | #26 |
| Cross-reference links between statutes | Missing | #27 |
| Inline notes | Missing | #28 |
| Table of contents pane and metadata inspector on wide screens | Missing | #35 |
| Reading the text as of a past date, version comparator | Blocked: the API has no historical text; owner decision pending | #7 |

## Sparade

Route: `Sparade`. Code: `ui/sparade/SparadeScreen.kt`. Reference: architecture §4 (saved articles and notes).

| Feature | Status | Issue |
| --- | --- | --- |
| Bookmarked documents stored on the device, remove action, empty state | Done | |
| Repealed state kept on bookmarks | Missing | #21 |
| Saved single provisions, notes, grouping by layer, undo after remove | Missing | #28 |

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
