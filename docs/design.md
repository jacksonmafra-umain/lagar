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
