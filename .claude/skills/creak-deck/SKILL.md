---
name: create-deck
description: Create a beautiful multi-file HTML slide deck presentation from scratch — dark-themed, spacebar-driven, with fragment-by-fragment reveal, terminal demos, and feature grids. No frameworks, pure HTML/CSS/JS.
argument-hint: "[topic] [optional: number of slides or use-cases]"
---

# Create a Slide Deck Presentation

Create a complete, production-ready HTML slide deck for the topic: **$ARGUMENTS**

## Output Structure

```
<topic-slug>/
├── index.html              # Hub: hero + tile grid, one tile per section
├── assets/
│   ├── style.css           # Shared dark theme + fragment CSS
│   └── deck.js             # Slide engine with fragment reveal
└── slides/
    ├── 01-<name>.html      # Each section is its own deck
    ├── 02-<name>.html
    └── ...
```

Naming: use kebab-case for filenames, match the topic.

---

## Step 1 — Plan the Content

Before writing any files:
1. Identify 6–12 logical sections/use-cases for the topic
2. For each section, plan 3–4 slides:
   - **Slide 0** (title): section name, icon, one-sentence description
   - **Slide 1** (demo): split layout — steps on left, terminal demo on right
   - **Slide 2** (deep dive): split or full-width with more detail
   - **Slide 3** (capabilities): full-width feature grid (6 cards + tip box)
3. Think of realistic, concrete terminal demo conversations for each section

---

## Step 2 — Create `assets/style.css`

Use this exact file (copy verbatim, do not simplify):

```css
/* ═══════════════════════════════════════════════════════════
   GLOBAL CONFIG — Change these to resize everything
   ═══════════════════════════════════════════════════════════ */
:root {
  --font-size-base: 18px;
  --heading-scale: 1;
  --terminal-font-size: 0.78em;
  --ui-scale: 1;

  --bg: #0a0a0f;
  --surface: #12121a;
  --surface2: #1a1a2e;
  --surface3: #232340;
  --accent: #d97706;
  --accent2: #f59e0b;
  --accent3: #fbbf24;
  --text: #e8e8f0;
  --text-dim: #9898b4;
  --text-muted: #606080;
  --border: #2a2a45;
  --border-light: #3a3a55;
  --green: #22c55e; --blue: #3b82f6; --purple: #a855f7;
  --pink: #ec4899; --red: #ef4444; --cyan: #06b6d4;
  --teal: #14b8a6; --indigo: #6366f1; --orange: #f97316;
  --lime: #84cc16; --rose: #f43f5e; --sky: #0ea5e9;
  --radius: 14px; --radius-sm: 8px;
}

*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0 }
html, body { height: 100%; overflow: hidden; font-size: var(--font-size-base) }
body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text); line-height: 1.55 }
code, .mono { font-family: 'JetBrains Mono', monospace }
a { color: inherit; text-decoration: none }

.bg-grid { position:fixed; inset:0; background-image:linear-gradient(rgba(255,255,255,.018) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.018) 1px,transparent 1px); background-size:48px 48px; z-index:0; pointer-events:none }
.bg-glow { position:fixed; border-radius:50%; filter:blur(120px); opacity:.18; z-index:0; pointer-events:none }
.bg-glow.g1 { width:600px;height:600px;top:-200px;left:-200px;background:radial-gradient(circle,#d97706,transparent 70%) }
.bg-glow.g2 { width:500px;height:500px;bottom:-150px;right:-150px;background:radial-gradient(circle,#7c3aed,transparent 70%) }
.bg-glow.g3 { width:400px;height:400px;top:50%;left:50%;transform:translate(-50%,-50%);background:radial-gradient(circle,#0ea5e9,transparent 70%);opacity:.08 }

.progress-bar { position:fixed;top:0;left:0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent2));transition:width .4s ease;z-index:100 }
.counter { position:fixed;bottom:20px;right:24px;font-size:.75em;color:var(--text-muted);font-family:'JetBrains Mono',monospace;z-index:100 }
.nav-hint { position:fixed;bottom:20px;left:50%;transform:translateX(-50%);font-size:.72em;color:var(--text-muted);z-index:100 }
.nav-hint kbd { background:var(--surface2);border:1px solid var(--border);border-radius:4px;padding:1px 6px;font-family:inherit;font-size:.9em }
.back-pill { position:fixed;top:20px;left:24px;z-index:100;background:var(--surface2);border:1px solid var(--border);border-radius:20px;padding:6px 14px;font-size:.78em;color:var(--text-dim);transition:all .2s }
.back-pill:hover { background:var(--surface3);color:var(--text) }

.deck { position:relative; width:100vw; height:100vh; z-index:1 }
.slide { position:absolute;inset:0;display:flex;align-items:center;justify-content:center;padding:48px 64px;opacity:0;transform:translateY(40px);transition:opacity .5s ease,transform .5s ease;pointer-events:none;overflow:hidden }
.slide.active { opacity:1;transform:translateY(0);pointer-events:auto }
.slide.exit-up { opacity:0;transform:translateY(-40px) }

/* Title slide */
.uc-title { flex-direction:column;text-align:center;gap:16px }
.uc-icon { font-size:3.5em;line-height:1;margin-bottom:8px }
.uc-title h1 { font-size:calc(2.8em * var(--heading-scale));font-weight:800;letter-spacing:-.03em;background:linear-gradient(135deg,var(--text) 30%,var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent }
.uc-sub { font-size:1.1em;color:var(--text-dim);max-width:640px;line-height:1.6 }
.badge { display:inline-flex;align-items:center;padding:4px 12px;border-radius:20px;font-size:calc(.72em * var(--ui-scale));font-weight:600;letter-spacing:.05em;text-transform:uppercase }

/* Split layout */
.split { display:grid;grid-template-columns:1fr 1fr;gap:48px;width:100%;max-width:1280px;align-items:start }
.split-left { display:flex;flex-direction:column;gap:20px }
.split-left h2 { font-size:calc(1.7em * var(--heading-scale));font-weight:700;letter-spacing:-.02em }
.split-left p { color:var(--text-dim);line-height:1.65 }

/* Full-width layout */
.full-width { width:100%;max-width:1280px;display:flex;flex-direction:column;gap:20px }
.full-width h2 { font-size:calc(1.9em * var(--heading-scale));font-weight:700;letter-spacing:-.02em }
.full-width > p { color:var(--text-dim) }
.cols-2 { display:grid;grid-template-columns:1fr 1fr;gap:32px;align-items:start }

/* Steps */
.steps { display:flex;flex-direction:column;gap:12px }
.step { display:flex;gap:14px;align-items:flex-start;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:14px 16px }
.step-num { width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#000;font-weight:700;font-size:.82em;display:flex;align-items:center;justify-content:center;flex-shrink:0 }
.step-content h4 { font-size:.9em;font-weight:600;margin-bottom:2px }
.step-content p { font-size:.82em;color:var(--text-dim);margin:0 }

/* Feature grid */
.feat-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:16px }
.feat-card { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:18px 20px;transition:border-color .2s }
.feat-card:hover { border-color:var(--border-light) }
.feat-card h4 { font-size:.92em;font-weight:600;margin-bottom:8px }
.feat-card p { font-size:.8em;color:var(--text-dim);line-height:1.6 }
.feat-card code { background:var(--surface2);border-radius:4px;padding:1px 5px;font-size:.85em }

/* Tip / info boxes */
.tip-box, .info-box { display:flex;gap:12px;align-items:flex-start;padding:14px 16px;border-radius:var(--radius-sm) }
.tip-box { background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.25) }
.info-box { background:rgba(59,130,246,.08);border:1px solid rgba(59,130,246,.25) }
.tip-box p, .info-box p { font-size:.82em;color:var(--text-dim);line-height:1.6;margin:0 }
.tip-box p strong, .info-box p strong { color:var(--text) }
.tip-icon, .info-icon { font-size:1.1em;flex-shrink:0;margin-top:1px }

/* Terminal */
.terminal { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;font-size:var(--terminal-font-size) }
.terminal-bar { background:var(--surface2);padding:10px 14px;display:flex;align-items:center;gap:10px;border-bottom:1px solid var(--border) }
.dots span { width:10px;height:10px;border-radius:50%;display:inline-block;margin-right:4px }
.dots span:nth-child(1){background:#ff5f57}.dots span:nth-child(2){background:#ffbd2e}.dots span:nth-child(3){background:#28c840}
.term-title { font-size:.78em;color:var(--text-muted);font-family:'JetBrains Mono',monospace }
.terminal-body { padding:16px 18px;display:flex;flex-direction:column;gap:2px;font-family:'JetBrains Mono',monospace }
.terminal-body .line { white-space:pre-wrap;word-break:break-all;line-height:1.6 }
.terminal-body .blank { height:6px }
.prompt { color:var(--accent2);font-weight:600 }
.cmd { color:var(--text) }
.info { color:var(--blue) }
.output { color:var(--text-dim) }
.success { color:var(--green) }
.warn { color:var(--accent2) }
.highlight { color:var(--accent3);font-weight:500 }
.key { color:var(--sky) }
.str { color:var(--green) }
.cmt { color:var(--text-muted) }

/* Code block (non-terminal) */
.code-block { background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:16px 18px;font-family:'JetBrains Mono',monospace;font-size:var(--terminal-font-size);display:flex;flex-direction:column;gap:2px }
.code-block .line { white-space:pre-wrap;line-height:1.6;color:var(--text-dim) }

/* Fragment Reveal */
[data-fragment], [data-fragment-group] {
  opacity: 0; transform: translateY(8px);
  transition: opacity .35s ease, transform .35s ease;
  transition-delay: var(--frag-delay, 0s);
}
[data-fragment].revealed, [data-fragment-group].revealed {
  opacity: 1; transform: translateY(0);
}

/* Dot Indicator */
.fragment-dots { position:absolute; bottom:48px; left:50%; transform:translateX(-50%); display:flex; gap:8px; z-index:10 }
.fragment-dots .dot { width:6px; height:6px; border-radius:50%; background:var(--border-light); transition:background .3s ease, box-shadow .3s ease }
.fragment-dots .dot.lit { background:var(--accent2); box-shadow:0 0 6px rgba(245,158,11,.4) }
.fragment-dots.complete { opacity:.3; transition:opacity .8s ease .5s }

@media (max-width: 900px) {
  .split { grid-template-columns: 1fr }
  .feat-grid { grid-template-columns: 1fr 1fr }
  .slide { padding: 24px 20px }
}
```

---

## Step 3 — Create `assets/deck.js`

Use this exact file (copy verbatim):

```js
/**
 * Slide Deck Engine — shared across all presentations
 * Supports fragment-by-fragment reveal within slides.
 */
(function () {
  var slides  = document.querySelectorAll('.slide');
  var total   = slides.length;
  var current = 0;
  var busy    = false;

  var progress = document.querySelector('.progress-bar');
  var counter  = document.querySelector('.counter');

  /* ─── Fragment State ─── */
  var fragState = [];

  function initFragments() {
    slides.forEach(function (slide, i) {
      var items = [];
      var seenGroups = {};
      var els = slide.querySelectorAll('[data-fragment], [data-fragment-group]');
      els.forEach(function (el) {
        var group = el.getAttribute('data-fragment-group');
        if (group !== null) {
          if (!seenGroups[group]) {
            seenGroups[group] = true;
            var members = slide.querySelectorAll('[data-fragment-group="' + group + '"]');
            items.push({ elements: Array.from(members) });
          }
        } else {
          items.push({ elements: [el] });
        }
      });

      var dotsEl = null;
      if (items.length > 0) {
        dotsEl = document.createElement('div');
        dotsEl.className = 'fragment-dots';
        for (var d = 0; d < items.length; d++) {
          var dot = document.createElement('div');
          dot.className = 'dot';
          dotsEl.appendChild(dot);
        }
        slide.appendChild(dotsEl);
      }

      fragState[i] = { fragments: items, revealed: 0, dotsEl: dotsEl };
    });
  }

  function revealNext(si) {
    var state = fragState[si];
    if (!state || state.revealed >= state.fragments.length) return false;
    var frag = state.fragments[state.revealed];
    frag.elements.forEach(function (el) { el.classList.add('revealed'); });
    if (state.dotsEl) {
      state.dotsEl.children[state.revealed].classList.add('lit');
    }
    state.revealed++;
    if (state.dotsEl && state.revealed === state.fragments.length) {
      state.dotsEl.classList.add('complete');
    }
    return true;
  }

  function revealAll(si) {
    var state = fragState[si];
    if (!state) return;
    while (state.revealed < state.fragments.length) revealNext(si);
  }

  function unrevealLast(si) {
    var state = fragState[si];
    if (!state || state.revealed === 0) return false;
    state.revealed--;
    var frag = state.fragments[state.revealed];
    frag.elements.forEach(function (el) {
      el.style.setProperty('--frag-delay', '0s');
      el.classList.remove('revealed');
    });
    if (state.dotsEl) {
      state.dotsEl.children[state.revealed].classList.remove('lit');
      state.dotsEl.classList.remove('complete');
    }
    return true;
  }

  function update() {
    var pct = total > 1 ? (current / (total - 1)) * 100 : 100;
    if (progress) progress.style.width = pct + '%';
    if (counter)  counter.textContent  = (current + 1) + ' / ' + total;
  }

  function go(n) {
    if (n < 0 || n >= total || busy) return;
    busy = true;
    slides[current].classList.add('exit-up');
    slides[current].classList.remove('active');
    current = n;
    slides[current].classList.add('active');
    slides[current].classList.remove('exit-up');
    update();
    setTimeout(function () { busy = false; }, 520);
  }

  // Space / Down: reveal next fragment, or advance slide when all done
  function forward() { if (!revealNext(current)) go(current + 1); }

  initFragments();
  update();

  // Space / ArrowDown : fragment-first forward
  // ArrowUp           : unreveal last fragment
  // ArrowRight        : next slide (skip fragments)
  // ArrowLeft         : prev slide (skip fragments)
  // PageDown          : next slide
  // PageUp            : prev slide
  document.addEventListener('keydown', function (e) {
    if (e.key === ' ' || e.key === 'ArrowDown') {
      e.preventDefault(); forward();
    } else if (e.key === 'ArrowUp') {
      e.preventDefault(); unrevealLast(current);
    } else if (e.key === 'ArrowRight' || e.key === 'PageDown') {
      e.preventDefault(); go(current + 1);
    } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
      e.preventDefault(); go(current - 1);
    } else if (e.key === 'Home') {
      e.preventDefault(); go(0);
    } else if (e.key === 'End') {
      e.preventDefault(); revealAll(total - 1); go(total - 1);
    }
  });

  var lastWheel = 0;
  document.addEventListener('wheel', function (e) {
    var now = Date.now();
    if (now - lastWheel < 550) return;
    lastWheel = now;
    if (e.deltaY > 0) forward(); else go(current - 1);
  }, { passive: true });

  var touchY = null;
  document.addEventListener('touchstart', function (e) { touchY = e.touches[0].clientY; }, { passive: true });
  document.addEventListener('touchend',   function (e) {
    if (touchY === null) return;
    var diff = touchY - e.changedTouches[0].clientY;
    if (Math.abs(diff) > 40) { if (diff > 0) forward(); else go(current - 1); }
    touchY = null;
  });

  window.goSlide = function (n) { revealAll(n); go(n); };
})();
```

---

## Step 4 — Create `index.html`

The index page has exactly **2 slides**:
1. **Hero slide**: title, subtitle, one-sentence description of the whole deck
2. **Index slide**: grid of clickable tiles, one per section

Tile markup pattern:
```html
<a href="slides/01-name.html" class="uc-tile" onclick="...">
  <div class="tile-icon">EMOJI</div>
  <div class="tile-num">01</div>
  <div class="tile-title">Section Title</div>
  <div class="tile-desc">One-line description</div>
</a>
```

The index slide needs CSS for the tile grid. Add these styles in a `<style>` block in index.html:
```css
.uc-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; width:100%; max-width:1280px; }
.uc-tile { background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; cursor:pointer; transition:all .2s; display:flex; flex-direction:column; gap:6px; }
.uc-tile:hover { border-color:var(--accent); background:var(--surface2); transform:translateY(-2px); }
.tile-icon { font-size:1.8em; line-height:1; }
.tile-num { font-size:.68em; color:var(--text-muted); font-family:'JetBrains Mono',monospace; font-weight:600; }
.tile-title { font-size:.9em; font-weight:700; color:var(--text); }
.tile-desc { font-size:.75em; color:var(--text-dim); line-height:1.4; }
```

---

## Step 5 — Create Each Section Deck (`slides/NN-name.html`)

### HTML Boilerplate (copy for every file)
```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>NN — Section Title | Deck Title</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../assets/style.css">
</head>
<body>
<div class="bg-grid"></div><div class="bg-glow g1"></div><div class="bg-glow g2"></div><div class="bg-glow g3"></div>
<div class="progress-bar"></div><div class="counter"></div>
<div class="nav-hint"><kbd>Space</kbd>/<kbd>↓</kbd> next &middot; <kbd>↑</kbd> back &middot; <kbd>←</kbd><kbd>→</kbd> slides</div>
<a href="../index.html" class="back-pill">&#8592; &nbsp;Back to Index</a>

<div class="deck">
  <!-- slides go here -->
</div>
<script src="../assets/deck.js"></script>
</body>
</html>
```

### Slide 0 — Title (no fragments)
```html
<div class="slide uc-title active">
  <div class="badge" style="background:rgba(R,G,B,.15);color:#HEXCOLOR">Section NN</div>
  <div class="uc-icon">EMOJI</div>
  <h1>Section Title</h1>
  <p class="uc-sub">One to two sentence description of what this section covers.</p>
</div>
```
Pick a color from the theme variables (`--sky`, `--rose`, `--teal`, `--indigo`, `--lime`, etc.) — use different colors per section.

### Slide 1 — Demo (split layout with steps + terminal)
```html
<div class="slide">
  <div class="split">
    <div class="split-left">
      <div class="badge" ...>Demo</div>
      <h2>Descriptive Title</h2>
      <p>Context paragraph explaining what's being shown.</p>
      <div class="steps">
        <div class="step" data-fragment><div class="step-num">1</div><div class="step-content"><h4>Step title</h4><p>Description</p></div></div>
        <div class="step" data-fragment>...</div>
        <div class="step" data-fragment>...</div>
      </div>
      <div class="tip-box" data-fragment>
        <span class="tip-icon">💡</span>
        <p><strong>Pro Tip:</strong> ...</p>
      </div>
    </div>
    <div class="split-right">
      <div class="terminal">
        <div class="terminal-bar"><div class="dots"><span></span><span></span><span></span></div><span class="term-title">tool-name — context</span></div>
        <div class="terminal-body">
          <!-- Group 1: user prompt + initial output -->
          <div class="line" data-fragment-group="t1"><span class="prompt">You: </span><span class="cmd">User's command here</span></div>
          <div class="blank" data-fragment-group="t1"></div>
          <div class="line" data-fragment-group="t1"><span class="info">Processing...</span></div>
          <!-- Group 2: main response -->
          <div class="blank" data-fragment-group="t2"></div>
          <div class="line" data-fragment-group="t2"><span class="success">Result:</span> <span class="output">Description</span></div>
          <div class="line" data-fragment-group="t2"><span class="output">  detail line</span></div>
          <!-- Group 3: conclusion -->
          <div class="blank" data-fragment-group="t3"></div>
          <div class="line" data-fragment-group="t3"><span class="success">  ✓ Success message</span></div>
        </div>
      </div>
    </div>
  </div>
</div>
```

### Slide 2 — Deep Dive (split or full-width)
Use split for comparison/before-after, or full-width for a code block + explanation side by side (`.cols-2`).

For code blocks (non-terminal):
```html
<div class="code-block" data-fragment>
  <div class="line"><span class="cmt">// comment</span></div>
  <div class="line">{</div>
  <div class="line">  <span class="key">"key"</span>: <span class="str">"value"</span></div>
  <div class="line">}</div>
</div>
```

### Slide 3 — Capabilities (full-width feature grid)
```html
<div class="slide">
  <div class="full-width">
    <div class="badge" ...>Capabilities</div>
    <h2>What You Can Do</h2>
    <div class="feat-grid">
      <div class="feat-card" data-fragment><h4>EMOJI Title</h4><p>Description with <code>example command</code> in it.</p></div>
      <!-- 6 cards total -->
    </div>
    <div class="tip-box" data-fragment style="margin-top:8px">
      <span class="tip-icon">💡</span>
      <p><strong>Key Insight:</strong> ...</p>
    </div>
  </div>
</div>
```

---

## Fragment Rules

- **Every `.step`** gets `data-fragment`
- **Every `.feat-card`** gets `data-fragment`
- **Every `.tip-box` and `.info-box`** gets `data-fragment`
- **Every standalone `.code-block`** (not a terminal) gets `data-fragment`
- **Terminal lines** are grouped by chat exchange using `data-fragment-group="t1"`, `"t2"`, `"t3"` etc.:
  - `t1`: user prompt + any "scanning/analyzing..." lines
  - `t2`: main response/output block
  - `t3`: follow-up response or conclusion
  - More groups if there are multiple back-and-forths
- **Title slides** (slide 0): NO fragments
- **Index slide tiles**: NO fragments

---

## Color Assignment for Section Badges

Rotate through these badge colors, one per section:
| Color var | hex | rgba for background |
|-----------|-----|---------------------|
| `--sky` | `#0ea5e9` | `rgba(14,165,233,.15)` |
| `--rose` | `#f43f5e` | `rgba(244,63,94,.15)` |
| `--teal` | `#14b8a6` | `rgba(20,184,166,.15)` |
| `--indigo` | `#6366f1` | `rgba(99,102,241,.15)` |
| `--lime` | `#84cc16` | `rgba(132,204,22,.15)` |
| `--orange` | `#f97316` | `rgba(249,115,22,.15)` |
| `--pink` | `#ec4899` | `rgba(236,72,153,.15)` |
| `--purple` | `#a855f7` | `rgba(168,85,247,.15)` |
| `--cyan` | `#06b6d4` | `rgba(6,182,212,.15)` |
| `--red` | `#ef4444` | `rgba(239,68,68,.15)` |

---

## Quality Checklist

Before finishing, verify:
- [ ] `index.html` tile grid has correct `href` for every section file
- [ ] Every section file has `class="slide uc-title active"` on slide 0 (the first one)
- [ ] No other slide has `active` on it initially
- [ ] Every `.step`, `.feat-card`, `.tip-box`, `.info-box` has `data-fragment`
- [ ] Terminal exchanges are split into logical `data-fragment-group` groups
- [ ] No orphan terminal lines without a fragment group (except always-visible header lines if desired)
- [ ] `assets/style.css` and `assets/deck.js` paths are correct relative to each file's location
- [ ] Terminal demos use realistic, concrete content (not generic placeholders)
- [ ] Each section has a unique badge color
