// Workspace ambient background — ported from the landing page's `universe()`
// IIFE (templates/static/js/landing/landing.js, the section starting at
// "research universe: cursor-reactive knowledge field"). Same canvas-2D
// approach, same node/link/glow structure, same requestAnimationFrame +
// elapsed-time motion, same reduced-motion / resize-debounce handling.
//
// Deliberate workspace differences (all others match the original):
//   - Cream palette (#ece9dc base) instead of the landing page's dark green.
//   - Node count driven by the #quota select, not by viewport area.
//   - No text labels on nodes.
//   - Canvas is viewport-fixed so content scrolls over it.
//   - Pointer events arrive via window/document listeners (canvas is
//     pointer-events:none) and clientX/Y are used directly as canvas coords
//     (fixed canvas means clientX === canvas-local X, no offset needed).
//
// The landing page's own files are untouched by this module.
(function () {
  "use strict";

  var canvas = document.querySelector("[data-ws-bg]");
  if (!canvas || canvas.dataset.wsBgInit) return;
  canvas.dataset.wsBgInit = "1";
  var ctx = canvas.getContext("2d");
  if (!ctx) return;

  var mqReduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var mqFine   = window.matchMedia("(pointer: fine)");
  var reduce      = mqReduce.matches;
  var finePointer = mqFine.matches;

  var quotaEl = document.getElementById("quota");

  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function lerp(a, b, t)   { return a + (b - a) * t; }

  // -- palette: workspace warm cream tones, never the landing page's green --
  // Node/line hues are warm taupe/stone — clearly darker than cream so they
  // read at a glance. Glow is warm near-white; higher alpha than the dark-bg
  // version needs because cream already starts near-white (less headroom).
  var NODE_RGB = "141,116,82";
  var LINE_RGB = "118,98,70";
  var HALO_RGB = "141,116,82";

  // Dark-mode palette: exact mint tones from landing.js universe()
  var D_NODE = "169,212,190";
  var D_LINE = "169,212,190";
  var D_HALO = "169,212,190";
  function isDarkMode() { return document.body && document.body.dataset.theme === "dark"; }

  function rgba(rgb, a) { return "rgba(" + rgb + "," + a + ")"; }

  // -- state ---------------------------------------------------------------
  var dpr = 1, W = 0, H = 0;
  var nodes = [];
  var nextSector = 0;
  var SECTOR_COLS = 5, SECTOR_ROWS = 4;
  var sectorOrder = [];
  (function buildSectorOrder() {
    var i, j, k, tmp;
    for (i = 0; i < SECTOR_COLS * SECTOR_ROWS; i++) sectorOrder.push(i);
    for (j = sectorOrder.length - 1; j > 0; j--) {
      k = Math.floor(Math.random() * (j + 1));
      tmp = sectorOrder[j]; sectorOrder[j] = sectorOrder[k]; sectorOrder[k] = tmp;
    }
  })();

  var glow = { x: 0, y: 0, tx: 0, ty: 0, level: 0, target: 0 };

  // mouse: local canvas coords (= clientX/Y for a fixed canvas)
  var mouse = { x: -9999, y: -9999, active: false };

  // avoidRect is used ONLY during initial node placement (pickPosition).
  // It is never consulted in the per-frame physics. Applying a continuous
  // per-frame push from this rect caused node drift whenever the page
  // scrolled (viewport-coords in avoidRect became stale) and whenever
  // Advanced Options opened/closed (card height changed without re-measure).
  // Removing it from the frame loop eliminates both problems.
  var avoidRect = null;

  var bgLayer = document.createElement("canvas");
  var bgCtx   = bgLayer.getContext("2d");
  var running = false, rafId = null, lastTs = 0;

  // ---- placement helpers -----------------------------------------------
  function measureAvoidRect() {
    var card = document.getElementById("wsSearchCard");
    if (!card) { avoidRect = null; return; }
    var r = card.getBoundingClientRect(), pad = 36;
    avoidRect = { x: r.left - pad, y: r.top - pad,
                  w: r.width + pad * 2, h: r.height + pad * 2 };
  }

  function minSpacingFor(count) {
    var areaPerNode = (W * H) / Math.max(1, count);
    return clamp(Math.sqrt(areaPerNode) * 0.5, 46, 200);
  }

  function pickPosition() {
    var sector = sectorOrder[nextSector % sectorOrder.length];
    nextSector++;
    var col = sector % SECTOR_COLS, row = Math.floor(sector / SECTOR_COLS);
    var sw = W / SECTOR_COLS, sh = H / SECTOR_ROWS;
    var margin = Math.min(sw, sh) * 0.18;
    var minDist = minSpacingFor(Math.max(nodes.length + 1, 5));
    var best = null, bestScore = -1;

    for (var attempt = 0; attempt < 10; attempt++) {
      var x = col * sw + margin + Math.random() * (sw - margin * 2);
      var y = row * sh + margin + Math.random() * (sh - margin * 2);

      if (avoidRect) {
        var ar = avoidRect;
        if (x > ar.x && x < ar.x + ar.w && y > ar.y && y < ar.y + ar.h) {
          var dl = x - ar.x, dr = ar.x + ar.w - x,
              dt = y - ar.y, db = ar.y + ar.h - y;
          var m = Math.min(dl, dr, dt, db);
          if (m === dl) x = ar.x - 12;
          else if (m === dr) x = ar.x + ar.w + 12;
          else if (m === dt) y = ar.y - 12;
          else y = ar.y + ar.h + 12;
        }
      }
      x = clamp(x, 10, W - 10);
      y = clamp(y, 10, H - 10);

      var minSeen = Infinity;
      for (var i = 0; i < nodes.length; i++) {
        var ddx = nodes[i].ox - x, ddy = nodes[i].oy - y;
        var d = Math.sqrt(ddx * ddx + ddy * ddy);
        if (d < minSeen) minSeen = d;
      }
      if (minSeen >= minDist) return { x: x, y: y };
      if (minSeen > bestScore) { bestScore = minSeen; best = { x: x, y: y }; }
    }
    return best || { x: W / 2, y: H / 2 };
  }

  // ---- node lifecycle --------------------------------------------------
  function addNode() {
    var pos = pickPosition();
    nodes.push({
      x: pos.x, y: pos.y, ox: pos.x, oy: pos.y,
      nx: W ? pos.x / W : 0.5, ny: H ? pos.y / H : 0.5,
      vx: 0, vy: 0,
      r: 2 + Math.random() * 1.6,
      opacity: reduce ? 1 : 0, target: 1,
      removing: false,
      phase: Math.random() * Math.PI * 2,
      driftScale: 0.7 + Math.random() * 0.6,
    });
  }

  function setCount(target) {
    var i, need, fading, active, toRemove;
    target = clamp(Math.round(target) || 0, 0, SECTOR_COLS * SECTOR_ROWS);
    active = nodes.filter(function (n) { return !n.removing; });
    if (target > active.length) {
      need = target - active.length;
      fading = nodes.filter(function (n) { return n.removing; });
      for (i = 0; i < fading.length && need > 0; i++, need--) {
        fading[i].removing = false; fading[i].target = 1;
      }
      for (i = 0; i < need; i++) addNode();
    } else if (target < active.length) {
      toRemove = active.slice(active.length - (active.length - target));
      toRemove.forEach(function (n) { n.removing = true; n.target = 0; });
      if (reduce) nodes = nodes.filter(function (n) { return !n.removing; });
    }
    if (reduce) renderStatic();
  }

  function currentQuotaValue() {
    var v = quotaEl ? parseInt(quotaEl.value, 10) : NaN;
    return Number.isFinite(v) && v > 0 ? v : 5;
  }

  // ---- resize: preserve relative positions, no node restart ----------
  function resize() {
    var prevW = W, prevH = H;
    W = window.innerWidth;
    H = window.innerHeight;
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    canvas.width  = Math.round(W * dpr);
    canvas.height = Math.round(H * dpr);
    canvas.style.width  = W + "px";
    canvas.style.height = H + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    bgLayer.width  = Math.round(W * dpr);
    bgLayer.height = Math.round(H * dpr);
    bgCtx.setTransform(dpr, 0, 0, dpr, 0, 0);

    measureAvoidRect();

    if (prevW && prevH && (prevW !== W || prevH !== H)) {
      var sx = W / prevW, sy = H / prevH;
      nodes.forEach(function (n) {
        n.x  *= sx; n.y  *= sy; n.ox *= sx; n.oy *= sy;
        n.vx *= sx; n.vy *= sy;
      });
    } else {
      nodes.forEach(function (n) {
        n.ox = n.nx * W; n.oy = n.ny * H; n.x = n.ox; n.y = n.oy;
      });
    }
    nodes.forEach(function (n) {
      n.nx = n.ox / W; n.ny = n.oy / H;
      n.x  = clamp(n.x,  8, W - 8); n.y  = clamp(n.y,  8, H - 8);
      n.ox = clamp(n.ox, 8, W - 8); n.oy = clamp(n.oy, 8, H - 8);
    });

    paintBackgroundLayer();
    if (reduce) renderStatic();
  }

  // ---- static gradient wash (painted once per resize or theme change) ---
  function paintBackgroundLayer() {
    var g, mR, cx, cy, maxR, vign;
    bgCtx.clearRect(0, 0, W, H);

    if (isDarkMode()) {
      // Exact landing-page universe gradient:
      // linear-gradient(180deg, #0f2a1e 0%, #071009 70%, #05100a 100%)
      mR = Math.max(W, H);
      g = bgCtx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0,   "#0f2a1e");
      g.addColorStop(0.7, "#071009");
      g.addColorStop(1,   "#05100a");
      bgCtx.fillStyle = g; bgCtx.fillRect(0, 0, W, H);

      // Landing .sch-invert ambient radial glow at top-left:
      // radial-gradient(120% 90% at 12% 0%, rgba(63,155,115,0.14), transparent)
      g = bgCtx.createRadialGradient(0.12*W, 0, 0, 0.12*W, 0, mR*0.85);
      g.addColorStop(0, "rgba(63,155,115,0.14)");
      g.addColorStop(1, "rgba(63,155,115,0)");
      bgCtx.fillStyle = g; bgCtx.fillRect(0, 0, W, H);
    } else {
      mR = Math.max(W, H); cx = W / 2; cy = H / 2;
      bgCtx.fillStyle = "#ece9dc"; bgCtx.fillRect(0, 0, W, H);

      g = bgCtx.createRadialGradient(0.2*W, 0.16*H, 0, 0.2*W, 0.16*H, mR*0.85);
      g.addColorStop(0, "rgba(250,247,237,0.55)"); g.addColorStop(1, "rgba(250,247,237,0)");
      bgCtx.fillStyle = g; bgCtx.fillRect(0, 0, W, H);

      g = bgCtx.createRadialGradient(0.84*W, 0.88*H, 0, 0.84*W, 0.88*H, mR*0.8);
      g.addColorStop(0, "rgba(222,211,185,0.5)"); g.addColorStop(1, "rgba(222,211,185,0)");
      bgCtx.fillStyle = g; bgCtx.fillRect(0, 0, W, H);

      g = bgCtx.createRadialGradient(0.75*W, 0.12*H, 0, 0.75*W, 0.12*H, mR*0.6);
      g.addColorStop(0, "rgba(250,247,237,0.28)"); g.addColorStop(1, "rgba(250,247,237,0)");
      bgCtx.fillStyle = g; bgCtx.fillRect(0, 0, W, H);

      maxR = Math.sqrt(cx*cx + cy*cy);
      vign = bgCtx.createRadialGradient(cx, cy, maxR*0.55, cx, cy, maxR*1.25);
      vign.addColorStop(0, "rgba(196,182,150,0)"); vign.addColorStop(1, "rgba(196,182,150,0.1)");
      bgCtx.fillStyle = vign; bgCtx.fillRect(0, 0, W, H);
    }
  }

  // ---- links: sparse near-neighbor, viewport-relative floor ----------
  // For 5 nodes spread across a full viewport, a purely area-based
  // threshold can fall below the inter-node distance and produce no lines.
  // The viewport-fraction floor ensures connections remain visible.
  function computeLinks() {
    var minDist = minSpacingFor(Math.max(nodes.length, 5));
    var linkDist = Math.max(minDist * 2.2, Math.min(W, H) * 0.4);
    var maxPerNode = 2;
    var seen = Object.create(null);
    var result = [];
    var i, j, k, a, b, cands, dx, dy, d, j2, key;

    for (i = 0; i < nodes.length; i++) {
      a = nodes[i];
      if (a.opacity < 0.05) continue;
      cands = [];
      for (j = 0; j < nodes.length; j++) {
        if (i === j) continue;
        b = nodes[j];
        if (b.opacity < 0.05) continue;
        dx = a.x - b.x; dy = a.y - b.y;
        d = Math.sqrt(dx*dx + dy*dy);
        if (d < linkDist) cands.push({ j: j, d: d });
      }
      cands.sort(function (p, q) { return p.d - q.d; });
      for (k = 0; k < Math.min(maxPerNode, cands.length); k++) {
        j2 = cands[k].j;
        key = i < j2 ? i + "," + j2 : j2 + "," + i;
        if (seen[key]) continue;
        seen[key] = true;
        result.push({ a: i, b: j2, d: cands[k].d, maxD: linkDist });
      }
    }
    return result;
  }

  // ---- glow: pointer-following light -------------------------------------
  function drawGlow() {
    if (glow.level <= 0.002) return;
    var lv = glow.level;
    var radius, g;
    if (isDarkMode()) {
      // Original landing universe() glow — exact values, not boosted
      radius = Math.max(W, H) * 0.5;
      g = ctx.createRadialGradient(glow.x, glow.y, 0, glow.x, glow.y, radius);
      g.addColorStop(0,   "rgba(63,155,115,"  + (0.20 * lv).toFixed(3) + ")");
      g.addColorStop(0.5, "rgba(47,125,93,"   + (0.07 * lv).toFixed(3) + ")");
      g.addColorStop(1,   "rgba(63,155,115,0)");
    } else {
      // Cream: higher alpha needed (near-white on near-white has less headroom)
      radius = clamp(Math.min(W, H) * 0.42, 280, 520);
      g = ctx.createRadialGradient(glow.x, glow.y, 0, glow.x, glow.y, radius);
      g.addColorStop(0,    "rgba(255,252,242," + (0.68 * lv).toFixed(3) + ")");
      g.addColorStop(0.28, "rgba(255,252,242," + (0.40 * lv).toFixed(3) + ")");
      g.addColorStop(0.60, "rgba(255,252,242," + (0.14 * lv).toFixed(3) + ")");
      g.addColorStop(1,    "rgba(255,252,242,0)");
    }
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
  }

  function drawLinksAndNodes() {
    var links = computeLinks();
    var i, l, a, b, alpha, n, haloR, halo;
    var dark   = isDarkMode();
    var lRGB   = dark ? D_LINE : LINE_RGB;
    var nRGB   = dark ? D_NODE : NODE_RGB;
    var hRGB   = dark ? D_HALO : HALO_RGB;
    var nAlpha = dark ? 0.50 : 0.72;
    var hAlpha = dark ? 0.14 : 0.24;

    ctx.lineWidth = 0.85;
    for (i = 0; i < links.length; i++) {
      l = links[i]; a = nodes[l.a]; b = nodes[l.b];
      alpha = (1 - l.d / l.maxD) * 0.28 * Math.min(a.opacity, b.opacity);
      if (alpha <= 0.005) continue;
      ctx.strokeStyle = rgba(lRGB, alpha);
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
    }

    for (i = 0; i < nodes.length; i++) {
      n = nodes[i];
      if (n.opacity <= 0.005) continue;
      haloR = n.r * 5.5;
      halo = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, haloR);
      halo.addColorStop(0, rgba(hRGB, hAlpha * n.opacity));
      halo.addColorStop(1, rgba(hRGB, 0));
      ctx.fillStyle = halo;
      ctx.beginPath(); ctx.arc(n.x, n.y, haloR, 0, Math.PI * 2); ctx.fill();

      ctx.beginPath(); ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fillStyle = rgba(nRGB, nAlpha * n.opacity);
      ctx.fill();
    }
  }

  function renderStatic() {
    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(bgLayer, 0, 0, W, H);
    nodes.forEach(function (n) {
      n.x = n.ox; n.y = n.oy; n.opacity = n.removing ? 0 : 1;
    });
    nodes = nodes.filter(function (n) { return !n.removing; });
    drawLinksAndNodes();
  }

  // ---- animated loop: original universe() motion + pointer node force --
  function frame(ts) {
    if (!running) return;
    if (!lastTs) lastTs = ts;
    var dt = Math.min(48, ts - lastTs) / 16.67;
    lastTs = ts;
    var time = ts / 1000;
    var i, n, dx, dy, d2, d, f, dir;

    glow.x = lerp(glow.x, glow.tx, 0.05 * dt);
    glow.y = lerp(glow.y, glow.ty, 0.05 * dt);
    glow.level = lerp(glow.level, glow.target, 0.06 * dt);

    for (i = nodes.length - 1; i >= 0; i--) {
      n = nodes[i];
      n.opacity = lerp(n.opacity, n.target, 0.05 * dt);
      if (n.removing && n.opacity < 0.01) { nodes.splice(i, 1); continue; }

      // Spring home — matches landing universe() coefficient (0.004)
      n.vx += (n.ox - n.x) * 0.004 * dt;
      n.vy += (n.oy - n.y) * 0.004 * dt;

      // Ambient drift — matches landing universe() (0.012 per axis)
      n.vx += Math.cos(time * 0.4 * n.driftScale + n.phase) * 0.012 * dt;
      n.vy += Math.sin(time * 0.35 * n.driftScale + n.phase) * 0.012 * dt;

      // Pointer force — ported directly from landing.js universe():
      //   repel nodes that are very close (< 72px), gently attract those
      //   in the mid-range (72–160px).  This is the primary visible cursor
      //   interaction that was absent from the previous workspace version.
      if (mouse.active && finePointer) {
        dx = n.x - mouse.x; dy = n.y - mouse.y;
        d2 = dx * dx + dy * dy;
        if (d2 < 160 * 160) {
          d = Math.sqrt(d2) || 1;
          f = 1 - d / 160;
          dir = d < 72 ? 1 : -0.35;
          n.vx += (dx / d) * f * dir * 0.9 * dt;
          n.vy += (dy / d) * f * dir * 0.9 * dt;
        }
      }

      // Damping — matches landing universe() (0.92)
      n.vx *= 0.92;
      n.vy *= 0.92;
      n.x += n.vx * dt;
      n.y += n.vy * dt;
      n.x = clamp(n.x, 6, W - 6);
      n.y = clamp(n.y, 6, H - 6);
    }

    ctx.clearRect(0, 0, W, H);
    ctx.drawImage(bgLayer, 0, 0, W, H);
    drawGlow();
    drawLinksAndNodes();

    rafId = requestAnimationFrame(frame);
  }

  function start() {
    if (running || reduce) return;
    running = true; lastTs = 0;
    rafId = requestAnimationFrame(frame);
  }
  function stop() {
    running = false;
    if (rafId) { cancelAnimationFrame(rafId); rafId = null; }
  }

  // ---- pointer handling -------------------------------------------------
  // Canvas is pointer-events:none, so we listen at window/document level.
  // For a fixed canvas, clientX/Y equal canvas-local coords (no offset).
  if (finePointer && !reduce) {
    window.addEventListener("pointermove", function (e) {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
      glow.tx = e.clientX;
      glow.ty = e.clientY;
      glow.target = 1;
    }, { passive: true });

    document.addEventListener("mouseleave", function () {
      mouse.active = false;
      mouse.x = mouse.y = -9999;
      glow.target = 0;
    });
  }

  if (!reduce) {
    document.addEventListener("visibilitychange", function () {
      if (document.hidden) stop(); else start();
    });
  }

  glow.x  = window.innerWidth  * 0.5;
  glow.y  = window.innerHeight * 0.35;
  glow.tx = glow.x;
  glow.ty = glow.y;

  var rt;
  window.addEventListener("resize", function () {
    clearTimeout(rt); rt = setTimeout(resize, 160);
  }, { passive: true });

  if (quotaEl) {
    quotaEl.addEventListener("change", function () {
      setCount(currentQuotaValue());
    });
  }

  // ---- boot ------------------------------------------------------------
  resize();
  setCount(currentQuotaValue());
  if (reduce) renderStatic(); else start();

  // Repaint background layer (and glow/nodes on next frame) when the user
  // toggles light ↔ dark. Node positions and velocities are intentionally
  // preserved — only palette and bgLayer gradient change.
  window.addEventListener("scholara-theme-change", function () {
    paintBackgroundLayer();
    if (reduce) renderStatic();
  });
})();
