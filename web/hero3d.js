/* Kestrel — WebGL hero.
 *
 * A field of instanced quads drifting in 3D with depth fog, parallaxing to
 * pointer/touch. Hand-written WebGL rather than Three.js: this project has a
 * documented zero-dependency, no-build constraint, and vendoring ~600 KB of
 * library for one decorative scene is disproportionate. The rules from the
 * ui-ux-pro-max Three.js guidance still apply and are honoured here:
 *
 *   - one GL context for the page lifetime, disposed on teardown
 *   - instanced draw (one call for all cards) rather than N draws
 *   - explicit deletion of buffers, program and shaders on dispose
 *   - particle/instance count kept well under the mobile ceiling
 *   - exponential depth fog for atmosphere and cheap far culling
 *   - prefers-reduced-motion renders a single static frame, never animates
 *   - touch events alongside pointer events
 *   - graceful, silent fallback to the CSS gradient when WebGL is absent
 *
 * The scene is decorative: the canvas is aria-hidden and every word in the
 * hero is real DOM text behind it.
 */

const VERT = `
attribute vec2 aCorner;        // unit quad corner, -0.5 .. 0.5
attribute vec3 aOffset;        // instance position
attribute vec2 aSize;          // instance size
attribute float aSeed;         // per-instance phase
attribute vec3 aTint;

uniform mat4 uProj;
uniform float uTime;
uniform vec2 uParallax;

varying float vDepth;
varying vec2 vUv;
varying vec3 vTint;

void main() {
  vUv = aCorner + 0.5;
  vTint = aTint;

  // Drift: each card rises slowly and wraps, with a lateral sway.
  float t = uTime * 0.06 + aSeed;
  vec3 pos = aOffset;
  pos.y = mod(aOffset.y + t * 1.6, 9.0) - 4.5;
  pos.x += sin(t * 1.7 + aOffset.z) * 0.22;

  // Parallax: nearer cards move more, which reads as depth.
  float near = clamp((pos.z + 7.0) / 7.0, 0.0, 1.0);
  pos.xy += uParallax * near * 0.55;

  // Billboard the quad, gently rotated per instance.
  float a = sin(t * 0.9 + aSeed * 3.0) * 0.22;
  vec2 c = vec2(aCorner.x * aSize.x, aCorner.y * aSize.y);
  vec2 rot = vec2(c.x * cos(a) - c.y * sin(a), c.x * sin(a) + c.y * cos(a));

  vec4 world = vec4(pos + vec3(rot, 0.0), 1.0);
  vDepth = -pos.z;
  gl_Position = uProj * world;
}`;

const FRAG = `
precision mediump float;

varying float vDepth;
varying vec2 vUv;
varying vec3 vTint;

uniform vec3 uFog;

void main() {
  // Rounded-rect mask, computed analytically so there is no texture to load.
  vec2 p = abs(vUv - 0.5) * 2.0;
  float r = 0.28;
  vec2 q = max(p - (1.0 - r), 0.0);
  float d = length(q) - r;
  float alpha = smoothstep(0.02, -0.02, d);
  if (alpha < 0.01) discard;

  // A soft diagonal sheen gives the flat quad some form.
  float sheen = 0.55 + 0.45 * smoothstep(0.0, 1.4, vUv.x + vUv.y);
  vec3 col = vTint * sheen;

  // FogExp2 — atmosphere, and far instances fade out entirely.
  float fog = 1.0 - exp(-0.030 * vDepth * vDepth);
  col = mix(col, uFog, clamp(fog, 0.0, 1.0));

  gl_FragColor = vec4(col, alpha * (1.0 - fog * 0.85));
}`;

const INSTANCES = 90;      // one instanced draw call; far below any mobile ceiling
const FOG_LIGHT = [0.25, 0.28, 0.72];
const FOG_DARK  = [0.05, 0.06, 0.13];

function compile(gl, type, src) {
  const sh = gl.createShader(type);
  gl.shaderSource(sh, src);
  gl.compileShader(sh);
  if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) {
    const log = gl.getShaderInfoLog(sh);
    gl.deleteShader(sh);
    throw new Error(`shader: ${log}`);
  }
  return sh;
}

/** Perspective projection, column-major, looking down -Z. */
function perspective(fovy, aspect, near, far) {
  const f = 1 / Math.tan(fovy / 2);
  const nf = 1 / (near - far);
  return new Float32Array([
    f / aspect, 0, 0, 0,
    0, f, 0, 0,
    0, 0, (far + near) * nf, -1,
    0, 0, 2 * far * near * nf, 0,
  ]);
}

/**
 * Mounts the scene into `canvas`.
 * @returns {{dispose: () => void}} always — the no-op form when unsupported.
 */
export function mountHero(canvas) {
  const noop = { dispose() {} };
  if (!canvas) return noop;

  const gl = canvas.getContext('webgl', {
    alpha: true, antialias: true, premultipliedAlpha: false,
    powerPreference: 'low-power', depth: false,
  });
  // No WebGL (old browser, blocked, software-rendering disabled): leave the
  // canvas empty and let the CSS gradient behind it stand on its own.
  if (!gl) return noop;

  const ext = gl.getExtension('ANGLE_instanced_arrays');
  if (!ext) return noop;

  let program, vs, fs;
  try {
    vs = compile(gl, gl.VERTEX_SHADER, VERT);
    fs = compile(gl, gl.FRAGMENT_SHADER, FRAG);
    program = gl.createProgram();
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      throw new Error(gl.getProgramInfoLog(program));
    }
  } catch {
    [vs, fs].forEach((s) => s && gl.deleteShader(s));
    if (program) gl.deleteProgram(program);
    return noop;
  }
  gl.deleteShader(vs);
  gl.deleteShader(fs);
  gl.useProgram(program);

  // --- geometry: one unit quad, reused by every instance --------------------
  const quad = new Float32Array([-0.5, -0.5, 0.5, -0.5, -0.5, 0.5, 0.5, 0.5]);
  const quadBuf = gl.createBuffer();
  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
  gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);

  // --- per-instance attributes ---------------------------------------------
  const offsets = new Float32Array(INSTANCES * 3);
  const sizes = new Float32Array(INSTANCES * 2);
  const seeds = new Float32Array(INSTANCES);
  const tints = new Float32Array(INSTANCES * 3);

  // Deterministic PRNG so the scene is identical on every load.
  let s = 20260812;
  const rnd = () => (s = (s * 1664525 + 1013904223) % 4294967296) / 4294967296;

  for (let i = 0; i < INSTANCES; i++) {
    const z = -1.2 - rnd() * 6.0;
    offsets.set([(rnd() - 0.5) * 9.5, rnd() * 9.0 - 4.5, z], i * 3);
    const w = 0.30 + rnd() * 0.42;
    sizes.set([w, w * (0.66 + rnd() * 0.3)], i * 2);
    seeds[i] = rnd() * 6.28;
    // Indigo → violet → cyan, matching the brand ramp.
    const h = rnd();
    tints.set(
      h < 0.55 ? [0.42, 0.46, 0.95]
        : h < 0.85 ? [0.62, 0.45, 0.98]
          : [0.36, 0.78, 0.94],
      i * 3,
    );
  }

  const buffers = {};
  const bindInstanced = (name, data, size) => {
    const buf = gl.createBuffer();
    buffers[name] = buf;
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    const loc = gl.getAttribLocation(program, name);
    gl.enableVertexAttribArray(loc);
    gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
    ext.vertexAttribDivisorANGLE(loc, 1);
    return loc;
  };

  gl.bindBuffer(gl.ARRAY_BUFFER, quadBuf);
  const cornerLoc = gl.getAttribLocation(program, 'aCorner');
  gl.enableVertexAttribArray(cornerLoc);
  gl.vertexAttribPointer(cornerLoc, 2, gl.FLOAT, false, 0, 0);
  ext.vertexAttribDivisorANGLE(cornerLoc, 0);

  bindInstanced('aOffset', offsets, 3);
  bindInstanced('aSize', sizes, 2);
  bindInstanced('aSeed', seeds, 1);
  bindInstanced('aTint', tints, 3);

  const uProj = gl.getUniformLocation(program, 'uProj');
  const uTime = gl.getUniformLocation(program, 'uTime');
  const uParallax = gl.getUniformLocation(program, 'uParallax');
  const uFog = gl.getUniformLocation(program, 'uFog');

  gl.enable(gl.BLEND);
  gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  gl.clearColor(0, 0, 0, 0);

  // --- sizing ---------------------------------------------------------------
  let dpr = 1;
  function resize() {
    // Cap DPR at 2: beyond that the fill cost doubles for no visible gain.
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = canvas.clientWidth || 1;
    const h = canvas.clientHeight || 1;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    gl.viewport(0, 0, canvas.width, canvas.height);
    gl.uniformMatrix4fv(uProj, false, perspective(1.05, w / h, 0.1, 30));
  }

  // --- interaction ----------------------------------------------------------
  const target = { x: 0, y: 0 };
  const current = { x: 0, y: 0 };
  const host = canvas.parentElement || canvas;

  function pointTo(clientX, clientY) {
    const r = host.getBoundingClientRect();
    target.x = ((clientX - r.left) / r.width - 0.5) * 2;
    target.y = -((clientY - r.top) / r.height - 0.5) * 2;
  }
  const onMove = (e) => pointTo(e.clientX, e.clientY);
  const onTouch = (e) => {
    if (!e.touches.length) return;
    pointTo(e.touches[0].clientX, e.touches[0].clientY);
  };
  const onLeave = () => { target.x = 0; target.y = 0; };

  host.addEventListener('pointermove', onMove);
  host.addEventListener('pointerleave', onLeave);
  // passive: never block scrolling to run a decorative effect.
  host.addEventListener('touchmove', onTouch, { passive: true });
  host.addEventListener('touchend', onLeave, { passive: true });

  const isDark = () => document.documentElement.dataset.theme === 'dark';
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)');

  function draw(timeSec) {
    const fog = isDark() ? FOG_DARK : FOG_LIGHT;
    gl.uniform3f(uFog, fog[0], fog[1], fog[2]);
    gl.uniform1f(uTime, timeSec);
    gl.uniform2f(uParallax, current.x, current.y);
    gl.clear(gl.COLOR_BUFFER_BIT);
    ext.drawArraysInstancedANGLE(gl.TRIANGLE_STRIP, 0, 4, INSTANCES);
  }

  let raf = 0;
  let running = false;
  const start = performance.now();

  function frame(now) {
    const t = (now - start) / 1000;
    current.x += (target.x - current.x) * 0.045;
    current.y += (target.y - current.y) * 0.045;
    draw(t);
    raf = requestAnimationFrame(frame);
  }

  function startLoop() {
    if (running || reduced.matches) return;
    running = true;
    raf = requestAnimationFrame(frame);
  }
  function stopLoop() {
    running = false;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
  }

  // Pause when scrolled away or the tab is hidden — no GPU work off-screen.
  const io = new IntersectionObserver(
    ([entry]) => (entry.isIntersecting ? startLoop() : stopLoop()),
    { threshold: 0.01 },
  );
  io.observe(canvas);

  const onVisibility = () => (document.hidden ? stopLoop() : startLoop());
  document.addEventListener('visibilitychange', onVisibility);

  const onResize = () => { resize(); if (!running) draw(2.0); };
  window.addEventListener('resize', onResize);

  // Repaint on theme change so the fog matches the new surface immediately.
  const themeObserver = new MutationObserver(() => { if (!running) draw(2.0); });
  themeObserver.observe(document.documentElement, {
    attributes: true, attributeFilter: ['data-theme'],
  });

  const onReducedChange = () => {
    if (reduced.matches) { stopLoop(); draw(2.0); } else { startLoop(); }
  };
  reduced.addEventListener('change', onReducedChange);

  resize();
  if (reduced.matches) {
    // Honour the OS preference: one composed frame, then nothing moves.
    draw(2.0);
  } else {
    startLoop();
  }

  return {
    dispose() {
      stopLoop();
      io.disconnect();
      themeObserver.disconnect();
      reduced.removeEventListener('change', onReducedChange);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('resize', onResize);
      host.removeEventListener('pointermove', onMove);
      host.removeEventListener('pointerleave', onLeave);
      host.removeEventListener('touchmove', onTouch);
      host.removeEventListener('touchend', onLeave);

      // WebGL never frees GPU resources on its own.
      Object.values(buffers).forEach((b) => gl.deleteBuffer(b));
      gl.deleteBuffer(quadBuf);
      gl.deleteProgram(program);
      gl.getExtension('WEBGL_lose_context')?.loseContext();
    },
  };
}
