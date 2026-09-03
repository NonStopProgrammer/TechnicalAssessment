/* Phoenix website — vanilla JS only, no external dependencies.
   1. Reveal-on-scroll for .rv elements (with a safety fallback so the
      page is never left blank on browsers where observers misbehave)
   2. Healing timeline lights up in sequence when visible
   3. Workflow Builder mock runs a looping "live run" simulation
   All animation respects prefers-reduced-motion. */

(function () {
  'use strict';

  var reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var each = function (list, fn) { Array.prototype.forEach.call(list, fn); };

  /* ---------- 1. reveal on scroll ---------- */
  var revealEls = document.querySelectorAll('.rv');
  var revealAll = function () { each(revealEls, function (el) { el.classList.add('on'); }); };
  var ioFired = false;

  if (reduceMotion || !('IntersectionObserver' in window)) {
    revealAll();
  } else {
    var io = new IntersectionObserver(function (entries) {
      ioFired = true;
      each(entries, function (en) {
        if (en.isIntersecting) { en.target.classList.add('on'); io.unobserve(en.target); }
      });
    }, { threshold: 0.12 });
    each(revealEls, function (el) { io.observe(el); });
    /* safety net: if the observer never fires (unusual browser/embedding),
       show everything rather than leaving the page blank */
    setTimeout(function () { if (!ioFired) { revealAll(); } }, 1500);
  }

  /* ---------- 2. healing timeline sequence ---------- */
  var timeline = document.getElementById('healTimeline');
  if (timeline) {
    var steps = timeline.querySelectorAll('.tstep');
    var lightUp = function () {
      each(steps, function (step, i) {
        setTimeout(function () { step.classList.add('lit'); }, reduceMotion ? 0 : 500 * i);
      });
    };
    if (reduceMotion || !('IntersectionObserver' in window)) {
      lightUp();
    } else {
      var tlDone = false;
      var tio = new IntersectionObserver(function (entries) {
        each(entries, function (en) {
          if (en.isIntersecting && !tlDone) { tlDone = true; lightUp(); tio.unobserve(en.target); }
        });
      }, { threshold: 0.35 });
      tio.observe(timeline);
      setTimeout(function () { if (!tlDone) { tlDone = true; lightUp(); } }, 4000);
    }
  }

  /* ---------- 3. builder run simulation ---------- */
  var mock = document.getElementById('builderMock');
  if (mock) {
    var nodes = mock.querySelectorAll('.node');
    var arrows = mock.querySelectorAll('.narrow');
    var statusBox = document.getElementById('mockStatus');
    var statusText = document.getElementById('mockText');
    var bar = document.getElementById('mockBar');

    var phases = [
      { node: 0, text: 'Reading ORDERS from oracle_crm — 42,318 new rows since last watermark', pct: 20 },
      { node: 1, text: 'Running SQL curation — standardize, enrich', pct: 45 },
      { node: 2, text: 'Data quality gate — 4 rules · 0 quarantined · counts reconcile', pct: 70 },
      { node: 3, text: 'Writing to BigQuery — overwrite_partition (idempotent)', pct: 92 }
    ];

    var setClass = function (el, cls, onOff) {
      if (onOff) { el.classList.add(cls); } else { el.classList.remove(cls); }
    };

    var setAll = function (state) {
      each(nodes, function (n) {
        n.classList.remove('running'); n.classList.remove('done');
        if (state) { n.classList.add(state); }
      });
      each(arrows, function (a) {
        a.classList.remove('done');
        if (state === 'done') { a.classList.add('done'); }
      });
    };

    if (reduceMotion) {
      /* static "completed run" view — no animation */
      setAll('done');
      statusBox.classList.add('done');
      statusText.textContent = 'Run complete — 42,318 rows · DQ passed · watermark committed';
      bar.style.width = '100%';
      return;
    }

    var phase = -1;
    var started = false;
    var tick = function () {
      phase += 1;
      if (phase < phases.length) {
        var p = phases[phase];
        each(nodes, function (n, i) {
          setClass(n, 'running', i === p.node);
          setClass(n, 'done', i < p.node);
        });
        each(arrows, function (a, i) { setClass(a, 'done', i < p.node); });
        statusBox.classList.add('running');
        statusBox.classList.remove('done');
        statusText.textContent = p.text;
        bar.style.width = p.pct + '%';
        setTimeout(tick, 2200);
      } else if (phase === phases.length) {
        setAll('done');
        statusBox.classList.remove('running');
        statusBox.classList.add('done');
        statusText.textContent = 'Run complete — 42,318 rows · DQ passed · watermark committed · audit written';
        bar.style.width = '100%';
        setTimeout(tick, 4200);
      } else {
        /* reset and loop */
        setAll(null);
        statusBox.classList.remove('done');
        statusText.textContent = 'Scheduled — next run triggered by AutoSys / Composer';
        bar.style.width = '0%';
        phase = -1;
        setTimeout(tick, 1800);
      }
    };
    var start = function () { if (!started) { started = true; tick(); } };

    /* start the simulation when the mock scrolls into view */
    if ('IntersectionObserver' in window) {
      var mio = new IntersectionObserver(function (entries) {
        each(entries, function (en) {
          if (en.isIntersecting) { start(); mio.unobserve(en.target); }
        });
      }, { threshold: 0.3 });
      mio.observe(mock);
      setTimeout(start, 5000);
    } else {
      start();
    }
  }
})();
