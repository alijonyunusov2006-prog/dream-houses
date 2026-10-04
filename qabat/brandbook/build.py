# Брендбук Qabat Print Lab — навык personal-brandbook, движок Chromium (HTML → PDF).
# Запуск: python3 build.py  → brandbook.html; затем node render.mjs → Qabat-брендбук.pdf
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from marks import avatar, full_logo, MINT, INK, PAPER

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

about = page(2, 'Кто мы', f'''
<p class="lead">Qabat — небольшая мастерская 3D-печати в Душанбе. Мы печатаем вещи, которые нужны людям дома, в подарок и в работе. Печатаем слой за слоем — поэтому и название: «қабат» по-таджикски значит «слой».</p>
<div class="grid2">
 <div><div class="label">Что делаем</div>
 <ul><li>лампы и ночники со светом внутри;</li><li>подарки и сувениры, именные брелоки;</li><li>игрушки и фиджеты;</li><li>декор: вазы, подставки, органайзеры;</li><li>восстановление деталей: нет детали или сломалась — смоделируем и напечатаем;</li><li>архитектурные макеты и печать по идее клиента.</li></ul></div>
 <div><div class="label">Миссия</div><p>Делать полезные и красивые вещи быстро и честно: понятная цена, реальный срок, аккуратная работа.</p>
 <div class="label">Слоган</div><p class="big">Слой за слоем</p>
 <div class="label">Характер</div><p>Минималистичный, светлый, спокойный. Уют и доверие вместо крика и скидок.</p></div>
</div>
<div class="note">Qabat — отдельный бренд. Его стиль и тексты не смешиваем с другими проектами владельца.</div>''')

aud = page(3, 'Для кого мы', '''
<div class="cards">
 <div class="card"><h3>Для себя и дома</h3><p><b>Нужно:</b> красивая и полезная вещь — лампа, ваза, органайзер.</p><p><b>Боится:</b> заплатить и получить кривую пластмассу.</p><p><b>Даём:</b> фото и видео реальных изделий, честный срок.</p></div>
 <div class="card"><h3>На подарок</h3><p><b>Нужно:</b> необычный подарок с именем, фото или номером машины.</p><p><b>Боится:</b> не успеть к празднику.</p><p><b>Даём:</b> срок называем сразу и держим, упаковка готова к вручению.</p></div>
 <div class="card"><h3>Компании и мероприятия</h3><p><b>Нужно:</b> сувениры с логотипом, подарки гостям на той, корпоративы.</p><p><b>Боится:</b> срыва партии и разного качества.</p><p><b>Даём:</b> образец до партии, график печати.</p></div>
 <div class="card"><h3>Мастера и архитекторы</h3><p><b>Нужно:</b> деталь, которую нигде не купить, или макет.</p><p><b>Боится:</b> что деталь не подойдёт по размеру.</p><p><b>Даём:</b> замер, модель, примерка — потом печать.</p></div>
</div>
<div class="label">Что их объединяет</div>
<p>Им нужна конкретная вещь, сделанная аккуратно и в срок. Они пишут в Instagram и хотят понятного ответа: цена, срок, как забрать.</p>''')

logo = page(4, 'Логотип', f'''
<div class="grid2 center">
 <div><div class="frame">{full_logo(width=300)}</div><div class="cap">Полный логотип — знак и надпись QABAT / PRINT LAB. Для упаковки, наклеек, визиток, обложек видео.</div></div>
 <div><div class="frame round">{avatar(size=300)}</div><div class="cap">Знак в круге — аватарка Instagram и Facebook, иконка, печать на изделиях.</div></div>
</div>
<div class="grid2">
 <div><div class="label">Правила</div><ul>
  <li>Вокруг логотипа — свободное поле не меньше высоты одного слоя стопки.</li>
  <li>Полный логотип — не мельче 30 мм в печати и 240 пикселей на экране.</li>
  <li>Фон — светлый или графитовый. На тёмном слои становятся белыми, мята остаётся.</li>
 </ul></div>
 <div><div class="label">Нельзя</div><ul class="no">
  <li>растягивать и сжимать;</li><li>менять цвета и добавлять тени, обводки, градиенты;</li><li>ставить на пёстрое фото без плашки;</li><li>переставлять надпись и знак.</li>
 </ul></div>
</div>
<div class="note">Знак в этом документе перерисован вектором по выбранному варианту. Основной файл логотипа — у владельца.</div>''')

def sw(name, hx, role, dark=False):
    return f'<div class="sw"><div class="chip" style="background:{hx};{"border:1px solid #ddd;" if not dark else ""}"></div><div><b>{name}</b> <span class="hex">{hx}</span><p>{role}</p></div></div>'
colors = page(5, 'Фирменные цвета', f'''
<p class="lead">Белый и мята: светло, свежо, современно. Мята — только акцент, не заливаем ею всё подряд.</p>
{sw("Мята", MINT, "Главный акцент: трубка и верхний слой знака, кнопки, обложки «Актуального», плашки с ценой.", True)}
{sw("Графит", INK, "Текст, знак, тёмный фон для контраста. Вместо чисто чёрного.", True)}
{sw("Тёплый белый", PAPER, "Фон страниц, постов и фото. Вместо чисто белого.")}
{sw("Светлая мята", LIGHT, "Подложки, кружки на обложках, фон карточек товара.")}
{sw("Тёмная мята", DEEP, "Ссылки и мелкий текст-акцент на белом — читается лучше, чем светлая мята.", True)}
{sw("Серый", GREY, "Подписи, второстепенный текст.", True)}
<div class="note">Мята логотипа снята с файла на глаз. Если в исходнике другой оттенок — сверим пипеткой и поправим код.</div>''')

typo = page(6, 'Шрифты', '''
<div class="tsample"><div class="mont" style="font-size:30pt;font-weight:600">Montserrat</div><p>Заголовки, цены, надписи на обложках. Близок к надписи QABAT. Начертания: Medium 500, SemiBold 600.</p>
<div class="mont" style="font-size:16pt;font-weight:600">Лампа «Луна» — 250 сомони</div><div class="mont" style="font-size:12pt;font-weight:500;letter-spacing:.18em">ҚАБАТ · СЛОЙ ЗА СЛОЕМ</div></div>
<div class="tsample"><div style="font-size:30pt;font-weight:600">Inter</div><p>Основной текст: описания, ответы, условия. Начертания: Regular 400, SemiBold 600.</p>
<p style="font-size:12pt">Напечатаем ваш номер машины на брелоке. Обычно — за один день. Забрать можно в студии или заказать доставку по Душанбе.</p>
<p style="font-size:12pt">Ҳарфҳои тоҷикӣ: ғ ӣ қ ӯ ҳ ҷ — Ғ Ӣ Қ Ӯ Ҳ Ҷ</p></div>
<div class="grid2"><div><div class="label">Где взять</div><p>Оба шрифта бесплатные (лицензия OFL), с кириллицей и таджикскими буквами. Есть в Canva, CapCut и Google Fonts.</p></div>
<div><div class="label">Правило</div><p>Не больше двух шрифтов. Заголовок — Montserrat, текст — Inter. Капслок — только для коротких надписей.</p></div></div>''')

voice = page(7, 'Голос бренда', '''
<div class="propose">Предложение JARVIS — поправьте голосом, пересоберу.</div>
<div class="grid2">
 <div><div class="label">Как говорим</div><ul>
 <li>На «вы», тепло и просто, коротко.</li><li>Сначала главное: цена, срок, как получить.</li><li>Пишем на языке клиента: русский или тоҷикӣ.</li><li>Только правду о сроке и наличии. Не уверены — говорим «уточню у мастера».</li></ul></div>
 <div><div class="label">Чего не говорим</div><ul class="no">
 <li>«Лучшие цены в городе!!!», «Срочно! Только сегодня!»</li><li>«Готово» — пока вещь не напечатана и не проверена.</li><li>«Будет через час» без проверки очереди.</li><li>Канцелярит и споры с клиентом.</li></ul></div>
</div>
<div class="label">Примеры</div>
<div class="quote">Напечатаем ваш номер на брелоке. Обычно за день — точный срок скажу после проверки очереди.</div>
<div class="quote">Сломалась деталь? Пришлите фото и размеры — смоделируем и напечатаем.</div>
<div class="quote">Лампа «Луна» есть в наличии: 3 штуки, 250 сомони. Забрать можно сегодня до 19:00.</div>
<div class="quote">Салом! Брелок бо рақами мошин — 40 сомонӣ. Одатан дар як рӯз тайёр мекунем.</div>
<div class="note">Таджикские фразы проверяет владелец, прежде чем бот начнёт их писать.</div>''')

values = page(8, 'Ценности и контакты', '''
<div class="propose">Ценности — предложение JARVIS. Контакты впишите сами.</div>
<div class="values">
 <div class="v"><span>1</span><div><b>Честность.</b> Цена и срок — как есть. Не обещаем то, чего не проверили.</div></div>
 <div class="v"><span>2</span><div><b>Аккуратность.</b> Каждый слой и каждая упаковка — чтобы не стыдно было подарить.</div></div>
 <div class="v"><span>3</span><div><b>Польза.</b> Печатаем вещи, которыми пользуются, а не пылесборники.</div></div>
 <div class="v"><span>4</span><div><b>Уют.</b> Тёплый свет, мягкие формы, спокойные цвета.</div></div>
 <div class="v"><span>5</span><div><b>Решаем задачу.</b> Нет нужной детали — придумаем и сделаем.</div></div>
</div>
<div class="label">Контакты</div>
<table class="contacts">
<tr><td>Instagram</td><td>@______________ (варианты: @qabat, @qabat.tj, @qabat.print, @qabatprintlab)</td></tr>
<tr><td>Facebook</td><td>Qabat — 3D-печать</td></tr>
<tr><td>WhatsApp / Telegram</td><td>+992 ___ __ __ __</td></tr>
<tr><td>Адрес</td><td>Душанбе, ____________________</td></tr>
<tr><td>Часы работы</td><td>____________________</td></tr>
</table>''')

insta = page(9, 'Стиль в Instagram', f'''
<div class="grid2">
 <div><div class="label">Фото и видео</div><ul>
 <li>Светлый фон, дневной свет или лайтбокс.</li><li>Одна вещь в кадре, рядом — рука или предмет для масштаба.</li><li>Мятный акцент в кадре: подставка, бумага, лента.</li><li>Reels: таймлапс печати, «до и после», как вещь работает.</li><li>Обложки Reels: название товара шрифтом Montserrat на тёплом белом.</li></ul></div>
 <div><div class="label">Сетка профиля</div><p>Чередуем: товар крупно → процесс печати → вещь в интерьере. Каждый третий пост — видео.</p>
 <div class="label">Подписи</div><p>Первая строка — что это и цена. Дальше: срок, цвета, как заказать. 3–5 хештегов.</p></div>
</div>
<div class="label">Обложки «Актуального»</div>
<div class="hl">{''.join(f'<div><img src="../kit/hl/A-{k}.png"><span>{n}</span></div>' for k,n in [("lampy","Лампы"),("igrushki","Игрушки"),("breloki","Брелоки"),("podarki","Подарки"),("dekor","Декор"),("process","Процесс"),("detali","Детали"),("otzyvy","Отзывы"),("zakaz","Заказ")])}</div>''')

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
