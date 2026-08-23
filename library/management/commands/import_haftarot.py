import re
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.models import Haftarah, HaftarahVerse, Parasha
from library.torah_data import HAFTARAH_BOOKS

from .import_texts import TEXTS_HE_CACHE_DIR, fetch_hebrew_chapter

TEXTS_RU_HAFTARAH_DIR = Path(settings.BASE_DIR) / "texts" / "ru_haftarah"

# "Ашкеназим: 42:5-43:10" / "Сефарадим: 42:5-21" - границы чтения по традиции.
# Второе число главы не указывают, если чтение не выходит за пределы первой главы.
RANGE_LINE_RE = re.compile(r"^(Ашкеназим|Сефарадим):\s*(\d+):(\d+)\s*-\s*(?:(\d+):)?(\d+)\s*$")
VERSE_MARKER_RE = re.compile(r"\((\d+)\)")

TRADITION_BY_LABEL = {
    "Ашкеназим": Haftarah.TRADITION_ASHKENAZI,
    "Сефарадим": Haftarah.TRADITION_SEPHARDI,
}


def parse_haftarah_file(path: Path):
    """Разбирает текстовый файл гафтары: заголовки с границами чтения по традициям
    ("Ашкеназим: 42:5-43:10") плюс основной текст - главы отдельной строкой-числом,
    стихи с номером в скобках внутри абзаца ("(5) текст... (6) текст..."). Прочие
    строки (заголовок, пояснения вида "Здесь начинают...") просто пропускаются."""
    ranges = {}
    verses = []
    current_chapter = None

    for raw_line in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw_line.strip()
        if not line:
            continue

        m = RANGE_LINE_RE.match(line)
        if m:
            label, start_ch, start_v, end_ch, end_v = m.groups()
            ranges[TRADITION_BY_LABEL[label]] = (
                int(start_ch), int(start_v), int(end_ch or start_ch), int(end_v),
            )
            continue

        if line.isdigit():
            current_chapter = int(line)
            continue

        markers = list(VERSE_MARKER_RE.finditer(line))
        if not markers or current_chapter is None:
            continue

        for i, marker in enumerate(markers):
            verse_num = int(marker.group(1))
            text_start = marker.end()
            text_end = markers[i + 1].start() if i + 1 < len(markers) else len(line)
            text = line[text_start:text_end].strip()
            verses.append((current_chapter, verse_num, text))

    return ranges, verses


class Command(BaseCommand):
    help = (
        "Импортирует тексты гафтарот из texts/ru_haftarah/<недельная_глава>/<книга>.txt "
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

            for txt_file in sorted(parasha_dir.glob("*.txt")):
                self.import_haftarah_file(parasha, txt_file)

    def import_haftarah_file(self, parasha: Parasha, txt_file: Path):
        book_slug = txt_file.stem
        if book_slug not in HAFTARAH_BOOKS:
            self.stdout.write(self.style.WARNING(
                f"{txt_file}: пропускаю - нет описания книги '{book_slug}' "
                "в library/torah_data.py HAFTARAH_BOOKS"
            ))
            return
        book_name_ru, book_name_he, sefaria_name = HAFTARAH_BOOKS[book_slug]

        ranges, parsed_verses = parse_haftarah_file(txt_file)
        if not parsed_verses:
            self.stdout.write(self.style.WARNING(f"{txt_file}: не найдено ни одного стиха"))
            return
        if not ranges:
            self.stdout.write(self.style.WARNING(
                f"{txt_file}: не найдено ни одной строки с границами чтения "
                "(\"Ашкеназим: ...\" / \"Сефарадим: ...\") - гафтара не будет создана"
            ))
            return

        chapters_needed = sorted({chapter for chapter, verse, text in parsed_verses})
        he_cache_dir = TEXTS_HE_CACHE_DIR / "_haftarah" / book_slug
        he_by_chapter = {
            chapter: fetch_hebrew_chapter(sefaria_name, chapter, he_cache_dir)
            for chapter in chapters_needed
        }

        created = []
        for tradition, (start_ch, start_v, end_ch, end_v) in ranges.items():
            haftarah, _ = Haftarah.objects.update_or_create(
                parasha=parasha, tradition=tradition,
                defaults={"book_name_ru": book_name_ru, "book_name_he": book_name_he},
            )
            haftarah.verses.all().delete()
            for chapter, verse, text_ru in parsed_verses:
                if not (start_ch, start_v) <= (chapter, verse) <= (end_ch, end_v):
                    continue
                he_verses = he_by_chapter.get(chapter)
                text_he = ""
                if he_verses and 1 <= verse <= len(he_verses):
                    text_he = he_verses[verse - 1]
                HaftarahVerse.objects.create(
                    haftarah=haftarah, chapter=chapter, verse=verse,
                    text_he=text_he, text_ru=text_ru,
                )
            created.append(tradition)

        self.stdout.write(self.style.SUCCESS(
            f"{txt_file.name}: гафтара для '{parasha.name_ru}' ({book_name_ru}) "
            f"создана/обновлена: {', '.join(created)}"
        ))
