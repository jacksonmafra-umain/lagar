# Design system inventory

The implemented system is "Nordic Juridisk Klarhet", defined in the root `DESIGN.md`. Values are never
copied by hand: the Gradle plugin in `app/build-logic` (`app.lagar.design-tokens`) reads the YAML
frontmatter of `DESIGN.md` and generates `app.lagar.designsystem.generated.Tokens.kt` (task
`:shared:generateDesignTokens`, output under `app/shared/build/generated/designTokens`). Changing a value
in `DESIGN.md` is all it takes; `./gradlew -p build-logic test` covers the generator.

## Generated tokens (`app.lagar.designsystem.generated`)

| Symbol | Content |
| --- | --- |
| `LightTokens`, `DarkTokens` | One `Color` per M3 role (`colors`, `colors-dark`), camelCase of the key |
| `LayerKey` | `Fundamental, FundamentalAccent, SfsAct, SfsOrdinance, Agency, CaseLaw, Eu, Region, Municipality, Service, Repealed` |
| `LayerTokens` | `base(k)`, `text(k)`, `dark(k)` |
| `TypeTokens` | One `TextStyleSpec(sizeSp, lineHeightSp, weight, letterSpacingEm, family: FontKey)` per typography key |
| `SpacingTokens`, `RadiusTokens` | `Dp` values (1rem = 16dp; `rounded.DEFAULT` is `default`) |

## Handwritten theme (`app.lagar.designsystem`)

All paths below are relative to `app/shared/src/commonMain/kotlin/app/lagar/`.

| File | Content |
| --- | --- |
| `designsystem/LagarTheme.kt` | `LagarTheme(darkTheme, reduceTransparency) { }` wraps `MaterialTheme`; the `LagarTheme` object exposes `.colors` (M3 `ColorScheme`), `.layers` (`LayerColors`), `.status` (`StatusColors`), `.type` (`LagarTypography`), `.spacing` (`LagarSpacing`), `.isDark` and `.reduceTransparency` |
| `designsystem/LagarColors.kt` | `lagarLightColorScheme()`, `lagarDarkColorScheme()` from `LightTokens` / `DarkTokens` |
| `designsystem/LayerPalette.kt` | `LayerColors`: `accent`, `onTint`, `tint`, `border` (see the rules below) |
| `designsystem/StatusColors.kt` | `StatusColors.inForce` (status dot, the Region accent) and `onInForce` (its label, the Region `onTint`) |
| `designsystem/LagarTypography.kt` | `LagarTypography` (one `TextStyle` per type token), `rememberLagarTypography()`, `toMaterial()` |
| `designsystem/LagarShapes.kt` | M3 `Shapes`: `extraSmall` = `RadiusTokens.sm` (4dp), `small` = `default` (8dp), `medium` = `md` (12dp), `large` = `lg` (16dp), `extraLarge` = `xl` (24dp) |
| `designsystem/LagarSpacing.kt` | `LagarSpacing`: `gutter`, `gutterMobile`, `margin`, `marginMobile`, `xs`, `sm`, `md`, `lg`, `xl` |
| `designsystem/Glass.kt` | `GlassTier`, `Modifier.glass(...)`, `glassFill(...)` (see Glass below) |
| `designsystem/SystemReduceTransparency.kt` | `systemReduceTransparency()`, expect/actual for the platform setting |
| `ui/shell/ShellDimens.kt` | Component sizes: 48dp `TouchTarget`, 56dp `TabMinHeight`, 64dp `TopBarMinHeight`, 320dp `DrawerWidth`, 24dp `IconSize`, 20dp `SmallIconSize`, 32dp `AvatarSize`, 40dp `DrawerLogoSize`, 1dp `Hairline`, 2dp `TextGap`, 6dp `PillPaddingVertical` |
| `ui/common/IconColor.kt` | `Color.iconColor()`: white or near-black, whichever reads better on a layer fill |

- Fonts: Inter (400/500/600/700) and Source Serif 4 (400/700) in `composeResources/font/`; the SIL OFL
  licences are in `composeResources/files/licenses/` (non-font files do not belong in `font/`).
  Inter is UI chrome, Source Serif 4 is legal text (`bodyLegal*`); `statuteNum` is bold Inter.
- Type sizes are `sp`, so they follow the system font scale.

## Layer color rules

- `LayerColors.accent(k)`: icons, borders, indicator lines, chart series, solid fills (`base` in light, `dark` in dark).
- `LayerColors.onTint(k)`: text and badge labels (`text` in light, `dark` in dark).
- `LayerColors.tint(k)`: badge and panel background, accent at 12% (light) / 16% (dark) alpha.
- `LayerColors.border(k)`: accent at 20% alpha.
- Never put text in a `base` color: six bases fail contrast on their own tint. Always use `onTint`.
- Text and icons on a solid `accent` fill use `accent.iconColor()`, never a fixed white.
- Pick the color from the item `type`, not the spec `layer` field (acts and ordinances differ):
  `DisplayLayer.fromRoute(layer, type)` in `domain/DisplayLayer.kt` maps an API layer and type to a display level.
- Type names come from `typeNameRes(type)` in `ui/common/LayerLabels.kt`: fundamental law, act, ordinance,
  agency regulation, case report, case notice, EU regulation, EU directive, EU decision, county regulation,
  municipal regulation, and "other statute" for any type without its own name. Level names, descriptions and
  icons come from `nameRes()`, `descriptionRes()` and `iconRes()` in the same file.
- Layer color is never the only signal: badges carry the name or citation; repealed also gets a
  strikethrough and an icon.

## Glass (`Modifier.glass(tier, hazeState = null, shape = null, border = null)`)

| Tier | Use | Fill (light / dark) | Blur | Shadow | Opaque fallback |
| --- | --- | --- | --- | --- | --- |
| `Card` (1) | Article cards, § containers, input frames | white 0.85 / surface 0.85 | none | none | `surfaceContainerLowest` (dark `surfaceContainerLow`) |
| `Bar` (2) | Top bars, bottom bar, sticky footers | 0.72 | 20dp, saturate 180% | 8dp ambient aura | `surfaceContainer` |
| `Overlay` (3) | Drawer, modal sheets | 0.88 | 28dp, saturate 180% | 16dp diffuse | `surfaceContainerHigh` |

All tiers get the frosted border (top `rgba(255,255,255,0.65)`, dark `0.12`, fading to the outer stroke
`rgba(0,0,0,0.06)`, dark `0.4`) and the specular top highlight. A non-null `border` replaces the frosted
border, for cards with a layer edge (location card, drawer scope card, an open accordion) and for the input
frame's idle, focus and error edges. The default shapes are `RadiusTokens.lg` for `Card`, none for `Bar` and
`RadiusTokens.xl` for `Overlay`; callers pass the shape they need.

Blur is done by Haze (`haze-blur`): mark the content behind with `Modifier.hazeSource(state)` and pass the same
`HazeState`. `Card` never blurs and ignores `hazeState`, so long lists of cards stay cheap.

`glassFill(tier, hasBlurSource, reduceTransparency)` picks the fill (`GlassFill.Blurred`, `Translucent` or `Opaque`):

- reduce transparency on: `Opaque` for every tier;
- `Card`: `Translucent`;
- `Bar` and `Overlay`: `Blurred` with a `HazeState`, `Opaque` without one. Where Haze cannot blur on a target,
  it draws the same opaque fallback.

Modal sheets use `Modifier.sheetGlass()` (`ui/common/SheetGlass.kt`), the `Overlay` tier on the whole sheet with
the top-rounded `SheetShape` (`RadiusTokens.xl`). A modal sheet is drawn in its own window, where Haze has no
backdrop to sample, so sheets always use the opaque fallback with the border, highlight and shadow.

### Reduce transparency

`ReduceTransparency` (`settings/ReduceTransparency.kt`) is `System`, `On` or `Off`, stored in `UserPreferences`
and chosen in Settings. `System` follows `systemReduceTransparency()`: iOS reads
`UIAccessibilityIsReduceTransparencyEnabled` and its change notification, the web follows the
`prefers-reduced-transparency` media query (browsers without it keep the glass), and Android, which has no such
setting, reports false. `App.kt` passes the resolved value to `LagarTheme`, and every glass tier and the glass
secondary button then draw opaque.

### Where each tier is used

| Tier | Surfaces |
| --- | --- |
| `Card` | `FeedCard`, `StatuteRow`, `StatuteContainer`, the Sparade provision and note cards, the advanced search `FilterCard`s, `LayerDistributionChart`, the home `LocationCard`, the important-laws `AccordionHeader`, the drawer scope card, the splash logo card, `InputFrame` (text fields and search command bars), the Hierarki `MinistryRow` |
| `Bar` | `LagarTopBar`, `LagarBottomBar`, `BackTopBar`, the advanced search footer |
| `Overlay` | `LagarDrawerContent`; `ScopeSheet`, `ComingSoonSheet`, `TableOfContentsSheet`, `NoteEditorSheet` and the locality `OptionSheet` through `sheetGlass()` |

Layer-tinted panels (`LayerRow`, `NormPyramid` bands, onboarding `ScopeCard`, the constitution `FlagshipCard`,
the repealed banner) keep their layer `tint` fill instead of glass: the tint carries the layer.

## Component inventory

As built. Every component uses only tokens from the sections above. Components marked **deferred** are
defined in `DESIGN.md` but have no screen that needs them yet. Paths are relative to `ui/`. Screen status
lives in [`docs/screens.md`](screens.md).

| Component | Implementation | Tokens used |
| --- | --- | --- |
| Normative badge / chip | `LayerBadge` in `common/LayerBadge.kt` | `CircleShape`, layer `tint` fill, 1dp layer `border`, `labelSm` in `onTint` |
| Repealed badge | `RepealedBadge` in `common/RepealedBadge.kt` | `Repealed` layer `tint` / `border` / `onTint`, `CircleShape`, 14dp `ic_history` icon, `labelSm` |
| Validity label (reader § card) | `ValidityLabel` in `reader/ValidityMarkers.kt` | Chip above the § text, `shapes.small` (8dp, wraps long conditions), 1dp `border`, `labelSm` in `onTint`: "Upphör att gälla …" in the `Repealed` layer colours with a 14dp `ic_history` icon, "Träder i kraft …" in the document's layer `tint` / `border` / `onTint` |
| Pill tab | `PillTab` in `common/PillTab.kt`; Hierarki "Lager / Pyramid" switch, Explore feed tabs, layer list series switch | 32dp `CircleShape` pill in a 48dp target, `Role.Tab`; selected: layer `accent` fill and border, `labelSm` bold upper case in `iconColor()`; unselected: `surfaceContainerLowest`, 1dp `outlineVariant`, `onSurface` |
| Series switch (layer list) | `SeriesSwitch` in `list/LayerListScreen.kt` | Horizontally scrolling row of `PillTab`s: "All" in the level colour, then one per series (`typeNameRes`), each in its own level's colour from `DisplayLayer.fromRoute` |
| Layer row (Hierarki) | `LayerRow` in `hierarki/LayerRow.kt` | `shapes.large`, layer `tint` fill and 1dp `border`, 40dp `accent` icon square (`shapes.medium`) with `iconColor()` icon, "N. Name" in bold `bodyUi` `onTint` followed by a `LayerBadge` with the authority (Riksdag, Regering, ...), `labelSm` examples in `onSurfaceVariant`, `labelSm` count or "coming soon" in `onTint`, `onTint` chevron; SFS rows add a "By ministry" pill (`surface` at 60%, 1dp layer `border`, `labelSm` `onTint`, 48dp target) |
| Ministry row (Hierarki) | `MinistryRow` in `hierarki/MinistriesScreen.kt` | `GlassTier.Card` (`shapes.medium`) with a 1dp layer `border`, bold `bodyUi` name in `onSurface`, `labelSm` count in `onTint`, `onTint` chevron, 56dp minimum height |
| Layer distribution chart | `LayerDistributionChart` in `hierarki/LayerDistributionChart.kt` | `GlassTier.Card` (`shapes.large`), 12dp `surfaceContainer` track, layer `accent` segments, legend chips in `surfaceContainerLow` (`shapes.medium`) with a 10dp `accent` dot and `labelSm` |
| Hierarki pyramid | `NormPyramid` in `hierarki/NormPyramid.kt` | layer `tint` bands with 1dp `border` (`shapes.medium`), `labelMd` / `labelSm` in `onTint`, "coming soon" in `onSurfaceVariant` |
| Bottom navigation bar | `LagarBottomBar` in `shell/BottomBar.kt` | `GlassTier.Bar`, `labelSm`, `RadiusTokens.lg` selected pill (`primaryFixed` with `onPrimaryFixedVariant` light, `primaryContainer` with `onPrimaryContainer` dark) |
| Top bar (tab screens) | `LagarTopBar` in `shell/TopBar.kt` | `GlassTier.Bar`, `headlineSm` "Lagar" in `primary`, scope chip, search, theme and menu (`ic_menu`, opens the drawer) icon buttons in `onSurfaceVariant`; the wide top bar uses the same menu button |
| Scope chip (top bar) | `ScopeChip` in `shell/TopBar.kt` | layer `tint` pill, `labelMd` bold in `onTint`, expand icon; opens the scope sheet |
| Back top bar (pushed screens) | `BackTopBar` in `common/BackTopBar.kt`; layer list, reader, search, advanced search, settings | `GlassTier.Bar`, 64dp minimum height, `sm` vertical padding so a multi-line title stays clear of the edges, 48dp back target, `onSurfaceVariant` icon, title slot |
| Side drawer | `LagarDrawerContent` in `shell/Drawer.kt` | `GlassTier.Overlay` (`RadiusTokens.xl`); header with 40dp `primary` crown circle, `headlineMd` "Lagar" in `primary` and `labelSm` tagline; bold `labelSm` upper-case section headings in `onSurfaceVariant` (heading semantics); one scope row per scope in a radio group (`GlassTier.Card`, `shapes.large`, 1dp layer `border`, 2dp `accent` when active; 40dp layer `tint` icon square with `accent` icon, bold `bodyUi` name, `LayerBadge` "Active" or document count, `labelSm` locality or hint); six entries (Explore, Hierarchy, Saved, Services, Advanced search, Settings) in 48dp rows with a `RadiusTokens.lg` selected pill (`primaryFixed` light, `primaryContainer` dark), Saved with a bold `labelSm` count pill in the same colours (announced as a document count); `labelSm` About block with the data build date; scrolls at large font sizes |
| Scope sheet | `ScopeSheet` in `home/ScopeSheet.kt` | `sheetGlass()`, `headlineMd` / `headlineSm` titles, onboarding `ScopeCard`s with "Active" and count badges, `LocalityPickers`, `LagarButton` "Done" |
| Scope card (onboarding, scope sheet) | `ScopeCard` and `ScopeInfoCard` in `onboarding/ScopeCard.kt` | `shapes.large`, layer `tint` fill, 1dp layer `border` (2dp `accent` when selected), 44dp `accent` icon square (`shapes.medium`), `headlineSm` name in `onTint`, `bodyUi` description, `LayerBadge`s; 28dp check circle (`accent` when selected, `surfaceContainerHighest` otherwise) |
| Locality picker field | `PickerField` in `onboarding/LocalityPickers.kt` | `labelMd` label, `shapes.small`, `surfaceContainerLowest` (disabled `surfaceContainerLow`), 1dp `outlineVariant`, `bodyUi` value, `Role.DropdownList` |
| Use my location | `UseLocation` in `onboarding/LocalityPickers.kt` | full-width `LagarSecondaryButton` with `ic_my_location` and `labelMd` text; outcome row with `ic_info` (`primary` for a suggestion, `onSurfaceVariant` otherwise), `bodyUi` text, polite live region; `labelSm` privacy note in `onSurfaceVariant` |
| Locality option sheet | `OptionSheet` in `onboarding/LocalityPickers.kt` | `sheetGlass()`, `headlineSm` title, `LagarTextField` filter, `bodyUi` options (`primary` when selected) |
| Step header (onboarding) | `StepHeader` in `onboarding/StepHeader.kt` | `surfaceContainerHigh` pill with `labelMd`, three-segment bar in `primary` / `outlineVariant` ; on steps 2 and 3 led by a 48dp back target with `ic_arrow_back` in `onSurfaceVariant`, labelled "Back to the previous step" |
| Splash | `SplashScreen` in `onboarding/SplashScreen.kt` | 128dp `GlassTier.Card` (`RadiusTokens.xl`) holding a 96dp `primary` crown circle, `displayLgMobile` "Lagar" in `primary`, `bodyUi` tagline, `primary` progress bar on `surfaceContainerHigh` |
| Home hero | `HomeHero` in `home/HomeHero.kt` | Scope `tint` to transparent gradient, `headlineSm` title with the emphasis in `onTint`, `labelSm` subtitle; Region / Kommun: 44dp `accent` icon circle; advanced search link in bold `labelSm` `onTint` |
| Level quick links | `LayerChips` in `home/HomeHero.kt` | 30dp `CircleShape` pills in 48dp targets; first filled with `accent` and `iconColor()` text, the rest `surfaceContainerLowest` with layer `border` and `onTint` text; bold `labelSm` upper case |
| Location card (Region / Kommun home) | `LocationCard` in `home/HomeScreen.kt` | `GlassTier.Card` (`shapes.large`) with 1dp layer `border`, `labelSm` label in `onTint`, bold `bodyUi` name |
| Feed card | `FeedCard` in `home/FeedCard.kt` | `GlassTier.Card` (`shapes.large`); `LayerBadge` "Type number" (`typeNameRes`), in-force date pill (`CircleShape`, `surfaceContainer`, `labelSm` `onSurfaceVariant`), relative issue age (`labelSm`); `bodyUi` title (3 lines); "amended through" line in semibold `labelSm` `onTint`; `outlineVariant` divider; `InForce` status (8dp `status.inForce` dot, `labelMd` `onInForce`) or `RepealedBadge`; "read full text" in `labelMd` `onTint` with chevron; 48dp bookmark toggle (`onTint` when saved) |
| Explore feed | `ExploreFeed` in `home/ExploreFeed.kt` | `headlineSm` title, `PillTab`s for newest and saved, `FeedCard`s, `LagarSecondaryButton` "Show more" |
| Key laws | `ImportantLaws` in `home/ImportantLaws.kt` | 44dp Fundamental `tint` crown medallion; `FlagshipCard` (`shapes.large`, Fundamental `tint`, 1.5dp `accent` border, bold `bodyUi` in `onTint`); `AccordionHeader` (`GlassTier.Card`, `shapes.large`, 1dp layer `accent` border when open, bold `labelMd`) over `StatuteRow`s |
| Layer list row | `StatuteRow` in `list/StatuteRow.kt`; layer list, search results, key laws, Sparade | `GlassTier.Card` (`shapes.medium`), 3dp layer `accent` indicator, `codeCitation` number in `onTint`, `bodyUi` title (2 lines), `labelSm` year, `RepealedBadge` and strikethrough when repealed, `onSurfaceVariant` chevron |
| § container (legal text card) | `StatuteContainer` in `reader/LegalMarkdown.kt` | `GlassTier.Card` (`shapes.medium`), 3dp layer `accent` indicator, `bodyLegalMd` text, `readingColumn()` width (about 70 characters), 48dp actions button in the upper right (20dp `ic_more_vert` in `onSurfaceVariant`, or `ic_bookmark_filled` in layer `onTint` once saved, announced as "Saved") |
| Section actions menu (reader) | `SectionActions` in `reader/Notes.kt`; § cards and chapter headings | M3 `DropdownMenu` in `surfaceContainerHigh` (the `Overlay` opaque fallback), `shapes.medium`; 48dp items with a 20dp leading icon (`onSurfaceVariant`, the bookmark in layer `onTint` when saved) and `bodyUi` text in `onSurface` |
| Note chip | `NoteChip` and `DocumentNote` in `reader/Notes.kt`; under a § card's text, a chapter heading and the reader header | layer `tint` fill, 1dp layer `border`, `shapes.small`, 48dp minimum height, 20dp `ic_note` in `onTint` (labelled "Note"), `bodyUi` text in `onSurface` (four lines); without a document note, an "Add note" action in `labelMd` `onTint` |
| Note editor sheet | `NoteEditorSheet` in `reader/Notes.kt` | `sheetGlass()`, `headlineSm` title (heading), multi-line `LagarTextField` (four lines), `labelSm` on-device notice in `onSurfaceVariant`, `LagarSecondaryButton` "Delete note" in `error` and `LagarButton` "Save note" |
| Sparade list | `SparadeScreen` in `sparade/SparadeScreen.kt` | `LagarTextField` search with `ic_search`; `PillTab` filters in the SFS act colour; level headings (10dp layer `accent` dot, bold upper-case `labelSm` in `onSurfaceVariant`, heading semantics); documents as `StatuteRow` with a `labelSm` note line; provisions and notes as `StatuteRow`-shaped `GlassTier.Card`s (`codeCitation` label in `onTint`, `labelSm` document title, `bodyLegalMd` excerpt in three lines or `bodyUi` note text); 48dp remove buttons (filled bookmark in `onTint`, `ic_delete` in `onSurfaceVariant` for notes); M3 snackbar with "Undo" above the bottom bar |
| Table of contents sheet | `TableOfContentsSheet` in `reader/TableOfContentsSheet.kt` | `sheetGlass()`, `headlineMd` title, `headlineSm` chapter rows (48dp), § chips in layer `tint` / `border` with bold `labelMd` `onTint` text (`shapes.small`, 48dp targets) |
| Amendment list | `AmendmentsSection` in `reader/AmendmentsSection.kt` | 48dp toggle with `labelMd` count and expand icon; rows with `codeCitation` number (`onTint`, underlined when it links), `labelSm` entry into force and scope in `onSurfaceVariant`, `bodyUi` title |
| Legal text | `LegalMarkdown` in `reader/LegalMarkdown.kt` | `bodyLegalMd` (Source Serif 4) paragraphs and lists, `**N §**` in `statuteNum`, `headlineMd` / `headlineSm` headings |
| Metadata header | `MetadataHeader` in `reader/MetadataHeader.kt` | `LayerBadge`, `codeCitation` number in layer `onTint`, `headlineMd` title, `labelSm` / `bodyUi` facts, `outlineVariant` divider; repealed: `Repealed` badge and number, struck-through number and title (`onSurfaceVariant`), banner in `Repealed` `tint` / `border` (`shapes.medium`) with history icon and `bodyUi` text in `onTint` |
| Empty state ("coming soon") | `EmptyState` in `common/EmptyState.kt` (`StatusMessage`) | 64dp `surfaceContainerHigh` circle, `onSurfaceVariant` icon, `headlineSm` title, `bodyUi` text in `onSurfaceVariant` |
| Error state with retry | `ErrorState` in `common/ErrorState.kt` (`StatusMessage`) | as the empty state with an `error` icon tint and a `LagarButton` retry |
| "Coming soon" sheet | `ComingSoonSheet` in `common/ComingSoonSheet.kt` | `sheetGlass()` with an `EmptyState` |
| Primary button | `LagarButton` in `common/LagarButtons.kt`; onboarding steps, scope sheet "Done", retry, advanced search "Sök" | `primary` fill with `onPrimary` label, or a layer `accent` fill with `iconColor()` label; `shapes.small` (`RadiusTokens.default`); 1dp edge in the label colour at 16%; 48dp min height |
| Secondary button | `LagarSecondaryButton` in `common/LagarButtons.kt`; "Show more" on the home | `surfaceContainerLowest` at 0.6 alpha (opaque under reduce transparency, no blur), 1dp `outlineVariant` edge, `primary` (or layer `onTint`) label, `shapes.small`, 48dp min height |
| Input frame | `InputFrame` in `common/LagarTextField.kt` | `GlassTier.Card` fill, `shapes.small`, 1dp `outlineVariant` (or layer `accent`) border; focused: 1.5dp `primary` border and a 4dp `primary` 15% glow; error: 1.5dp `error` border; 48dp min height |
| Text field | `LagarTextField` in `common/LagarTextField.kt`; advanced search text, locality filter, Sparade search, note editor (multi-line) | `InputFrame`, `labelMd` label above, `bodyUi` text and placeholder (`onSurfaceVariant`), optional leading icon, `labelSm` `error` message below (polite live region) |
| Search command bar | `SearchField` in `home/HomeHero.kt`, `SearchInput` in `search/SearchScreen.kt` | `InputFrame` with the scope's layer `accent` idle border, `onTint` search icon and cursor, `ShortcutHint` on the web; the home bar ends in a 36dp layer `accent` submit button (`shapes.small`) in a 48dp target; the search screen's bar sits in the `BackTopBar`, which supplies the blur |
| Shortcut key cap | `ShortcutHint` in `common/LagarTextField.kt`, label from `searchShortcutHint()` (`common/SearchShortcut.kt`) | `labelSm` in `onSurfaceVariant`, 1dp `outlineVariant` border, `RadiusTokens.sm`; `⌘K` on Apple platforms, `Ctrl+K` elsewhere, web only |
| Checkbox | `LagarCheckbox` in `common/LagarCheckbox.kt`; advanced search type filters | 18dp square, `RadiusTokens.sm` (4dp); unchecked: 2dp `onSurfaceVariant` border; checked: layer `accent` (or `primary`) fill with `ic_check` in `iconColor()`; the row carries `Role.Checkbox` |
| Advanced search filter card | `FilterCard` in `search/AdvancedSearchScreen.kt` | `GlassTier.Card` (`shapes.large`); collapsible: 48dp header (bold `labelMd` title, heading semantics, expanded state announced), layer `tint` / `onTint` "Active" badge, `ic_expand_more` turning 180°; action pills (`Pill`: layer `tint` / `border` when filled, `surfaceContainerLowest` / `outlineVariant` otherwise); M3 `RadioButton` options |
| Date field and picker | `DateField`, `LagarDatePickerDialog` in `search/DateField.kt`; advanced search dates | `InputFrame` with `labelMd` label, `bodyUi` date in the app language ("15 Oct 2026", "15 okt. 2026"), `ic_expand_more` in layer `onTint`; M3 `DatePicker` in a `GlassTier.Overlay` dialog (`RadiusTokens.xl`), selected day and year in layer `accent` with `iconColor()`, today ring in `accent`, today and buttons in `onTint` |
| Search sort tabs and match highlight | `SortRow` in `search/SearchScreen.kt` (`PillTab`); `StatuteRow` `highlights` and `note` | `labelMd` "Sort by", `PillTab`s in the scope colour; matched words bold on the layer `tint`; `labelSm` "Found in the text" note in `onTint` |
| Advanced search footer | `AdvancedSearchScreen` in `search/AdvancedSearchScreen.kt` | `GlassTier.Bar` over the form, full-width layer `accent` `LagarButton` |
| Settings controls (radio) | `OptionGroup` in `settings/SettingsScreen.kt`; language, theme, reduce transparency | `labelMd` section title, optional `labelSm` description, M3 `RadioButton` with `primary` selected and `onSurfaceVariant` unselected, 48dp rows, `bodyUi` labels |
| Cross-reference | `LegalMarkdown` in `reader/LegalMarkdown.kt`, citations found by `reader/CrossReferences.kt`, underline drawn by `DottedUnderlinePainter` (`reader/DottedUnderline.kt`) | citation text (`lagen (1962:700)`, `Lag (1994:458)`, `NJA 2026:38`) in the target layer's `onTint` (layer from the target's `type`, SFS act when unknown) with a dotted underline (1.5dp round dots, 2dp gap, 2.5dp below the baseline); a link role that opens the target in the reader; only when the API publishes the target |

## Top bar label scaling

The top bar holds the title, scope chip and three icon buttons on one line, so `LagarTopBar` caps the
font scale of its own content at 1.3 (`MAX_BAR_FONT_SCALE`) and ellipsizes the title; the chip and the
buttons keep full accessible names.

## Bottom bar label scaling

The four equal-width tabs cannot hold a 200% label ("Hierarki", "Tjänster"), so `LagarBottomBar` caps
the font scale of its own content at 1.3 (`MAX_LABEL_FONT_SCALE`); the rest of the app keeps the full
system scale. The label is never truncated or hidden: each tab is a `selectable` with `Role.Tab` whose
merged semantics carry the full label text, so screen readers always get the complete name.

## Hierarki pyramid label scaling

The upper bands of `NormPyramid` are narrow (50% of the width at the top), so each band caps the font
scale of its own content at 1.3 (`MAX_FONT_SCALE`). Names are never truncated or hidden; the rest of the
screen follows the full system scale. Layer rows in Hierarki stay at full scale: past 1.3 they stop
truncating the title and description and wrap them instead.
