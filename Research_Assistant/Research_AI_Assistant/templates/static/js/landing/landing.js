/* ============================================================================
   Scholara landing — vanilla progressive enhancement.
   The page is fully readable and usable with JavaScript disabled.
   ========================================================================== */
(function () {
  "use strict";

  var mqReduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var mqFine = window.matchMedia("(pointer: fine)");
  var reduce = mqReduce.matches;

  var clamp = function (v, a, b) { return v < a ? a : v > b ? b : v; };
  var lerp = function (a, b, t) { return a + (b - a) * t; };

  /* ---- footer year ----------------------------------------------------- */
  document.querySelectorAll("[data-year]").forEach(function (el) {
    el.textContent = String(new Date().getFullYear());
  });

  /* ---- nav: stuck state + mobile menu -------------------------------- */
  (function nav() {
    var el = document.querySelector("[data-nav]");
    if (!el) return;

    // Publish the real navbar height so sticky sections can offset from it
    // (CSS var --sch-nav-h; the stylesheet carries a 74px fallback).
    var root = document.querySelector(".scholara") || document.documentElement;
    var syncNavH = function () {
      var h = Math.round(el.getBoundingClientRect().height);
      if (h) root.style.setProperty("--sch-nav-h", h + "px");
    };
    syncNavH();
    window.addEventListener("resize", syncNavH, { passive: true });
    if (window.ResizeObserver) new ResizeObserver(syncNavH).observe(el);

    var stick = function () {
      el.classList.toggle("is-stuck", window.scrollY > 10);
    };
    stick();
    window.addEventListener("scroll", stick, { passive: true });

    var btn = el.querySelector("[data-nav-toggle]");
    var menu = el.querySelector("#sch-nav-links");
    if (!btn || !menu) return;
    var close = function () {
      el.classList.remove("is-open");
      btn.setAttribute("aria-expanded", "false");
    };
    btn.addEventListener("click", function () {
      var open = el.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
    menu.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", close);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  })();

  /* ---- generic reveal ---------------------------------------------------- */
  (function reveal() {
    var items = document.querySelectorAll("[data-reveal]");
    if (reduce || !("IntersectionObserver" in window)) {
      items.forEach(function (el) { el.classList.add("is-visible"); });
      return;
    }
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            en.target.classList.add("is-visible");
            io.unobserve(en.target);
          }
        });
      },
      { rootMargin: "0px 0px -10% 0px", threshold: 0.12 }
    );
    items.forEach(function (el) { io.observe(el); });
  })();

  /* ---- hero: workspace sequence + cursor parallax ------------------- */
  (function hero() {
    var desk = document.querySelector("[data-desk]");
    if (desk && !reduce && "IntersectionObserver" in window) {
      // arm immediately so the intro can play; content stays visible if this
      // script never runs (no armed class = no hidden state).
      desk.classList.add("is-armed");
      var io = new IntersectionObserver(
        function (entries) {
          entries.forEach(function (en) {
            if (en.isIntersecting) {
              desk.classList.add("is-live");
              io.disconnect();
            }
          });
        },
        { threshold: 0.35 }
      );
      io.observe(desk);
    }

    var layers = Array.prototype.slice.call(
      document.querySelectorAll("[data-parallax]")
    );
    var scene = document.querySelector("[data-parallax-scene]");
    if (!layers.length || !scene || reduce || !mqFine.matches) return;

    var tx = 0, ty = 0, cx = 0, cy = 0, raf = null;
    var tick = function () {
      cx = lerp(cx, tx, 0.08);
      cy = lerp(cy, ty, 0.08);
      layers.forEach(function (el) {
        var f = parseFloat(el.getAttribute("data-parallax")) || 0;
        el.style.transform =
          "translate3d(" + (cx * f).toFixed(2) + "px," + (cy * f).toFixed(2) + "px,0)";
      });
      if (Math.abs(cx - tx) > 0.1 || Math.abs(cy - ty) > 0.1) {
        raf = requestAnimationFrame(tick);
      } else {
        raf = null;
      }
    };
    scene.addEventListener("pointermove", function (e) {
      var r = scene.getBoundingClientRect();
      tx = e.clientX - (r.left + r.width / 2);
      ty = e.clientY - (r.top + r.height / 2);
      if (!raf) raf = requestAnimationFrame(tick);
    });
    scene.addEventListener("pointerleave", function () {
      tx = 0; ty = 0;
      if (!raf) raf = requestAnimationFrame(tick);
    });
  })();

  /* ---- "A living system" workflow strip ---------------------------------
     Question -> Discover -> Read -> Compare -> Synthesize -> Cite, as one
     plain six-column row in normal document flow (original presentation).
     The fill is a passive, ambient reveal driven by scroll position — the
     same read-only technique as [data-reveal] elsewhere: it never calls
     preventDefault and never touches scrollTop/scrollLeft, so it cannot
     trap or redirect vertical wheel/touch scrolling. Clicking a stage, or
     using Left/Right once the row has focus, additionally lets a visitor
     jump the highlight to any stage on demand. */
  (function workflow() {
    var strip = document.querySelector("[data-flow]");
    if (!strip) return;
    var line = strip.querySelector("[data-flow-line]");
    var stages = Array.prototype.slice.call(strip.querySelectorAll(".sch-stage"));
    if (!line || !stages.length) return;
    var n = stages.length;

    var render = function (active) {
      stages.forEach(function (s, i) {
        s.classList.toggle("is-on", i < active);
        // aria-current marks a single "you are here", not every lit dot
        if (i === active - 1) s.setAttribute("aria-current", "step");
        else s.removeAttribute("aria-current");
      });
      line.style.setProperty("--flow-progress", (active / n) * 100 + "%");
    };

    if (reduce) {
      render(n);
      stages.forEach(function (s, i) {
        s.addEventListener("click", function () { render(i + 1); });
      });
      return;
    }

    var manual = -1; // last stage a visitor explicitly chose, if any
    var ticking = false;
    var update = function () {
      ticking = false;
      if (manual >= 0) return; // a deliberate choice takes priority over the ambient reveal
      var r = strip.getBoundingClientRect();
      var vh = window.innerHeight;
      // progress as the strip travels through the middle of the viewport —
      // read-only bookkeeping, identical in spirit to the page's other
      // scroll-triggered reveals; it never intercepts the scroll itself
      var p = clamp((vh * 0.85 - r.top) / (r.height + vh * 0.5), 0, 1);
      render(Math.round(p * n));
    };
    var onScroll = function () {
      if (!ticking) { ticking = true; requestAnimationFrame(update); }
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    update();

    stages.forEach(function (s, i) {
      s.addEventListener("click", function () {
        manual = i;
        render(i + 1);
      });
    });
    line.addEventListener("keydown", function (e) {
      if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
      e.preventDefault();
      var base = manual >= 0 ? manual : Math.max(0, stages.filter(function (s) {
        return s.classList.contains("is-on");
      }).length - 1);
      manual = clamp(base + (e.key === "ArrowRight" ? 1 : -1), 0, n - 1);
      render(manual + 1);
    });
  })();

  /* ---- struggle: trigger the pull-in once ------------------------------- */
  (function struggle() {
    var el = document.querySelector("[data-struggle]");
    if (!el) return;
    if (reduce || !("IntersectionObserver" in window)) return; // resting state
    el.classList.add("is-armed");
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) {
            el.classList.add("is-visible");
            io.disconnect();
          }
        });
      },
      { rootMargin: "0px 0px -22% 0px", threshold: 0.4 }
    );
    io.observe(el);
  })();

  /* ---- "How Scholara works": an open research book (StPageFlip) ---------
     8 leaves (4 stage-copy / 4 sticky-note, interleaved) live in
     [data-story-leaves] at all times — that is also the complete no-JS
     fallback (a plain stacked reading list). With JS and enough width,
     they're moved into a vendored StPageFlip instance for a genuine
     diagonal page curl; under prefers-reduced-motion or a narrow
     viewport, they're moved into the same holder in "paged" mode instead
     (an instant copy+note pair swap, no library, no animation).
     StPageFlip is vendored locally (static/js/landing/vendor/page-flip/)
     — no CDN, no jQuery, no build step. It owns its own drag/corner
     interaction and is built to coexist with page scroll
     (mobileScrollSupport), but Next/Previous/the rail/arrow keys never
     touch scroll either way — normal vertical wheel/touch scrolling is
     never read, touched, or pre-empted by this code. */
  (function book() {
    var stage = document.querySelector("[data-flip-stage]");
    var leavesHolder = document.querySelector("[data-story-leaves]");
    if (!stage || !leavesHolder) return;
    var leaves = Array.prototype.slice.call(leavesHolder.querySelectorAll("[data-leaf]"));
    if (!leaves.length || leaves.length % 2 !== 0) return;
    var n = leaves.length / 2; // number of stages (copy+note pairs)

    var wrap = stage.closest(".sch-wrap");
    var prevBtn = wrap && wrap.querySelector("[data-story-prev]");
    var nextBtn = wrap && wrap.querySelector("[data-story-next]");
    var segs = wrap ? Array.prototype.slice.call(wrap.querySelectorAll("[data-story-seg]")) : [];
    var countEl = wrap && wrap.querySelector("[data-story-count]");
    var live = wrap && wrap.querySelector("[data-story-live]");
    var titles = [
      "Search trusted academic literature",
      "Understand papers through clear AI explanations",
      "Compare findings, methods, and limitations",
      "Turn evidence into structured notes and citations"
    ];

    var hasPageFlip = typeof window.St !== "undefined" && typeof window.St.PageFlip === "function";
    var mqStoryDesktop = window.matchMedia("(min-width: 641px)");
    var useBookMode = function () { return hasPageFlip && !mqReduce.matches && mqStoryDesktop.matches; };

    var current = 0; // stage index, 0..n-1
    var mode = null; // "book" | "paged"
    var pageFlip = null;
    var flipbookEl = null;
    var animating = false;

    var updateChrome = function (idx) {
      segs.forEach(function (s, i) {
        s.classList.toggle("is-filled", i <= idx);
        if (i === idx) s.setAttribute("aria-current", "step");
        else s.removeAttribute("aria-current");
      });
      if (countEl) {
        countEl.innerHTML =
          "<b>" + String(idx + 1).padStart(2, "0") + "</b>&nbsp;/&nbsp;" + String(n).padStart(2, "0");
      }
      var isAnimating = mode === "book" && animating;
      if (prevBtn) prevBtn.disabled = isAnimating || idx <= 0;
      if (nextBtn) nextBtn.disabled = isAnimating || idx >= n - 1;
      if (live) live.textContent = "Stage " + (idx + 1) + " of " + n + ": " + titles[idx];
    };

    var renderPaged = function (idx) {
      leaves.forEach(function (l, i) { l.hidden = Math.floor(i / 2) !== idx; });
    };

    /* ---- tear down whichever mode is currently mounted, always
       returning the 8 leaves to the plain holder in original order ---- */
    var teardown = function () {
      if (pageFlip) {
        try { pageFlip.destroy(); } catch (err) { /* noop */ }
        pageFlip = null;
      }
      leaves.forEach(function (l) {
        l.classList.remove("stf__item", "--soft", "--hard");
        l.removeAttribute("style");
        leavesHolder.appendChild(l);
      });
      if (flipbookEl && flipbookEl.parentNode) flipbookEl.parentNode.removeChild(flipbookEl);
      flipbookEl = null;
      animating = false;
    };

    var mountBook = function () {
      teardown();
      mode = "book";
      leavesHolder.hidden = true;
      leavesHolder.removeAttribute("data-mode");

      flipbookEl = document.createElement("div");
      flipbookEl.className = "sch-flipbook";
      stage.appendChild(flipbookEl);

      pageFlip = new window.St.PageFlip(flipbookEl, {
        width: 480,
        height: 620,
        size: "stretch",
        minWidth: 300,
        maxWidth: 620,
        minHeight: 420,
        maxHeight: 760,
        showCover: false,
        usePortrait: false, // this section's own breakpoint handles narrow widths instead
        mobileScrollSupport: true,
        useMouseEvents: true,
        disableFlipByClick: true,
        drawShadow: true,
        maxShadowOpacity: 0.55,
        flippingTime: 900,
        startPage: current * 2
      });
      pageFlip.loadFromHTML(leaves);

      pageFlip.on("flip", function (e) {
        current = clamp(Math.round(e.data / 2), 0, n - 1);
        updateChrome(current);
      });
      pageFlip.on("changeState", function (e) {
        animating = e.data === "flipping";
        flipbookEl.classList.toggle("is-flipping", animating);
        updateChrome(current);
      });

      updateChrome(current);
    };

    var mountPaged = function () {
      teardown();
      mode = "paged";
      leavesHolder.hidden = false;
      leavesHolder.setAttribute("data-mode", "paged");
      renderPaged(current);
      updateChrome(current);
    };

    var applyMode = function () {
      var wantBook = useBookMode();
      if (wantBook && mode !== "book") mountBook();
      else if (!wantBook && mode !== "paged") mountPaged();
    };

    var next = function () {
      if (mode === "book") {
        if (!animating && current < n - 1) pageFlip.flipNext();
      } else {
        goTo(current + 1);
      }
    };
    var prev = function () {
      if (mode === "book") {
        if (!animating && current > 0) pageFlip.flipPrev();
      } else {
        goTo(current - 1);
      }
    };
    var goTo = function (target) {
      target = clamp(target, 0, n - 1);
      if (target === current) return;
      if (mode === "book") {
        if (animating) return;
        pageFlip.flip(target * 2);
      } else {
        current = target;
        renderPaged(current);
        updateChrome(current);
      }
    };

    if (prevBtn) prevBtn.addEventListener("click", prev);
    if (nextBtn) nextBtn.addEventListener("click", next);
    segs.forEach(function (s, i) { s.addEventListener("click", function () { goTo(i); }); });

    stage.setAttribute("tabindex", "0");
    stage.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { e.preventDefault(); next(); }
      else if (e.key === "ArrowLeft") { e.preventDefault(); prev(); }
    });

    applyMode();

    // Re-evaluate on resize/orientation change and on a reduced-motion
    // preference toggle, but only actually tear down and remount when
    // the desired mode has actually changed — not on every pixel.
    var debounced = null;
    window.addEventListener("resize", function () {
      window.clearTimeout(debounced);
      debounced = window.setTimeout(applyMode, 200);
    }, { passive: true });
    if (mqStoryDesktop.addEventListener) mqStoryDesktop.addEventListener("change", applyMode);
    if (mqReduce.addEventListener) mqReduce.addEventListener("change", applyMode);
  })();

  /* ---- research universe: cursor-reactive knowledge field --------- */
  (function universe() {
    var canvas = document.querySelector("[data-universe]");
    if (!canvas) return;
    var ctx = canvas.getContext("2d");
    if (!ctx) return;

    var CONCEPTS = [
      "Methods", "Findings", "Evidence", "Citations", "Research Binder",
      "Knowledge Graph", "Limitations", "Hypothesis", "Sample", "Replication",
      "Effect size", "Peer review", "Meta-analysis", "Corpus"
    ];

    var dpr = 1, W = 0, H = 0;
    var nodes = [];
    var mouse = { x: -9999, y: -9999, active: false };
    var glow = { x: 0.5, y: 0.4, tx: 0.5, ty: 0.4 };
    var running = false;
    var mobile = !mqFine.matches || window.innerWidth < 861;

    var resize = function () {
      var rect = canvas.getBoundingClientRect();
      dpr = Math.min(window.devicePixelRatio || 1, 1.6);
      W = rect.width;
      H = rect.height;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      build();
    };

    var build = function () {
      nodes = [];
      var centers;
      if (mobile) {
        // top + bottom bands only — the centre column is all copy on phones
        centers = [
          { x: 0.28 * W, y: 0.12 * H }, { x: 0.74 * W, y: 0.16 * H },
          { x: 0.22 * W, y: 0.88 * H }, { x: 0.78 * W, y: 0.84 * H }
        ];
      } else {
        centers = [0.09, 0.19, 0.81, 0.91].map(function (cx, c) {
          return { x: cx * W, y: (0.24 + 0.52 * ((c * 0.37 + 0.2) % 1)) * H };
        });
      }
      var count = mobile ? 18 : Math.min(48, Math.round((W * H) / 32000));
      var clusters = centers.length;
      for (var i = 0; i < count; i++) {
        var ci = i % clusters;
        var cc = centers[ci];
        var ang = (i / count) * Math.PI * 2 + i;
        var rad = (mobile ? 22 : 30) + ((i * 53) % (mobile ? 80 : 120));
        var x = clamp(cc.x + Math.cos(ang) * rad, 18, W - 18);
        var y = clamp(cc.y + Math.sin(ang) * rad, 24, H - 24);
        var labelled = !mobile && i % 3 === 0;
        nodes.push({
          x: x, y: y, ox: x, oy: y, vx: 0, vy: 0,
          cluster: ci,
          r: labelled ? 3 : 1.5 + ((i * 7) % 10) / 12,
          label: labelled ? CONCEPTS[(i / 3 | 0) % CONCEPTS.length] : null,
          phase: (i * 0.7) % (Math.PI * 2)
        });
      }
    };

    var t0 = 0;
    var frame = function (ts) {
      if (!running) return;
      if (!t0) t0 = ts;
      var dt = Math.min(40, ts - t0) / 16.67;
      t0 = ts;

      // background wash + glow
      var bg = ctx.createLinearGradient(0, 0, 0, H);
      bg.addColorStop(0, "#0f2a1e");
      bg.addColorStop(0.7, "#071009");
      bg.addColorStop(1, "#05100a");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, W, H);

      glow.x = lerp(glow.x, glow.tx, 0.05);
      glow.y = lerp(glow.y, glow.ty, 0.05);
      var g = ctx.createRadialGradient(
        glow.x * W, glow.y * H, 0,
        glow.x * W, glow.y * H, Math.max(W, H) * 0.5
      );
      g.addColorStop(0, "rgba(63,155,115,0.20)");
      g.addColorStop(0.5, "rgba(47,125,93,0.07)");
      g.addColorStop(1, "rgba(0,0,0,0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, W, H);

      var time = ts / 1000;
      var linkDist = mobile ? 96 : 132;

      var cxp = W / 2;
      var cyp = H / 2;
      var keepW = Math.min(W * 0.4, 520);
      var keepH = H * 0.34;
      for (var i = 0; i < nodes.length; i++) {
        var p = nodes[i];
        // spring home
        p.vx += (p.ox - p.x) * 0.004 * dt;
        p.vy += (p.oy - p.y) * 0.004 * dt;
        // ambient drift
        p.vx += Math.cos(time * 0.4 + p.phase) * 0.012 * dt;
        p.vy += Math.sin(time * 0.35 + p.phase) * 0.012 * dt;
        if (mobile) {
          // keep the vertical centre band clear (all copy lives there)
          var cdy = p.y - cyp;
          if (Math.abs(cdy) < keepH) {
            p.vy += (cdy >= 0 ? 1 : -1) * (1 - Math.abs(cdy) / keepH) * 0.14 * dt;
          }
        } else {
          // keep the central column clear for the headline + CTA
          var cdx = p.x - cxp;
          if (Math.abs(cdx) < keepW) {
            p.vx += (cdx >= 0 ? 1 : -1) * (1 - Math.abs(cdx) / keepW) * 0.12 * dt;
          }
        }
        // pointer force (desktop)
        if (mouse.active) {
          var dx = p.x - mouse.x, dy = p.y - mouse.y;
          var d2 = dx * dx + dy * dy;
          var reach = 150;
          if (d2 < reach * reach) {
            var d = Math.sqrt(d2) || 1;
            var f = (1 - d / reach);
            // repel up close, gently attract at mid range
            var dir = d < 70 ? 1 : -0.35;
            p.vx += (dx / d) * f * dir * 0.9 * dt;
            p.vy += (dy / d) * f * dir * 0.9 * dt;
          }
        }
        p.vx *= 0.92;
        p.vy *= 0.92;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
      }

      // links
      for (var a = 0; a < nodes.length; a++) {
        for (var b = a + 1; b < nodes.length; b++) {
          var na = nodes[a], nb = nodes[b];
          var lx = na.x - nb.x, ly = na.y - nb.y;
          var dist = Math.sqrt(lx * lx + ly * ly);
          if (dist < linkDist) {
            var alpha = (1 - dist / linkDist) * (na.cluster === nb.cluster ? 0.4 : 0.16);
            ctx.strokeStyle = "rgba(169,212,190," + alpha.toFixed(3) + ")";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(na.x, na.y);
            ctx.lineTo(nb.x, nb.y);
            ctx.stroke();
          }
        }
      }

      // nodes + labels (labels only in the outer thirds, never over the copy)
      ctx.font = '11px "JetBrains Mono", ui-monospace, monospace';
      ctx.textBaseline = "middle";
      for (var k = 0; k < nodes.length; k++) {
        var nd = nodes[k];
        ctx.beginPath();
        ctx.arc(nd.x, nd.y, nd.r, 0, Math.PI * 2);
        ctx.fillStyle = nd.label ? "rgba(196,228,209,0.92)" : "rgba(169,212,190,0.5)";
        ctx.fill();
        if (nd.label && (nd.x < W * 0.28 || nd.x > W * 0.72)) {
          var right = nd.x > W * 0.5;
          ctx.textAlign = right ? "right" : "left";
          ctx.fillStyle = "rgba(226,238,228,0.55)";
          ctx.fillText(nd.label, nd.x + (right ? -8 : 8), nd.y);
        }
      }
      ctx.textAlign = "left";

      requestAnimationFrame(frame);
    };

    var start = function () {
      if (running) return;
      running = true;
      t0 = 0;
      requestAnimationFrame(frame);
    };
    var stop = function () { running = false; };

    // static single frame for reduced motion
    if (reduce) {
      resize();
      running = true;
      frame(0);
      running = false;
      window.addEventListener("resize", function () {
        resize(); running = true; frame(0); running = false;
      });
      return;
    }

    if (!mobile) {
      canvas.addEventListener("pointermove", function (e) {
        var r = canvas.getBoundingClientRect();
        mouse.x = e.clientX - r.left;
        mouse.y = e.clientY - r.top;
        mouse.active = true;
        glow.tx = clamp(mouse.x / W, 0, 1);
        glow.ty = clamp(mouse.y / H, 0, 1);
      });
      canvas.addEventListener("pointerleave", function () {
        mouse.active = false;
        mouse.x = mouse.y = -9999;
        glow.tx = 0.5; glow.ty = 0.4;
      });
    } else {
      // slow ambient glow orbit on mobile
      setInterval(function () {
        glow.tx = 0.5 + 0.28 * Math.cos(Date.now() / 5200);
        glow.ty = 0.42 + 0.2 * Math.sin(Date.now() / 6100);
      }, 400);
    }

    var vis = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) start();
          else stop();
        });
      },
      { threshold: 0.05 }
    );

    var rt;
    window.addEventListener("resize", function () {
      clearTimeout(rt);
      rt = setTimeout(function () {
        mobile = !mqFine.matches || window.innerWidth < 861;
        resize();
      }, 180);
    });

    resize();
    vis.observe(canvas);
  })();
})();
