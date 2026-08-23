import urllib.error
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand

from library.torah_data import PARASHOT

# Гугл-доки с гафтарот, один на книгу Торы: вкладка Google Docs = недельная глава.
# Экспорт в текст (?format=txt) отдаёт ВСЕ вкладки одним файлом подряд, каждая
# со своим заголовком "Г̃афтара недельной главы Торы «...»".
DOC_IDS = [
    "1YeMEN4iGC9-JP0IUeQOcaubvAJ2f9-jEux8eceXQZwU",  # Берешит
    "1YES1JySEnjgXI2xPbLIK5OUsaUqNSL0JT34DVSYj-Ek",  # Шмот
    "12KAO637KSw3bc8CXMY68LnbMA5qXA2NlQ0aTN0ser0o",  # Ваикра
    "1YUsVVsYmgRjhYY5BqKvHSe1N6zUMvic0NwglFS4NQ2A",  # Бемидбар
    "1ZxFYM7nxCs4XmtTWEOzr6SDCJCcVP2tDKgLzavbYSpU",  # Дварим
]

TEXTS_RU_HAFTARAH_DIR = Path(settings.BASE_DIR) / "texts" / "ru_haftarah"

# Обычно "Г̃афтара недельной главы Торы «...»", но у особых гафтарот (напр.
# суббота "Шува" перед Йом Кипуром) заголовок другой - "Г̃афтара Шаббата «Шува»
# глава Ваелех". Общее для всех - начинается с "афтара" (без регистра для "Г/г").
HAFTARAH_HEADER_MARKERS = ("афтара недельной главы торы", "афтара шаббата")

# Заголовок вкладки в документе иногда пишется не так, как у нас в PARASHOT
# (другой вариант транслитерации/написания) - явные исключения сюда.
DOC_PARASHA_ALIASES = {
    "Лех-леха": "lech-lecha",
    "Вайэра": "vayera",
    "Хайей Сара": "chayei-sara",
    "Толедот": "toldot",
    "Вайэцэ": "vayetze",
    "Вайэшэв": "vayeshev",
    "Микэц": "miketz",
    "Вайхи": "vayechi",
    "Йитро": "yitro",
    "Терума": "teruma",
    "Ки тиса": "ki-tisa",
    "Вайакг̃эль": "vayakhel",
    "Пекудэй": "pekudei",
    "Вайикра": "vaikra",
    "Шемини": "shmini",
    "Ахарей мот": "achrei-mot",
    "Кедошим": "kedoshim",
    "Бег̃ар": "behar",
    "Бег̃аа̃лотеха́́": "behaalotcha",
    "Шелах-леха": "shlach",
    "Пинехас": "pinchas",
    "Масъэй": "masei",
    "Деварим": "devarim",
    "Экэв": "eikev",
    "Шофетим": "shoftim",
    "Ки тецэ": "ki-teitzei",
    "Ки таво": "ki-tavo",
    "Г̃аазину": "haazinu",
    "Ве-зот г̃абераха": "vezot-habracha",
    "Ваелех": "vayeilech",
}

NAME_RU_TO_SLUG = {name_ru: slug for slug, (name_ru, name_he, order) in PARASHOT.items()}


class Command(BaseCommand):
    help = (
        "Скачивает общий документ с гафтарот (Google Docs, вкладка = недельная глава), "
        "раскладывает найденные вкладки по texts/ru_haftarah/<глава>/haftarah.txt "
        "и запускает import_haftarot. Разбор структуры текста (книга, диапазоны, "
        "традиции) - в import_haftarot, здесь только нарезка на вкладки."
    )

    def handle(self, *args, **options):
        written = []
        for doc_id in DOC_IDS:
            written += self.sync_one_doc(doc_id)

        if not written:
            self.stdout.write(self.style.WARNING("Ни одной вкладки не удалось разложить в файлы"))
            return

        self.stdout.write(self.style.SUCCESS(f"Разложено вкладок: {len(written)}"))
        for title, path in written:
            self.stdout.write(f"  {title} -> {path.relative_to(settings.BASE_DIR)}")

        self.stdout.write("Запускаю import_haftarot...")
        call_command("import_haftarot")

    def sync_one_doc(self, doc_id):
        export_url = f"https://docs.google.com/document/d/{doc_id}/export?format=txt"
        try:
            with urllib.request.urlopen(export_url, timeout=20) as resp:
                raw = resp.read().decode("utf-8-sig")
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            self.stderr.write(self.style.ERROR(f"Не удалось скачать документ {doc_id}: {e}"))
            return []

        lines = raw.splitlines()
        header_idxs = [
            i for i, line in enumerate(lines)
            if any(marker in line.lower() for marker in HAFTARAH_HEADER_MARKERS)
        ]
        if not header_idxs:
            self.stdout.write(self.style.WARNING(f"Документ {doc_id}: не нашлось ни одной вкладки с гафтарой"))
            return []

        written = []
        for n, j in enumerate(header_idxs):
            title = lines[j - 1].strip() if j > 0 else ""
            start = j - 1 if j > 0 else j
            end = (header_idxs[n + 1] - 1) if n + 1 < len(header_idxs) else len(lines)
            block_lines = lines[start:end]

            parasha_slug = NAME_RU_TO_SLUG.get(title) or DOC_PARASHA_ALIASES.get(title)
            if not parasha_slug:
                self.stdout.write(self.style.WARNING(
                    f"Вкладка с заголовком '{title}' - не нахожу такую недельную главу "
                    "в library/torah_data.py PARASHOT, пропускаю"
                ))
                continue

            out_dir = TEXTS_RU_HAFTARAH_DIR / parasha_slug
            out_dir.mkdir(parents=True, exist_ok=True)
            out_path = out_dir / "haftarah.txt"
            out_path.write_text("\n".join(block_lines).strip() + "\n", encoding="utf-8")
            written.append((title, out_path))

        return written
