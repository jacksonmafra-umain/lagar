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

- `LagarTheme(darkTheme) { }` wraps `MaterialTheme` (colors, typography and shapes mapped from the tokens).
- `LagarTheme.colors` (M3 `ColorScheme`), `.layers` (`LayerColors`), `.type` (`LagarTypography`),
  `.spacing` (`LagarSpacing`), `.isDark`.
- Fonts: Inter (400/500/600/700) and Source Serif 4 (400/700) in `composeResources/font/`; the SIL OFL
  licences are in `composeResources/files/licenses/` (non-font files do not belong in `font/`).
  Inter is UI chrome, Source Serif 4 is legal text (`bodyLegal*`); `statuteNum` is bold Inter.
- Type sizes are `sp`, so they follow the system font scale.

## Layer color rules

- `LayerColors.accent(k)`: icons, borders, indicator lines, chart series (`base` in light, `dark` in dark).
- `LayerColors.onTint(k)`: text and badge labels (`text` in light, `dark` in dark).
- `LayerColors.tint(k)`: badge and panel background, accent at 12% (light) / 16% (dark) alpha.
- `LayerColors.border(k)`: accent at 20% alpha.
- Never put text in a `base` color: six bases fail contrast on their own tint. Always use `onTint`.
- Pick the color from the item `type`, not the spec `layer` field (acts and ordinances differ).
- Layer color is never the only signal: badges carry the name or citation; repealed also gets a
  strikethrough and an icon.

## Glass (`Modifier.glass(tier, hazeState, shape)`)

| Tier | Use | Fill (light / dark) | Blur | Shadow |
| --- | --- | --- | --- | --- |
| `Card` (1) | Article cards, document body | white 0.85 / surface 0.85 | none | none |
| `Bar` (2) | Sticky headers, norm bars | 0.72 | 20dp, saturate 180% | ambient aura |
| `Overlay` (3) | Floating overlays, drawers | 0.88 | 28dp, saturate 180% | diffuse |

All tiers get the frosted border (top/sides `rgba(255,255,255,0.65)`, dark `0.12`, fading to the
outer stroke `rgba(0,0,0,0.06)`, dark `0.4`) and the specular top highlight. Blur is done by Haze
(`haze-blur`): mark the content behind with `Modifier.hazeSource(state)` and pass the same `HazeState`.

Fallback: with `hazeState == null` (or where Haze cannot blur, which uses the same opaque tint) the
surface is an opaque `surfaceContainer*` role with the same border: Card `surfaceContainerLowest`
(dark `surfaceContainerLow`), Bar `surfaceContainer`, Overlay `surfaceContainerHigh`.

## Component inventory

As built. Every component uses only tokens from the sections above. Components marked **deferred** are
defined in `DESIGN.md` but have no screen that needs them yet.

| Component | Implementation | Tokens used |
| --- | --- | --- |
| Normative badge / chip | `ui/common/LayerBadge.kt` | `CircleShape`, `layers.tint` fill, `layers.onTint` text, `labelSm` |
| Repealed badge | `ui/common/RepealedBadge.kt` | `Repealed` layer `tint` / `onTint`, `CircleShape`, history icon, `labelSm` |
| Layer row (Utforska) | `ui/utforska/LayerRow.kt` | `shapes.large`, layer `tint` fill, 40dp `accent` icon square (`shapes.medium`), "N. Name" in `bodyUi` `onTint`, `labelSm` description in `onSurfaceVariant`, `LayerBadge` with count or "coming soon" |
| Layer list row (layer list) | `ui/list/StatuteRow.kt` | `shapes.medium`, `surfaceContainerLowest` fill, 1dp `outlineVariant` border, 3dp layer `accent` indicator, `codeCitation` number, `bodyUi` title, `labelSm` year, `RepealedBadge` when repealed |
| Layer distribution chart | `ui/utforska/LayerDistributionChart.kt` | `shapes.large`, `surfaceContainerLowest` card, `surfaceContainer` track, layer `accent` segments, `surfaceContainerLow` legend chips, `labelSm` |
| Hierarki pyramid | `ui/hierarki/NormPyramid.kt` | layer `tint` bands (`shapes.medium`), `labelMd` / `labelSm` in `onTint`, `onSurfaceVariant` counts |
| Bottom navigation bar | `ui/shell/BottomBar.kt` | `GlassTier.Bar`, `labelSm`, `RadiusTokens.lg` selected pill (`primaryFixed` light, `primaryContainer` dark) |
| Top bar (tab screens) | `ui/shell/TopBar.kt` | `GlassTier.Bar`, `headlineSm` in `primary`, icon buttons, 32dp `primary` avatar |
| Back top bar (pushed screens) | `ui/common/BackTopBar.kt`, used by layer list, reader and settings | `GlassTier.Bar`, 48dp back target, `onSurfaceVariant` icon, title slot (`headlineSm` or `codeCitation`) |
| Side drawer | `ui/shell/Drawer.kt` | `GlassTier.Overlay` (`RadiusTokens.xl`, `surfaceContainerHigh`); header with 40dp `primary` crown circle, `headlineMd` "Lagar" in `primary` and `labelSm` tagline; scope card (`shapes.large`, `surfaceContainerLowest`, 1dp layer `border`, `bodyUi` bold scope name, `labelSm` locality, layer `tint` "Change" pill with `onTint` text); six entries (Explore, Hierarchy, Saved, Services, Advanced search, Settings) in 48dp rows with `RadiusTokens.lg` selected pill (`primaryFixed` light, `primaryContainer` dark); `labelMd` / `labelSm` About block with data build date; scrolls at large font sizes |
| Scope sheet | `ui/home/ScopeSheet.kt` | M3 modal sheet, scope cards in layer `tint` / `border`, "Active" and "Coming soon" badges, region and kommun pickers, primary "Done" button |
| Scope chip (top bar) | `ui/shell/TopBar.kt` | layer `tint` fill, `labelMd` bold in `onTint`, expand icon; opens the scope sheet |
| Location card (Region / Kommun home) | `ui/home/HomeScreen.kt` | `shapes.large`, `surfaceContainerLowest`, 1dp layer `border`, `labelSm` label in `onTint`, `bodyUi` bold name |
| § container (legal text card) | `StatuteContainer` in `ui/reader/LegalMarkdown.kt` | `surfaceContainerLowest` fill, 1dp `outlineVariant` border, `shapes.medium`, 3dp layer `accent` indicator, `bodyLegalMd` text, reading column width |
| Empty state ("coming soon") | `ui/common/EmptyState.kt` (`StatusMessage`) | 64dp `surfaceContainerHigh` circle, `onSurfaceVariant` icon, `headlineSm` title, `bodyUi` text in `onSurfaceVariant` |
| Error state with retry | `ui/common/ErrorState.kt` (`StatusMessage`) | 64dp `surfaceContainerHigh` circle, `error` icon tint, `headlineSm` title, `bodyUi` text, M3 `Button` for retry |
| "Coming soon" sheet | `ui/common/ComingSoonSheet.kt` | M3 modal sheet, `surfaceContainerLowest` container |
| Metadata header | `ui/reader/MetadataHeader.kt` | `codeCitation` number in layer `onTint`, `headlineMd` title, `labelSm` / `bodyUi` facts, `outlineVariant` divider |
| Settings controls (radio) | `ui/settings/SettingsScreen.kt` | M3 `RadioButton` with `primary` selected and `onSurfaceVariant` unselected, 48dp rows, `bodyUi` labels |
| Glass secondary button | deferred | `DESIGN.md` glass fill is 0.6 alpha, not the `GlassTier.Card` 0.85; give it its own spec when built |
| Primary button | deferred (retry uses the M3 `Button` themed by `LagarTheme`) | layer `accent` (or `primary`) fill, `onPrimary` text, `RadiusTokens.default` |
| Cross-reference | deferred | dotted underline in target layer `onTint` |

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
screen follows the full system scale. Layer rows in Utforska stay at full scale: past 1.3 they stop
truncating the title and description and wrap them instead.
