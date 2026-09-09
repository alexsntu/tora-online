from django.db import migrations
from django.utils.text import slugify

_RU_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
    "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
    "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
    "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
    "я": "ya",
}


def slugify_ru(text):
    transliterated = "".join(_RU_TRANSLIT.get(ch, ch) for ch in text.lower())
    return slugify(transliterated)


def backfill_question_slug(apps, schema_editor):
    Question = apps.get_model("library", "Question")
    used = set(Question.objects.exclude(slug=None).exclude(slug="").values_list("slug", flat=True))
    for q in Question.objects.filter(is_published=True).filter(slug__isnull=True).order_by("pk"):
        base_slug = slugify_ru(q.title or q.text) or "vopros"
        slug = base_slug
        n = 2
        while slug in used:
            slug = f"{base_slug}-{n}"
            n += 1
        used.add(slug)
        Question.objects.filter(pk=q.pk).update(slug=slug)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('library', '0027_question_slug'),
    ]

    operations = [
        migrations.RunPython(backfill_question_slug, noop),
    ]
