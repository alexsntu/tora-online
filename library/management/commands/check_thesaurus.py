from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import models

from library.thesaurus import THESAURUS, find_wrong, normalize

# Где ищем русский текст в репозитории. Миграции не трогаем (это история),
# сам тезаурус перечисляет неверные написания намеренно.
FILE_GLOBS = ("library/**/*.py", "library/**/*.html", "templates/**/*.html", "config/**/*.py", "README.md")
FILE_EXCLUDE_PARTS = ("migrations",)
FILE_EXCLUDE_NAMES = ("thesaurus.py", "tests.py")

# Приложения, чьи текстовые поля проверяем в базе: контент портала и названия
# прав в админке (они создаются из verbose_name и сами не переименовываются).
DB_APP_LABELS = ("library", "auth")

# Записи, которые не трогаем и не считаем расхождением: (модель, pk).
DB_EXEMPT = {
    # Вопрос посетителя, в котором оба написания стоят намеренно - не исправлять.
    ("library.Question", 3),
}


class Command(BaseCommand):
    help = (
        "Проверяет, что термины из library/thesaurus.py везде написаны одинаково: "
        "в шаблонах, коде и текстовых полях базы. С --fix исправляет найденное в базе "
        "(файлы репозитория правятся руками и коммитятся)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--fix", action="store_true", help="Исправить неверные написания в базе")

    def handle(self, *args, **options):
        self.stdout.write("Тезаурус:")
        for term in THESAURUS:
            self.stdout.write(f"  {term.canonical} / {term.plural} ({term.hebrew}) - не пишем: {', '.join(term.wrong)}")

        file_hits = self.check_files()
        db_hits = self.check_db(fix=options["fix"])

        if not file_hits and not db_hits:
            self.stdout.write(self.style.SUCCESS("Расхождений с тезаурусом нет."))
        elif options["fix"]:
            self.stdout.write(self.style.SUCCESS(f"В базе исправлено значений: {db_hits}."))
            if file_hits:
                self.stdout.write(self.style.WARNING(f"В файлах осталось строк с расхождениями: {file_hits}."))
        else:
            self.stdout.write(self.style.WARNING(
                f"Расхождений: в файлах - {file_hits}, в базе - {db_hits}. "
                "Базу можно исправить через --fix."
            ))

    def check_files(self):
        hits = 0
        base = Path(settings.BASE_DIR)
        for pattern in FILE_GLOBS:
            for path in sorted(base.glob(pattern)):
                if path.name in FILE_EXCLUDE_NAMES or any(part in FILE_EXCLUDE_PARTS for part in path.parts):
                    continue
                for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    wrong = find_wrong(line)
                    if wrong:
                        hits += 1
                        self.stdout.write(f"{path.relative_to(base)}:{n}: {', '.join(wrong)}")
        return hits

    def check_db(self, fix):
        hits = 0
        for model in apps.get_models():
            if model._meta.app_label not in DB_APP_LABELS:
                continue
            fields = [
                f.name for f in model._meta.concrete_fields
                if isinstance(f, (models.CharField, models.TextField)) and not f.choices
            ]
            if not fields:
                continue
            for obj in model._default_manager.only("pk", *fields).iterator():
                if (model._meta.label, obj.pk) in DB_EXEMPT:
                    continue
                changed = {}
                for name in fields:
                    value = getattr(obj, name)
                    wrong = find_wrong(value) if value else []
                    if wrong:
                        hits += 1
                        changed[name] = normalize(value)
                        self.stdout.write(
                            f"{model._meta.label} #{obj.pk}, поле {name}: {', '.join(wrong)}"
                        )
                if fix and changed:
                    # update() вместо save(): правим только текст, без побочных
                    # эффектов save() и сигналов.
                    model._default_manager.filter(pk=obj.pk).update(**changed)
        return hits
