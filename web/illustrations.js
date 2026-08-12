/* Product artwork.
 *
 * The catalog is synthetic, so there are no real product photographs to show
 * — and using stock photos of real goods would misrepresent generated data
 * (and drag in licensing questions). Instead each product gets a flat vector
 * illustration drawn from its title noun, tinted by a hue derived from its
 * item id. Same id always yields the same artwork, so the catalog looks
 * stable across reloads.
 *
 * Vector-only keeps these crisp at any size and theme-adaptive, per the
 * ui-ux-pro-max `vector-only-assets` rule.
 */

/* Deterministic hue from the item id — golden-angle stepping so neighbouring
   ids land far apart on the colour wheel instead of forming a gradient. */
function hueFor(itemId) {
  return Math.round((itemId * 137.508) % 360);
}

function palette(itemId) {
  const h = hueFor(itemId);
  return {
    bg: `hsl(${h} 62% 94%)`,
    bgDark: `hsl(${h} 30% 20%)`,
    main: `hsl(${h} 58% 56%)`,
    dark: `hsl(${h} 62% 38%)`,
    light: `hsl(${h} 70% 78%)`,
  };
}

/* Each shape function draws inside a 200×150 viewBox. */
const SHAPES = {
  Jacket: (c) => `
    <path d="M70 44 58 52v58h84V52l-12-8-30 10Z" fill="${c.main}"/>
    <path d="M70 44 58 52l12 16 10-14Z" fill="${c.dark}"/>
    <path d="M130 44l12 8-12 16-10-14Z" fill="${c.dark}"/>
    <path d="M100 54v56" stroke="${c.light}" stroke-width="3" stroke-linecap="round"/>
    <path d="M58 60 44 74v22h14" fill="${c.dark}"/>
    <path d="M142 60l14 14v22h-14" fill="${c.dark}"/>`,
  Sneakers: (c) => `
    <path d="M44 96c0-14 8-22 8-32l18 4 8 12 26 6 22 10c8 4 12 8 12 14H46Z" fill="${c.main}"/>
    <path d="M44 96h94v12H50a6 6 0 0 1-6-6Z" fill="${c.dark}"/>
    <path d="M72 68l10 14M86 74l8 12" stroke="${c.light}" stroke-width="3" stroke-linecap="round"/>`,
  Backpack: (c) => `
    <rect x="64" y="48" width="72" height="72" rx="16" fill="${c.main}"/>
    <path d="M82 52v-6a18 18 0 0 1 36 0v6" stroke="${c.dark}" stroke-width="6" fill="none"/>
    <rect x="78" y="82" width="44" height="24" rx="6" fill="${c.light}"/>
    <path d="M64 70h72" stroke="${c.dark}" stroke-width="4"/>`,
  Headphones: (c) => `
    <path d="M56 96V78a44 44 0 0 1 88 0v18" stroke="${c.main}" stroke-width="10" fill="none" stroke-linecap="round"/>
    <rect x="44" y="88" width="24" height="34" rx="10" fill="${c.dark}"/>
    <rect x="132" y="88" width="24" height="34" rx="10" fill="${c.dark}"/>`,
  Watch: (c) => `
    <rect x="84" y="30" width="32" height="30" rx="8" fill="${c.dark}"/>
    <rect x="84" y="94" width="32" height="30" rx="8" fill="${c.dark}"/>
    <rect x="70" y="52" width="60" height="52" rx="14" fill="${c.main}"/>
    <circle cx="100" cy="78" r="18" fill="${c.light}"/>
    <path d="M100 68v10l7 5" stroke="${c.dark}" stroke-width="3" stroke-linecap="round" fill="none"/>`,
  Blender: (c) => `
    <path d="M68 30h64l-8 56H76Z" fill="${c.light}"/>
    <rect x="64" y="24" width="72" height="10" rx="5" fill="${c.dark}"/>
    <path d="M132 40h10a8 8 0 0 1 0 16h-11" fill="none" stroke="${c.light}" stroke-width="6"/>
    <path d="M76 86h48l4 12H72Z" fill="${c.dark}"/>
    <rect x="70" y="98" width="60" height="26" rx="8" fill="${c.main}"/>
    <circle cx="88" cy="111" r="5" fill="${c.dark}"/>
    <rect x="100" y="107" width="22" height="8" rx="4" fill="${c.dark}"/>`,
  'Desk Lamp': (c) => `
    <ellipse cx="100" cy="122" rx="34" ry="8" fill="${c.dark}"/>
    <path d="M100 118V74l-24-14" stroke="${c.main}" stroke-width="7" fill="none" stroke-linecap="round"/>
    <path d="M56 66 76 44l22 16-20 22Z" fill="${c.main}"/>
    <circle cx="76" cy="60" r="6" fill="${c.light}"/>`,
  Notebook: (c) => `
    <rect x="60" y="34" width="80" height="88" rx="8" fill="${c.main}"/>
    <rect x="60" y="34" width="16" height="88" rx="8" fill="${c.dark}"/>
    <path d="M88 58h38M88 74h38M88 90h24" stroke="${c.light}" stroke-width="4" stroke-linecap="round"/>`,
  'Water Bottle': (c) => `
    <rect x="86" y="26" width="28" height="16" rx="4" fill="${c.dark}"/>
    <path d="M82 42h36a10 10 0 0 1 10 10v58a12 12 0 0 1-12 12H84a12 12 0 0 1-12-12V52a10 10 0 0 1 10-10Z" fill="${c.main}"/>
    <rect x="82" y="66" width="36" height="24" rx="4" fill="${c.light}"/>`,
  Sunglasses: (c) => `
    <path d="M40 62h50v10a20 20 0 0 1-40 0Z" fill="${c.main}"/>
    <path d="M110 62h50v10a20 20 0 0 1-40 0Z" fill="${c.main}"/>
    <path d="M90 68h20" stroke="${c.dark}" stroke-width="6"/>
    <path d="M40 62 30 52M160 62l10-10" stroke="${c.dark}" stroke-width="5" stroke-linecap="round"/>`,
  Keyboard: (c) => `
    <rect x="34" y="54" width="132" height="48" rx="8" fill="${c.main}"/>
    <g fill="${c.light}">
      <rect x="46" y="64" width="14" height="10" rx="2"/><rect x="66" y="64" width="14" height="10" rx="2"/>
      <rect x="86" y="64" width="14" height="10" rx="2"/><rect x="106" y="64" width="14" height="10" rx="2"/>
      <rect x="126" y="64" width="28" height="10" rx="2"/>
      <rect x="46" y="82" width="34" height="10" rx="2"/><rect x="86" y="82" width="48" height="10" rx="2"/>
      <rect x="140" y="82" width="14" height="10" rx="2"/>
    </g>`,
  'Monitor Stand': (c) => `
    <rect x="48" y="30" width="104" height="60" rx="6" fill="${c.main}"/>
    <rect x="56" y="38" width="88" height="44" rx="3" fill="${c.light}"/>
    <path d="M92 90h16v14H92Z" fill="${c.dark}"/>
    <rect x="64" y="104" width="72" height="12" rx="6" fill="${c.dark}"/>`,
  'Yoga Mat': (c) => `
    <rect x="40" y="52" width="120" height="48" rx="10" fill="${c.main}"/>
    <ellipse cx="40" cy="76" rx="12" ry="24" fill="${c.dark}"/>
    <ellipse cx="160" cy="76" rx="12" ry="24" fill="${c.light}"/>`,
  'Coffee Grinder': (c) => `
    <path d="M72 34h56l-14 30H86Z" fill="${c.light}"/>
    <path d="M114 64h-28l-4 8h36Z" fill="${c.dark}"/>
    <rect x="76" y="72" width="48" height="48" rx="6" fill="${c.main}"/>
    <rect x="86" y="86" width="28" height="20" rx="3" fill="${c.light}"/>
    <path d="M100 34V24h18" fill="none" stroke="${c.dark}" stroke-width="5" stroke-linecap="round"/>
    <circle cx="122" cy="24" r="6" fill="${c.dark}"/>`,
  'Phone Case': (c) => `
    <rect x="72" y="26" width="56" height="98" rx="12" fill="${c.main}"/>
    <rect x="80" y="38" width="40" height="70" rx="4" fill="${c.light}"/>
    <circle cx="100" cy="116" r="4" fill="${c.dark}"/>
    <circle cx="112" cy="34" r="4" fill="${c.dark}"/>`,
};

const FALLBACK = (c) => `
  <rect x="60" y="46" width="80" height="66" rx="10" fill="${c.main}"/>
  <path d="M60 76h80" stroke="${c.light}" stroke-width="4"/>
  <circle cx="100" cy="96" r="8" fill="${c.light}"/>`;

/** Extracts the product noun from a generated title like "Desk Lamp #412". */
export function nounOf(title) {
  return String(title || '').split('#')[0].trim();
}

/**
 * Inline SVG artwork for a product. Always decorative (`aria-hidden`): the
 * product name sits right beside it as real text, so announcing the picture
 * too would just make screen readers repeat themselves.
 */
export function productArt(itemId, title) {
  const c = palette(itemId);
  const draw = SHAPES[nounOf(title)] || FALLBACK;
  return `<svg viewBox="0 0 200 150" aria-hidden="true" focusable="false"
      preserveAspectRatio="xMidYMid meet" style="--art-bg:${c.bg};--art-bg-dark:${c.bgDark}">
    <rect width="200" height="150" class="art-bg"/>
    ${draw(c)}
  </svg>`;
}

/** A small category glyph reusing the same artwork language. */
export function categoryArt(categoryId) {
  const c = palette(categoryId * 7);
  return `<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false" width="22" height="22">
    <rect x="3" y="6" width="18" height="14" rx="3" fill="${c.main}"/>
    <rect x="6" y="3" width="12" height="5" rx="2" fill="${c.dark}"/>
    <circle cx="12" cy="14" r="3" fill="${c.light}"/>
  </svg>`;
}
