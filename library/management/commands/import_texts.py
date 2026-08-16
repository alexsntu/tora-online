import html
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.models import Book, Category, Parasha, Verse
from library.torah_data import BOOKS, CATEGORIES, PARASHOT

VERSE_LINE_RE = re.compile(r"^(\d+):(\d+)\s+(.+)$")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SECTION_MARKER_RE = re.compile(r"\{[פס]\}")

TEXTS_RU_DIR = Path(settings.BASE_DIR) / "texts" / "ru"
TEXTS_HE_CACHE_DIR = Path(settings.BASE_DIR) / "texts" / "he"


def clean_hebrew(raw: str) -> str:
    text = html.unescape(raw)
    text = HTML_TAG_RE.sub("", text)
    text = SECTION_MARKER_RE.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def fetch_hebrew_chapter(sefaria_name: str, chapter: int, cache_dir: Path):
    """Возвращает список стихов на иврите для главы, используя локальный кэш json."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{chapter}.json"
    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    url = f"https://www.sefaria.org/api/texts/{sefaria_name}.{chapter}?context=0"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError):
        return None

    he_verses = [clean_hebrew(v) for v in data.get("he", [])]
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(he_verses, f, ensure_ascii=False, indent=2)
    return he_verses


def seed_categories():
    """Создаёт/обновляет иерархию разделов библиотеки (Танах/Тора/Талмуд и т.д.)."""
    # сначала родительские (без parent_slug), потом дочерние — порядок в словаре это гарантирует
    for slug, (name_ru, name_he, parent_slug, order) in CATEGORIES.items():
        parent = Category.objects.get(slug=parent_slug) if parent_slug else None
        Category.objects.update_or_create(
            slug=slug,
            defaults={"name_ru": name_ru, "name_he": name_he, "parent": parent, "order": order},
        )


class Command(BaseCommand):
    help = (
        "Импортирует русский текст из texts/ru/<книга>/<парашот>.txt "
        "и подтягивает параллельный иврит с Sefaria (с локальным кэшем в texts/he/)."
    )

    def handle(self, *args, **options):
        if not TEXTS_RU_DIR.exists():
            raise CommandError(f"Нет каталога {TEXTS_RU_DIR}")

        seed_categories()

        for book_dir in sorted(TEXTS_RU_DIR.iterdir()):
            if not book_dir.is_dir():
                continue
            book_slug = book_dir.name
            if book_slug not in BOOKS:
                self.stdout.write(self.style.WARNING(
                    f"Пропускаю каталог '{book_slug}': нет описания книги в library/torah_data.py BOOKS"
                ))
                continue

            name_ru, name_he, sefaria_name, order, category_slug = BOOKS[book_slug]
            category = Category.objects.get(slug=category_slug)
            book, _ = Book.objects.update_or_create(
                slug=book_slug,
                defaults={
                    "name_ru": name_ru,
                    "name_he": name_he,
                    "order": order,
                    "category": category,
                },
            )

            for txt_file in sorted(book_dir.glob("*.txt")):
                self.import_parasha_file(book, sefaria_name, txt_file)

    def import_parasha_file(self, book: Book, sefaria_name: str, txt_file: Path):
        parasha_slug = txt_file.stem
        lines = txt_file.read_text(encoding="utf-8").splitlines()

        parsed = []
        for i, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            m = VERSE_LINE_RE.match(line)
            if not m:
                self.stdout.write(self.style.WARNING(
                    f"{txt_file.name}:{i}: не удалось разобрать строку {line!r}, пропускаю"
                ))
                continue
            chapter, verse, text_ru = int(m.group(1)), int(m.group(2)), m.group(3).strip()
            parsed.append((chapter, verse, text_ru))

        if not parsed:
            self.stdout.write(self.style.WARNING(f"{txt_file.name}: не найдено ни одного стиха"))
            return

        chapters_needed = sorted({chapter for chapter, verse, text_ru in parsed})
        he_cache_dir = TEXTS_HE_CACHE_DIR / book.slug
        he_by_chapter = {}
        for chapter in chapters_needed:
            he_verses = fetch_hebrew_chapter(sefaria_name, chapter, he_cache_dir)
            if he_verses is None:
                self.stdout.write(self.style.WARNING(
                    f"Не удалось получить иврит для {book.name_ru} {chapter} с Sefaria "
                    "(нет сети?) — текст на иврите будет пустым для этой главы"
                ))
            he_by_chapter[chapter] = he_verses

        verse_objs = []
        for chapter, verse, text_ru in parsed:
            he_verses = he_by_chapter.get(chapter)
            text_he = ""
            if he_verses and 1 <= verse <= len(he_verses):
                text_he = he_verses[verse - 1]

            obj, _ = Verse.objects.update_or_create(
                book=book,
                chapter=chapter,
                verse=verse,
                defaults={"text_ru": text_ru, "text_he": text_he},
            )
            verse_objs.append(obj)

        verse_objs.sort(key=lambda v: (v.chapter, v.verse))
        start_verse, end_verse = verse_objs[0], verse_objs[-1]

        name_ru, name_he, order = PARASHOT.get(
            parasha_slug, (parasha_slug.replace("-", " ").title(), "", 0)
        )
        Parasha.objects.update_or_create(
            slug=parasha_slug,
            defaults={
                "name_ru": name_ru,
                "name_he": name_he,
                "order": order,
                "start_verse": start_verse,
                "end_verse": end_verse,
            },
        )

        self.stdout.write(self.style.SUCCESS(
            f"{txt_file.name}: импортировано {len(verse_objs)} стихов "
            f"({start_verse} — {end_verse}), недельная глава '{name_ru}'"
        ))
