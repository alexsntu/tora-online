from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from library.models import HaftarahOccasion

from .import_haftarot import import_haftarah_file

TEXTS_RU_HAFTARAH_OCCASIONS_DIR = Path(settings.BASE_DIR) / "texts" / "ru_haftarah_occasions"


class Command(BaseCommand):
    help = (
        "Импортирует тексты гафтарот особых дат из "
        "texts/ru_haftarah_occasions/<категория>/<дата>/haftarah.txt (категория - "
        "dates/regalim/arba_parshiyot, см. HaftarahOccasion.CATEGORY_CHOICES). "
        "Сама HaftarahOccasion должна быть уже создана (в админке или через shell) - "
        "команда только заливает текст в уже существующую дату, как import_haftarot "
        "для недельных глав."
    )

    def handle(self, *args, **options):
        if not TEXTS_RU_HAFTARAH_OCCASIONS_DIR.exists():
            raise CommandError(f"Нет каталога {TEXTS_RU_HAFTARAH_OCCASIONS_DIR}")

        for category_dir in sorted(TEXTS_RU_HAFTARAH_OCCASIONS_DIR.iterdir()):
            if not category_dir.is_dir():
                continue
            for occasion_dir in sorted(category_dir.iterdir()):
                if not occasion_dir.is_dir():
                    continue
                occasion_slug = occasion_dir.name
                try:
                    occasion = HaftarahOccasion.objects.get(slug=occasion_slug)
                except HaftarahOccasion.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"Пропускаю '{occasion_slug}': такой особой даты нет в базе "
                        "(создай HaftarahOccasion в админке или через shell)"
                    ))
                    continue

                txt_file = occasion_dir / "haftarah.txt"
                if not txt_file.exists():
                    self.stdout.write(self.style.WARNING(f"{occasion_dir}: нет файла haftarah.txt"))
                    continue
                import_haftarah_file(txt_file, {"occasion": occasion}, self.stdout, self.style)
