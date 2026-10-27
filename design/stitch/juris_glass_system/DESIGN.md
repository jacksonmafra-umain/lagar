---
name: Juris Glass System
colors:
  surface: '#f7f9ff'
  surface-dim: '#d7dae1'
  surface-bright: '#f7f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f1f4fa'
  surface-container: '#ebeef5'
  surface-container-high: '#e5e8ef'
  surface-container-highest: '#e0e2e9'
  on-surface: '#181c21'
  on-surface-variant: '#454653'
  inverse-surface: '#2d3136'
  inverse-on-surface: '#eef1f8'
  outline: '#767685'
  outline-variant: '#c6c5d5'
  surface-tint: '#4951c3'
  primary: '#00004d'
  on-primary: '#ffffff'
  primary-container: '#00008c'
  on-primary-container: '#7981f6'
  inverse-primary: '#bfc2ff'
  secondary: '#835418'
  on-secondary: '#ffffff'
  secondary-container: '#ffc07a'
  on-secondary-container: '#794c10'
  tertiary: '#00140a'
  on-tertiary: '#ffffff'
  tertiary-container: '#002c1b'
  on-tertiary-container: '#459c73'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#e0e0ff'
  primary-fixed-dim: '#bfc2ff'
  on-primary-fixed: '#00006e'
  on-primary-fixed-variant: '#3037aa'
  secondary-fixed: '#ffddbb'
  secondary-fixed-dim: '#f9ba75'
  on-secondary-fixed: '#2b1700'
  on-secondary-fixed-variant: '#673d00'
  tertiary-fixed: '#9cf5c6'
  tertiary-fixed-dim: '#80d8ab'
  on-tertiary-fixed: '#002113'
  on-tertiary-fixed-variant: '#005235'
  background: '#f7f9ff'
  on-background: '#181c21'
  surface-variant: '#e0e2e9'
typography:
  headline-xl:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Inter
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.015em
  headline-lg:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-legal:
    fontFamily: Source Serif 4
    fontSize: 17px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: 0.01em
  body-legal-quote:
    fontFamily: Source Serif 4
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: 0.01em
  body-ui:
    fontFamily: Inter
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 22px
  label-lg:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-md:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-mono:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.04em
rounded:
  sm: 0.5rem
  DEFAULT: 1rem
  md: 1.5rem
  lg: 2rem
  xl: 3rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.75rem
  margin: 1.25rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style
The design system pairs the authoritative rigor of Brazilian jurisprudence with a tactile, fluid mobile interface. Designed for jurists, magistrates, legal scholars, and citizens parsing complex statutes on handheld viewports, it reconciles the systematic token architecture of Material You (M3) with the optical polish and luminous depth of Apple's Human Interface Guidelines (Liquid Glass).

The aesthetic voice is scholarly, contemporary, and exact:
- **Rigorous Clarity:** Legal prose demands maximum legibility; structural framing recedes to allow statutory texts absolute visual priority.
- **Translucent Materiality:** Modals, navigation bars, and search overlays employ tinted frosted glass (`backdrop-filter: blur(20px)`) to preserve spatial context while reading dense articles.
- **Chromatic Jurisdictions (*Âmbitos*):** Color is not ornamental; it serves as cognitive anchoring for municipal (*Carmim*), state (*Esmeralda*), federal (*Ocre Dourado*), and institutional (*Marinho*) legal spheres, dynamically recalibrating surface tints and active states.

## Colors
The palette organizes legal authority through four primary jurisdictional tiers, each mapped to high-contrast surface pairs exceeding WCAG 2.2 AA (and meeting AAA for body copy).

### Jurisdictional Spheres (*Âmbitos*)
- **Institucionais (Primary Default):** `#00008C` (Formal Deep Navy). Paired with `#FFFFFF` text (contrast 12.6:1) and subtle blue-tinted container surfaces (`rgba(0, 0, 140, 0.06)`).
- **Federais (Secondary):** `#8A5A1E` (Academic Warm Ochre). Used for national codes, constitutional articles, and federal decrees; button fill text is `#FFFFFF` (contrast 5.8:1); light badge accent `#F7EEDB` with foreground `#5C3A0D`.
- **Estaduais (Tertiary):** `#1B7A54` (Deep Emerald Green). For state constitutions and local decrees. On buttons, use `#FFFFFF` (contrast 5.2:1).
- **Municipais:** `#B71C1C` (Deep Carmim Crimson). Reserved for municipal organic laws, master plans, and city council acts. Always paired with `#FFFFFF` text (contrast 6.8:1).

### Semantic & Collision Safeguards
Because crimson and green serve as jurisdictional identifiers, semantic states must avoid ambiguous overlap:
- **Semantic Error / Revocation (*Revogado*):** `#881337` (Burgundy Rose, with diagonal strike-through token).
- **Semantic Success / In Force (*Vigente*):** `#065F46` (Forest Teal, distinct from Emerald #1B7A54).
- **Semantic Warning / In Progress (*Vacatio Legis*):** `#A16207` (Deep Amber).
- **Neutral Canvas:** `#F8F9FA` for general backgrounds, `#FFFFFF` for primary cards, `#1F2328` for statutory text.

## Typography
Typography uses a dual-engine architecture:
- **System Interface (Inter):** Handles application shells, tabs, filters, metadata, tabular numbers (`font-variant-numeric: tabular-nums`), and legal citation numbering (e.g., `Art. 5º, Inciso LV`).
- **Statutory Prose (Source Serif 4):** Reserved strictly for legal statutes, legal articles (*artigos*), paragraphs (*parágrafos*), and items (*incisos*). Set at a golden proportion line-height of `1.65` (~28px on 17px base) and constrained to a optimal readability measure of `68ch`.

All legal numeric counters and article references feature explicit tabular alignment to preserve indentation hierarchy across indented clauses (*alíneas*).

## Layout & Spacing
The layout follows an adaptive single-column document flow on mobile viewports with a 4-column sub-grid, expanding to an asymmetric 12-column split on tablets (3 columns for index/articles navigation, 9 columns for statutory reading).

Margins are locked to `1rem` on mobile devices with `safe-area-inset` buffers accommodating bottom sheets and dynamic camera notches. Dense legal lists utilize vertical rhythms structured around the 8pt grid (`space-sm` = 8px, `space-md` = 16px, `space-lg` = 24px), while statutory sub-items receive strict structural horizontal indents:
- *Caput:* 0 offset
- *Parágrafo único / §:* 1.25rem indent
- *Incisos (I, II...):* 2rem indent
- *Alíneas (a, b...):* 2.75rem indent

## Elevation & Depth
Depth is realized through the Liquid Glass paradigm augmented by Material You tonal layering:

1. **Layer 0 (Canvas Base):** Solid neutral tint `#F8F9FA`.
2. **Layer 1 (Card Containers):** Pure `#FFFFFF` surface with low-contrast borders (`1px solid rgba(0, 0, 0, 0.08)`) and ambient diffusion `box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04)`.
3. **Layer 2 (Liquid Glass Navigation & Bottom Sheets):** Translucent background `rgba(255, 255, 255, 0.78)` with `backdrop-filter: blur(20px) saturate(180%)`, framed by an ultra-subtle highlight border `1px solid rgba(255, 255, 255, 0.65)` on top and `1px solid rgba(0, 0, 0, 0.06)` on bottom. Casts an ambient shadow: `0 8px 32px rgba(0, 0, 0, 0.08)`.
4. **Layer 3 (Floating Action Controls & Context Overlays):** Dynamic jurisdictionally tinted glass or high-contrast pill `box-shadow: 0 12px 24px -4px rgba(0, 0, 0, 0.16)`.

## Shapes
The design adopts a pill-centric geometric hierarchy (roundedness scale 3). Interactive controls—including Search Anchors, Floating Action Buttons, and Jurisdictional Filter Chips—utilize full continuous curvature (*squircle* or `border-radius: 9999px`). 

Statute cards and modal bottom sheets utilize softer large radii (`rounded-2xl` = 1.5rem to 2rem) with continuous curvature transitions to mimic physical glass slabs.

## Components

### 1. Jurisdictional Filter Chips (M3 Adaptive)
- **Geometry:** Height 36px, `rounded-full`, horizontal padding 14px.
- **States:**
  - *Inactive:* Transparent background, `1px solid rgba(0, 0, 0, 0.12)`, text `#1F2328`, label-md font.
  - *Active (Municipal):* Background `#B71C1C`, text `#FFFFFF`, icon filled.
  - *Active (Estadual):* Background `#1B7A54`, text `#FFFFFF`.
  - *Active (Federal):* Background `#8A5A1E`, text `#FFFFFF`.
  - *Active (Institucional):* Background `#00008C`, text `#FFFFFF`.
- **Focus Ring:** 2px solid offset ring with jurisdictional hue, contrast ratio > 3:1 against white canvas.

### 2. Statutory Legal Cards & Articles
- **Surface:** `#FFFFFF` background, `rounded-xl` (16px), interior padding 20px.
- **Header Badge:** Pill tag indicating legal validity status (*Vigente*, *Revogado parcialmente*, *Vacatio legis*).
- **Prose Block:** `body-legal` typographic style, `max-width: 68ch`, selectable with native iOS handles, equipped with inline marginalia anchors for commentary.

### 3. Liquid Glass Bottom Navigation & Action Bar
- **Surface:** `rgba(255, 255, 255, 0.82)` with `backdrop-filter: blur(20px)`.
- **Border:** Top border `1px solid rgba(255, 255, 255, 0.5)`.
- **Placement:** Suspended 12px above bottom screen margin, pill-shaped or edge-to-edge docked with safe-area padding.
- **Action Items:** 4 primary navigation slots with 24px optical icons and tabular 11px micro-labels.

### 4. Floating Action Button (FAB)
- **Shape:** Pill shape (`rounded-full`), height 52px, padding 0 20px.
- **Dynamic Theming:** Adapts color to current document jurisdiction (e.g., `#00008C` for Federal Constitution views).
- **Elevation:** 0 10px 20px -3px rgba(0,0,0,0.18).

### 5. Search & Citation Input
- **Surface:** `rgba(240, 242, 245, 0.85)` filled style, `rounded-full`, height 48px.
- **Leading Icon:** Search magnifier; Trailing: Voice dictation and jurisdiction quick-toggle badge.
- **Focus:** Border transitions to `2px solid var(--jurisdiction-primary)` with background shifting to `#FFFFFF`.