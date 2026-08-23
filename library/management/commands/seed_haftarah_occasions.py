from django.core.management.base import BaseCommand

from library.models import HaftarahOccasion

# (slug, name_ru, category, order) - особые даты для гафтарот, вне недельного цикла.
# Источник текстов: texts/ru_haftarah_occasions/<category>/<slug>/haftarah.txt
# (см. import_haftarot_occasions). Порядок внутри категории - как в оглавлении
# /haftarot/, задан пользователем при загрузке документа с текстами.
MANIFEST = [
    ("erev-rosh-chodesh-shabbat", "Шаббат Эрэв Рош ходеш", "dates", 8),
    ("rosh-hashana-1", "Рош а-Шана (1 день)", "dates", 1),
    ("rosh-hashana-2", "Рош а-Шана (2 день)", "dates", 2),
    ("shabbat-shuva", "Шаббат Шува", "dates", 3),
    ("yom-kippur", "Йом Кипур", "dates", 4),
    ("pesach-1", "Песах (1 день)", "regalim", 1),
    ("pesach-chol-hamoed", "Шаббат Холь а-Моэд (Песах)", "regalim", 2),
    ("pesach-7", "Песах (7 день)", "regalim", 3),
    ("shavuot", "Шавуот", "regalim", 4),
    ("sukkot-1", "Суккот (1 день)", "regalim", 10),
    ("sukkot-chol-hamoed", "Шаббат Холь а-Моэд (Суккот)", "regalim", 11),
    ("shmini-atzeret", "Шмини Ацерет", "regalim", 12),
    ("chanukah-shabbat-1", "1-й Шаббат Хануки", "dates", 5),
    ("chanukah-shabbat-2", "2-й Шаббат Хануки", "dates", 6),
    ("shabbat-shkalim", "Шаббат Шкалим", "arba_parshiyot", 1),
    ("shabbat-zachor", "Шаббат Захор", "arba_parshiyot", 2),
    ("shabbat-para", "Шаббат Пара", "arba_parshiyot", 3),
    ("shabbat-hachodesh", "Шаббат а-Ходеш", "arba_parshiyot", 4),
    ("shabbat-hagadol", "Шаббат а-Гадоль", "dates", 7),
    ("fast-day-mincha", "Общественный пост, Минха", "dates", 9),
]


class Command(BaseCommand):
    help = "Создаёт/обновляет HaftarahOccasion (особые даты для гафтарот) из MANIFEST."

    def handle(self, *args, **options):
        for slug, name_ru, category, order in MANIFEST:
            obj, created = HaftarahOccasion.objects.update_or_create(
                slug=slug, defaults={"name_ru": name_ru, "category": category, "order": order},
            )
            self.stdout.write(self.style.SUCCESS(f"{'создан' if created else 'обновлён'}: {obj}"))
