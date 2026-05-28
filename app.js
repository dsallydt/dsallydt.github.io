(async function () {
  const res = await fetch('manifest.json', { cache: 'no-cache' });
  const photos = await res.json();

  const nightCount = photos.filter(p => p.is_night).length;
  const title = nightCount + ' Nights on the Charles';
  document.getElementById('title').textContent = title;
  document.getElementById('subtitle').textContent = 'and a few days';
  document.title = title;

  const stage = document.getElementById('stage');
  const caption = document.getElementById('caption');
  const counter = document.getElementById('counter');
  const grid = document.getElementById('grid');
  const prev = document.getElementById('prev');
  const next = document.getElementById('next');

  // Carousel: lazy-build slide elements; only show one at a time.
  const slides = photos.map((p, i) => {
    const img = document.createElement('img');
    img.alt = '';
    img.dataset.src = 'images/web/' + p.file;
    if (i === 0) img.src = img.dataset.src;
    stage.appendChild(img);
    return img;
  });

  function fmtDate(iso) {
    const d = new Date(iso);
    if (isNaN(d)) return iso;
    const date = d.toLocaleDateString(undefined, { year: 'numeric', month: 'long', day: 'numeric' });
    const time = d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    return date + ' · ' + time;
  }

  let idx = 0;
  function show(i) {
    idx = (i + photos.length) % photos.length;
    slides.forEach((el, j) => el.classList.toggle('active', j === idx));
    // Lazy load current + neighbors
    [idx - 1, idx, idx + 1].forEach(k => {
      const n = (k + photos.length) % photos.length;
      const el = slides[n];
      if (!el.src) el.src = el.dataset.src;
    });
    renderCaption(photos[idx]);
    counter.textContent = (idx + 1) + ' / ' + photos.length;
  }

  function renderCaption(p) {
    caption.replaceChildren();
    caption.append(fmtDate(p.date));
    if (p.weather) {
      caption.append(document.createElement('br'));
      const w = document.createElement('span');
      w.className = 'weather';
      w.textContent = p.weather;
      caption.append(w);
    }
    if (p.caption) {
      const n = document.createElement('span');
      n.className = 'note';
      n.textContent = p.caption;
      caption.append(n);
    }
  }

  prev.addEventListener('click', () => show(idx - 1));
  next.addEventListener('click', () => show(idx + 1));
  document.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowLeft') show(idx - 1);
    if (e.key === 'ArrowRight') show(idx + 1);
  });

  // Swipe support
  let touchX = null;
  stage.addEventListener('touchstart', (e) => { touchX = e.touches[0].clientX; }, { passive: true });
  stage.addEventListener('touchend', (e) => {
    if (touchX === null) return;
    const dx = e.changedTouches[0].clientX - touchX;
    if (Math.abs(dx) > 40) show(idx + (dx < 0 ? 1 : -1));
    touchX = null;
  });

  show(0);

  // Grid
  photos.forEach((p, i) => {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.setAttribute('aria-label', fmtDate(p.date));
    btn.addEventListener('click', () => {
      show(i);
      document.querySelector('.carousel').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
    const img = document.createElement('img');
    img.loading = 'lazy';
    img.src = 'images/thumb/' + p.file;
    img.alt = '';
    btn.appendChild(img);
    grid.appendChild(btn);
  });
})();
