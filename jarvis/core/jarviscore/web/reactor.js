/* Реактор JARVIS — кольца, как у Джарвиса из «Железного человека» (по образцу владельца 2026-10-20).
   Один рисовальщик на все три вида окна: «Джарвис» на весь экран, «Уголок», «Рабочий стол».
   state: {level 0..1 (голос), work bool, flash 0..1 (новый ответ), listen bool, label строка в центре} */
(function () {
  const TAU = Math.PI * 2, CY = "0,229,255", AMB = "255,176,46";
  const rgba = (c, a) => `rgba(${c},${a})`;

  function arc(g, cx, cy, r, a0, a1, w, color, alpha) {
    g.strokeStyle = rgba(color, alpha); g.lineWidth = w;
    g.beginPath(); g.arc(cx, cy, r, a0, a1); g.stroke();
  }

  function ticks(g, cx, cy, r, n, len, rot, alpha, every) {
    for (let i = 0; i < n; i++) {
      const a = i / n * TAU + rot, long = i % every === 0, l = long ? len * 1.7 : len;
      g.strokeStyle = rgba(CY, long ? alpha : alpha * .55); g.lineWidth = long ? 2.2 : 1.4;
      g.beginPath(); g.moveTo(cx + Math.cos(a) * r, cy + Math.sin(a) * r);
      g.lineTo(cx + Math.cos(a) * (r - l), cy + Math.sin(a) * (r - l)); g.stroke();
    }
  }

  function draw(g, W, H, st, t) {
    const cx = W / 2, cy = H / 2, R = Math.min(W, H) * .46, lv = st.level || 0, fl = st.flash || 0;
    const sp = st.work ? 1 : .25;
    g.save();
    g.shadowColor = rgba(CY, .9); g.shadowBlur = R * .05;
    // внешнее тонкое кольцо с «замками» по бокам
    arc(g, cx, cy, R, 0, TAU, R * .006, CY, .75);
    for (const a of [0, Math.PI]) {
      g.fillStyle = rgba(CY, .7);
      for (let k = -3; k <= 3; k++) {
        const aa = a + k * .022;
        g.fillRect(cx + Math.cos(aa) * (R - R * .02) - 2, cy + Math.sin(aa) * (R - R * .02) - 2, 4, 4);
      }
    }
    arc(g, cx, cy, R * .965, -.9 + t * .03, .4 + t * .03, R * .012, CY, .5);
    arc(g, cx, cy, R * .965, 2.2 + t * .03, 3.3 + t * .03, R * .012, CY, .5);
    // шкала с делениями
    ticks(g, cx, cy, R * .9, 72, R * .045, -t * .02 * (st.work ? 3 : 1), .9, 6);
    // толстая голубая полоса — главный «обод», светится от голоса
    g.shadowBlur = R * .04;
    const band = R * .1, rb = R * .7;
    arc(g, cx, cy, rb, 0, TAU, band, CY, .22 + lv * .5 + fl * .2);
    for (let i = 0; i < 36; i++) {                               // деления на полосе
      const a = i / 36 * TAU + t * .05 * sp;
      g.strokeStyle = rgba(CY, .35); g.lineWidth = 1;
      g.beginPath(); g.moveTo(cx + Math.cos(a) * (rb - band / 2), cy + Math.sin(a) * (rb - band / 2));
      g.lineTo(cx + Math.cos(a) * (rb + band / 2), cy + Math.sin(a) * (rb + band / 2)); g.stroke();
    }
    arc(g, cx, cy, rb + band / 2, 0, TAU, 1.5, CY, .6);
    arc(g, cx, cy, rb - band / 2, 0, TAU, 1.5, CY, .6);
    // сегменты, бегущие по полосе — быстрее, когда работает
    for (let k = 0; k < 3; k++) {
      const s = t * sp * 1.4 + k * TAU / 3;
      arc(g, cx, cy, rb, s, s + .35 + lv, band * .55, CY, .55 + lv * .4);
    }
    // янтарная дуга слева и янтарные точки сверху
    g.shadowColor = rgba(AMB, .9);
    const amb0 = Math.PI * .78 + Math.sin(t * sp) * .08;
    arc(g, cx, cy, R * .6, amb0, amb0 + .55 + (st.work ? Math.abs(Math.sin(t * 2)) * .4 : 0), R * .018, AMB, .95);
    g.strokeStyle = rgba(AMB, .9); g.lineWidth = 2;
    g.strokeRect(cx + Math.cos(Math.PI * .92) * R * .63 - R * .03, cy + Math.sin(Math.PI * .92) * R * .63, R * .045, R * .12);
    for (let i = 0; i < 5; i++) {
      const a = -Math.PI / 2 - .32 + i * .16 + Math.sin(t * .8) * .02;
      g.fillStyle = rgba(AMB, .55 + .45 * Math.abs(Math.sin(t * 2 + i)));
      g.beginPath(); g.arc(cx + Math.cos(a) * R * .62, cy + Math.sin(a) * R * .62, R * .012, 0, TAU); g.fill();
    }
    // внутренние кольца
    g.shadowColor = rgba(CY, .9);
    arc(g, cx, cy, R * .53, 0, TAU, R * .028, CY, .85 + fl * .15);
    arc(g, cx, cy, R * .485, 0, TAU, 1.2, CY, .55);
    for (let k = 0; k < 4; k++) { const s = -t * sp * .9 + k * TAU / 4; arc(g, cx, cy, R * .45, s, s + .9, 2, CY, .5); }
    // голос: лучи внутрь от внутреннего кольца
    if (lv > .02) {
      for (let i = 0; i < 90; i++) {
        const a = i / 90 * TAU, h = R * lv * (.05 + .12 * Math.abs(Math.sin(i * 1.3 + t * 11)));
        g.strokeStyle = rgba(CY, .7); g.lineWidth = 1.6; g.beginPath();
        g.moveTo(cx + Math.cos(a) * R * .44, cy + Math.sin(a) * R * .44);
        g.lineTo(cx + Math.cos(a) * (R * .44 - h), cy + Math.sin(a) * (R * .44 - h)); g.stroke();
      }
    }
    // надпись в центре
    const label = st.label || "J.A.R.V.I.S.";
    g.shadowBlur = R * .06; g.shadowColor = rgba(CY, 1);
    g.fillStyle = `rgba(240,252,255,${.92 + fl * .08})`;
    g.textAlign = "center"; g.textBaseline = "middle";
    let fs = R * .13; g.font = `600 ${fs}px Rajdhani, "Segoe UI", sans-serif`;
    while (g.measureText(label).width > R * .8 && fs > 8) { fs *= .92; g.font = `600 ${fs}px Rajdhani, "Segoe UI", sans-serif`; }
    g.fillText(label, cx, cy);
    if (st.listen) { g.font = `500 ${R * .045}px Rajdhani, sans-serif`; g.fillStyle = rgba(AMB, .9); g.fillText("СЛУШАЮ", cx, cy + R * .16); }
    else if (st.work) { g.font = `500 ${R * .045}px Rajdhani, sans-serif`; g.fillStyle = rgba(CY, .8); g.fillText("РАБОТАЮ", cx, cy + R * .16); }
    g.restore();
  }

  /* фон «чертежи»: рисуется один раз в отдельный слой */
  function blueprint(W, H, seed = 7) {
    const c = document.createElement("canvas"); c.width = Math.max(1, W); c.height = Math.max(1, H);
    const g = c.getContext("2d");
    let s = seed; const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
    g.strokeStyle = "rgba(90,190,230,.10)"; g.lineWidth = 1;
    for (let x = 0; x < W; x += 32) { g.beginPath(); g.moveTo(x, 0); g.lineTo(x, H); g.stroke(); }
    for (let y = 0; y < H; y += 32) { g.beginPath(); g.moveTo(0, y); g.lineTo(W, y); g.stroke(); }
    g.strokeStyle = "rgba(120,210,245,.16)";
    for (let i = 0; i < 70; i++) {                       // планы, рамки, оси — как листы чертежей
      const x = rnd() * W, y = rnd() * H, w = 30 + rnd() * 220, h = 20 + rnd() * 160;
      const k = rnd();
      if (k < .45) g.strokeRect(x, y, w, h);
      else if (k < .7) { g.beginPath(); g.arc(x, y, h / 2, 0, TAU); g.stroke(); g.beginPath(); g.moveTo(x - h / 2 - 8, y); g.lineTo(x + h / 2 + 8, y); g.moveTo(x, y - h / 2 - 8); g.lineTo(x, y + h / 2 + 8); g.stroke(); }
      else { g.beginPath(); g.moveTo(x, y); g.lineTo(x + w, y); g.stroke();
        for (let j = 0; j <= 4; j++) { g.beginPath(); g.moveTo(x + w * j / 4, y - 4); g.lineTo(x + w * j / 4, y + 4); g.stroke(); } }
    }
    g.fillStyle = "rgba(120,210,245,.18)"; g.font = "10px 'IBM Plex Mono', monospace";
    for (let i = 0; i < 26; i++) g.fillText(["A-1", "1:100", "Ø 240", "±0.000", "+3.300", "14 500", "R 1200", "СЕК. 2"][i % 8], rnd() * W, rnd() * H);
    return c;
  }

  window.Reactor = {draw, blueprint};
})();
