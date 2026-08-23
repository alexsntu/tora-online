import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.models import Haftarah, HaftarahVerse, Parasha
from library.torah_data import HAFTARAH_BOOKS

from .import_texts import TEXTS_HE_CACHE_DIR, fetch_hebrew_chapter

TEXTS_RU_HAFTARAH_DIR = Path(settings.BASE_DIR) / "texts" / "ru_haftarah"

# Название книги, как встречается в исходном тексте -> наш слаг в HAFTARAH_BOOKS
# (library/torah_data.py). Сортировка по убыванию длины, чтобы "Мелахим I" не
# перехватило совпадение раньше более длинного "Мелахим II" и т.п.
BOOK_ALIASES = {
    "Йешайа": "yeshayahu",
    "Мелахим II": "melachim-2",
    "Мелахим I": "melachim-1",
    "Малахи": "malachi",
    "Г̃ошэа̃": "hoshea",
    "Йоэйль": "yoel",
    "Амос": "amos",
    "Овадйа": "ovadia",
    "Йехэзкэйл": "yechezkel",
}
BOOK_ALIASES_SORTED = sorted(BOOK_ALIASES, key=len, reverse=True)

TRADITION_LABELS = {"Ашкеназим": Haftarah.TRADITION_ASHKENAZI, "Сефарадим": Haftarah.TRADITION_SEPHARDI}
BOTH = frozenset(TRADITION_LABELS.values())

RANGE_IN_TEXT_RE = re.compile(r"(\d+):(\d+)\s*-\s*(?:(\d+):)?(\d+)")
COLON_TRADITION_RE = re.compile(r"^(Ашкеназим|Сефарадим):\s*(.*)$")
IZ_KNIGI_RE = re.compile(r"^Из книги «([^»]+)»")
PAREN_RE = re.compile(r"^\((.+)\)$")
BOTH_SUFFIX_RE = re.compile(r"\(ашкеназим и сефарадим\)\s*$", re.IGNORECASE)
VERSE_MARKER_RE = re.compile(r"\((\d+)\)")


def resolve_book_prefix(text):
    """Если строка начинается с известного названия книги (BOOK_ALIASES), возвращает
    (слаг, остаток строки после названия) - иначе (None, text)."""
    for label in BOOK_ALIASES_SORTED:
        if text == label or text.startswith(label + " "):
            return BOOK_ALIASES[label], text[len(label):].strip()
    return None, text


def parse_haftarah_file(path: Path):
    """Разбирает текстовый файл гафтары. Поддерживает оба варианта источника:
    - "общий поток" (Берешит, Ноах, Вайера и т.п.): одна книга на всю гафтару,
      текст один, а традиции (Ашкеназим/Сефарадим) - просто разные диапазоны
      глав:стихов внутри него ("Ашкеназим: 42:5-43:10" и т.п.);
    - "раздельные разделы" (Вайеце и т.п.): в тексте есть явные подзаголовки
      "Ашкеназим"/"Сефарадим" (без двоеточия), каждый со своим текстом и, порой,
      другой книгой-источником (случается переход на вторую книгу для "хорошего
      окончания" чтения).
    Возвращает range_by_tradition (для первого варианта) и verses - плоский список
    в порядке чтения, с пометкой, к какой традиции относится (BOTH - когда общий
    поток и деление только по диапазону)."""
    range_by_tradition = {}
    verses = []
    current_traditions = BOTH
    current_book_slug = None
    current_chapter = None

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line in TRADITION_LABELS:
            current_traditions = frozenset({TRADITION_LABELS[line]})
            continue

        m = COLON_TRADITION_RE.match(line)
        if m:
            label, rest = m.groups()
            rm = RANGE_IN_TEXT_RE.search(rest)
            if rm:
                sc, sv, ec, ev = rm.groups()
                range_by_tradition[TRADITION_LABELS[label]] = (int(sc), int(sv), int(ec or sc), int(ev))
            continue

        m = IZ_KNIGI_RE.match(line)
        if m:
            slug, _ = resolve_book_prefix(m.group(1))
            if slug:
                current_book_slug = slug
            continue

        m = PAREN_RE.match(line)
        if m:
            slug, rest = resolve_book_prefix(m.group(1))
            if slug and RANGE_IN_TEXT_RE.match(rest):
                current_book_slug = slug
            continue

        m = BOTH_SUFFIX_RE.search(line)
        if m:
            slug, rest = resolve_book_prefix(line[:m.start()].strip())
            if slug:
                current_book_slug = slug
            continue

        slug, rest = resolve_book_prefix(line)
        if slug and RANGE_IN_TEXT_RE.match(rest):
            current_book_slug = slug
            continue

        if line.isdigit():
            current_chapter = int(line)
            continue

        markers = list(VERSE_MARKER_RE.finditer(line))
        if markers and current_chapter is not None and current_book_slug:
            for i, marker in enumerate(markers):
                verse_num = int(marker.group(1))
                text_start = marker.end()
                text_end = markers[i + 1].start() if i + 1 < len(markers) else len(line)
                text = line[text_start:text_end].strip()
                verses.append({
                    "traditions": current_traditions, "book_slug": current_book_slug,
                    "chapter": current_chapter, "verse": verse_num, "text": text,
                })
            continue
        # иначе - пояснение/разделитель/обрывок (напр. "Показать главы полностью",
        # "________________") - пропускаем

    return range_by_tradition, verses


def verses_for_tradition(tradition, verses, range_by_tradition):
    """Стихи для одной традиции: помеченные конкретной традицией - как есть;
    помеченные BOTH ("общий поток") - только если попадают в её диапазон
    (если диапазон вообще объявлен - иначе весь поток идёт в обе традиции)."""
    result = []
    for v in verses:
        if v["traditions"] != BOTH:
            if tradition in v["traditions"]:
                result.append(v)
            continue
        rng = range_by_tradition.get(tradition)
        if rng is None:
            result.append(v)
            continue
        sc, sv, ec, ev = rng
        if (sc, sv) <= (v["chapter"], v["verse"]) <= (ec, ev):
            result.append(v)
    return result


class Command(BaseCommand):
    help = (
        "Импортирует тексты гафтарот из texts/ru_haftarah/<недельная_глава>/haftarah.txt "
        "(отдельный раздел, не часть обычного текста Танаха) и подтягивает параллельный "
        "иврит с Sefaria (как import_texts, с локальным кэшем)."
    )

    def handle(self, *args, **options):
        if not TEXTS_RU_HAFTARAH_DIR.exists():
            raise CommandError(f"Нет каталога {TEXTS_RU_HAFTARAH_DIR}")

        for parasha_dir in sorted(TEXTS_RU_HAFTARAH_DIR.iterdir()):
            if not parasha_dir.is_dir():
                continue
            parasha_slug = parasha_dir.name
            try:
                parasha = Parasha.objects.get(slug=parasha_slug)
            except Parasha.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"Пропускаю '{parasha_slug}': такой недельной главы нет в базе"
                ))
                continue

            txt_file = parasha_dir / "haftarah.txt"
            if not txt_file.exists():
                self.stdout.write(self.style.WARNING(f"{parasha_dir}: нет файла haftarah.txt"))
                continue
            self.import_haftarah_file(parasha, txt_file)

    def import_haftarah_file(self, parasha: Parasha, txt_file: Path):
        range_by_tradition, all_verses = parse_haftarah_file(txt_file)
        if not all_verses:
            self.stdout.write(self.style.WARNING(f"{txt_file}: не найдено ни одного стиха"))
            return

        book_slugs_used = {v["book_slug"] for v in all_verses}
        unknown = book_slugs_used - HAFTARAH_BOOKS.keys()
        if unknown:
            self.stdout.write(self.style.WARNING(
                f"{txt_file}: неизвестные книги {unknown} - добавь в HAFTARAH_BOOKS "
                "(library/torah_data.py), пропускаю"
            ))
            return

        he_cache = {}
        for book_slug in book_slugs_used:
            _, _, sefaria_name = HAFTARAH_BOOKS[book_slug]
            chapters_needed = sorted({v["chapter"] for v in all_verses if v["book_slug"] == book_slug})
            he_cache_dir = TEXTS_HE_CACHE_DIR / "_haftarah" / book_slug
            for chapter in chapters_needed:
                he_cache[(book_slug, chapter)] = fetch_hebrew_chapter(sefaria_name, chapter, he_cache_dir)

        created = []
        for tradition in (Haftarah.TRADITION_ASHKENAZI, Haftarah.TRADITION_SEPHARDI):
            tradition_verses = verses_for_tradition(tradition, all_verses, range_by_tradition)
            if not tradition_verses:
                continue

            haftarah, _ = Haftarah.objects.update_or_create(parasha=parasha, tradition=tradition)
            haftarah.verses.all().delete()
            for order, v in enumerate(tradition_verses):
                book_name_ru, book_name_he, _ = HAFTARAH_BOOKS[v["book_slug"]]
                he_verses = he_cache.get((v["book_slug"], v["chapter"]))
                text_he = ""
                if he_verses and 1 <= v["verse"] <= len(he_verses):
                    text_he = he_verses[v["verse"] - 1]
                HaftarahVerse.objects.create(
                    haftarah=haftarah, order=order,
                    book_name_ru=book_name_ru, book_name_he=book_name_he,
                    chapter=v["chapter"], verse=v["verse"],
                    text_he=text_he, text_ru=v["text"],
                )
            created.append(tradition)

        if not created:
            self.stdout.write(self.style.WARNING(f"{txt_file}: не удалось определить ни одной традиции"))
            return

        self.stdout.write(self.style.SUCCESS(
            f"{txt_file.parent.name}: гафтара создана/обновлена: {', '.join(created)}"
        ))
