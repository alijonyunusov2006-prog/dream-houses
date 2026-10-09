# Брендбук Qabat Print Lab — навык personal-brandbook, движок Chromium (HTML → PDF).
# Запуск: python3 build.py  → brandbook.html; затем node render.mjs → Qabat-брендбук.pdf
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from marks import avatar, avatar_full, full_logo, MINT, INK, PAPER

FONTS = sys.argv[1] if len(sys.argv) > 1 else 'fonts.css'
css_fonts = open(FONTS).read() if os.path.exists(FONTS) else ''

DEEP = "#1F7F69"; LIGHT = "#E2F6EF"; GREY = "#6B7471"

def page(n, title, body, cls=''):
    return f'''<section class="page {cls}">
<div class="head"><span class="hn">{n:02d}</span><h2>{title}</h2></div>
{body}
<div class="footer"><span>Qabat Print Lab</span><span>Слой за слоем</span><span>{n}</span></div>
</section>'''

cover = f'''<section class="page cover">
<div class="kicker">БРЕНДБУК · ВЕРСИЯ 1</div>
<div class="cover-logo">{full_logo(width=520)}</div>
<div class="slogan">Слой за слоем</div>
<div class="pos">3D-печать в Душанбе: лампы, подарки, игрушки,<br>детали и макеты на заказ</div>
<div class="year">2026</div>
</section>'''

import content as C
li = lambda xs: ''.join(f'<li>{x}</li>' for x in xs)
A = C.ABOUT
about = page(2, 'Кто мы', f"""
<p class="lead">{A['lead']}</p>
<div class="grid2">
 <div><div class="label">Что делаем</div><ul>{li(A['what'])}</ul></div>
 <div><div class="label">Миссия</div><p>{A['mission']}</p>
 <div class="label">Слоган</div><p class="big">{A['slogan']}</p>
 <div class="label">Характер</div><p>{A['character']}</p></div>
</div>
<div class="note">{A['note']}</div>""")

aud = page(3, 'Для кого мы', '<div class="cards">' + ''.join(
    f'<div class="card"><h3>{t}</h3><p><b>Нужно:</b> {n}</p><p><b>Боится:</b> {f}</p><p><b>Даём:</b> {g}</p></div>' for t, n, f, g in C.AUDIENCE)
    + f'</div><div class="label">Что их объединяет</div><p>{C.AUDIENCE_COMMON}</p>')

L = C.LOGO
logo = page(4, 'Логотип', f"""
<div class="grid2 center">
 <div><div class="frame">{full_logo(width=300)}</div><div class="cap">{L['full']}</div></div>
 <div><div class="frame round">{avatar_full(size=300)}</div><div class="cap">{L['avatar']} {L['mark']}</div></div>
</div>
<div class="grid2">
 <div><div class="label">Правила</div><ul>{li(L['rules'])}</ul></div>
 <div><div class="label">Нельзя</div><ul class="no">{li(L['no'])}</ul></div>
</div>
<div class="note">{L['note']}</div>""")

def sw(name, hx, role):
    edge = "border:1px solid #ddd;" if hx.upper() in (PAPER.upper(), "#E2F6EF") else ""
    return f'<div class="sw"><div class="chip" style="background:{hx};{edge}"></div><div><b>{name}</b> <span class="hex">{hx}</span><p>{role}</p></div></div>'
colors = page(5, 'Фирменные цвета', f'<p class="lead">{C.COLORS_LEAD}</p>' + ''.join(sw(*c) for c in C.COLORS) + f'<div class="note">{C.COLORS_NOTE}</div>')

F = C.FONTS
typo = page(6, 'Шрифты', f"""
<div class="tsample"><div class="mont" style="font-size:30pt;font-weight:600">{F['display'][0]}</div><p>{F['display'][1]}</p>
<div class="mont" style="font-size:16pt;font-weight:600">{F['sample_title']}</div><div class="mont" style="font-size:12pt;font-weight:500;letter-spacing:.18em">{F['sample_caps']}</div></div>
<div class="tsample"><div style="font-size:30pt;font-weight:600">{F['body'][0]}</div><p>{F['body'][1]}</p>
<p style="font-size:12pt">{F['sample_text']}</p>
<p style="font-size:12pt">{F['sample_tj']}</p></div>
<div class="grid2"><div><div class="label">Где взять</div><p>{F['where']}</p></div>
<div><div class="label">Правило</div><p>{F['rule']}</p></div></div>""")

V = C.VOICE
voice = page(7, 'Голос бренда', f"""
<div class="propose">{V['propose']}</div>
<div class="grid2">
 <div><div class="label">Как говорим</div><ul>{li(V['do'])}</ul></div>
 <div><div class="label">Чего не говорим</div><ul class="no">{li(V['dont'])}</ul></div>
</div>
<div class="label">Примеры</div>""" + ''.join(f'<div class="quote">{q}</div>' for q in V['examples']) + f'<div class="note">{V["note"]}</div>')

values = page(8, 'Ценности и контакты', f'<div class="propose">{C.VALUES_PROPOSE}</div><div class="values">' + ''.join(
    f'<div class="v"><span>{i}</span><div><b>{t}.</b> {w}</div></div>' for i, (t, w) in enumerate(C.VALUES, 1))
    + '</div><div class="label">Контакты</div><table class="contacts">' + ''.join(f'<tr><td>{k}</td><td>{v}</td></tr>' for k, v in C.CONTACTS) + '</table>')

I = C.INSTA
HL = [("lampy","Лампы"),("igrushki","Игрушки"),("breloki","Брелоки"),("podarki","Подарки"),("dekor","Декор"),("process","Процесс"),("detali","Детали"),("otzyvy","Отзывы"),("zakaz","Заказ")]
insta = page(9, 'Стиль в Instagram', f"""
<div class="grid2">
 <div><div class="label">Фото и видео</div><ul>{li(I['photo'])}</ul></div>
 <div><div class="label">Сетка профиля</div><p>{I['grid']}</p>
 <div class="label">Подписи</div><p>{I['captions']}</p></div>
</div>
<div class="label">Обложки «Актуального»</div>
<div class="hl">""" + ''.join(f'<div><img src="../kit/hl/A-{k}.png"><span>{n}</span></div>' for k, n in HL) + '</div>')

style = f'''
:root{{--mint:{MINT};--ink:{INK};--paper:{PAPER};--deep:{DEEP};--light:{LIGHT};--grey:{GREY}}}
body{{margin:0;font-family:Inter,sans-serif;color:var(--ink)}}
.page{{width:210mm;height:297mm;box-sizing:border-box;background:var(--paper);padding:20mm 18mm 22mm;position:relative;overflow:hidden}}
h2,h3,.mont,.slogan,.kicker,.hn{{font-family:Montserrat,sans-serif}}
.head{{display:flex;align-items:center;gap:5mm;border-bottom:1.2mm solid var(--mint);padding-bottom:4mm;margin-bottom:8mm}}
.hn{{font-weight:600;font-size:11pt;color:var(--deep);background:var(--light);border-radius:50%;width:11mm;height:11mm;display:flex;align-items:center;justify-content:center}}
h2{{margin:0;font-size:22pt;font-weight:600}}
h3{{margin:0 0 2mm;font-size:12.5pt;font-weight:600}}
p,li{{font-size:11.5pt;line-height:1.6;margin:0 0 3mm}}
ul{{padding-left:5mm;margin:0 0 3mm}} ul.no li::marker{{content:"✕  ";color:#c0504d}}
.lead{{font-size:14pt;line-height:1.55;margin-bottom:8mm}}
.big{{font-family:Montserrat;font-size:18pt;font-weight:600;color:var(--deep)}}
.label{{font-family:Montserrat;font-weight:600;font-size:9.5pt;letter-spacing:.14em;text-transform:uppercase;color:var(--deep);margin:5mm 0 2mm}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:9mm}}
.center{{text-align:center}}
.note{{position:absolute;left:18mm;right:18mm;bottom:28mm;font-size:9pt;color:var(--grey);border-left:1mm solid var(--mint);padding:1mm 0 1mm 4mm}}
.propose{{display:inline-block;background:var(--light);color:var(--deep);font-size:9pt;font-weight:600;padding:2mm 4mm;border-radius:10mm;margin-bottom:5mm}}
.footer{{position:absolute;left:18mm;right:18mm;bottom:11mm;display:flex;justify-content:space-between;font-size:8pt;color:var(--grey);border-top:.3mm solid #d9dedc;padding-top:3mm}}
.cover{{display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center}}
.cover .kicker{{position:absolute;top:22mm;letter-spacing:.32em;font-size:9pt;font-weight:600;color:var(--deep)}}
.cover .slogan{{font-size:20pt;font-weight:500;margin-top:-6mm}}
.cover .pos{{margin-top:6mm;font-size:11pt;color:var(--grey);line-height:1.6}}
.cover .year{{position:absolute;bottom:20mm;font-family:Montserrat;font-weight:600;color:var(--deep)}}
.cover-logo svg{{display:block}}
.cards{{display:grid;grid-template-columns:1fr 1fr;gap:6mm;margin-bottom:4mm}}
.card{{background:#fff;border-radius:4mm;padding:7mm 6mm;border-top:1.2mm solid var(--mint)}}
.card p{{font-size:10.8pt}}
.frame{{width:70mm;height:70mm;margin:0 auto 4mm;border-radius:4mm;overflow:hidden;box-shadow:0 0 0 .3mm #dfe3e1}}
.frame svg{{width:100%;height:100%}} .frame.round{{border-radius:50%}}
.cap{{font-size:10.5pt;color:var(--grey);line-height:1.5;margin-bottom:6mm}}
.sw{{display:flex;gap:6mm;align-items:center;margin-bottom:6mm}}
.chip{{width:28mm;height:20mm;border-radius:3mm;flex:0 0 auto}}
.sw p{{margin:1mm 0 0;font-size:11pt;color:#3b4441}} .hex{{font-family:Montserrat;font-weight:600;color:var(--deep);font-size:9pt;margin-left:2mm}}
.tsample{{background:#fff;border-radius:4mm;padding:8mm;margin-bottom:8mm}}
.quote{{border-left:1.2mm solid var(--mint);padding:1.5mm 0 1.5mm 5mm;margin:0 0 5mm;font-size:12pt;line-height:1.5}}
.values .v{{display:flex;gap:4mm;align-items:flex-start;margin-bottom:5.5mm;font-size:12pt;line-height:1.5}}
.values .v span{{flex:0 0 auto;width:8mm;height:8mm;border-radius:50%;background:var(--mint);color:var(--ink);font-family:Montserrat;font-weight:600;font-size:9.5pt;display:flex;align-items:center;justify-content:center}}
.contacts{{width:100%;border-collapse:collapse;font-size:11.5pt}} .contacts td{{padding:3.6mm 2mm;border-bottom:.3mm solid #dfe3e1}} .contacts td:first-child{{font-weight:600;width:42mm}}
.hl{{display:grid;grid-template-columns:repeat(5,1fr);gap:5mm 3mm;text-align:center}}
.hl img{{width:26mm;height:26mm;border-radius:50%;box-shadow:0 0 0 .4mm #e0e4e2}} .hl span{{display:block;font-size:10pt;margin-top:1.5mm}}
'''

html = f'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><title>Qabat — брендбук</title>
<style>{css_fonts}</style><style>{style}</style></head><body>
{cover}{about}{aud}{logo}{colors}{typo}{voice}{values}{insta}
</body></html>'''
open(os.path.join(os.path.dirname(__file__) or '.', 'brandbook.html'), 'w').write(html)
print('ok', len(html))
