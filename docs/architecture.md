# Lagar — Software Architecture, Navigation & Contexts

Technical and conceptual documentation of the **Lagar** app architecture: the mental model of the *normhierarki* (Nordic normative hierarchy), the color taxonomy, context/scope management, and the navigation tree combining **Material You (M3)** and **Liquid Glass (Apple HIG)** patterns.

Visual values (colors, glass, typography) are defined in [`DESIGN.md`](../DESIGN.md), which is the source of truth when this document and it differ.

---

## 1. Overview and Mental Model

**Lagar** is a unified platform and app for looking up, interpreting and navigating the whole Swedish legal and regulatory ecosystem. It addresses the classic problem of scattered norms by placing every act in a clear hierarchical pyramid, where a norm's legal force sets its visual and chromatic weight in the interface.

### 1.1 Core Architectural Principles
- **Strict Normhierarki**: The higher a norm sits in the hierarchy (*Grundlagar*), the deeper, more stable and more distinguished its palette and metadata.
- **Cross-cutting Status**: Validity status (such as *Upphävd* / repealed) cuts across every layer and overrides it with faded, strikethrough and neutral grey (`#8A8F98`) treatments.
- **Hybrid Design System**: Combines the information density and accessible robustness of **Material Design 3 (M3)** with the tactile depth, glass refraction and calculated translucency of **Liquid Glass (Apple HIG / iOS 18)**.

---

## 2. Normative Layers and Color Identity (Colors by Layer)

The visual architecture assigns each issuing body and normative level a specific hue. Card and badge surfaces use **10–12% opacity** with backdrop blur, while icons and borders use the full color. Text uses the layer's accessible `text` token (see `DESIGN.md`).

| Level | Layer | Primary color | Hex | Highlights & icons |
| :---: | :--- | :--- | :---: | :--- |
| **1** | **Grundlagar** (Fundamental laws) | Deep royal blue | `#0B3D91` | Royal crown (`#FECC02`), Regeringsformen, TF, YGL, SO |
| **2** | **SFS Lagar** (Acts of Parliament) | Flag blue | `#005B99` | Scales of justice, Riksdag, Brottsbalken |
| **3** | **SFS Förordningar** (Government ordinances) | Light blue | `#4A90C8` | Regulatory scroll, Regeringen |
| **4** | **Myndighetsföreskrifter** (Agency regulations) | Teal | `#0F7C7A` | Technical shield, FFFS, Skatteverket, Arbetsmiljöverket |
| **5** | **Rättspraxis** (Case law and precedents) | Burgundy | `#7A2E4D` | Judge's gavel, color of judges' robes, HD/NJA |
| **6** | **EU-rätt** (European Union law) | Violet | `#5B3FA6` | Circle of stars, GDPR, AI Act |
| **7** | **Regioner** (Regional norms / healthcare) | Forest green | `#2E7D32` | Medical cross, regional healthcare and transport rules |
| **8** | **Kommuner** (Municipal norms) | Falu red | `#8B2E1F` | Traditional Falun red, local statutes |
| **9** | **Tjänster** (Public services and citizen utilities) | Flag yellow | `#E0A100` | Kungörelser |
| **—** | **Upphävd** (Repealed / historical) | Grey | `#8A8F98` | Neutral badge, strikethrough text, inactive history |

---

## 3. Context Management (Context Engine)

The app works with three simultaneous context layers:

```
┌────────────────────────────────────────────────────────┐
│ 1. Global Context (Jurisdiction)                       │
│    • Display mode (Light / Dark Glass)                 │
│    • Language and legal vocabulary                     │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ 2. Scope Context (Normative Scope)                     │
│    • National (Riksdag / Regeringen)                   │
│    • Regional (e.g. Region Stockholm, Skåne)           │
│    • Municipal (local Kommun: Göteborg, Malmö, etc.)   │
│    • Case law / Courts                                 │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│ 3. Norm Context (Document State)                       │
│    • Timeline version (temporal consolidation)         │
│    • Validity (in force, repealed, vacatio legis)      │
│    • Table of contents and cross-references to layers  │
└────────────────────────────────────────────────────────┘
```

There are no user accounts or sign-in: the app is anonymous, and bookmarks and settings stay on the device.

### Context Transition Rules
1. **Filter Inheritance**: When the scope changes (e.g. from National to Municipal), the search bar and filter chips reconfigure their act-type options dynamically (replacing SFS with municipal regulations).
2. **Temporal State Preservation**: The reader keeps the selected point in time so the user can see how the legislation read in any given year.

---

## 4. Navigation Map and Flows (Navigation Architecture)

Navigation uses a 4-pillar App Shell with support for floating modal sheets:

```
[ Splash & Loading ]
         │
         ▼
[ Onboarding Flow ] ──► 1. Welcome and main focus
         │          ──► 2. Scope, with its Kommun / län (GPS suggestion)
         ▼
┌─────────────────────────────────────────────────────────────┐
│                       MAIN APP SHELL                        │
├──────────────┬──────────────┬───────────────┬───────────────┤
│   Utforska   │   Hierarki   │    Sparade    │   Tjänster    │
│   (Explore)  │ (Hierarchy)  │   (Saved)     │  (Services)   │
└──────┬───────┴──────┬───────┴───────┬───────┴───────┬───────┘
       │              │               │               │
       ├──────────────┼───────────────┼───────────────┤
       ▼              ▼               ▼               ▼
   [ Search &      [ Interactive  [ Saved         [ Notices & ]
    Mixed Feed ]     Tree ]         Articles &      Gazettes  ]
       │                            Notes ]
       │
       ├──► [ Modal: Change Location / Scope ]
       ├──► [ Sheet: Advanced Search and Time Filters ]
       └──► [ Screen: Consolidated Norm Reader & Table of Contents ]
```

### Flow Descriptions

1. **Onboarding & Initial Setup**:
   - Presents the size of the legal corpus and lets the user choose a primary focus (e.g. general citizen, student or municipal lawyer).
   - Smart location: identifies the user's *Kommun* to load local regulations automatically.

2. **Utforska (Explore) tab**:
   - Dynamic feed with new court precedents, the latest enacted laws (*SFS*) and a quick bar with shortcuts to the major codes (*Brottsbalken*, *Miljöbalken*).

3. **Hierarki (Norm Pyramid) tab**:
   - Structured view of the 9 levels, charts of the corpus distribution (across an estimated 40k+ acts) and browsing by issuing source.

4. **Advanced Search (Search Modal)**:
   - Combines terms in the title/summary or full text, a publication date range filter and a toggle for active vs. repealed norms.

5. **Consolidated Norm Reader (Document Viewer)**:
   - Immersive legal reading typography with inline notes, article shortcuts and a historical version comparator.

---

## 5. UI Implementation Practices (Design Tokens)

Summary only; exact values for both light and dark mode are in `DESIGN.md` (*Elevation & Depth*, *Dark Liquid Glass*, *Implementation Notes*).

- **Backdrop Blur**: `blur(20px)` for sticky headers and filters, `blur(28px)` for floating overlays and drawers; solid fallback when blur is unavailable or reduce transparency is on.
- **Glass Borders**: 1px frosted border, `rgba(255, 255, 255, 0.65)` in light mode and `rgba(255, 255, 255, 0.12)` in dark mode, each with a fine outer stroke.
- **Diffuse Shadows**: Opaque drop shadows are avoided; elevation comes from translucent planes, with only faint ambient shadows on tiers 2 and 3.
