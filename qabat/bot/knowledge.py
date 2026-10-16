# Что бот знает о Qabat: собирается из qabat/kit/data.py — один источник с каталогом и страницей.
# Пока владелец не утвердил цены (решение 2026-10-05), цены в подсказку модели не попадают.
import importlib.util
import os
import re

_KIT = os.path.join(os.path.dirname(__file__), "..", "kit", "data.py")
_MONEY = re.compile(r"(от\s+)?\d[\d\s.,–-]*\s*(сомони|сомонӣ|смн|сом\b|tjs|\$|долл)", re.I)


def load_kit(path: str = _KIT):
    spec = importlib.util.spec_from_file_location("qabat_kit_data", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _no_money(text: str) -> str:
    return _MONEY.sub("цена у мастера", text)


def catalog_lines(kit, prices_on: bool = False) -> list[str]:
    lines = []
    for p in kit.PRODUCTS:
        pid, name, group, kind, _pl, _g, _h, _m, _e, _pack, price, stock, note = p
        how = "есть на складе" if kind == "stock" else "под заказ"
        note = note if prices_on else _no_money(note)
        tail = f"; цена {price} сомони" if prices_on else ""
        lines.append(f"- {pid} · {name} ({group}, {how}{tail}). {note}")
    for name, text in kit.SERVICES:
        lines.append(f"- Услуга «{name}». {text if prices_on else _no_money(text)}")
    return lines


RULES = """Ты — помощник в чате Qabat Print Lab, студии 3D-печати в Душанбе. Пиши коротко, тепло и по делу, 1–3 предложения.
Отвечай на языке клиента: по-русски или по-таджикски (тоҷикӣ).
Правила, которые нельзя нарушать:
1. {price_rule}
2. Не обещай точный срок. Можно сказать «обычно 1 день», точный срок называет мастер.
3. Не пиши «готово» и «оплата получена». Не проси предоплату. Не обещай скидок.
4. Не выдумывай товары, цвета и наличие — только из каталога ниже. Не знаешь — «уточню у мастера».
5. Именной заказ (брелок с номером или именем, литофан, топпер) — спроси текст, цвет и количество, потом повтори заказ целиком и спроси «Всё верно?».
6. Жалобы, опт от 30 штук, восстановление деталей, «хочу как на картинке», макеты — скажи, что передаёшь мастеру.
Каталог:
{catalog}"""


def system_prompt(kit=None, prices_on: bool = False) -> str:
    kit = kit or load_kit()
    price_rule = ("Цены называй только из каталога." if prices_on
                  else "Цены не называй вообще. На вопрос о цене отвечай: «Цену уточнит мастер — напишите размер и цвет».")
    return RULES.format(price_rule=price_rule, catalog="\n".join(catalog_lines(kit, prices_on)))
