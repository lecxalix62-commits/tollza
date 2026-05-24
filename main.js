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

/* ===================================================================
   11. ИГРА: «Поймай комментарий»
   Тулза-кликер — падающие иконки ВК. Кликай хорошие, не задевай баны.
=================================================================== */
(function tulzaGame() {
  const canvas = document.getElementById('g-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const stage = document.getElementById('g-stage');
  const overlay = document.getElementById('g-overlay');
  const titleEl = document.getElementById('g-title');
  const descEl = document.getElementById('g-desc');
  const startBtn = document.getElementById('g-start');
  const scoreEl = document.getElementById('g-score');
  const comboEl = document.getElementById('g-combo');
  const timeEl = document.getElementById('g-time');
  const bestEl = document.getElementById('g-best');

  const W = canvas.width, H = canvas.height;

  // Поддержка high-DPI: масштабируем при необходимости
  function fitCanvas() {
    const rect = stage.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    canvas.width  = Math.round(rect.width  * dpr);
    canvas.height = Math.round(rect.height * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  fitCanvas();
  window.addEventListener('resize', fitCanvas);

  // Типы целей (с весами для генерации)
  const TYPES = [
    { kind: 'heart', emoji: '♥', color: '#ff6b85', value: 10, weight: 5, size: 38 },
    { kind: 'msg',   emoji: '💬', color: '#9bd17a', value: 15, weight: 4, size: 40 },
    { kind: 'mail',  emoji: '✉',  color: '#c8ec9c', value: 25, weight: 2, size: 42 },
    { kind: 'ban',   emoji: '🚫', color: '#ff8068', value: -20, weight: 2, size: 42, bad: true },
  ];
  const TOTAL_WEIGHT = TYPES.reduce((s, t) => s + t.weight, 0);

  function pickType() {
    let r = Math.random() * TOTAL_WEIGHT;
    for (const t of TYPES) { if ((r -= t.weight) <= 0) return t; }
    return TYPES[0];
  }

  let entities = [];
  let particles = [];
  let score = 0;
  let combo = 1;
  let comboStreak = 0;
  let timeLeft = 30;
  let lastSpawn = 0;
  let spawnInterval = 700;
  let running = false;
  let last = 0;
  let timerHandle = null;

  let best = parseInt(localStorage.getItem('tulza_best') || '0', 10);
  bestEl.textContent = best;

  function spawn() {
    const type = pickType();
    const cssW = canvas.clientWidth || W;
    const cssH = canvas.clientHeight || H;
    entities.push({
      type,
      x: 40 + Math.random() * (cssW - 80),
      y: -40,
      vx: (Math.random() - 0.5) * 60,
      vy: 90 + Math.random() * 90,
      rot: (Math.random() - 0.5) * 0.4,
      vrot: (Math.random() - 0.5) * 1.2,
      r: type.size / 2,
      alive: true,
      born: performance.now(),
    });
  }

  function addParticles(x, y, color, count = 12) {
    for (let i = 0; i < count; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = 80 + Math.random() * 180;
      particles.push({
        x, y,
        vx: Math.cos(a) * s,
        vy: Math.sin(a) * s,
        life: 0.6 + Math.random() * 0.4,
        age: 0,
        color,
        size: 2 + Math.random() * 3,
      });
    }
  }

  function showPop(x, y, text, isMinus) {
    const el = document.createElement('div');
    el.className = 'score-pop' + (isMinus ? ' minus' : '');
    el.textContent = text;
    // координаты в css-пикселях относительно stage
    const rect = stage.getBoundingClientRect();
    const scale = rect.width / (canvas.clientWidth || W);
    el.style.left = (x * scale) + 'px';
    el.style.top  = (y * scale) + 'px';
    stage.appendChild(el);
    setTimeout(() => el.remove(), 900);
  }

  function drawEntity(e) {
    ctx.save();
    ctx.translate(e.x, e.y);
    ctx.rotate(e.rot);
    // glow
    ctx.shadowColor = e.type.color;
    ctx.shadowBlur = 22;
    // фон-кружок
    const grad = ctx.createRadialGradient(0, 0, 0, 0, 0, e.r * 1.4);
    grad.addColorStop(0, e.type.color + 'cc');
    grad.addColorStop(1, e.type.color + '00');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(0, 0, e.r * 1.4, 0, Math.PI * 2);
    ctx.fill();
    // emoji
    ctx.shadowBlur = 6;
    ctx.font = `${e.type.size}px "Apple Color Emoji","Segoe UI Emoji","Noto Color Emoji",system-ui`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#fff';
    ctx.fillText(e.type.emoji, 0, 2);
    ctx.restore();
  }

  function drawParticle(p) {
    const a = 1 - (p.age / p.life);
    ctx.globalAlpha = a;
    ctx.fillStyle = p.color;
    ctx.shadowColor = p.color;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
    ctx.fill();
    ctx.globalAlpha = 1;
    ctx.shadowBlur = 0;
  }

  function loop(now) {
    if (!running) return;
    const dt = Math.min(0.06, (now - last) / 1000);
    last = now;

    const cssW = canvas.clientWidth || W;
    const cssH = canvas.clientHeight || H;
    ctx.clearRect(0, 0, cssW, cssH);

    // Spawn
    if (now - lastSpawn > spawnInterval) {
      spawn();
      lastSpawn = now;
      spawnInterval = Math.max(280, 700 - (30 - timeLeft) * 14);
    }

    // Entities
    for (const e of entities) {
      if (!e.alive) continue;
      e.x += e.vx * dt;
      e.y += e.vy * dt;
      e.rot += e.vrot * dt;
      // bounce off side walls
      if (e.x < e.r) { e.x = e.r; e.vx *= -1; }
      if (e.x > cssW - e.r) { e.x = cssW - e.r; e.vx *= -1; }
      // упал — пропускаем
      if (e.y > cssH + 60) {
        e.alive = false;
        if (!e.type.bad) {
          combo = 1;
          comboStreak = 0;
          comboEl.textContent = '×1';
        }
      } else {
        drawEntity(e);
      }
    }
    entities = entities.filter(e => e.alive);

    // Particles
    for (const p of particles) {
      p.age += dt;
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.vy += 220 * dt; // gravity
      drawParticle(p);
    }
    particles = particles.filter(p => p.age < p.life);

    requestAnimationFrame(loop);
  }

  function endGame() {
    running = false;
    clearInterval(timerHandle);
    overlay.classList.remove('hidden');
    titleEl.textContent = 'Время вышло';
    descEl.innerHTML = `Ваш результат: <strong style="color:var(--moss-lt);">${score}</strong> очков<br>${score > best ? '🌿 Новый рекорд!' : `Рекорд: ${best}`}`;
    startBtn.querySelector('span').textContent = 'Сыграть ещё';

    if (score > best) {
      best = score;
      localStorage.setItem('tulza_best', String(best));
      bestEl.textContent = best;
    }
  }

  function startGame() {
    score = 0;
    combo = 1;
    comboStreak = 0;
    timeLeft = 30;
    entities = [];
    particles = [];
    lastSpawn = 0;
    spawnInterval = 700;
    scoreEl.textContent = '0';
    comboEl.textContent = '×1';
    timeEl.textContent = '30';
    overlay.classList.add('hidden');
    running = true;
    last = performance.now();
    requestAnimationFrame((t) => { last = t; loop(t); });

    clearInterval(timerHandle);
    timerHandle = setInterval(() => {
      timeLeft -= 1;
      timeEl.textContent = timeLeft;
      if (timeLeft <= 0) endGame();
    }, 1000);
  }

  // Клик/тач по канвасу
  function handleHit(clientX, clientY) {
    if (!running) return;
    const rect = canvas.getBoundingClientRect();
    const scale = (canvas.clientWidth || W) / rect.width;
    const x = (clientX - rect.left) * scale;
    const y = (clientY - rect.top)  * scale;

    // ищем ближайшую цель в радиусе
    let best = null, bestDist = Infinity;
    for (const e of entities) {
      if (!e.alive) continue;
      const dx = e.x - x, dy = e.y - y;
      const d2 = dx*dx + dy*dy;
      const hitR = e.r * 1.5;
      if (d2 < hitR * hitR && d2 < bestDist) {
        best = e;
        bestDist = d2;
      }
    }
    if (!best) {
      // мисклик — мягкий штраф к комбо
      combo = 1;
      comboStreak = 0;
      comboEl.textContent = '×1';
      return;
    }

    best.alive = false;
    addParticles(best.x, best.y, best.type.color, best.type.bad ? 16 : 12);

    if (best.type.bad) {
      score = Math.max(0, score + best.type.value);
      combo = 1;
      comboStreak = 0;
      comboEl.textContent = '×1';
      showPop(best.x, best.y, `${best.type.value}`, true);
    } else {
      comboStreak += 1;
      if (comboStreak % 3 === 0) {
        combo = Math.min(5, combo + 1);
        comboEl.textContent = '×' + combo;
        comboEl.classList.add('flash');
        setTimeout(() => comboEl.classList.remove('flash'), 220);
      }
      const gain = best.type.value * combo;
      score += gain;
      showPop(best.x, best.y, `+${gain}`, false);
    }
    scoreEl.textContent = score;
  }

  canvas.addEventListener('pointerdown', (e) => handleHit(e.clientX, e.clientY));

  startBtn.addEventListener('click', startGame);
})();
