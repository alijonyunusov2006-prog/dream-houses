# Собирает qabat/instagram-guide.html (артефакт «Qabat Instagram») из template.html и data.py
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(HERE, '..', 'brandbook'))
import data
from marks import avatar, MINT, INK, PAPER
colors = [("Мята", MINT, "акцент: трубка, верхний слой, кнопки"), ("Графит", INK, "текст и знак"),
          ("Тёплый белый", PAPER, "фон"), ("Светлая мята", "#E2F6EF", "подложки, обложки"),
          ("Тёмная мята", "#1F7F69", "ссылки и мелкий акцент"), ("Серый", "#6B7471", "подписи")]
D = dict(defaults=data.DEFAULTS, pack=data.PACK, products=data.PRODUCTS, services=data.SERVICES,
         purchases=data.PURCHASES, highlights=data.HIGHLIGHTS, posts=data.POSTS, checklist=data.CHECKLIST, colors=colors)
html = open(os.path.join(HERE, 'template.html')).read()
ava = avatar(size=96).replace('width="96" height="96"', 'width="100%" height="100%"')
html = html.replace('/*AVATAR*/', ava).replace('/*DATA*/', json.dumps(D, ensure_ascii=False))
out = os.path.join(HERE, '..', 'instagram-guide.html')
open(out, 'w').write(html)
print('ok', len(html))

# --- Память JARVIS: каталог и закупка в Markdown (из тех же данных) ---
B = os.path.join(HERE, '..', '..', 'jarvis', 'brain', '30-projects', '3d-print-biznes')
MAT = {"pla": "PLA", "petg": "PETG", "silk": "Silk PLA"}
d = data.DEFAULTS
lines = ["# Qabat — каталог и цены (2026-10-04)", "",
 "Источник: `qabat/kit/data.py` — меняй там и пересобирай `python3 qabat/kit/build_kit.py`; страница и этот файл обновятся вместе.",
 "**Цены — оценка JARVIS.** Цен 3D-печати в Душанбе в интернете нет; курс и цену пластика проверить не удалось (сайты закрыты для облачной сессии). Владелец вписывает свои цифры на странице комплекта.", "",
 "## Формула себестоимости",
 f"пластик × (1 + брак {d['waste']}%) × цена кг + часы × машино-час {d['machine']} сом + минуты/60 × час работы {d['labour']} сом + электроника + упаковка (пакет {data.PACK['s']}, коробка {data.PACK['b']}, подарочная {data.PACK['g']} сом).",
 f"Цена пластика по умолчанию: PLA {d['pla']}, PETG {d['petg']}, Silk {d['silk']} сом/кг. Курс {d['rate']} сом за $1 — уточнить. Минимальная наценка ×2.",
 "Машино-час: износ принтера, сопла, стола + свет 0,12 кВт × 0,9465 сом/кВт·ч (тариф для бизнеса, ПК и принтеры в студии).", "",
 "| Артикул | Товар | Тип | Пластик | г | ч | Себест., сом | Цена, сом | Наценка | Склад |", "|---|---|---|---|---|---|---|---|---|---|"]
hours = 0; mat = {}
for p in data.PRODUCTS:
    c = data.cost(p)
    if p[11]:
        hours += p[6] * p[11]; mat[p[4]] = mat.get(p[4], 0) + p[5] * p[11] * (1 + d['waste'] / 100)
    lines.append(f"| {p[0]} | {p[1]} | {'склад' if p[3]=='stock' else 'под заказ'} | {MAT[p[4]]} | {p[5]} | {p[6]} | {c} | {p[10]} | ×{p[10]/c:.1f} | {p[11] or '—'} |")
lines += ["", "Заметки по товарам:"] + [f"- **{p[0]}** {p[12]}" for p in data.PRODUCTS]
lines += ["", "## Услуги"] + [f"- **{n}.** {t}" for n, t in data.SERVICES]
lines += ["", "## Первый склад",
 f"- Печати: **{hours:g} машино-часов** → ≈{hours/36:.0f} дней на P1S + K1 по 18 ч в сутки.",
 "- Пластик: " + ", ".join(f"{MAT[k]} {v/1000:.1f} кг" for k, v in mat.items()) + ".",
 "- Запас 5 шт. (мелочь — 10). Когда остаток меньше 5 — товар попадает в вечернюю партию 20:00.", "",
 "## Почему эти товары (тренды Таджикистана, оценка JARVIS)",
 "- Машины и номера — брелоки с номером, держатели в машину: машину в Душанбе любят и украшают.",
 "- Той и праздники — сувениры гостям, топперы, формочки на Навруз: большие партии, сезонный спрос.",
 "- Подарки с фото и именем — литофаны, органайзеры с именем: «вау» на видео, хорошо продаются в Reels.",
 "- Модные игрушки — флекси-драконы, яйца драконов, фиджеты: вирусные видео во всём мире, дети и подростки.",
 "- Свет — «Луна», «Гриб», «Чароғ», Smart на ESP32: лампы — первая идея владельца, его опыт умных макетов.",
 "- Религиозные подарки — складная подставка для Корана: подарок на Рамазан, делать бережно и аккуратно.",
 "Проверить спрос: опрос в историях Instagram и первые 2 недели продаж → JARVIS убирает слабые товары."]
open(os.path.join(B, 'каталог-и-цены.md'), 'w').write('\n'.join(lines) + '\n')

L = ["# Qabat — закупка для старта (2026-10-04)", "",
 "Покупает владелец. JARVIS ничего не заказывает без «да». У владельца уже есть: **чёрный PETG**, **сушилки в принтерах**.",
 f"Цены — ориентир в долларах (AliExpress и местные магазины, без доставки), в сомони по курсу {d['rate']} — уточнить.", "",
 "| Группа | Что | Сколько | ≈ $ | Зачем | Очередь |", "|---|---|---|---|---|---|"]
for x in data.PURCHASES:
    L.append(f"| {x[0]} | {x[1]} | {x[2]} | {x[3]} | {x[4]} | {'сразу' if x[5]==1 else 'можно позже'} |")
s1 = sum(x[3] for x in data.PURCHASES if x[5] == 1); s = sum(x[3] for x in data.PURCHASES)
L += ["", f"**Итого: сразу ≈ ${s1} (≈ {s1*d['rate']:.0f} сом), весь список ≈ ${s} (≈ {s*d['rate']:.0f} сом).**"]
open(os.path.join(B, 'закупка.md'), 'w').write('\n'.join(L) + '\n')
print('brain ok')
