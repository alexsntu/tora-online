from django.core.management.base import BaseCommand

from library.aliyot_data import ALIYOT
from library.models import AliyahMarker, Parasha, Verse


class Command(BaseCommand):
    help = (
        "Проставляет границы 7 алий для каждой недельной главы, из library/aliyot_data.py "
        "(источник - Sefaria, статичная разбивка, не зависит от календаря конкретного года)."
    )

    def handle(self, *args, **options):
        for slug, aliyot in ALIYOT.items():
            try:
                parasha = Parasha.objects.get(slug=slug)
            except Parasha.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Пропускаю '{slug}': такой недельной главы нет в базе"))
                continue

            AliyahMarker.objects.filter(parasha=parasha).delete()
            created = 0
            for number, (book_slug, sc, sv, ec, ev) in enumerate(aliyot, start=1):
                try:
                    start_verse = Verse.objects.get(book__slug=book_slug, chapter=sc, verse=sv)
                except Verse.DoesNotExist:
                    self.stdout.write(self.style.WARNING(
                        f"{slug}: не нашёл стих {book_slug} {sc}:{sv} (алия {number}) в базе"
                    ))
                    continue
                AliyahMarker.objects.create(parasha=parasha, number=number, start_verse=start_verse)
                created += 1

            self.stdout.write(self.style.SUCCESS(f"{slug}: проставлено алий: {created}"))
