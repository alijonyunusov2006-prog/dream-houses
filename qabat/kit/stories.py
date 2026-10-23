# Картинки историй 1080×1920 для разделов «Актуального» Qabat. Тексты — data.STORIES, обложки — hl/A-*.png.
# Запуск: python3 stories.py <fonts.css> [bez-cen] → stories/ или stories-bez-cen/*.html, затем node render_stories.mjs → stories/*.jpg
import os, sys, base64, html
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import data
css = open(sys.argv[1]).read() if len(sys.argv) > 1 else ''
NOPRICE = len(sys.argv) > 2 and sys.argv[2] == 'bez-cen'
SRC = data.STORIES_NOPRICE if NOPRICE else data.STORIES
OUT = os.path.join(HERE, 'stories-bez-cen' if NOPRICE else 'stories')
os.makedirs(OUT, exist_ok=True)
names = {k: n for k, n, _ in data.HIGHLIGHTS}
DELIV = 'Самовывоз или доставка по Душанбе.'
for k in data.HIGHLIGHT_ORDER:
    text = SRC[k].replace('{deliv}', DELIV)
    lines = text.split('\n')
    title, body = ('Как заказать', lines[1:]) if k == 'zakaz' else (names[k], lines[1:] if lines[0].startswith('Лампы Qabat') else lines)
    ico = base64.b64encode(open(os.path.join(HERE, 'hl', f'A-{k}.png'), 'rb').read()).decode()
    rows = ''.join(f'<p>{html.escape(l)}</p>' for l in body)
    page = f'''<!doctype html><meta charset="utf-8"><style>{css}
html,body{{margin:0;width:1080px;height:1920px}}
body{{background:#FAFAF8;color:#1F2523;font-family:Inter,sans-serif;display:flex;flex-direction:column;align-items:center;box-sizing:border-box;padding:300px 96px 300px}}
.ico{{width:360px;height:360px;border-radius:50%;box-shadow:0 0 0 4px #E2F6EF}}
.tag{{margin-top:56px;font:600 34px Montserrat;letter-spacing:.2em;text-transform:uppercase;color:#1F7F69}}
h1{{margin:20px 0 0;font:700 104px/1.05 Montserrat;text-align:center;letter-spacing:-.01em}}
.rule{{width:140px;height:12px;border-radius:6px;background:#74DCC4;margin:52px 0 44px}}
.body{{display:flex;flex-direction:column;gap:22px;width:100%}}
.body p{{margin:0;font:500 46px/1.3 Inter;text-align:center}}
.foot{{margin-top:auto;padding-top:48px;display:flex;flex-direction:column;align-items:center;gap:12px}}
.foot b{{font:600 44px Montserrat;background:#74DCC4;color:#10201B;padding:22px 48px;border-radius:999px}}
.foot span{{font:500 32px Inter;color:#5E6965}}
</style>
<img class="ico" src="data:image/png;base64,{ico}"><div class="tag">Qabat · 3D-печать</div>
<h1>{html.escape(title)}</h1><div class="rule"></div><div class="body">{rows}</div>
<div class="foot"><b>Заказ — в Direct</b><span>Qabat · 3D-печать Душанбе</span></div>'''
    open(os.path.join(OUT, f'{k}.html'), 'w').write(page)
print('ok', len(data.HIGHLIGHT_ORDER))
