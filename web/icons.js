/* One icon family: 24×24 viewBox, 1.5px stroke, round caps/joins, no fills.
   The ui-ux-pro-max skill's `no-emoji-icons` and `icon-style-consistent`
   rules rule out emoji and mixed icon sets, so every glyph in the UI comes
   from this file. `currentColor` lets each icon inherit its context's
   semantic token, which keeps contrast correct in both themes. */

const PATHS = {
  home: '<path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V20a1 1 0 0 0 1 1h3.5v-6h5v6H18a1 1 0 0 0 1-1V9.5"/>',
  grid: '<rect x="3" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="3" width="7.5" height="7.5" rx="1.5"/><rect x="3" y="13.5" width="7.5" height="7.5" rx="1.5"/><rect x="13.5" y="13.5" width="7.5" height="7.5" rx="1.5"/>',
  cart: '<circle cx="9" cy="20" r="1.4"/><circle cx="18" cy="20" r="1.4"/><path d="M2.5 3h2.2l2.4 12.1a1.5 1.5 0 0 0 1.5 1.2h8.9a1.5 1.5 0 0 0 1.5-1.2L21 7H6"/>',
  chart: '<path d="M3 3v16.5a1.5 1.5 0 0 0 1.5 1.5H21"/><path d="M7.5 15.5V11"/><path d="M12 15.5V7"/><path d="M16.5 15.5v-6"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m20 20-4.9-4.9"/>',
  sun: '<circle cx="12" cy="12" r="4.2"/><path d="M12 2.5v2M12 19.5v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M2.5 12h2M19.5 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4"/>',
  moon: '<path d="M20 14.2A8.2 8.2 0 0 1 9.8 4a8.5 8.5 0 1 0 10.2 10.2Z"/>',
  chevronRight: '<path d="m9 5 7 7-7 7"/>',
  chevronLeft: '<path d="m15 5-7 7 7 7"/>',
  arrowRight: '<path d="M4 12h15"/><path d="m13 6 6 6-6 6"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  minus: '<path d="M5 12h14"/>',
  trash: '<path d="M3.5 6h17"/><path d="M8.5 6V4.5A1.5 1.5 0 0 1 10 3h4a1.5 1.5 0 0 1 1.5 1.5V6"/><path d="M18.5 6v13.5A1.5 1.5 0 0 1 17 21H7a1.5 1.5 0 0 1-1.5-1.5V6"/><path d="M10 10.5v6M14 10.5v6"/>',
  checkCircle: '<circle cx="12" cy="12" r="9"/><path d="m8 12 2.8 2.8L16 9.5"/>',
  alertCircle: '<circle cx="12" cy="12" r="9"/><path d="M12 7.5v5"/><path d="M12 16.2h.01"/>',
  package: '<path d="M12 2.8 3.5 7.4v9.2L12 21.2l8.5-4.6V7.4Z"/><path d="M3.5 7.4 12 12l8.5-4.6"/><path d="M12 12v9.2"/>',
  user: '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/>',
  sparkles: '<path d="m12 3 1.9 4.9L19 9.8l-5.1 1.9L12 16.6l-1.9-4.9L5 9.8l5.1-1.9Z"/><path d="M18.5 15.5 19.4 18l2.5.9-2.5.9-.9 2.5-.9-2.5-2.5-.9 2.5-.9Z"/>',
  tag: '<path d="M3 12.4V4.5A1.5 1.5 0 0 1 4.5 3h7.9a1.5 1.5 0 0 1 1 .4l8.1 8.1a1.5 1.5 0 0 1 0 2.1l-7.9 7.9a1.5 1.5 0 0 1-2.1 0L3.4 13.4a1.5 1.5 0 0 1-.4-1Z"/><circle cx="8" cy="8" r="1.4"/>',
  truck: '<path d="M2.5 6.5A1.5 1.5 0 0 1 4 5h9.5v11H2.5Z"/><path d="M13.5 9H17l4 3.5V16h-7.5Z"/><circle cx="7" cy="18.5" r="1.8"/><circle cx="17.5" cy="18.5" r="1.8"/>',
  shield: '<path d="M12 3 5 5.8v5.5c0 4.3 2.9 8.1 7 9.4 4.1-1.3 7-5.1 7-9.4V5.8Z"/><path d="m9 12 2.2 2.2L15.5 10"/>',
  creditCard: '<rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="M2.5 9.8h19"/><path d="M6.5 14.5h3"/>',
  filter: '<path d="M3 5.5h18"/><path d="M6.5 12h11"/><path d="M10 18.5h4"/>',
  refresh: '<path d="M20.5 11a8.5 8.5 0 0 0-14.6-4.6L3 9"/><path d="M3.5 13a8.5 8.5 0 0 0 14.6 4.6L21 15"/><path d="M3 4.5V9h4.5"/><path d="M21 19.5V15h-4.5"/>',
  activity: '<path d="M3 12h4l2.5-7 4 14 2.5-7h5"/>',
  menu: '<path d="M3.5 6.5h17M3.5 12h17M3.5 17.5h17"/>',
  x: '<path d="m6 6 12 12M18 6 6 18"/>',
  database: '<ellipse cx="12" cy="5.5" rx="8" ry="3"/><path d="M4 5.5v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/><path d="M4 11.5v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"/>',
  layers: '<path d="m12 3 9 4.5-9 4.5-9-4.5Z"/><path d="m3 12.5 9 4.5 9-4.5"/><path d="m3 17 9 4.5 9-4.5"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5.2l3.4 2"/>',
  list: '<path d="M8.5 6.5h12M8.5 12h12M8.5 17.5h12"/><path d="M3.8 6.5h.01M3.8 12h.01M3.8 17.5h.01"/>',
  users: '<circle cx="9.5" cy="8" r="3.6"/><path d="M3 20a6.5 6.5 0 0 1 13 0"/><path d="M16.5 4.6a3.6 3.6 0 0 1 0 6.8"/><path d="M18 20a6.6 6.6 0 0 0-2-4.7"/>',
  gauge: '<path d="M3.5 17a9 9 0 1 1 17 0"/><path d="m12 13 4-3.5"/><circle cx="12" cy="14" r="1.6"/>',
  box: '<path d="M3.5 7.5 12 3l8.5 4.5v9L12 21l-8.5-4.5Z"/><path d="M3.5 7.5 12 12l8.5-4.5"/><path d="M12 12v9"/>',
};

/** Returns an inline SVG string. Decorative by default; pass `label` for
 *  standalone meaning so screen readers announce it. */
export function icon(name, { size = 20, label = null, cls = '' } = {}) {
  const d = PATHS[name];
  if (!d) return '';
  const a11y = label
    ? `role="img" aria-label="${label}"`
    : 'aria-hidden="true" focusable="false"';
  return `<svg ${a11y} class="${cls}" width="${size}" height="${size}" viewBox="0 0 24 24"
    fill="none" stroke="currentColor" stroke-width="1.5"
    stroke-linecap="round" stroke-linejoin="round">${d}</svg>`;
}

export const ICON_NAMES = Object.keys(PATHS);
