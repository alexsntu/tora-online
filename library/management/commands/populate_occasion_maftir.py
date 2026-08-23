from django.core.management.base import BaseCommand
from django.db.models import Q

from library.models import HaftarahOccasion, OccasionMaftirVerse, Verse

# occasion_slug -> список сегментов (book_slug, start_chapter, start_verse, end_chapter, end_verse).
# Мафтир - доп. отрывок Торы для особой даты; текст уже есть в основном Танахе
# (полный текст Торы), поэтому здесь только ссылки на существующие Verse, без
# нового импорта. Источник: документ "Специальные главы Торы на праздники".
MAFTIR_MAP = {
    "rosh-hashana-1": [("bemidbar", 29, 1, 29, 6)],
    "rosh-hashana-2": [("bemidbar", 29, 1, 29, 6)],
    "yom-kippur": [("bemidbar", 29, 7, 29, 11)],
    "yom-kippur-mincha": [("vaikra", 18, 1, 18, 30)],
    "sukkot-1": [("vaikra", 22, 26, 23, 44)],
    "shmini-atzeret": [("devarim", 33, 1, 34, 12)],
    "shabbat-shkalim": [("shmot", 30, 11, 30, 16)],
    "shabbat-zachor": [("devarim", 25, 17, 25, 19)],
    "shabbat-para": [("bemidbar", 19, 1, 19, 22)],
    "shabbat-hachodesh": [("shmot", 12, 1, 12, 20)],
    "pesach-1": [("shmot", 12, 21, 12, 51)],
    "pesach-chol-hamoed": [("shmot", 33, 12, 34, 26)],
    "pesach-7": [("shmot", 13, 17, 15, 26)],
    "shavuot": [("bemidbar", 28, 26, 28, 31)],
    "fast-day-mincha": [("shmot", 32, 11, 32, 14), ("shmot", 34, 1, 34, 10)],
    "tisha-bav": [("devarim", 4, 25, 4, 40)],
}


class Command(BaseCommand):
    help = (
        "Привязывает мафтир (доп. отрывок Торы) к особым датам - ссылками на уже "
        "загруженный текст Торы (library.models.Verse), из MAFTIR_MAP."
    )

    def handle(self, *args, **options):
        for slug, segments in MAFTIR_MAP.items():
            try:
                occasion = HaftarahOccasion.objects.get(slug=slug)
            except HaftarahOccasion.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Пропускаю '{slug}': такой даты нет в базе"))
                continue

            occasion.maftir_verses.all().delete()
            order = 0
            for segment_num, (book_slug, sc, sv, ec, ev) in enumerate(segments):
                range_q = (
                    (Q(chapter__gt=sc) | Q(chapter=sc, verse__gte=sv))
                    & (Q(chapter__lt=ec) | Q(chapter=ec, verse__lte=ev))
                )
                verses = list(
                    Verse.objects.filter(book__slug=book_slug).filter(range_q).order_by("chapter", "verse")
                )
                if not verses:
                    self.stdout.write(self.style.WARNING(
                        f"{slug}: не нашёл стихов {book_slug} {sc}:{sv}-{ec}:{ev} в базе"
                    ))
                    continue
                for v in verses:
                    OccasionMaftirVerse.objects.create(
                        occasion=occasion, order=order, segment=segment_num, verse=v,
                    )
                    order += 1

            self.stdout.write(self.style.SUCCESS(
                f"{slug}: мафтир проставлен ({order} стихов) - {occasion.maftir_range_display}"
            ))
