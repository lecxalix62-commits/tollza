// =============================================================
// ТУЛЗА — анимации презентации
// =============================================================

/* ---------- 1. Споры (плавающие частицы) ---------- */
(function spawnSpores() {
  const wrap = document.getElementById('spores');
  if (!wrap) return;
  const COUNT = 28;
  for (let i = 0; i < COUNT; i++) {
    const s = document.createElement('span');
    s.className = 'spore';
    const size = Math.random() * 4 + 2;
    s.style.width = s.style.height = size + 'px';
    s.style.left = Math.random() * 100 + '%';
    s.style.animationDuration = (Math.random() * 18 + 16) + 's';
    s.style.animationDelay = -Math.random() * 30 + 's';
    s.style.setProperty('--dx', (Math.random() * 200 - 100) + 'px');
    s.style.opacity = (Math.random() * 0.5 + 0.3).toFixed(2);
    wrap.appendChild(s);
  }
})();

/* ---------- 2. Параллакс при скролле ---------- */
(function parallax() {
  const layers = [
    { el: document.querySelector('.layer-back'),  speed: 0.1 },
    { el: document.querySelector('.layer-mid'),   speed: 0.25 },
    { el: document.querySelector('.layer-front'), speed: 0.45 },
    { el: document.querySelector('.sunbeam'),     speed: -0.15 },
  ];
  let ticking = false;
  window.addEventListener('scroll', () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      const y = window.scrollY;
      layers.forEach(({ el, speed }) => {
        if (el) el.style.transform = `translateY(${y * speed}px)`;
      });
      ticking = false;
    });
  }, { passive: true });
})();

/* ---------- 3. Параллакс мыши на hero ---------- */
(function mouseParallax() {
  const hero = document.querySelector('.hero');
  const preview = document.querySelector('.preview-card');
  if (!hero || !preview) return;

  hero.addEventListener('mousemove', (e) => {
    const r = hero.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    preview.style.transform =
      `perspective(1200px) rotateY(${-6 + x * 6}deg) rotateX(${4 - y * 6}deg) translateZ(0)`;
  });
  hero.addEventListener('mouseleave', () => {
    preview.style.transform = 'perspective(1200px) rotateY(-6deg) rotateX(4deg)';
  });
})();

/* ---------- 4. Кнопки — «жидкое» свечение под курсором ---------- */
document.querySelectorAll('.btn-primary').forEach(btn => {
  btn.addEventListener('mousemove', (e) => {
    const r = btn.getBoundingClientRect();
    btn.style.setProperty('--mx', `${((e.clientX - r.left) / r.width) * 100}%`);
    btn.style.setProperty('--my', `${((e.clientY - r.top)  / r.height) * 100}%`);
  });
});

/* ---------- 5. Счётчики в hero ---------- */
(function counters() {
  const nums = document.querySelectorAll('.stat-num');
  const io = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      const el = entry.target;
      const target = parseInt(el.dataset.target, 10);
      const duration = 1800;
      const start = performance.now();
      function tick(now) {
        const p = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - p, 3);
        const val = Math.floor(target * eased);
        el.textContent = val.toLocaleString('ru-RU');
        if (p < 1) requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
      io.unobserve(el);
    });
  }, { threshold: 0.5 });
  nums.forEach(n => io.observe(n));
})();

/* ---------- 6. Шаги "How it works" — реактивное появление ---------- */
(function stepsReveal() {
  const steps = document.querySelectorAll('.step');
  const io = new IntersectionObserver((entries) => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        setTimeout(() => entry.target.classList.add('visible'), i * 120);
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.3 });
  steps.forEach(s => io.observe(s));
})();

/* ---------- 7. Терминал — печать запуска ТУЛЗЫ ---------- */
(function terminal() {
  const el = document.getElementById('terminal');
  if (!el) return;

  const lines = [
    { txt: '<span class="meta">[10:42:01]</span> запуск тулзы...', cls: '' },
    { txt: '<span class="arrow">→</span> авторизация ВКонтакте... <span class="ok">ok</span>', cls: '' },
    { txt: '<span class="arrow">→</span> загружаю сегмент "мамы 25-40, СПб"...', cls: '' },
    { txt: '   найдено <span class="ok">4 218</span> пользователей', cls: '' },
    { txt: '<span class="arrow">→</span> запускаю автокомментинг...', cls: '' },
    { txt: '   <span class="ok">✓</span> комментарий #1 опубликован', cls: '' },
    { txt: '   <span class="ok">✓</span> комментарий #2 опубликован', cls: '' },
    { txt: '   <span class="ok">✓</span> комментарий #3 опубликован', cls: '' },
    { txt: '<span class="arrow">→</span> запускаю авторассылку...', cls: '' },
    { txt: '   <span class="ok">✓</span> 28 сообщений в очереди', cls: '' },
    { txt: '   <span class="ok">✓</span> 5 ответов получено', cls: '' },
    { txt: '<span class="meta">[10:42:48]</span> ТУЛЗА растёт <span class="ok">●</span><span class="cursor"></span>', cls: '' },
  ];

  let i = 0;
  function next() {
    if (i >= lines.length) return;
    const span = document.createElement('span');
    span.className = 'line';
    span.innerHTML = lines[i].txt;
    el.appendChild(span);
    i++;
    setTimeout(next, 320 + Math.random() * 280);
  }
  // Запустить когда виден
  const io = new IntersectionObserver((entries) => {
    if (entries[0].isIntersecting) {
      next();
      io.disconnect();
    }
  });
  io.observe(el);
})();

/* ---------- 8. Плавная подсветка nav при скролле ---------- */
(function navTint() {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  window.addEventListener('scroll', () => {
    if (window.scrollY > 30) {
      nav.style.borderBottom = '1px solid rgba(155,209,122,0.1)';
    } else {
      nav.style.borderBottom = '0';
    }
  }, { passive: true });
})();

/* ---------- 9. Подкачивание мха — лёгкое колыхание травинок ---------- */
(function swayBlades() {
  const blades = document.querySelectorAll('.moss-blades .blade, .fern path');
  blades.forEach((b, i) => {
    b.style.transformOrigin = 'bottom';
    b.style.transformBox = 'fill-box';
    b.animate(
      [
        { transform: 'rotate(-2deg)' },
        { transform: 'rotate(2deg)' },
        { transform: 'rotate(-2deg)' },
      ],
      {
        duration: 3500 + (i % 5) * 500,
        iterations: Infinity,
        easing: 'ease-in-out',
        delay: (i * 80) % 1500,
      }
    );
  });
})();

/* ---------- 10. Капли росы — мерцание ---------- */
(function dew() {
  document.querySelectorAll('.dew circle').forEach((c, i) => {
    c.animate(
      [
        { opacity: 0.3, r: c.getAttribute('r') * 0.8 },
        { opacity: 1,   r: c.getAttribute('r') * 1.2 },
        { opacity: 0.3, r: c.getAttribute('r') * 0.8 },
      ],
      { duration: 2400 + i * 400, iterations: Infinity, easing: 'ease-in-out', delay: i * 300 }
    );
  });
})();
