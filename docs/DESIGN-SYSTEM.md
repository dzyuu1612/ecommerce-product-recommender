# Design system

The Kestrel console is plain HTML, CSS and ES modules — no framework, no build
step, no `node_modules`. Everything below lives in `web/`.

- [Provenance](#provenance)
- [Tokens](#tokens)
- [Contrast — measured](#contrast--measured)
- [Typography](#typography)
- [Iconography](#iconography)
- [Product artwork](#product-artwork)
- [Layout and shell](#layout-and-shell)
- [Components](#components)
- [Motion](#motion)
- [Accessibility checklist](#accessibility-checklist)
- [Verification](#verification)

---

## Provenance

The system is built against the rule set from
[ui-ux-pro-max-skill](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill)
(MIT © 2024 Next Level Builder). Running its generator against this product:

```
$ python design_system.py "e-commerce storefront with ML recommendations dashboard"
Pattern: Real-Time / Operations Landing
Color Strategy: Dark or neutral. Status colors (green/amber/red). Data-dense but scannable.
```

That pattern is what drove the shift from a plain shop page to a **console
shell**: persistent left sidebar, dense KPI tiles, status-coloured badges, and
tabular data.

**No code from the skill is vendored.** Its rules are design guidance — facts
and conventions like "4.5:1 minimum contrast", "44×44 touch targets", "no
emoji as icons" — and each is implemented from scratch here. The rule-by-rule
mapping is in [../THIRD_PARTY.md](../THIRD_PARTY.md).

### One deliberate divergence

The skill recommends loading fonts **from the Google Fonts CDN**. This project
**self-hosts** instead, because the app must run offline and inside a container
with no egress — a CDN font is a hard external dependency at first paint, and
its swap causes exactly the `content-jumping` layout shift the skill's own
performance rules warn about.

The typeface itself follows the recommendation's intent (technical, precise,
excellent at small sizes in dense data): **Inter**, vendored as unicode-range
subsets. See [Typography](#typography).

---

## Tokens

Components never contain a raw hex value. Everything resolves through a
semantic token, which is what makes the two themes a *design* rather than an
inversion.

### Colour roles

| Token | Role |
|---|---|
| `--bg` / `--surface` / `--surface-2` / `--surface-3` | Page → card → raised → sunken |
| `--sidebar-bg` / `--sidebar-text` / `--sidebar-muted` | The dark rail, in both themes |
| `--border` / `--border-strong` | Hairlines vs. input borders |
| `--text` / `--text-muted` / `--text-subtle` | Three-step text hierarchy |
| `--accent` / `--accent-hover` / `--accent-soft` / `--accent-text` | Brand + interactive |
| `--ok` / `--warn` / `--err` / `--info` (+ `-soft`, `-line`) | Status, per the skill's ops palette |

The sidebar stays dark in light mode on purpose: it is chrome, not content,
and the contrast anchors the eye on the working area.

### Scales

| Scale | Values |
|---|---|
| Spacing | `--sp-1..16` → 4, 8, 12, 16, 20, 24, 32, 40, 48, 64 |
| Type | `--fs-2xs..4xl` → 11, 12, 13, 14, 15, 17, 20, 24, 30, 36 |
| Radius | `--r-xs..full` → 4, 6, 8, 12, 16, 999 |
| Elevation | `--e-1..3` — hairline, card, overlay |
| Z-index | `base 0 · sticky 20 · topbar 40 · sidebar 50 · overlay 60 · toast 100` |

A named z-index scale exists so nothing ever reaches for `z-index: 9999`.

---

## Contrast — measured

Ratios below were **computed in the browser** from the live tokens, not
estimated. Every pair clears WCAG AA (4.5:1) in **both** themes.

| Pair | Light | Dark |
|---|---|---|
| `text` / `surface` | 17.39:1 | 15.10:1 |
| `text-muted` / `surface` | 7.32:1 | 7.70:1 |
| `text-subtle` / `surface` | 4.86:1 | 5.41:1 |
| `accent-text` / `surface` | 7.40:1 | 8.18:1 |
| `ok` / `ok-soft` | 4.80:1 | 8.01:1 |
| `warn` / `warn-soft` | 5.34:1 | 9.18:1 |
| `err` / `err-soft` | 5.72:1 | 7.47:1 |
| `info` / `info-soft` | 6.53:1 | 7.02:1 |
| `sidebar-text` / `sidebar-bg` | 10.59:1 | 10.77:1 |
| `sidebar-muted` / `sidebar-bg` | 4.83:1 | 5.12:1 |

Measuring caught two real failures that eyeballing had missed:

1. An earlier palette shipped `--text-subtle` at **4.11:1** in light — fine for
   large text, **not** for the small meta text it was actually used on.
2. `--sidebar-muted` in dark landed at **4.41:1** — used for the "SHOP" /
   "OPERATIONS" group labels.

Both were fixed by darkening/lightening the token. Neither was fixed by
softening the claim.

---

## Typography

**Inter**, self-hosted as a variable font. Inter was designed for user
interfaces at small sizes — tall x-height, open apertures, unambiguous
letterforms — which is what a data-dense console needs.

### Vendoring

Shipped as three unicode-range subsets so the browser downloads only what a
page actually uses:

| Subset | Size | Covers |
|---|---|---|
| `inter-latin.woff2` | 47 KB | Core Latin, punctuation, currency |
| `inter-latin-ext.woff2` | 83 KB | Extended Latin |
| `inter-vietnamese.woff2` | 10 KB | Vietnamese diacritics |

140 KB total on disk; a typical English page fetches only the 47 KB latin
subset. Licence: **SIL OFL 1.1**, included at `web/fonts/LICENSE-Inter.txt` as
the licence requires.

`font-display: swap` with a metrics-adjacent system fallback keeps first paint
immediate and the swap from moving layout.

### OpenType features

```css
font-feature-settings: "cv05" 1, "cv09" 1, "ss03" 1;
font-optical-sizing: auto;
```

`cv05` gives the lowercase **l** a tail so it cannot be confused with capital
I or the digit 1 — which matters when product ids and metric names sit next to
numbers. `cv09` is the slashed zero. `ss03` fixes the quote and apostrophe
shapes.

### Scale and tracking

| Use | Token | Notes |
|---|---|---|
| UI text | `--font-ui` | Inter var, with a system fallback chain |
| Ids, metrics, code | `--font-mono` | `.mono` utility |
| Numeric columns | `font-variant-numeric: tabular-nums` | Digits keep their column as values change |

Optical tracking is tokenised rather than guessed per component, because
larger type needs tighter tracking and small uppercase labels need looser:

| Token | Value | Applied to |
|---|---|---|
| `--track-tight` | `-0.021em` | `h1`, hero headline |
| `--track-snug` | `-0.014em` | `h2`, `h3` |
| `--track-normal` | `-0.006em` | Body |
| `--track-wide` | `0.06em` | Uppercase micro-labels |

Body is 15px at 1.55 line-height; long-form paragraphs cap at `76ch` to stay
in the readable 60–75 character band. Headings use `text-wrap: balance` so a
two-line headline breaks evenly rather than leaving one orphan word.

---

## Iconography

One family, defined once in `web/icons.js`:

- 24×24 viewBox, **1.5px stroke**, round caps and joins, no fills
- `currentColor` throughout, so every icon inherits its context's token and
  stays correct in both themes
- Decorative by default (`aria-hidden` + `focusable="false"`); pass a `label`
  to make one meaningful

**Zero emoji in the UI.** The skill's `no-emoji-icons` rule caught a real
regression in an earlier revision, which used 🌙/☀️ for the theme toggle:
emoji are font-dependent, render differently per platform, and cannot be
driven by design tokens. Both are now SVG.

---

## Product artwork

The catalog is synthetic. There are no real photographs, and using stock
photos of real goods would misrepresent generated data as well as raising
licensing questions.

`web/illustrations.js` draws a **flat vector illustration per product noun**
(jacket, sneakers, blender, coffee grinder, …), tinted by a hue derived from
the item id via golden-angle stepping so adjacent ids land far apart on the
colour wheel. The same id always yields the same artwork.

Artwork backgrounds use `--art-bg` / `--art-bg-dark` so illustrations sit
correctly on both themes.

All 15 nouns were rendered side by side and reviewed. Two — coffee grinder and
blender — read as the wrong object in the first pass and were redrawn.

---

## The 3D hero

The storefront hero renders a field of instanced quads drifting in 3D with
depth fog, parallaxing to pointer and touch. It lives in `web/hero3d.js`.

### Why hand-written WebGL, not Three.js

The skill's Three.js guidance is what this follows — but the library itself is
not vendored. This project has a documented zero-dependency, no-build
constraint, and ~600 KB of library for one decorative panel is
disproportionate. The scene is ~90 instanced quads and two short shaders;
writing it directly is smaller than the loader would be.

Every rule from the skill's Three.js data is honoured regardless:

| Rule | How |
|---|---|
| Single renderer per page | One context, created once, disposed on navigation |
| Dispose on removal | `dispose()` deletes every buffer, the program, and calls `WEBGL_lose_context` |
| Instanced draw for repeated objects | One `drawArraysInstancedANGLE` call for all 90 quads |
| Particle count ceiling | 90 instances — far below the mobile ceiling |
| `FogExp2` for depth | Exponential fog in the fragment shader; far instances fade out entirely |
| `prefers-reduced-motion` | Checked **before** any animation starts; renders one static frame and never runs a loop |
| Touch events for mobile | `touchmove` / `touchend`, registered `passive` so scrolling is never blocked |

### Beyond the skill's list

- **Off-screen and hidden tabs do no GPU work.** An `IntersectionObserver`
  and `visibilitychange` stop the rAF loop.
- **DPR capped at 2.** Beyond that the fill cost doubles for no visible gain.
- **Deterministic layout.** A seeded PRNG means the scene is identical on
  every load — no flicker of a different arrangement between reloads.
- **Theme-aware.** A `MutationObserver` on `data-theme` repaints the fog
  colour, so the hero matches light and dark immediately.

### It is decorative, and degrades to nothing

The canvas is `aria-hidden`. Every word in the hero is real DOM text sitting
above it, and a fixed scrim between the canvas and the copy keeps text
contrast constant no matter what the scene renders. If WebGL is missing,
blocked, or the instancing extension is unavailable, `mountHero` returns a
no-op and the CSS gradient carries the panel alone — verified by a test that
stubs `getContext` to return `null` and confirms the page still renders fully
with no errors.

---

## Layout and shell

```
┌───────────┬─────────────────────────────────┐
│ sidebar   │ topbar  (title · theme toggle)  │
│ (252px)   ├─────────────────────────────────┤
│  SHOP     │ breadcrumbs                     │
│   …       │ page head                       │
│  OPS      │ content                         │
│   …       │                                 │
│ ─────────  │                                │
│ browsing  │                                 │
│ as ▾      │                                 │
└───────────┴─────────────────────────────────┘
```

- Sidebar is sticky, full height, and splits **Shop** from **Operations** —
  the two audiences in one shell, because the ops numbers are produced by the
  shopping.
- Below **1024px** the sidebar becomes an overlay drawer with a scrim, a
  toggle whose `aria-expanded` tracks state, and Escape-to-close.
- Breakpoints: **375 / 768 / 1024 / 1440**, all verified.

### Grid tracks

Collapsing grids use `minmax(0, 1fr)`, **including inside media queries**. A
bare `1fr` is `minmax(auto, 1fr)`: the track refuses to shrink below its
content's min-content width, and one unbreakable `<code>` span pushes the whole
page into horizontal scroll. This caused a real 3px overflow at 375px on the
operations page before it was fixed.

---

## Components

| Component | Rules honoured |
|---|---|
| Buttons | One primary CTA per screen; press feedback that never shifts layout; ≥44px on coarse pointers |
| Inputs | Always labelled; per-field error with `aria-invalid`; focus moves to the first offender |
| Data tables | Sticky header, right-aligned tabular numerics, `overflow-x: auto` wrapper; a `compact` variant for narrow columns that drops columns instead of hiding them behind a scrollbar |
| KPI tiles | Label, value, optional note; value uses tabular numerics |
| Badges | Colour **plus** text, and a dot for shape — never colour alone |
| Skeletons | Sized to the real component so nothing jumps when data lands |
| Empty states | Icon, explanation, and a way out |
| Errors | Inline, quoting the server's `detail`, with a Retry button |
| Toasts | `role="status"`, auto-dismiss, never blocking |

---

## Motion

- Transitions are **160ms** with `cubic-bezier(.2,0,0,1)` — inside the
  150–300ms band the skill specifies.
- Only `background`, `border-color`, `color`, `opacity` and `transform` are
  animated.
- `prefers-reduced-motion: reduce` collapses every duration to ~0 and disables
  the shimmer.

---

## Accessibility checklist

- [x] Skip link to `#main`
- [x] One `<h1>` per page; headings never skip a level
- [x] Visible 2px `:focus-visible` ring with offset on every control
- [x] `aria-label` on every icon-only button
- [x] `aria-current="page"` on the active nav item — and detail pages
      (product, checkout) highlight their parent section so you never lose
      your place
- [x] `aria-live="polite"` on the view container and toasts
- [x] Form labels bound with `for`; `aria-invalid` on failures
- [x] Colour never the sole carrier of meaning
- [x] `prefers-reduced-motion` respected
- [x] Tables have captions (visually hidden) and `scope` on headers
- [x] No horizontal scroll at 375px
- [x] Touch targets ≥44px on coarse pointers

---

## Verification

Automated with Playwright against the running app:

| Check | Result |
|---|---|
| All 9 routes render, correct topbar/nav/h1 | pass |
| Console errors | 0 |
| Horizontal scroll at 375 / 768 / 1024 / 1440 | none |
| Emoji in rendered text | none |
| Icon-only buttons without `aria-label` | 0 |
| `<h1>` per page | exactly 1 |
| Contrast, all 20 pairs, both themes | ≥ 4.5:1 |
| Mobile drawer: toggle, scrim, Escape | pass |
| Checkout validation: 5 fields flagged, focus moved | pass |
| Hero animates (frame hashes differ) | pass |
| Hero repaints on theme change | pass |
| Hero static under `prefers-reduced-motion` | pass |
| No GL context leak after 12 navigations | pass |
| Page fully usable with WebGL stubbed out | pass |

> **A note on how the hero was verified.** The first attempt read pixels back
> with `gl.readPixels` and reported an empty canvas. That was the *test* being
> wrong, not the renderer: the context uses the default
> `preserveDrawingBuffer: false`, so the drawing buffer is undefined once the
> frame has been composited. The check was rewritten to compare screenshot
> hashes of the hero region — which measures what a user actually sees.

Bugs this verification found and fixed, rather than shipped:

1. `e.currentTarget` read after `await` — null by then, threw on every
   product-page add-to-cart.
2. No sidebar item highlighted on product pages.
3. 3px horizontal overflow at 375px from a bare `1fr` grid track.
4. Compact event feed overflowing its 330px column.
5. Two contrast failures (above).
