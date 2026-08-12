/* Kestrel — storefront + operations console for recsys-lite.
 *
 * Plain ES modules, no build step, no framework. Two route groups share one
 * application shell: SHOP (what a customer sees) and OPERATIONS (what the
 * team running the recommender sees). Keeping them in one shell is the point
 * — every ops number on the right is produced by the shopping on the left.
 */

import { icon } from './icons.js';
import { productArt, categoryArt } from './illustrations.js';
import { mountHero } from './hero3d.js';

/* ========================================================================== */
/* state                                                                      */
/* ========================================================================== */

const state = {
  userId: null,
  categories: [],
  cart: readJSON('kestrel_cart', []),
  recRefreshTimer: null,
  eventPoll: null,
  hero: null,          // WebGL scene owned by the home page; disposed on exit
};

/** Online feature store TTL is 8s; wait just past it before re-querying. */
const FEATURE_TTL_MS = 9000;

function readJSON(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
function saveCart() {
  localStorage.setItem('kestrel_cart', JSON.stringify(state.cart));
  renderSidebar();
}
const cartCount = () => state.cart.reduce((n, l) => n + l.qty, 0);
const cartTotal = () => state.cart.reduce((n, l) => n + l.qty * l.price, 0);

const money = (n) => `$${n.toFixed(2)}`;
const int = (n) => Number(n).toLocaleString('en-US');
const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function timeAgo(ts) {
  const s = Math.max(0, Math.floor(Date.now() / 1000) - ts);
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/* ========================================================================== */
/* api                                                                        */
/* ========================================================================== */

async function api(path, options) {
  const res = await fetch(path, options);
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch { /* no json body */ }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}
const postJSON = (path, body) => api(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

/* ========================================================================== */
/* chrome: toast, theme, nav                                                  */
/* ========================================================================== */

let toastTimer;
function toast(message, kind = 'ok') {
  const el = document.getElementById('toast');
  el.style.borderLeftColor = `var(--${kind})`;
  el.innerHTML = `${icon(kind === 'ok' ? 'checkCircle' : 'alertCircle', { size: 17 })}<span>${esc(message)}</span>`;
  el.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => el.classList.remove('show'), 3800);
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  const btn = document.getElementById('theme-toggle');
  const goingDark = theme === 'light';
  btn.innerHTML = icon(goingDark ? 'moon' : 'sun', { size: 19 });
  btn.setAttribute('aria-label', `Switch to ${goingDark ? 'dark' : 'light'} theme`);
  localStorage.setItem('kestrel_theme', theme);
}

const NAV = [
  {
    title: 'Shop',
    items: [
      { route: 'home', href: '#/', label: 'Storefront', iconName: 'home' },
      { route: 'catalog', href: '#/catalog', label: 'Catalog', iconName: 'grid' },
      { route: 'cart', href: '#/cart', label: 'Cart', iconName: 'cart', badge: cartCount },
    ],
  },
  {
    title: 'Operations',
    items: [
      { route: 'ops', href: '#/ops', label: 'Overview', iconName: 'gauge' },
      { route: 'models', href: '#/ops/models', label: 'Models', iconName: 'layers' },
      { route: 'drift', href: '#/ops/drift', label: 'Data drift', iconName: 'activity' },
      { route: 'events', href: '#/ops/events', label: 'Event stream', iconName: 'list' },
    ],
  },
];

/* Detail pages have no sidebar entry of their own, but the user must never
   lose their place — so they highlight the section they belong to. */
const NAV_PARENT = { product: 'catalog', checkout: 'cart' };

function renderSidebar() {
  const route = parseRoute().name;
  const current = NAV_PARENT[route] ?? route;
  document.getElementById('sidebar-nav').innerHTML = NAV.map((group) => `
    <div class="nav-group">
      <p class="nav-group-title">${group.title}</p>
      ${group.items.map((it) => {
        const n = it.badge ? it.badge() : 0;
        return `<a class="nav-item" href="${it.href}"
                   ${it.route === current ? 'aria-current="page"' : ''}>
                  ${icon(it.iconName, { size: 18 })}
                  <span>${it.label}</span>
                  ${n > 0 ? `<span class="nav-badge">${n}</span>` : ''}
                </a>`;
      }).join('')}
    </div>`).join('');
}

function setNavOpen(open) {
  const app = document.getElementById('app');
  app.classList.toggle('nav-open', open);
  document.getElementById('scrim').hidden = !open;
  const btn = document.getElementById('nav-toggle');
  btn.setAttribute('aria-expanded', String(open));
  btn.setAttribute('aria-label', open ? 'Close navigation' : 'Open navigation');
  btn.innerHTML = icon(open ? 'x' : 'menu', { size: 20 });
}

/* ========================================================================== */
/* shared fragments                                                           */
/* ========================================================================== */

function breadcrumbs(trail) {
  return `<nav class="breadcrumbs" aria-label="Breadcrumb">${
    trail.map((t, i) => i === trail.length - 1
      ? `<span aria-current="page">${esc(t.label)}</span>`
      : `<a href="${t.href}">${esc(t.label)}</a>
         <span class="sep" aria-hidden="true">${icon('chevronRight', { size: 13 })}</span>`
    ).join('')}</nav>`;
}

const skeletonGrid = (n = 8) =>
  `<div class="product-grid">${'<div class="skeleton skeleton-card"></div>'.repeat(n)}</div>`;
const skeletonKpis = (n = 4) =>
  `<div class="kpi-grid">${'<div class="skeleton skeleton-kpi"></div>'.repeat(n)}</div>`;

function emptyState({ title, body, actionHref, actionLabel, iconName = 'box' }) {
  return `<div class="empty-state">
    <span class="empty-icon">${icon(iconName, { size: 24 })}</span>
    <div><h3>${esc(title)}</h3><p style="margin-top:var(--sp-2)">${esc(body)}</p></div>
    ${actionHref ? `<a class="btn btn-primary" href="${actionHref}">${esc(actionLabel)}</a>` : ''}
  </div>`;
}

function errorState(err, retry) {
  const id = `r${Math.random().toString(36).slice(2, 8)}`;
  if (retry) queueMicrotask(() => document.getElementById(id)?.addEventListener('click', retry));
  return `<div class="alert alert-err" role="alert">
    ${icon('alertCircle', { size: 18 })}
    <div>
      <strong>Could not load this.</strong>
      <p style="margin-top:var(--sp-1)">${esc(err.message)}</p>
      ${retry ? `<button id="${id}" class="btn btn-secondary btn-sm" style="margin-top:var(--sp-3)">Retry</button>` : ''}
    </div>
  </div>`;
}

function kpi({ label, value, note, iconName, tone }) {
  return `<div class="kpi">
    <p class="kpi-label">${iconName ? icon(iconName, { size: 13 }) : ''}${esc(label)}</p>
    <p class="kpi-value"${tone ? ` style="color:var(--${tone})"` : ''}>${value}</p>
    ${note ? `<p class="kpi-note">${note}</p>` : ''}
  </div>`;
}

function productCard(p, { score = null, ribbon = null } = {}) {
  return `<article class="product-card">
    ${ribbon ? `<span class="card-ribbon">${ribbon}</span>` : ''}
    <a class="product-media" href="#/product/${p.item_id}" tabindex="-1" aria-hidden="true">
      ${productArt(p.item_id, p.title)}
    </a>
    <div class="product-body">
      <h3 class="product-title"><a href="#/product/${p.item_id}">${esc(p.title)}</a></h3>
      <p class="product-meta"><span>Cat ${p.category_id}</span><span>·</span><span>Brand ${p.brand_id}</span></p>
      ${score !== null ? `
        <div>
          <div class="score-bar" role="img"
               aria-label="Match score ${score.toFixed(3)} out of 1">
            <i style="width:${Math.max(2, Math.min(100, score * 100)).toFixed(1)}%"></i>
          </div>
          <p class="product-meta" style="margin-top:4px">match ${score.toFixed(3)}</p>
        </div>` : ''}
      <p class="product-price">${money(p.price)}</p>
      <div class="product-actions">
        <button class="btn btn-primary btn-sm" data-add="${p.item_id}">Add to cart</button>
        <a class="btn btn-secondary btn-sm" href="#/product/${p.item_id}">Details</a>
      </div>
    </div>
  </article>`;
}

function wireAddButtons(root) {
  root.querySelectorAll('[data-add]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      try {
        const p = await api(`/api/products/${Number(btn.dataset.add)}`);
        addToCart(p, 1);
        await postJSON('/api/events', { user_id: state.userId, item_id: p.item_id, event_type: 'cart' });
        toast(`${p.title} added to cart.`);
        scheduleRecRefresh();
      } catch (err) {
        toast(err.message, 'err');
      } finally {
        btn.disabled = false;
      }
    });
  });
}

function addToCart(product, qty) {
  const line = state.cart.find((l) => l.item_id === product.item_id);
  if (line) line.qty += qty;
  else state.cart.push({ item_id: product.item_id, title: product.title, price: product.price, qty });
  saveCart();
}

function scheduleRecRefresh() {
  clearTimeout(state.recRefreshTimer);
  state.recRefreshTimer = setTimeout(() => {
    if (parseRoute().name === 'home') router();
  }, FEATURE_TTL_MS);
}

/* ========================================================================== */
/* SHOP pages                                                                 */
/* ========================================================================== */

async function pageHome(view) {
  view.innerHTML = `
    <section class="hero">
      <canvas class="hero-canvas" id="hero-canvas" aria-hidden="true"></canvas>
      <div class="hero-glow" aria-hidden="true"></div>
      <h1>A storefront wired to a live recommender</h1>
      <p>Browse, add to cart, check out. Every action is written to the event log,
         turned into point-in-time features and scored by a sequence ranking model.
         Watch it happen under Operations.</p>
      <div class="hero-actions">
        <a class="btn btn-primary btn-lg" href="#/catalog">Browse catalog ${icon('arrowRight', { size: 17 })}</a>
        <a class="btn btn-secondary btn-lg" href="#/ops">Operations console</a>
      </div>
      <div class="hero-stats" id="hero-stats"></div>
    </section>

    <section class="section" aria-labelledby="recs-h">
      <div class="section-head">
        <div><h2 id="recs-h">Recommended for you</h2><p class="sub" id="recs-sub">Loading…</p></div>
        <a class="btn btn-ghost btn-sm" href="#/catalog">All products ${icon('chevronRight', { size: 13 })}</a>
      </div>
      <div id="recs">${skeletonGrid(5)}</div>
    </section>

    <section class="section" aria-labelledby="cats-h">
      <div class="section-head"><div><h2 id="cats-h">Categories</h2></div></div>
      <div id="cats" class="category-grid"></div>
    </section>`;

  state.hero = mountHero(document.getElementById('hero-canvas'));

  api('/api/stats').then((s) => {
    document.getElementById('hero-stats').innerHTML = [
      ['Products', int(s.n_products)], ['Shoppers', int(s.n_users)],
      ['Events logged', int(s.n_events)], ['Model', s.champion_version ?? '—'],
    ].map(([k, v]) => `<div class="hero-stat"><div class="v">${v}</div><div class="k">${k}</div></div>`).join('');
  }).catch(() => { /* hero stats are decorative; the page works without them */ });

  const recBox = document.getElementById('recs');
  try {
    const [resp, profile] = await Promise.all([
      api(`/api/recommend/${state.userId}?k=10`),
      api(`/api/users/${state.userId}/profile`),
    ]);
    document.getElementById('recs-sub').innerHTML = profile.is_cold_start
      ? `New shopper — showing store favourites. <span class="chip">${icon('activity', { size: 11 })} ${esc(resp.ab_variant)} · ${esc(resp.model_version)}</span>`
      : `From ${profile.n_events} interactions${profile.preferred_categories.length
          ? `, mostly category ${profile.preferred_categories.join(', ')}` : ''}.
         <span class="chip">${icon('activity', { size: 11 })} ${esc(resp.ab_variant)} · ${esc(resp.model_version)}</span>`;

    recBox.innerHTML = resp.items.length
      ? `<div class="product-grid">${resp.items.map((it) => productCard(it, {
          score: it.score,
          ribbon: profile.is_cold_start ? '<span class="badge badge-warn">Popular</span>' : null,
        })).join('')}</div>`
      : emptyState({ title: 'No recommendations yet', body: 'Browse a few products first.',
                     actionHref: '#/catalog', actionLabel: 'Browse catalog' });
    wireAddButtons(recBox);
  } catch (err) {
    recBox.innerHTML = errorState(err, router);
  }

  try {
    if (!state.categories.length) state.categories = await api('/api/categories');
    document.getElementById('cats').innerHTML = state.categories.slice(0, 12).map((c) => `
      <a class="category-tile" href="#/catalog?category=${c.category_id}">
        <span aria-hidden="true">${categoryArt(c.category_id)}</span>
        <span><span class="tile-name">Category ${c.category_id}</span>
              <span class="tile-count">${c.n_items} items</span></span>
      </a>`).join('');
  } catch (err) {
    document.getElementById('cats').innerHTML = errorState(err);
  }
}

async function pageCatalog(view, params) {
  view.innerHTML = `
    ${breadcrumbs([{ label: 'Storefront', href: '#/' }, { label: 'Catalog' }])}
    <div class="page-head"><div><h1>Catalog</h1>
      <p class="lede">Every product in the demo store. Filter, search and sort — all client side over one fetch.</p>
    </div></div>
    <div class="toolbar">
      <div class="search-field">
        <span class="search-icon" aria-hidden="true">${icon('search', { size: 17 })}</span>
        <label class="sr-only" for="q">Search products by name</label>
        <input id="q" type="search" placeholder="Search products…" autocomplete="off" />
      </div>
      <label class="sr-only" for="cat">Filter by category</label>
      <select id="cat"><option value="">All categories</option></select>
      <label class="sr-only" for="sort">Sort products</label>
      <select id="sort">
        <option value="featured">Sort: featured</option>
        <option value="price-asc">Price: low to high</option>
        <option value="price-desc">Price: high to low</option>
        <option value="name">Name A–Z</option>
      </select>
      <span class="chip" id="count" aria-live="polite"></span>
    </div>
    <div id="grid">${skeletonGrid(10)}</div>`;

  if (!state.categories.length) {
    try { state.categories = await api('/api/categories'); } catch { /* filter degrades gracefully */ }
  }
  const catSel = document.getElementById('cat');
  state.categories.forEach((c) => catSel.add(new Option(`Category ${c.category_id} (${c.n_items})`, c.category_id)));
  catSel.value = params.get('category') || '';

  let items = [];
  const grid = document.getElementById('grid');

  const render = () => {
    const q = document.getElementById('q').value.trim().toLowerCase();
    const sort = document.getElementById('sort').value;
    let list = q ? items.filter((p) => p.title.toLowerCase().includes(q)) : items.slice();
    if (sort === 'price-asc') list.sort((a, b) => a.price - b.price);
    else if (sort === 'price-desc') list.sort((a, b) => b.price - a.price);
    else if (sort === 'name') list.sort((a, b) => a.title.localeCompare(b.title));

    document.getElementById('count').textContent = `${list.length} product${list.length === 1 ? '' : 's'}`;
    grid.innerHTML = list.length
      ? `<div class="product-grid">${list.map((p) => productCard(p)).join('')}</div>`
      : emptyState({ title: 'No matches', body: 'Try another search term or clear the category filter.', iconName: 'search' });
    wireAddButtons(grid);
  };

  const load = async () => {
    grid.innerHTML = skeletonGrid(10);
    const c = catSel.value;
    try {
      items = await api(c ? `/api/catalog?limit=200&category_id=${c}` : '/api/catalog?limit=120');
      render();
    } catch (err) { grid.innerHTML = errorState(err, load); }
  };

  document.getElementById('q').addEventListener('input', render);
  document.getElementById('sort').addEventListener('change', render);
  catSel.addEventListener('change', () => {
    const v = catSel.value;
    history.replaceState(null, '', v ? `#/catalog?category=${v}` : '#/catalog');
    load();
  });
  await load();
}

async function pageProduct(view, itemId) {
  view.innerHTML = '<div class="skeleton skeleton-panel" style="height:340px"></div>';
  let p;
  try {
    p = await api(`/api/products/${itemId}`);
  } catch {
    view.innerHTML = breadcrumbs([{ label: 'Storefront', href: '#/' }, { label: 'Catalog', href: '#/catalog' }, { label: 'Not found' }])
      + emptyState({ title: 'Product not found', body: `No product with id ${itemId}.`,
                     actionHref: '#/catalog', actionLabel: 'Back to catalog', iconName: 'alertCircle' });
    return;
  }

  postJSON('/api/events', { user_id: state.userId, item_id: p.item_id, event_type: 'view' })
    .catch(() => { /* a dropped view event must never break the page */ });

  view.innerHTML = `
    ${breadcrumbs([
      { label: 'Storefront', href: '#/' }, { label: 'Catalog', href: '#/catalog' },
      { label: `Category ${p.category_id}`, href: `#/catalog?category=${p.category_id}` },
      { label: p.title },
    ])}
    <div class="pdp">
      <div class="pdp-media">${productArt(p.item_id, p.title)}</div>
      <div class="pdp-info">
        <div>
          <span class="badge badge-info">${icon('tag', { size: 11 })} Category ${p.category_id}</span>
          <h1 style="margin-top:var(--sp-3);font-size:var(--fs-3xl)">${esc(p.title)}</h1>
        </div>
        <p class="pdp-price">${money(p.price)}</p>
        <p style="color:var(--text-muted)">A synthetic catalog entry. Adding it to your cart
           writes a real event that changes what the model recommends next.</p>
        <dl class="spec-list">
          <dt>Product ID</dt><dd class="mono">#${p.item_id}</dd>
          <dt>Category</dt><dd>${p.category_id}</dd>
          <dt>Brand</dt><dd>${p.brand_id}</dd>
          <dt>Price</dt><dd>${money(p.price)}</dd>
        </dl>
        <div style="display:flex;gap:var(--sp-3);flex-wrap:wrap">
          <div class="qty">
            <button type="button" id="dec" aria-label="Decrease quantity">${icon('minus', { size: 17 })}</button>
            <output id="qty" aria-live="polite" aria-label="Quantity">1</output>
            <button type="button" id="inc" aria-label="Increase quantity">${icon('plus', { size: 17 })}</button>
          </div>
          <button class="btn btn-primary btn-lg" id="add" style="flex:1">
            ${icon('cart', { size: 17 })} Add to cart
          </button>
        </div>
        <div style="display:flex;gap:var(--sp-4);flex-wrap:wrap;color:var(--text-subtle);font-size:var(--fs-xs)">
          <span style="display:flex;align-items:center;gap:6px">${icon('truck', { size: 15 })} Simulated delivery</span>
          <span style="display:flex;align-items:center;gap:6px">${icon('shield', { size: 15 })} No real payment</span>
        </div>
      </div>
    </div>

    <section class="section" style="margin-top:var(--sp-12)" aria-labelledby="sim-h">
      <div class="section-head"><div>
        <h2 id="sim-h">Similar products</h2>
        <p class="sub">Same category, closest price — a content-based neighbour, not a model call.</p>
      </div></div>
      <div id="sim">${skeletonGrid(4)}</div>
    </section>`;

  let qty = 1;
  const out = document.getElementById('qty');
  document.getElementById('dec').addEventListener('click', () => { qty = Math.max(1, qty - 1); out.textContent = qty; });
  document.getElementById('inc').addEventListener('click', () => { qty = Math.min(99, qty + 1); out.textContent = qty; });

  const addBtn = document.getElementById('add');
  addBtn.addEventListener('click', async () => {
    addBtn.disabled = true;
    try {
      addToCart(p, qty);
      await postJSON('/api/events', { user_id: state.userId, item_id: p.item_id, event_type: 'cart' });
      toast(`${qty} × ${p.title} added to cart.`);
      scheduleRecRefresh();
    } catch (err) { toast(err.message, 'err'); }
    finally { addBtn.disabled = false; }
  });

  const sim = document.getElementById('sim');
  try {
    const items = await api(`/api/similar/${p.item_id}?k=4`);
    sim.innerHTML = items.length
      ? `<div class="product-grid">${items.map((s) => productCard(s)).join('')}</div>`
      : emptyState({ title: 'Nothing similar', body: 'This is the only product in its category.' });
    wireAddButtons(sim);
  } catch (err) { sim.innerHTML = errorState(err); }
}

function pageCart(view) {
  const render = () => {
    view.innerHTML = `
      ${breadcrumbs([{ label: 'Storefront', href: '#/' }, { label: 'Cart' }])}
      <div class="page-head"><div><h1>Cart</h1></div></div>
      ${state.cart.length === 0
        ? emptyState({ title: 'Your cart is empty', body: 'Add products and they appear here.',
                       actionHref: '#/catalog', actionLabel: 'Browse catalog', iconName: 'cart' })
        : `<div class="split">
             <div class="panel panel-flush">
               ${state.cart.map((l) => `
                 <div class="cart-line">
                   <div class="cart-line-media">${productArt(l.item_id, l.title)}</div>
                   <div>
                     <p style="font-weight:600"><a href="#/product/${l.item_id}">${esc(l.title)}</a></p>
                     <p class="product-meta" style="margin-top:2px">${money(l.price)} each</p>
                     <div style="display:flex;gap:var(--sp-2);margin-top:var(--sp-3)">
                       <div class="qty">
                         <button type="button" data-dec="${l.item_id}" aria-label="Decrease quantity of ${esc(l.title)}">${icon('minus', { size: 15 })}</button>
                         <output aria-label="Quantity of ${esc(l.title)}">${l.qty}</output>
                         <button type="button" data-inc="${l.item_id}" aria-label="Increase quantity of ${esc(l.title)}">${icon('plus', { size: 15 })}</button>
                       </div>
                       <button class="icon-btn" data-del="${l.item_id}" aria-label="Remove ${esc(l.title)} from cart">${icon('trash', { size: 17 })}</button>
                     </div>
                   </div>
                   <p class="cart-line-price">${money(l.price * l.qty)}</p>
                 </div>`).join('')}
             </div>
             <aside class="panel summary" aria-label="Order summary">
               <h2 style="margin-bottom:var(--sp-3)">Summary</h2>
               <div class="summary-row"><span>Items</span><span>${cartCount()}</span></div>
               <div class="summary-row"><span>Subtotal</span><span>${money(cartTotal())}</span></div>
               <div class="summary-row"><span>Shipping</span><span>Free</span></div>
               <div class="summary-row total"><span>Total</span><span>${money(cartTotal())}</span></div>
               <a class="btn btn-primary btn-block btn-lg" href="#/checkout" style="margin-top:var(--sp-4)">
                 Checkout ${icon('arrowRight', { size: 17 })}</a>
               <a class="btn btn-ghost btn-block btn-sm" href="#/catalog" style="margin-top:var(--sp-2)">Continue shopping</a>
             </aside>
           </div>`}`;

    const upd = (sel, fn) => view.querySelectorAll(sel).forEach((b) => b.addEventListener('click', () => { fn(b); saveCart(); render(); }));
    upd('[data-inc]', (b) => { state.cart.find((l) => l.item_id === +b.dataset.inc).qty += 1; });
    upd('[data-dec]', (b) => {
      const l = state.cart.find((x) => x.item_id === +b.dataset.dec);
      l.qty -= 1;
      if (l.qty <= 0) state.cart = state.cart.filter((x) => x !== l);
    });
    upd('[data-del]', (b) => { state.cart = state.cart.filter((l) => l.item_id !== +b.dataset.del); });
  };
  render();
}

function pageCheckout(view) {
  if (!state.cart.length) {
    view.innerHTML = breadcrumbs([{ label: 'Storefront', href: '#/' }, { label: 'Cart', href: '#/cart' }, { label: 'Checkout' }])
      + emptyState({ title: 'Nothing to check out', body: 'Your cart is empty.',
                     actionHref: '#/catalog', actionLabel: 'Browse catalog', iconName: 'cart' });
    return;
  }

  const step = (n, label, cls) => `<span class="step ${cls}"${cls === 'active' ? ' aria-current="step"' : ''}>
    <span class="step-num">${cls === 'done' ? icon('checkCircle', { size: 13 }) : n}</span> ${label}</span>`;

  view.innerHTML = `
    ${breadcrumbs([{ label: 'Storefront', href: '#/' }, { label: 'Cart', href: '#/cart' }, { label: 'Checkout' }])}
    <div class="stepper" aria-label="Checkout progress">
      ${step(1, 'Cart', 'done')}<span class="step-line" aria-hidden="true"></span>
      ${step(2, 'Details', 'active')}<span class="step-line" aria-hidden="true"></span>
      ${step(3, 'Confirmation', '')}
    </div>
    <div class="page-head"><div><h1>Checkout</h1></div></div>
    <div class="alert alert-info" style="margin-bottom:var(--sp-5)">
      ${icon('shield', { size: 18 })}
      <div><strong>Demo only.</strong> No payment is taken and nothing ships. Submitting records
      <em>purchase</em> events that feed the recommendation model.</div>
    </div>
    <div class="split">
      <form class="panel" id="form" novalidate>
        <h2 style="margin-bottom:var(--sp-4)">Delivery details</h2>
        <div class="form-grid">
          ${[['name', 'Full name', 'text', 'name'], ['email', 'Email', 'email', 'email']]
            .map(([id, label, type, ac]) => `
            <div class="field">
              <label for="${id}">${label}</label>
              <input id="${id}" type="${type}" autocomplete="${ac}" required />
              <span class="err">${icon('alertCircle', { size: 12 })} Please enter a valid ${label.toLowerCase()}.</span>
            </div>`).join('')}
          <div class="field full">
            <label for="address">Address</label>
            <input id="address" type="text" autocomplete="street-address" required />
            <span class="err">${icon('alertCircle', { size: 12 })} Please enter an address.</span>
          </div>
          <div class="field">
            <label for="city">City</label>
            <input id="city" type="text" autocomplete="address-level2" required />
            <span class="err">${icon('alertCircle', { size: 12 })} Please enter a city.</span>
          </div>
          <div class="field">
            <label for="zip">Postcode</label>
            <input id="zip" type="text" autocomplete="postal-code" required />
            <span class="err">${icon('alertCircle', { size: 12 })} Please enter a postcode.</span>
          </div>
        </div>
        <div id="form-error" style="margin-top:var(--sp-4)"></div>
      </form>
      <aside class="panel summary" aria-label="Order summary">
        <h2 style="margin-bottom:var(--sp-3)">Order</h2>
        ${state.cart.map((l) => `<div class="summary-row"><span>${l.qty} × ${esc(l.title)}</span><span>${money(l.price * l.qty)}</span></div>`).join('')}
        <div class="summary-row total"><span>Total</span><span>${money(cartTotal())}</span></div>
        <button class="btn btn-primary btn-block btn-lg" id="place" form="form" style="margin-top:var(--sp-4)">
          ${icon('creditCard', { size: 17 })} Place order</button>
      </aside>
    </div>`;

  const form = document.getElementById('form');
  const btn = document.getElementById('place');

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    let firstBad = null;
    form.querySelectorAll('input[required]').forEach((inp) => {
      const bad = !inp.value.trim() || !inp.checkValidity();
      inp.closest('.field').classList.toggle('invalid', bad);
      inp.setAttribute('aria-invalid', String(bad));
      if (bad && !firstBad) firstBad = inp;
    });
    if (firstBad) { firstBad.focus(); return; }

    btn.disabled = true;
    btn.innerHTML = `${icon('refresh', { size: 17 })} Placing order…`;
    try {
      const events = state.cart.map((l) => ({ user_id: state.userId, item_id: l.item_id, event_type: 'purchase' }));
      const res = await postJSON('/api/events/batch', { events });
      const total = cartTotal(); const count = cartCount();
      state.cart = []; saveCart();
      showConfirmation(view, { total, count, nEvents: res.n_events, step });
    } catch (err) {
      document.getElementById('form-error')?.replaceChildren();
      const box = document.getElementById('form-error');
      if (box) box.innerHTML = errorState(err);
      btn.disabled = false;
      btn.innerHTML = `${icon('creditCard', { size: 17 })} Place order`;
    }
  });
}

function showConfirmation(view, { total, count, nEvents, step }) {
  const ref = `KS-${Date.now().toString().slice(-8)}`;
  view.innerHTML = `
    ${breadcrumbs([{ label: 'Storefront', href: '#/' }, { label: 'Cart', href: '#/cart' }, { label: 'Confirmation' }])}
    <div class="stepper" aria-label="Checkout progress">
      ${step(1, 'Cart', 'done')}<span class="step-line" aria-hidden="true"></span>
      ${step(2, 'Details', 'done')}<span class="step-line" aria-hidden="true"></span>
      ${step(3, 'Confirmation', 'active')}
    </div>
    <div class="panel" style="text-align:center;padding:var(--sp-12) var(--sp-6)">
      <span class="empty-icon" style="margin:0 auto var(--sp-4);width:56px;height:56px;background:var(--ok-soft);color:var(--ok)">
        ${icon('checkCircle', { size: 28 })}</span>
      <h1 style="font-size:var(--fs-2xl)">Order confirmed</h1>
      <p style="color:var(--text-muted);margin-top:var(--sp-2)">
        <span class="mono">${ref}</span> — ${count} item${count === 1 ? '' : 's'}, ${money(total)}.
        Nothing was charged and nothing ships.</p>
      <div class="alert alert-ok" style="max-width:58ch;margin:var(--sp-6) auto 0;text-align:left">
        ${icon('activity', { size: 18 })}
        <div><strong>${nEvents} purchase event${nEvents === 1 ? '' : 's'} written to the log.</strong>
          <p style="margin-top:var(--sp-1)">They are now part of shopper ${state.userId}'s history.
          Check the <a href="#/ops/events">event stream</a>, then reload the storefront in a few
          seconds to see the recommendations move.</p></div>
      </div>
      <div style="display:flex;gap:var(--sp-3);justify-content:center;margin-top:var(--sp-6);flex-wrap:wrap">
        <a class="btn btn-primary" href="#/">Back to storefront</a>
        <a class="btn btn-secondary" href="#/ops/events">View event stream</a>
      </div>
    </div>`;
}

/* ========================================================================== */
/* OPERATIONS pages                                                           */
/* ========================================================================== */

async function pageOps(view) {
  view.innerHTML = `
    ${breadcrumbs([{ label: 'Operations' }, { label: 'Overview' }])}
    <div class="page-head"><div>
      <h1>Operations overview</h1>
      <p class="lede">Live state of the recommendation platform behind this storefront —
         catalog size, event volume, and the model currently serving traffic.</p>
    </div></div>
    <div id="kpis">${skeletonKpis(6)}</div>
    <div class="split">
      <section class="section" aria-labelledby="pipe-h">
        <div class="section-head"><div><h2 id="pipe-h">Pipeline</h2>
          <p class="sub">How a click becomes a recommendation.</p></div></div>
        <div class="panel">
          <ol style="margin:0;padding-left:var(--sp-5);display:flex;flex-direction:column;gap:var(--sp-3);color:var(--text-muted)">
            <li><strong style="color:var(--text)">Capture</strong> — storefront actions POST to
                <code class="mono">/api/events</code>, appended to the SQLite event log.</li>
            <li><strong style="color:var(--text)">Online features</strong> — an in-memory store
                rebuilds each shopper's sequence and candidate pool on an 8s TTL.</li>
            <li><strong style="color:var(--text)">Scoring</strong> — the champion (or A/B candidate)
                model scores the candidate pool and returns Top-K.</li>
            <li><strong style="color:var(--text)">Offline</strong> — <code class="mono">features.py</code>
                rebuilds point-in-time training rows; <code class="mono">train.py</code> retrains
                and auto-promotes on validation NDCG@5.</li>
          </ol>
        </div>
      </section>
      <section class="section" aria-labelledby="act-h">
        <div class="section-head"><div><h2 id="act-h">Latest activity</h2></div></div>
        <div class="panel panel-flush" id="mini-feed"><div class="skeleton skeleton-panel"></div></div>
      </section>
    </div>`;

  try {
    const s = await api('/api/stats');
    const byType = s.events_by_type || {};
    document.getElementById('kpis').innerHTML = `<div class="kpi-grid">
      ${kpi({ label: 'Products', value: int(s.n_products), note: `${s.n_categories} categories`, iconName: 'box' })}
      ${kpi({ label: 'Shoppers', value: int(s.n_users), iconName: 'users' })}
      ${kpi({ label: 'Events logged', value: int(s.n_events), note: `${int(s.events_last_24h)} in last 24h`, iconName: 'database' })}
      ${kpi({ label: 'Views', value: int(byType.view || 0), iconName: 'search' })}
      ${kpi({ label: 'Carts', value: int(byType.cart || 0), iconName: 'cart' })}
      ${kpi({ label: 'Purchases', value: int(byType.purchase || 0), tone: 'ok', iconName: 'checkCircle' })}
    </div>
    <div class="kpi-grid" style="margin-bottom:var(--sp-8)">
      ${kpi({ label: 'Champion model', value: esc(s.champion_version ?? '—'),
              note: s.champion_test_auc != null ? `test AUC ${s.champion_test_auc.toFixed(4)}` : '', iconName: 'layers' })}
      ${kpi({ label: 'Registered versions', value: int(s.n_model_versions), iconName: 'layers' })}
    </div>`;
  } catch (err) {
    document.getElementById('kpis').innerHTML = errorState(err, () => router());
  }

  try {
    const events = await api('/api/events/recent?limit=8');
    document.getElementById('mini-feed').innerHTML = renderEventTable(events, { compact: true });
  } catch (err) {
    document.getElementById('mini-feed').innerHTML = errorState(err);
  }
}

async function pageModels(view) {
  view.innerHTML = `
    ${breadcrumbs([{ label: 'Operations' }, { label: 'Models' }])}
    <div class="page-head"><div>
      <h1>Model registry</h1>
      <p class="lede">Every trained version the API can route traffic to. Metrics come from that
         version's real training run — nothing here is hardcoded.</p>
    </div></div>
    <div id="models" class="model-grid">
      <div class="skeleton skeleton-panel"></div><div class="skeleton skeleton-panel"></div>
    </div>
    <section class="section" style="margin-top:var(--sp-8)">
      <div class="panel">
        <h2 style="margin-bottom:var(--sp-2)">A/B routing</h2>
        <p style="color:var(--text-muted)">
          Set <code class="mono">RECSYS_LITE_AB_CANDIDATE_WEIGHT</code> (0–100) before starting the
          server to route that share of shoppers to the newest non-champion version. Assignment is a
          stable hash of the shopper id, so a given shopper always sees the same variant. The
          storefront shows which one served each response.
        </p>
      </div>
    </section>`;

  try {
    const versions = await api('/api/models');
    document.getElementById('models').innerHTML = versions.length ? versions.map((v) => {
      const hist = v.epoch_history.map((h) => h['ndcg@5']).filter((x) => x != null);
      return `<article class="model-card ${v.is_champion ? 'is-champion' : ''}">
        <div style="display:flex;justify-content:space-between;align-items:center">
          <h3 class="mono" style="font-size:var(--fs-lg)">${esc(v.version)}</h3>
          <span class="badge ${v.is_champion ? 'badge-ok' : 'badge-neutral'}">
            <span class="dot ${v.is_champion ? 'dot-ok' : 'dot-info'}"></span>
            ${v.is_champion ? 'champion' : 'candidate'}</span>
        </div>
        <dl class="model-metrics">
          <dt>val NDCG@5</dt><dd>${v.val_ndcg?.toFixed(4) ?? '—'}</dd>
          <dt>test AUC</dt><dd>${v.test_auc?.toFixed(4) ?? '—'}</dd>
          <dt>test NDCG@5</dt><dd>${v.test_ndcg?.toFixed(4) ?? '—'}</dd>
          <dt>epochs</dt><dd>${v.epoch_history.length}</dd>
        </dl>
        ${sparkline(hist)}
        <p class="kpi-note" style="margin-top:var(--sp-2)">Validation NDCG@5 per epoch</p>
      </article>`;
    }).join('') : emptyState({ title: 'No models registered', body: 'Run python -m recsys_lite.train first.', iconName: 'layers' });
  } catch (err) {
    document.getElementById('models').innerHTML = errorState(err, () => router());
  }
}

async function pageDrift(view) {
  view.innerHTML = `
    ${breadcrumbs([{ label: 'Operations' }, { label: 'Data drift' }])}
    <div class="page-head">
      <div><h1>Data drift</h1>
        <p class="lede">Population Stability Index between a recent and a baseline window of raw
           events. PSI &lt; 0.1 stable · 0.1–0.25 moderate · ≥ 0.25 significant.</p></div>
      <div class="toolbar" style="margin:0">
        <label class="sr-only" for="dr">Recent window, days</label>
        <input id="dr" type="number" value="3" min="1" max="30" style="width:80px" />
        <label class="sr-only" for="db">Baseline window, days</label>
        <input id="db" type="number" value="7" min="1" max="60" style="width:80px" />
        <button class="btn btn-secondary btn-sm" id="recompute">${icon('refresh', { size: 15 })} Recompute</button>
      </div>
    </div>
    <div id="drift"><div class="skeleton skeleton-panel"></div></div>`;

  const load = async () => {
    const box = document.getElementById('drift');
    box.innerHTML = '<div class="skeleton skeleton-panel"></div>';
    try {
      const r = document.getElementById('dr').value || 3;
      const b = document.getElementById('db').value || 7;
      const d = await api(`/api/drift?recent_days=${r}&baseline_days=${b}`);
      const tone = { stable: 'ok', moderate: 'warn', significant: 'err', insufficient_data: 'neutral' };
      box.innerHTML = `
        ${d.note ? `<div class="alert alert-warn" style="margin-bottom:var(--sp-4)">${icon('alertCircle', { size: 18 })}<div>${esc(d.note)}</div></div>` : ''}
        <div class="panel panel-flush"><div class="table-wrap">
          <table class="data-table">
            <caption class="sr-only">Population Stability Index per feature</caption>
            <thead><tr><th scope="col">Feature</th><th scope="col" class="num">PSI</th><th scope="col">Status</th></tr></thead>
            <tbody>${d.features.map((f) => `<tr>
              <td class="mono">${esc(f.feature)}</td>
              <td class="num">${f.psi === null ? '—' : f.psi.toFixed(4)}</td>
              <td><span class="badge badge-${tone[f.severity] || 'neutral'}">
                <span class="dot dot-${tone[f.severity] || 'info'}"></span>${esc(f.severity.replace('_', ' '))}</span></td>
            </tr>`).join('')}</tbody>
          </table>
        </div></div>
        <p class="kpi-note" style="margin-top:var(--sp-3)">
          ${int(d.n_recent_events)} recent events (${d.recent_days}d) vs ${int(d.n_baseline_events)}
          baseline events (${d.baseline_days}d before that).</p>`;
    } catch (err) { box.innerHTML = errorState(err, load); }
  };
  document.getElementById('recompute').addEventListener('click', load);
  await load();
}

function renderEventTable(events, { compact = false } = {}) {
  if (!events.length) {
    return emptyState({ title: 'No events yet', body: 'Interact with the storefront to generate some.', iconName: 'list' });
  }
  const tone = { view: 'neutral', cart: 'info', purchase: 'ok' };
  // The compact feed lives in a 330px column, so it drops the id and shopper
  // columns rather than overflowing into a scrollbar nobody will find.
  return `<div class="table-wrap"><table class="data-table${compact ? ' compact' : ''}">
    <caption class="sr-only">Most recent events</caption>
    <thead><tr>
      ${compact ? '' : '<th scope="col" class="num">ID</th>'}
      <th scope="col">When</th>
      ${compact ? '' : '<th scope="col">Shopper</th>'}
      <th scope="col">Action</th><th scope="col">Product</th>
    </tr></thead>
    <tbody>${events.map((e) => `<tr>
      ${compact ? '' : `<td class="num mono">${e.event_id}</td>`}
      <td style="color:var(--text-muted)">${timeAgo(e.ts)}</td>
      ${compact ? '' : `<td class="mono">${e.user_id}</td>`}
      <td><span class="badge badge-${tone[e.event_type] || 'neutral'}">${esc(e.event_type)}</span></td>
      <td><a class="cell-title" href="#/product/${e.item_id}" title="${esc(e.item_title)}">${esc(e.item_title)}</a></td>
    </tr>`).join('')}</tbody>
  </table></div>`;
}

async function pageEvents(view) {
  view.innerHTML = `
    ${breadcrumbs([{ label: 'Operations' }, { label: 'Event stream' }])}
    <div class="page-head">
      <div><h1>Event stream</h1>
        <p class="lede">The raw log every feature in this system is derived from. Shopping in
           another tab appends to it live.</p></div>
      <div class="toolbar" style="margin:0">
        <label class="sr-only" for="limit">Rows</label>
        <select id="limit">
          <option value="25">25 rows</option><option value="50">50 rows</option><option value="100">100 rows</option>
        </select>
        <button class="btn btn-secondary btn-sm" id="refresh">${icon('refresh', { size: 15 })} Refresh</button>
        <label class="chip" style="cursor:pointer">
          <input type="checkbox" id="auto" style="min-height:auto;margin-right:6px" /> Auto-refresh
        </label>
      </div>
    </div>
    <div class="panel panel-flush" id="feed"><div class="skeleton skeleton-panel"></div></div>`;

  const load = async () => {
    const box = document.getElementById('feed');
    try {
      const limit = document.getElementById('limit').value;
      box.innerHTML = renderEventTable(await api(`/api/events/recent?limit=${limit}`));
    } catch (err) { box.innerHTML = errorState(err, load); }
  };

  document.getElementById('refresh').addEventListener('click', load);
  document.getElementById('limit').addEventListener('change', load);
  document.getElementById('auto').addEventListener('change', (e) => {
    clearInterval(state.eventPoll);
    // Poll only while this page is mounted; the router clears it on exit.
    if (e.target.checked) state.eventPoll = setInterval(load, 5000);
  });
  await load();
}

function sparkline(values, { w = 260, h = 56 } = {}) {
  if (values.length < 2) return '<div class="spark"></div>';
  const min = Math.min(...values), max = Math.max(...values), span = max - min || 1;
  const step = w / (values.length - 1);
  const pts = values.map((v, i) => `${(i * step).toFixed(1)},${(h - ((v - min) / span) * (h - 8) - 4).toFixed(1)}`);
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${pts.join(' ')}" fill="none" stroke="var(--accent)" stroke-width="2"
      stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

/* ========================================================================== */
/* router                                                                     */
/* ========================================================================== */

const PAGES = {
  home:     { title: 'Storefront',        render: pageHome },
  catalog:  { title: 'Catalog',           render: pageCatalog },
  product:  { title: 'Product',           render: pageProduct },
  cart:     { title: 'Cart',              render: pageCart },
  checkout: { title: 'Checkout',          render: pageCheckout },
  ops:      { title: 'Operations',        render: pageOps },
  models:   { title: 'Model registry',    render: pageModels },
  drift:    { title: 'Data drift',        render: pageDrift },
  events:   { title: 'Event stream',      render: pageEvents },
};

function parseRoute() {
  const [path, query] = (location.hash.replace(/^#/, '') || '/').split('?');
  const parts = path.split('/').filter(Boolean);
  const params = new URLSearchParams(query || '');
  if (!parts.length) return { name: 'home', params };
  if (parts[0] === 'ops') {
    const sub = parts[1];
    if (sub === 'models') return { name: 'models', params };
    if (sub === 'drift') return { name: 'drift', params };
    if (sub === 'events') return { name: 'events', params };
    return { name: 'ops', params };
  }
  if (parts[0] === 'product') return { name: 'product', id: Number(parts[1]), params };
  return { name: PAGES[parts[0]] ? parts[0] : 'home', params };
}

let lastKey = null;

async function router() {
  // Tear down anything the outgoing page owned. The hero holds a GL context
  // and a rAF loop, so leaking it across navigations would burn a context
  // slot and keep rendering off-screen.
  clearInterval(state.eventPoll);
  state.hero?.dispose();
  state.hero = null;
  const route = parseRoute();
  const page = PAGES[route.name] ?? PAGES.home;
  const view = document.getElementById('view');

  document.title = `${page.title} — Kestrel`;
  document.getElementById('topbar-title').textContent = page.title;
  renderSidebar();
  if (window.matchMedia('(max-width: 1024px)').matches) setNavOpen(false);

  const key = route.name + (route.id ?? '');
  if (key !== lastKey) window.scrollTo({ top: 0, behavior: 'instant' });
  lastKey = key;

  try {
    await page.render(view, route.name === 'product' ? route.id : route.params);
  } catch (err) {
    view.innerHTML = errorState(err, router);
  }
}

/* ========================================================================== */
/* boot                                                                       */
/* ========================================================================== */

async function loadUsers() {
  const sel = document.getElementById('user-select');
  try {
    const { user_ids } = await api('/api/users?limit=40');
    const coldStart = Math.max(0, ...user_ids) + 9000;
    sel.innerHTML = [
      ...user_ids.map((id) => `<option value="${id}">Shopper ${id}</option>`),
      `<option value="${coldStart}">Shopper ${coldStart} (new)</option>`,
    ].join('');
    const saved = Number(localStorage.getItem('kestrel_user'));
    state.userId = (user_ids.includes(saved) || saved === coldStart) ? saved : (user_ids[0] ?? coldStart);
    sel.value = state.userId;
  } catch {
    state.userId = 1;
    sel.innerHTML = '<option value="1">Shopper 1</option>';
  }
  sel.addEventListener('change', () => {
    state.userId = Number(sel.value);
    localStorage.setItem('kestrel_user', String(state.userId));
    router();
  });
}

(async function boot() {
  applyTheme(localStorage.getItem('kestrel_theme') || 'light');
  document.getElementById('theme-toggle').addEventListener('click', () =>
    applyTheme(document.documentElement.dataset.theme === 'light' ? 'dark' : 'light'));

  setNavOpen(false);
  document.getElementById('nav-toggle').addEventListener('click', () =>
    setNavOpen(!document.getElementById('app').classList.contains('nav-open')));
  document.getElementById('scrim').addEventListener('click', () => setNavOpen(false));
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setNavOpen(false); });

  await loadUsers();
  window.addEventListener('hashchange', router);
  await router();
})();
