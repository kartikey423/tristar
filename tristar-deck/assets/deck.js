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
