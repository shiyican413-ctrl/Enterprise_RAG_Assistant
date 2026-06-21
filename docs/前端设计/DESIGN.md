# xAI — Style Reference
> cosmic void pierced by a single luminous thread

**Theme:** dark

xAI operates in the visual language of deep space: a near-black void where a single luminous word becomes the only source of light. The interface is almost entirely monochrome — pure whites and graphite grays on absolute black — treating the product wordmark as a celestial object that emits its own glow. Typography is whisper-thin (weight 400 across all sizes), trusting negative space and tight tracking to do the heavy lifting rather than weight or decoration. Components are skeletal: ghost pills, hairline borders at #1f2228, inputs defined only by a subtle focus ring, and abstract line illustrations that hint at cosmic phenomena. The only chromatic punctuation is a single electric blue (#2563eb) for input focus, and a warm amber light wash bleeding up from the footer horizon — the system treats color as rare atmospheric event, not decoration.

## Colors

| Name | Value | Role |
|------|-------|------|
| Void Black | `#0c0c0b` | Page canvas, input fills, icon backgrounds — the base layer everything floats on |
| Graphite | `#1f2228` | Hairline borders across all containers, cards, nav separators, and input outlines — defines structural edges without contrast |
| Charcoal | `#141619` | Secondary border tone for deeper structural edges |
| Smoke | `#474747` | Dark borders and separators for elevated surfaces and inverted UI. Do not promote it to the primary CTA color |
| Ash | `#7d8187` | Muted helper text, badge labels, secondary nav links — the voice that whispers rather than speaks |
| Bone | `#71717a` | Input focus ring shadow at 0px 0px 0px 2px — the only ambient glow in the system |
| Stellar White | `#ffffff` | Primary text, icon strokes, ghost-pill borders, and the hero wordmark — everything that should feel like emitted light |
| Signal Blue | `#2563eb` | Input focus border — the single chromatic accent, used exclusively to signal active state in text fields |
| Horizon Amber | `linear-gradient(to top, rgba(255, 99, 8, 0.1), rgba(189, 201, 230, 0.1), rgba(151, 196, 255, 0.1))` | Footer atmospheric wash — warm light bleeding from the bottom edge, transitioning through to cool blue at the horizon line |

## Typography

### universalSans — All display, heading, and body text — used universally across hero wordmark, section titles, card titles, descriptions, and navigation
- **Substitute:** Inter
- **Weights:** 400
- **Sizes:** 16px, 20px, 36px, 48px, 80px
- **Line height:** 1.00, 1.11, 1.20, 1.40, 1.50
- **Letter spacing:** -0.025em applied at all sizes (-0.4px at 16px, -0.5px at 20px, -0.9px at 36px, -1.2px at 48px, -2.0px at 80px)

### GeistMono — Eyebrow labels in [ BRACKETS ], nav links, badge text, button micro-labels — tracked out at +0.1em to function as technical metadata
- **Substitute:** JetBrains Mono
- **Weights:** 400
- **Sizes:** 12px, 14px
- **Line height:** 1.33, 1.43, 2.00
- **Letter spacing:** 0.1em (1.2px at 12px, 1.4px at 14px)

### Type Scale

| Role | Size | Line Height | Letter Spacing |
|------|------|-------------|----------------|
| mono-badge | 12px | 1.33 | 1.2px |
| mono-label | 14px | 1.43 | 1.4px |
| body | 16px | 1.4 | -0.4px |
| body-lg | 20px | 1.5 | -0.5px |
| heading | 36px | 1.2 | -0.9px |
| heading-lg | 48px | 1.11 | -1.2px |
| display | 80px | 1 | -2px |

## Spacing & Layout

**Base unit:** 4px

**Density:** comfortable

- **Page max-width:** 1200px
- **Section gap:** 96-120px
- **Card padding:** 32px
- **Element gap:** 12-16px

### Border Radius

- **cards:** 0px
- **inputs:** 24px
- **buttons:** 9999px

## Components

### Top Navigation Bar
**Role:** Persistent header across all pages

Transparent background, no border, 80px tall. Left: xAI logomark (X mark) in white, 12px gap, then horizontal nav links in GeistMono 14px tracked +0.1em at #ffffff. Right: 'TRY GROK' ghost pill button. Nav items separated by visual spacing, not dividers.

### Ghost Pill CTA
**Role:** Primary action button (TRY GROK in nav, READ ANNOUNCEMENT in hero)

Pill shape (9999px radius), 1px solid #ffffff border, transparent background, white text in universalSans 14px weight 400. Padding 8px 20px. No fill state — remains outlined on hover. Arrow icons (↗) appended in 12px for directional intent.

### Ghost Card Action Button
**Role:** Card-level call-to-action (USE NOW, BUILD NOW, LEARN MORE)

Pill shape (9999px radius), 1px solid #474747 border, transparent background, white text in universalSans 14px. Arrow icon (↗) trailing. Lower-contrast than the nav CTA — signals secondary action within card context.

### Navigation Link
**Role:** Top-nav menu items (GROK, API, COMPANY, COLOSSUS, CAREERS, etc.)

GeistMono 14px weight 400, letter-spacing 0.1em, color #ffffff. No hover state styling. Lettercase: uppercase.

### Hero Wordmark
**Role:** Centerpiece of the landing hero

universalSans 80px weight 400, line-height 1.0, letter-spacing -2.0px, color #ffffff. Renders as a massive luminous 'Grok' text — the typographic hero IS the visual hero. Backed by a dramatic light-source gradient bloom radiating from the right side.

### Search / Chat Input
**Role:** Primary input for user queries in hero

Full container width, ~600px centered. Background #0c0c0b (same as canvas — no fill contrast). 1px solid #1f2228 border, 24px radius. Padding 20px top/bottom. Placeholder 'What do you want to know?' in #7d8187, universalSans 16px. On focus: 2px ring shadow in #71717a (0px 0px 0px 2px). Trailing circular submit button with up-arrow icon, 1px #1f2228 border.

### Announcement Banner
**Role:** Hero-bottom callout for product updates

Two-line text block: headline in universalSans 16px #ffffff, subtext in #7d8187. Ghost pill CTA aligned right. No background or border — floats on canvas.

### Section Eyebrow Label
**Role:** Pre-title metadata (e.g., '[ PRODUCTS ]')

GeistMono 12px weight 400, letter-spacing 0.1em, color #7d8187. Enclosed in square brackets with spaces — functions as a technical spec annotation, not a heading.

### Section Title
**Role:** Primary heading for content sections ('AI for all humanity')

universalSans 48px weight 400, line-height 1.11, letter-spacing -1.2px, color #ffffff. Left-aligned. No max-width constraint — runs natural width.

### Product Card
**Role:** Feature card in 3-column grid (Grok, API, Developer Docs)

No background fill, no card border — cards are typographic columns separated by column gap only. Structure: card title (universalSans 36px weight 400, -0.9px tracking, #ffffff) → description (16px #7d8187) → abstract line illustration (1px #1f2228 strokes, ~200px tall) → ghost pill action at bottom. Column gap: 24px.

### Abstract Line Illustration
**Role:** Decorative visual within product cards

Thin 1px line art in #1f2228 — a comet arc for Grok, a terminal window frame for API, stacked document rectangles for Developer Docs. Minimal, geometric, monochrome. Functions as iconography, not illustration.

### Footer Link Column
**Role:** Site-map navigation in 5-column footer

Column header in GeistMono 12px tracked 0.1em, color #ffffff. Links below in universalSans 16px weight 400, color #ffffff, 8px row gap. No hover indicators. No dividers between columns.

### Footer Horizon Glow
**Role:** Atmospheric gradient wash at page bottom

Full-bleed linear gradient at the footer: warm amber (rgba(255, 99, 8, 0.1)) at the bottom edge, transitioning through cool blue (rgba(151, 196, 255, 0.1)) upward. Creates a sunrise/horizon effect against the void black — the only large-scale color event in the system.

## Do's and Don'ts

### Do
- Use #0c0c0b as the only canvas color — never introduce grays or off-blacks for page backgrounds
- Apply 9999px radius to all buttons, tags, and pill-shaped elements
- Define all structural edges with 1px solid #1f2228 borders — no shadows, no fills for separation
- Use universalSans weight 400 at all sizes — hierarchy comes from size and tracking, never weight
- Apply -0.025em letter-spacing to all universalSans text at every size
- Reserve #2563eb exclusively for input focus borders — never for buttons, links, or decorative elements
- Keep the amber horizon gradient as a full-bleed footer atmospheric event only — never repeat as section background

### Don't
- Never add background fills to cards — they must remain transparent, defined only by column gap and typography
- Never use weight 500+ — the system operates entirely at weight 400, and introducing bold breaks the whisper-quiet voice
- Never use shadows for elevation beyond the single 2px input focus ring — depth comes from luminosity, not z-axis
- Never use color for decorative purposes — #2563eb is functional (input focus) and the amber gradient is atmospheric (footer only)
- Never round card corners with 8-16px radii — cards have no radius (0px), only inputs (24px) and pills (9999px) are rounded
- Never add hover state background fills to ghost buttons — they remain outlined at all times
- Never introduce photography, human imagery, or product screenshots — the system is abstract and atmospheric only

## Elevation

- **Input Focus:** `rgb(113, 113, 122) 0px 0px 0px 2px`

## Surfaces

- **Void** (`#0c0c0b`) — Page canvas — the space everything exists in
- **Input Surface** (`#0c0c0b`) — Text field fills, same as canvas — fields are defined by border + focus ring, not fill contrast

## Imagery

The visual language is entirely abstract and atmospheric — no photography, no product screenshots, no human figures. The hero is a single dramatic light bloom: a radial gradient of white-to-blue luminance radiating from the right edge, as if a star is emerging from behind the 'Grok' wordmark. Product cards contain minimal 1px line drawings: a comet-arc sweep, a terminal window frame, stacked document rectangles. These are iconographic gestures, not illustrations. The footer introduces the system's only warm color — an amber-to-blue gradient horizon bleeding up from the bottom edge, suggesting atmospheric depth. Everything is geometric, monochrome, and restrained.

## Layout

Full-bleed dark canvas with a max-width 1200px content container, centered. The hero is full-viewport: massive centered 'Grok' wordmark (~80px) with a dramatic light-source bloom from the right, a single search input below at ~600px width, and an announcement banner anchored to the bottom. Sections flow vertically with generous 96-120px gaps. The 'AI for all humanity' section uses a 3-column product card grid with 24px column gaps — cards are borderless, defined only by vertical column separation. The footer is a 5-column link grid that bleeds into a full-width amber horizon gradient. Navigation is a single transparent top bar with no border or background. The overall rhythm is: massive whitespace → luminous centerpiece → quiet grid → atmospheric close.

## Similar Brands

- **SpaceX** — Same near-black void canvas with white minimal sans-serif typography and dramatic light/luminance effects as the primary visual language
- **Linear** — Dark-mode UI with single accent color, generous spacing, and weight-400-only typography creating whisper-quiet hierarchy
- **Vercel** — GeistMono monospace labels for metadata, hairline borders, pill-shaped ghost buttons, and near-black canvas
- **Anthropic** — Dark monochromatic palette with minimal chromatic accent, large luminous display type, and abstract atmospheric backgrounds
- **Stripe** — Clean restrained typography with tight letter-spacing on display sizes and pill-shaped UI controls
