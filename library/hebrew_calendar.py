"""Еврейский календарь: сегодняшняя дата, конвертация Григорианский/Еврейский,
недельная глава (парашат hа-шавуа), месячная сетка с праздниками - на pyluach,
без внешних сервисов."""

import calendar as py_calendar
import re
from datetime import timedelta

from pyluach import dates, parshios

GREGORIAN_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

GREGORIAN_MONTHS_NOM_RU = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

WEEKDAYS_SHORT_RU = ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"]

HEBREW_MONTHS_RU = {
    "Nissan": "нисана",
    "Iyar": "ияра",
    "Sivan": "сивана",
    "Tammuz": "таммуза",
    "Av": "ава",
    "Elul": "элуля",
    "Tishrei": "тишрея",
    "Cheshvan": "хешвана",
    "Kislev": "кислева",
    "Teves": "тевета",
    "Shevat": "швата",
    "Adar": "адара",
    "Adar 1": "адара I",
    "Adar 2": "адара II",
}

# Обратно: русское родительное -> английское имя месяца pyluach (для конвертера дат)
HEBREW_MONTHS_RU_TO_EN = {v: k for k, v in HEBREW_MONTHS_RU.items()}

# Именительный падеж (для подзаголовка над сеткой календаря - "Элул 5786"),
# в отличие от HEBREW_MONTHS_RU выше (родительный - "21 элуля 5786").
HEBREW_MONTHS_NOM_RU = {
    "Nissan": "Нисан",
    "Iyar": "Ияр",
    "Sivan": "Сиван",
    "Tammuz": "Таммуз",
    "Av": "Ав",
    "Elul": "Элул",
    "Tishrei": "Тишрей",
    "Cheshvan": "Хешван",
    "Kislev": "Кислев",
    "Teves": "Тевет",
    "Shevat": "Шват",
    "Adar": "Адар",
    "Adar 1": "Адар I",
    "Adar 2": "Адар II",
}

# pyluach.parshios.getparsha_string() (англ.) -> наш slug (library.models.Parasha).
# Используется вместо сравнения ивритских названий: pyluach иногда выводит написание
# без вав/йод (מלא/חסר варианты, напр. "תבא" вместо "תבוא" у нас), из-за чего
# посимвольное сравнение с никудом ошибочно не находило совпадение.
PARASHA_EN_TO_SLUG = {
    "Bereishis": "bereshit", "Noach": "noach", "Lech Lecha": "lech-lecha",
    "Vayeira": "vayera", "Chayei Sarah": "chayei-sara", "Toldos": "toldot",
    "Vayeitzei": "vayetze", "Vayishlach": "vayishlach", "Vayeishev": "vayeshev",
    "Mikeitz": "miketz", "Vayigash": "vayigash", "Vayechi": "vayechi",
    "Shemos": "shmot", "Va'eira": "vaera", "Bo": "bo", "Beshalach": "beshalach",
    "Yisro": "yitro", "Mishpatim": "mishpatim", "Terumah": "teruma",
    "Tetzaveh": "tetzave", "Ki Sisa": "ki-tisa",
    "Vayakhel": "vayakhel", "Pekudei": "pekudei",
    "Vayikra": "vaikra", "Tzav": "tzav", "Shemini": "shmini",
    "Tazria": "tazria", "Metzora": "metzora",
    "Acharei Mos": "achrei-mot", "Kedoshim": "kedoshim", "Emor": "emor",
    "Behar": "behar", "Bechukosai": "bechukotai",
    "Bamidbar": "bemidbar", "Nasso": "naso", "Beha'aloscha": "behaalotcha",
    "Shelach": "shlach", "Korach": "korach", "Chukas": "chukat", "Balak": "balak",
    "Pinchas": "pinchas", "Mattos": "matot", "Masei": "masei",
    "Devarim": "devarim", "Va'eschanan": "vaetchanan", "Eikev": "eikev",
    "Re'eh": "reeh", "Shoftim": "shoftim", "Ki Seitzei": "ki-teitzei",
    "Ki Savo": "ki-tavo", "Nitzavim": "nitzavim", "Vayeilech": "vayeilech",
    "Haazinu": "haazinu", "Vezos Haberachah": "vezot-habracha",
}

# Транслитерация pyluach.parshios.getparsha_string() (англ.) -> русское название,
# для отображения текста виджета даже пока соответствующая книга ещё не
# добавлена на сайт (тогда ссылки не будет - см. find_parasha_for_date).
PARASHA_NAMES_RU = {
    "Bereishis": "Берешит", "Noach": "Ноах", "Lech Lecha": "Лех-Леха",
    "Vayeira": "Вайера", "Chayei Sarah": "Хаей Сара", "Toldos": "Толдот",
    "Vayeitzei": "Вайеце", "Vayishlach": "Вайишлах", "Vayeishev": "Вайешев",
    "Mikeitz": "Микец", "Vayigash": "Вайигаш", "Vayechi": "Вайехи",
    "Shemos": "Шмот", "Va'eira": "Ваэра", "Bo": "Бо", "Beshalach": "Бешалах",
    "Yisro": "Итро", "Mishpatim": "Мишпатим", "Terumah": "Трума",
    "Tetzaveh": "Тецаве", "Ki Sisa": "Ки Тиса",
    "Vayakhel": "Вайакхель", "Pekudei": "Пкудей",
    "Vayikra": "Ваикра", "Tzav": "Цав", "Shemini": "Шмини",
    "Tazria": "Тазриа", "Metzora": "Мецора",
    "Acharei Mos": "Ахарей Мот", "Kedoshim": "Кдошим", "Emor": "Эмор",
    "Behar": "Беар", "Bechukosai": "Бехукотай",
    "Bamidbar": "Бемидбар", "Nasso": "Насо", "Beha'aloscha": "Бехаалотха",
    "Shelach": "Шлах", "Korach": "Корах", "Chukas": "Хукат", "Balak": "Балак",
    "Pinchas": "Пинхас", "Mattos": "Матот", "Masei": "Масей",
    "Devarim": "Дварим", "Va'eschanan": "Ваэтханан", "Eikev": "Экев",
    "Re'eh": "Реэ", "Shoftim": "Шофтим", "Ki Seitzei": "Ки Теце",
    "Ki Savo": "Ки Таво", "Nitzavim": "Ницавим", "Vayeilech": "Вайелех",
    "Haazinu": "Хаазину",
}


# (номер месяца pyluach, название) - для выпадающего списка в конвертере дат.
# 12/13 - Адар / Адар I / Адар II (13-й существует только в високосный год,
# см. convert_hebrew_to_gregorian).
HEBREW_MONTH_CHOICES = [
    (1, "Нисан"), (2, "Ияр"), (3, "Сиван"), (4, "Таммуз"), (5, "Ав"), (6, "Элул"),
    (7, "Тишрей"), (8, "Хешван"), (9, "Кислев"), (10, "Тевет"), (11, "Шват"),
    (12, "Адар (Адар I в високосный год)"), (13, "Адар II (только в високосный год)"),
]

GREGORIAN_MONTH_CHOICES = [(i + 1, name.capitalize()) for i, name in enumerate(GREGORIAN_MONTHS_RU)]

# pyluach.dates.HebrewDate.holiday() (англ., см. pyluach.utils) -> русское название.
HOLIDAY_NAMES_RU = {
    "Rosh Hashana": "Рош а-Шана",
    "Yom Kippur": "Йом Кипур",
    "Succos": "Суккот",
    "Shmini Atzeres": "Шмини Ацерет",
    "Simchas Torah": "Симхат Тора",
    "Chanuka": "Ханука",
    "Tu B'shvat": "Ту би-Шват",
    "Purim Katan": "Пурим Катан",
    "Purim": "Пурим",
    "Shushan Purim": "Шушан Пурим",
    "Pesach": "Песах",
    "Pesach Sheni": "Песах шени",
    "Lag Ba'omer": "Лаг ба-Омер",
    "Shavuos": "Шавуот",
    "Tu B'av": "Ту бе-Ав",
    "Tzom Gedalia": "Пост Гедалии",
    "10 of Teves": "10 Тевета",
    "Taanis Esther": "Пост Эстер",
    "17 of Tamuz": "17 Таммуза",
    "9 of Av": "Тиша бе-Ав",
}

# Постные дни (для отдельного визуального маркера - не такие "радостные", как Йом Тов).
FAST_DAYS_EN = {"Tzom Gedalia", "10 of Teves", "Taanis Esther", "17 of Tamuz", "9 of Av"}

_HOLIDAY_DAY_PREFIX_RE = re.compile(r"^(\d+)\s+(.*)$")


def _split_holiday_name(raw_name):
    """pyluach отдаёт многодневные праздники как '2 Succos' - разбираем на
    (номер_дня, базовое_имя); однодневные/посты возвращают (None, имя)."""
    m = _HOLIDAY_DAY_PREFIX_RE.match(raw_name)
    if m:
        return int(m.group(1)), m.group(2)
    return None, raw_name


def holiday_ru_for_hebdate(heb_date, israel=False):
    """Русское название праздника/поста для данной еврейской даты, или None."""
    raw = heb_date.holiday(israel=israel, prefix_day=True)
    if not raw:
        return None
    day_num, base_en = _split_holiday_name(raw)
    return {
        "name": HOLIDAY_NAMES_RU.get(base_en, base_en),
        "day_num": day_num,
        "is_fast": base_en in FAST_DAYS_EN,
    }


def parashot_list_for_date(greg_date, israel=False):
    """Список недельных глав для данной субботы - обычно одна, для сдвоенных
    недель (Ваякхель-Пкудей, Ницавим-Вайелех и т.п.) - две; каждая - со своей
    ссылкой (если её книга уже добавлена на сайт), кликабельны по отдельности."""
    from .models import Parasha

    parasha_en = parshios.getparsha_string(greg_date, israel=israel)
    if not parasha_en:
        return []
    result = []
    for part_en in (p.strip() for p in parasha_en.split(",")):
        slug = PARASHA_EN_TO_SLUG.get(part_en)
        obj = Parasha.objects.filter(slug=slug).first() if slug else None
        result.append({"name": obj.name_ru if obj else PARASHA_NAMES_RU.get(part_en, part_en), "obj": obj})
    return result


def month_calendar(year, month, israel=False):
    """Сетка григорианского месяца (недели вс-сб) для календарной страницы:
    каждый день - григорианское число + еврейская дата + праздник (если есть);
    по субботам - недельная глава (со ссылкой, если книга уже добавлена)."""
    cal = py_calendar.Calendar(firstweekday=6)  # неделя вс-сб, как в еврейском календаре
    today_py = dates.GregorianDate.today()
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        row = []
        for day in week:
            greg = dates.GregorianDate(day.year, day.month, day.day)
            heb = greg.to_heb()
            is_shabbat = day.weekday() == 5
            row.append({
                "day": day.day,
                "in_month": day.month == month,
                "is_today": day.year == today_py.year and day.month == today_py.month and day.day == today_py.day,
                "is_shabbat": is_shabbat,
                "hebrew_day": heb.day,
                "hebrew_month_ru": HEBREW_MONTHS_RU.get(heb.month_name(), heb.month_name()),
                "holiday": holiday_ru_for_hebdate(heb, israel=israel),
                "parashot": parashot_list_for_date(greg, israel=israel) if is_shabbat else [],
            })
        weeks.append(row)
    return weeks


def hebrew_month_span_ru(year, month):
    """Название(я) еврейского месяца/месяцев, приходящихся на данный
    григорианский месяц - для подзаголовка над сеткой (григорианский месяц
    почти всегда захватывает хвосты двух еврейских месяцев)."""
    last_day = py_calendar.monthrange(year, month)[1]
    heb_start = dates.GregorianDate(year, month, 1).to_heb()
    heb_end = dates.GregorianDate(year, month, last_day).to_heb()
    start_name = HEBREW_MONTHS_NOM_RU.get(heb_start.month_name(), heb_start.month_name())
    if heb_start.month_name() == heb_end.month_name() and heb_start.year == heb_end.year:
        return f"{start_name} {heb_start.year}"
    end_name = HEBREW_MONTHS_NOM_RU.get(heb_end.month_name(), heb_end.month_name())
    return f"{start_name} {heb_start.year} — {end_name} {heb_end.year}"


def upcoming_parashot(from_greg_date=None, count=8, israel=False):
    """Список ближайших недельных глав (суббот), начиная с сегодня/следующей субботы."""
    if from_greg_date is None:
        from_greg_date = dates.GregorianDate.today()
    cur = from_greg_date.shabbos()
    results = []
    for _ in range(count):
        parts = parashot_list_for_date(cur, israel=israel)
        if parts:
            results.append({
                "parts": parts,
                "gregorian_str": format_gregorian_ru(cur),
                "hebrew_str": format_hebrew_ru(cur.to_heb()),
            })
        cur_py = cur.to_pydate() + timedelta(days=7)
        cur = dates.GregorianDate(cur_py.year, cur_py.month, cur_py.day)
    return results


def upcoming_holidays(from_greg_date=None, days_ahead=400, israel=False, limit=10):
    """Список ближайших праздников/постов (первый день каждого + длительность),
    начиная с указанной даты (по умолчанию - сегодня)."""
    if from_greg_date is None:
        from_greg_date = dates.GregorianDate.today()
    cur = from_greg_date.to_heb()
    results = []
    for _ in range(days_ahead):
        info = holiday_ru_for_hebdate(cur, israel=israel)
        if info and info["day_num"] in (None, 1):
            length = 1
            probe = cur.add(days=1)
            while True:
                probe_info = holiday_ru_for_hebdate(probe, israel=israel)
                if probe_info and probe_info["name"] == info["name"] and probe_info["day_num"] and probe_info["day_num"] > 1:
                    length += 1
                    probe = probe.add(days=1)
                else:
                    break
            results.append({
                "name": info["name"],
                "is_fast": info["is_fast"],
                "length": length,
                "start_gregorian_str": format_gregorian_ru(cur.to_greg()),
                "start_hebrew_str": format_hebrew_ru(cur),
            })
            if len(results) >= limit:
                break
        cur = cur.add(days=1)
    return results


def convert_gregorian_to_hebrew(day, month, year):
    greg = dates.GregorianDate(year, month, day)
    heb = greg.to_heb()
    parasha_en = parshios.getparsha_string(greg)
    parasha_obj = find_parasha_for_date(greg) if parasha_en else None
    return {
        "gregorian_str": format_gregorian_ru(greg),
        "hebrew_str": format_hebrew_ru(heb),
        "parasha_ru": (parasha_obj.name_ru if parasha_obj else parasha_name_ru_fallback(parasha_en)) if parasha_en else None,
        "parasha_obj": parasha_obj,
        "parashot": parashot_list_for_date(greg),
    }


def convert_hebrew_to_gregorian(day, month, year):
    heb = dates.HebrewDate(year, month, day)
    greg = heb.to_greg()
    parasha_en = parshios.getparsha_string(greg)
    parasha_obj = find_parasha_for_date(greg) if parasha_en else None
    return {
        "gregorian_str": format_gregorian_ru(greg),
        "hebrew_str": format_hebrew_ru(heb),
        "parashot": parashot_list_for_date(greg),
        "parasha_ru": (parasha_obj.name_ru if parasha_obj else parasha_name_ru_fallback(parasha_en)) if parasha_en else None,
        "parasha_obj": parasha_obj,
    }


def parasha_name_ru_fallback(parasha_en):
    """Русское название по английскому выводу pyluach, включая сдвоенные
    недели вида "Vayakhel, Pekudei" -> "Вайакхель-Пкудей"."""
    parts = [p.strip() for p in parasha_en.split(",")]
    return "-".join(PARASHA_NAMES_RU.get(p, p) for p in parts)

def format_gregorian_ru(greg_date):
    return f"{greg_date.day} {GREGORIAN_MONTHS_RU[greg_date.month - 1]} {greg_date.year}"


def format_hebrew_ru(heb_date):
    month_ru = HEBREW_MONTHS_RU.get(heb_date.month_name(), heb_date.month_name())
    return f"{heb_date.day} {month_ru} {heb_date.year}"


def find_parasha_for_date(greg_date, israel=False):
    """Возвращает объект library.models.Parasha для данной секулярной даты,
    если она у нас загружена в базе (сверка по slug через PARASHA_EN_TO_SLUG)
    - или None, если это сдвоенное чтение или книга ещё не добавлена."""
    from .models import Parasha

    parasha_en = parshios.getparsha_string(greg_date, israel=israel)
    if not parasha_en or "," in parasha_en:
        return None
    slug = PARASHA_EN_TO_SLUG.get(parasha_en)
    if not slug:
        return None
    return Parasha.objects.filter(slug=slug).first()


def today_info(israel=False):
    """dict для виджета на главной: сегодняшние даты + недельная глава (+ссылка, если есть)."""
    greg_today = dates.GregorianDate.today()
    heb_today = greg_today.to_heb()
    parasha_en = parshios.getparsha_string(greg_today, israel=israel)
    parasha_he = parshios.getparsha_string(greg_today, hebrew=True, israel=israel)
    parasha_obj = find_parasha_for_date(greg_today, israel=israel)
    return {
        "gregorian_str": format_gregorian_ru(greg_today),
        "hebrew_str": format_hebrew_ru(heb_today),
        "parasha_en": parasha_en,
        "parasha_he": parasha_he,
        "parasha_ru": parasha_obj.name_ru if parasha_obj else parasha_name_ru_fallback(parasha_en),
        "parasha_obj": parasha_obj,
        "parashot": parashot_list_for_date(greg_today, israel=israel),
        "holiday": holiday_ru_for_hebdate(heb_today, israel=israel),
    }
