# Third-party material

All Python and JavaScript in this repository is original. This file records
outside material that influenced it, so the provenance is auditable.

## ui-ux-pro-max-skill — design methodology

- **Source:** https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
- **Licence:** MIT © 2024 Next Level Builder
- **What was used:** its UI/UX rule set (`references/pro-rules.md`,
  `references/quick-reference.md`) as the checklist the `web/` storefront was
  designed and audited against.
- **What was *not* used:** none of its code, CSS, data files, or assets are
  vendored or copied into this repository. The rules are design guidance —
  facts and conventions such as "minimum 4.5:1 contrast", "44×44 touch
  targets", "no emoji as icons", "4/8px spacing rhythm" — and the
  implementation of each is written from scratch here.

Concretely, the following were applied in `web/style.css`, `web/app.js`,
`web/icons.js` and `web/illustrations.js`:

| Rule | Where it landed |
|---|---|
| `no-emoji-icons` | `icons.js` — one 24×24 / 1.5px-stroke SVG family; zero emoji in the UI |
| `icon-style-consistent` | every glyph comes from that single file |
| `vector-only-assets` | product artwork is generated SVG (`illustrations.js`) |
| `color-semantic` | semantic tokens only; no raw hex inside components |
| `color-contrast` | body text ≥ 4.5:1 in both themes (measured, see README) |
| `focus-states` | 2px `:focus-visible` ring with offset on every control |
| `touch-target-size` | 44px minimum on buttons, nav links, qty steppers |
| `spacing-scale` | 4/8px token scale (`--sp-1` … `--sp-16`) |
| `elevation-consistent` | three-step shadow scale (`--e-1` … `--e-3`) |
| `z-index-management` | named scale (`--z-base` … `--z-toast`) |
| `dark-mode-pairing` | dark is a designed tonal set, not an inversion |
| `progressive-loading` | skeletons sized to the real layout box |
| `content-jumping` | `aspect-ratio` on media so artwork never shifts layout |
| `number-tabular` | `font-variant-numeric: tabular-nums` on all prices/metrics |
| `reduced-motion` | `prefers-reduced-motion` disables transitions and hover lift |
| `primary-action` | one primary CTA per screen; the rest are secondary/ghost |
| `skip-links`, `form-labels`, `aria-labels`, `heading-hierarchy` | `index.html` + `app.js` |

Its Three.js guidance (`data/stacks/threejs.csv`) shaped `web/hero3d.js` —
single context per page, explicit disposal, instanced draws, a conservative
instance count, exponential fog, `prefers-reduced-motion` checked before any
animation, and touch events alongside pointer events. **Three.js itself is not
used or vendored**; the scene is hand-written WebGL, because this project has
a zero-dependency, no-build constraint and ~600 KB of library for one
decorative panel is disproportionate.

## Inter — typeface

- **Source:** https://github.com/rsms/inter
- **Licence:** SIL Open Font License 1.1 — full text vendored at
  [`web/fonts/LICENSE-Inter.txt`](web/fonts/LICENSE-Inter.txt) as the licence
  requires
- **What is included:** three unicode-range subsets of the Inter variable font
  (`latin`, `latin-ext`, `vietnamese`; 140 KB total), obtained from the Google
  Fonts CDN and vendored so the application needs no network egress.
- **Modifications:** none. The files are unmodified subsets and the reserved
  font name is not used for any derivative.

## Behavior Sequence Transformer — model concept

- **Source:** Chen et al., 2019, *Behavior Sequence Transformer for E-commerce
  Recommendation in Alibaba* — https://arxiv.org/abs/1905.06874
- **What was used:** the published idea that a candidate item can be appended
  to a user's behavior sequence and related to it by self-attention.
- **What was *not* used:** no code from the paper's authors or from any
  library implementing it. `src/recsys_lite/model.py` is built on PyTorch's
  stock `nn.TransformerEncoder`.

## Population Stability Index — statistic

PSI is a standard, unattributed statistic in the ML-monitoring and credit-risk
literature. The conventional thresholds used in `src/recsys_lite/drift.py`
(< 0.1 stable, 0.1–0.25 moderate, ≥ 0.25 significant) are a widely published
rule of thumb, implemented here from the definition rather than copied.

## Runtime dependencies

Installed from PyPI, not vendored: `fastapi`, `uvicorn`, `pydantic`, `torch`,
`numpy` (plus `pytest` and `httpx` for development). Each carries its own
licence.
