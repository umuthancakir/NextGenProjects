'use strict';

/* ══════════════════════════════════════════════════════════════
   Matrix rain
   ══════════════════════════════════════════════════════════════ */
(function () {
  const canvas = document.getElementById('matrix-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789@#$%&*<>/\\|_+-=';
  const FS = 13;
  let cols, drops;

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    cols  = Math.floor(canvas.width / FS);
    drops = new Array(cols).fill(1);
  }
  resize();
  window.addEventListener('resize', resize, { passive: true });

  function draw() {
    ctx.fillStyle = 'rgba(10,10,15,0.055)';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = `${FS}px JetBrains Mono, monospace`;
    for (let i = 0; i < cols; i++) {
      // Lead character is brighter
      ctx.fillStyle = '#ff6b78';
      ctx.fillText(CHARS[Math.floor(Math.random() * CHARS.length)], i * FS, drops[i] * FS);
      // Fade trailing characters
      ctx.fillStyle = '#e63946';
      if (drops[i] * FS > 20) {
        ctx.fillText(CHARS[Math.floor(Math.random() * CHARS.length)], i * FS, (drops[i] - 1) * FS);
      }
      if (drops[i] * FS > canvas.height && Math.random() > 0.974) drops[i] = 0;
      drops[i]++;
    }
  }
  setInterval(draw, 55);
})();


/* ══════════════════════════════════════════════════════════════
   Typing animation
   ══════════════════════════════════════════════════════════════ */
(function () {
  const el = document.getElementById('typing-text');
  if (!el) return;

  const TITLES = [
    'Cyber Security Expert',
    'Penetration Tester',
    'Digital Forensics Specialist',
    'MSc Cyber Security Student',
    'Red Team Operator',
  ];

  let ti = 0, ci = 0, deleting = false, hold = 0;

  function tick() {
    const word = TITLES[ti];

    if (!deleting) {
      el.textContent = word.slice(0, ++ci);
      if (ci === word.length) { deleting = true; hold = 55; }
    } else {
      if (hold-- > 0) { setTimeout(tick, 50); return; }
      el.textContent = word.slice(0, --ci);
      if (ci === 0) { deleting = false; ti = (ti + 1) % TITLES.length; }
    }

    setTimeout(tick, deleting ? 38 : 72);
  }

  setTimeout(tick, 900);
})();


/* ══════════════════════════════════════════════════════════════
   Navbar: shrink + red underline on scroll
   ══════════════════════════════════════════════════════════════ */
(function () {
  const nav = document.getElementById('navbar');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    nav.classList.toggle('scrolled', window.scrollY > 60);
  }, { passive: true });
})();


/* ══════════════════════════════════════════════════════════════
   Mobile nav toggle
   ══════════════════════════════════════════════════════════════ */
(function () {
  const btn   = document.getElementById('nav-toggle');
  const links = document.getElementById('nav-links');
  if (!btn || !links) return;

  btn.addEventListener('click', () => {
    const open = links.classList.toggle('open');
    btn.classList.toggle('open', open);
    btn.setAttribute('aria-expanded', open);
  });

  links.querySelectorAll('a').forEach(a =>
    a.addEventListener('click', () => {
      links.classList.remove('open');
      btn.classList.remove('open');
    })
  );
})();


/* ══════════════════════════════════════════════════════════════
   Hero photo: show placeholder if image fails to load
   ══════════════════════════════════════════════════════════════ */
(function () {
  const img   = document.getElementById('hero-img');
  const frame = document.getElementById('hex-frame');
  if (!img || !frame) return;

  function fallback() { frame.classList.add('no-photo'); }

  img.addEventListener('error', fallback);
  // If already in error state (cached failure)
  if (img.complete && img.naturalWidth === 0) fallback();
})();


/* ══════════════════════════════════════════════════════════════
   Intersection Observer: fade-in, counters, skill bars
   ══════════════════════════════════════════════════════════════ */
(function () {

  /* ── Fade-in elements ─────────────────────────────────────── */
  const fadeObs = new IntersectionObserver((entries) => {
    entries.forEach((e, i) => {
      if (!e.isIntersecting) return;
      // Stagger siblings slightly for a cascade effect
      setTimeout(() => e.target.classList.add('visible'), i * 70);
      fadeObs.unobserve(e.target);
    });
  }, { threshold: 0.12 });

  document.querySelectorAll('.fade-in').forEach(el => fadeObs.observe(el));


  /* ── Animated counters ────────────────────────────────────── */
  function runCounter(el) {
    const target = parseInt(el.dataset.target, 10);
    const suffix = el.dataset.suffix || '';
    const DURATION = 1700;
    const t0 = performance.now();

    function step(now) {
      const p = Math.min((now - t0) / DURATION, 1);
      const ease = 1 - Math.pow(1 - p, 3);       // cubic ease-out
      el.textContent = Math.floor(ease * target) + suffix;
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  const counterObs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      runCounter(e.target);
      counterObs.unobserve(e.target);
    });
  }, { threshold: 0.5 });

  document.querySelectorAll('.stat-val[data-target]').forEach(el => counterObs.observe(el));


  /* ── Skill bar fills ──────────────────────────────────────── */
  const barObs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      e.target.style.width = e.target.dataset.w + '%';
      barObs.unobserve(e.target);
    });
  }, { threshold: 0.4 });

  document.querySelectorAll('.sfill[data-w]').forEach(el => barObs.observe(el));

})();


/* ══════════════════════════════════════════════════════════════
   Contact form feedback
   ══════════════════════════════════════════════════════════════ */
function handleForm(e) {
  e.preventDefault();
  const fb   = document.getElementById('form-feedback');
  const name = document.getElementById('fname').value.trim();
  const mail = document.getElementById('femail').value.trim();
  const msg  = document.getElementById('fmsg').value.trim();

  if (!name || !mail || !msg) {
    fb.textContent = '⚠ Please fill in all fields.';
    fb.className   = 'form-feedback err';
    return;
  }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(mail)) {
    fb.textContent = '⚠ Please enter a valid email address.';
    fb.className   = 'form-feedback err';
    return;
  }

  fb.textContent = '✓ Message received — I\'ll be in touch soon!';
  fb.className   = 'form-feedback ok';
  e.target.reset();

  setTimeout(() => { fb.textContent = ''; fb.className = 'form-feedback'; }, 5000);
}


/* ══════════════════════════════════════════════════════════════
   Smooth active nav link highlight on scroll
   ══════════════════════════════════════════════════════════════ */
(function () {
  const sections = document.querySelectorAll('section[id]');
  const links    = document.querySelectorAll('.nav-links a');
  if (!sections.length || !links.length) return;

  const obs = new IntersectionObserver((entries) => {
    entries.forEach(e => {
      if (!e.isIntersecting) return;
      links.forEach(a => {
        a.style.color = a.getAttribute('href') === '#' + e.target.id
          ? 'var(--red)'
          : '';
      });
    });
  }, { threshold: 0.4 });

  sections.forEach(s => obs.observe(s));
})();
