# Знак и логотип Qabat в SVG — перерисовано по знаку, который владелец поставил на аватарку (2026-10-04)
MINT = "#74DCC4"; INK = "#1F2523"; PAPER = "#FAFAF8"

def avatar(bg=PAPER, ink=INK, mint=MINT, size=1080):
    """Знак для аватарки: трубка уходит за левый край, как у владельца."""
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="{size}" height="{size}">
<rect width="1080" height="1080" fill="{bg}"/>
<path d="M-20 205 C 210 200, 380 215, 455 262 C 505 293, 520 330, 520 392" fill="none" stroke="{mint}" stroke-width="46" stroke-linecap="round"/>
<rect x="494" y="380" width="52" height="30" rx="4" fill="{ink}"/>
<path d="M482 412 H558 V466 Q558 476 548 476 H492 Q482 476 482 466 Z" fill="{ink}"/>
<path d="M500 476 H540 L528 506 H512 Z" fill="{ink}"/>
<path d="M520 504 C 518 540, 548 556, 640 566" fill="none" stroke="{ink}" stroke-width="7" stroke-linecap="round"/>
<rect x="320" y="560" width="440" height="84" rx="42" fill="{mint}"/>
<g fill="{ink}"><rect x="320" y="654" width="440" height="64" rx="32"/><rect x="320" y="726" width="440" height="64" rx="32"/>
<rect x="320" y="798" width="440" height="64" rx="32"/><rect x="320" y="870" width="440" height="64" rx="32"/></g>
</svg>'''

def mark_compact(ink=INK, mint=MINT):
    """Компактный знак с короткой трубкой-крючком (как в логотипе L1). Координаты 0..400."""
    return f'''<path d="M150 70 H200 A40 40 0 0 1 240 110 V128" fill="none" stroke="{mint}" stroke-width="34" stroke-linecap="round"/>
<rect x="222" y="124" width="36" height="20" rx="3" fill="{ink}"/>
<path d="M214 146 H266 V182 Q266 189 259 189 H221 Q214 189 214 182 Z" fill="{ink}"/>
<path d="M226 189 H254 L246 209 H234 Z" fill="{ink}"/>
<path d="M240 208 C 239 228, 256 236, 300 241" fill="none" stroke="{ink}" stroke-width="5" stroke-linecap="round"/>
<rect x="90" y="238" width="300" height="56" rx="28" fill="{mint}"/>
<g fill="{ink}"><rect x="90" y="300" width="300" height="42" rx="21"/><rect x="90" y="348" width="300" height="42" rx="21"/>
<rect x="90" y="396" width="300" height="42" rx="21"/></g>'''

def full_logo(bg=PAPER, ink=INK, mint=MINT, width=1080, inner_only=False):
    """Полный логотип: знак + QABAT + PRINT LAB (шрифт Montserrat должен быть подключён на странице).
    Сборка по правилам логотипа (правка владельца 2026-10-04: знак стоял слишком высоко и выглядел отдельно):
    зазор между низом знака и верхом заглавных QABAT — половина высоты заглавной буквы,
    вся композиция стоит по центру квадрата, поля сверху и снизу одинаковые."""
    S = 0.95                      # масштаб знака
    top, bottom = 53, 438         # верх трубки и низ стопки в координатах знака
    fs = 168; cap = fs * 0.70     # кегль QABAT и высота заглавной (Montserrat: 700/1000)
    gap = cap * 0.5               # зазор знак — надпись
    sub_gap = 82                  # от базовой линии QABAT до базовой линии PRINT LAB
    h_mark = (bottom - top) * S
    total = h_mark + gap + cap + sub_gap
    y0 = (1080 - total) / 2       # верх композиции
    ty = y0 - top * S             # сдвиг знака по вертикали
    base = y0 + h_mark + gap + cap
    inner = f'''<g transform="translate(312 {ty:.1f}) scale({S})">{mark_compact(ink, mint)}</g>
<text x="540" y="{base:.1f}" text-anchor="middle" font-family="Montserrat" font-weight="500" font-size="{fs}" letter-spacing="14" fill="{ink}">QABAT</text>
<text x="548" y="{base + sub_gap:.1f}" text-anchor="middle" font-family="Montserrat" font-weight="500" font-size="44" letter-spacing="22" fill="{ink}">PRINT LAB</text>'''
    if inner_only:
        return inner
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="{width}">
<rect width="1080" height="1080" fill="{bg}"/>
{inner}
</svg>'''

def avatar_full(bg=PAPER, ink=INK, mint=MINT, size=1080, scale=1.319, dx=4.6, dy=0.7):
    """Аватарка Instagram — полный логотип в круге (решение владельца 2026-10-04: на аватарку — логотип с надписью).
    Масштаб и сдвиг подобраны расчётом qabat/brandbook/fit_avatar.py: самый крупный логотип, который целиком
    помещается в круг с запасом 8% радиуса, ровно по центру по ширине и по высоте (выбор JARVIS из трёх вариантов:
    крупнее и выше центра — Q почти касается края; чуть выше центра; ровно по центру — самый спокойный и ровный)."""
    g = full_logo(ink=ink, mint=mint, inner_only=True)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 1080" width="{size}" height="{size}">
<rect width="1080" height="1080" fill="{bg}"/>
<g transform="translate({540 + dx:.1f} {540 + dy:.1f}) scale({scale}) translate(-540 -540)">{g}</g>
</svg>'''
