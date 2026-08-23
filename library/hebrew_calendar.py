"""Еврейский календарь: сегодняшняя дата, конвертация Григорианский/Еврейский,
недельная глава (парашат hа-шавуа) - на pyluach, без внешних сервисов."""

from pyluach import dates, parshios

GREGORIAN_MONTHS_RU = [
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
]

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


def convert_gregorian_to_hebrew(day, month, year):
    greg = dates.GregorianDate(year, month, day)
    heb = greg.to_heb()
    parasha_en = parshios.getparsha_string(greg)
    return {
        "gregorian_str": format_gregorian_ru(greg),
        "hebrew_str": format_hebrew_ru(heb),
        "parasha_ru": parasha_name_ru_fallback(parasha_en) if parasha_en else None,
    }


def convert_hebrew_to_gregorian(day, month, year):
    heb = dates.HebrewDate(year, month, day)
    greg = heb.to_greg()
    parasha_en = parshios.getparsha_string(greg)
    return {
        "gregorian_str": format_gregorian_ru(greg),
        "hebrew_str": format_hebrew_ru(heb),
        "parasha_ru": parasha_name_ru_fallback(parasha_en) if parasha_en else None,
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
    }
