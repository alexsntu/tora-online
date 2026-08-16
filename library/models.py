import re

from django.db import models

YOUTUBE_ID_RE = re.compile(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})")


class Category(models.Model):
    """Раздел библиотеки: Танах, Тора/Невиим/Ктувим внутри него, Талмуд и т.д. (как на Sefaria)."""

    name_ru = models.CharField("Название (рус.)", max_length=100)
    name_he = models.CharField("Название (иврит)", max_length=100, blank=True)
    slug = models.SlugField("Слаг (для ссылки)", unique=True)
    parent = models.ForeignKey(
        "self", verbose_name="Родительский раздел",
        null=True, blank=True, related_name="children", on_delete=models.CASCADE,
    )
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "раздел"
        verbose_name_plural = "Разделы библиотеки"

    def __str__(self):
        return self.name_ru


class Book(models.Model):
    category = models.ForeignKey(
        Category, verbose_name="Раздел",
        related_name="books", on_delete=models.PROTECT, null=True, blank=True,
    )
    name_ru = models.CharField("Название (рус.)", max_length=100)
    name_he = models.CharField("Название (иврит)", max_length=100, blank=True)
    slug = models.SlugField("Слаг (для ссылки)", unique=True)
    order = models.PositiveSmallIntegerField("Порядок", default=0)

    class Meta:
        ordering = ["order"]
        verbose_name = "книга"
        verbose_name_plural = "Книги"

    def __str__(self):
        return self.name_ru


class Verse(models.Model):
    book = models.ForeignKey(Book, verbose_name="Книга", related_name="verses", on_delete=models.CASCADE)
    chapter = models.PositiveSmallIntegerField("Глава")
    verse = models.PositiveSmallIntegerField("Стих")
    text_he = models.TextField("Текст (иврит)", blank=True)
    text_ru = models.TextField("Текст (рус.)", blank=True)

    class Meta:
        ordering = ["book", "chapter", "verse"]
        unique_together = ("book", "chapter", "verse")
        verbose_name = "стих"
        verbose_name_plural = "Стихи"

    def __str__(self):
        return f"{self.book.name_ru} {self.chapter}:{self.verse}"


class Parasha(models.Model):
    slug = models.SlugField("Слаг (для ссылки)", unique=True)
    name_ru = models.CharField("Название (рус.)", max_length=100)
    name_he = models.CharField("Название (иврит)", max_length=100, blank=True)
    order = models.PositiveSmallIntegerField("Порядок", default=0)
    start_verse = models.ForeignKey(
        Verse, verbose_name="Первый стих", related_name="parasha_start_of", on_delete=models.PROTECT,
    )
    end_verse = models.ForeignKey(
        Verse, verbose_name="Последний стих", related_name="parasha_end_of", on_delete=models.PROTECT,
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "недельная глава"
        verbose_name_plural = "Недельные главы"

    def __str__(self):
        return self.name_ru


class Material(models.Model):
    TYPE_VIDEO = "video"
    TYPE_ARTICLE = "article"
    TYPE_CHOICES = [
        (TYPE_VIDEO, "Видеоурок"),
        (TYPE_ARTICLE, "Статья"),
    ]

    type = models.CharField("Тип", max_length=10, choices=TYPE_CHOICES)
    title = models.CharField("Заголовок", max_length=255)
    url = models.URLField("Ссылка (YouTube / статья)", blank=True, help_text="Ссылка на YouTube (для видеоурока) или на статью")
    url_rutube = models.URLField("Ссылка (RuTube)", blank=True, help_text="Ссылка на RuTube (если есть, для видеоурока)")
    body = models.TextField("Текст статьи / комментарий", blank=True, help_text="Текст статьи или комментарий")
    verses = models.ManyToManyField(Verse, verbose_name="Стихи", related_name="materials", blank=True)
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "материал"
        verbose_name_plural = "Материалы (комментарии)"

    def __str__(self):
        return self.title

    @property
    def youtube_embed_url(self):
        if self.type != self.TYPE_VIDEO or not self.url:
            return ""
        m = YOUTUBE_ID_RE.search(self.url)
        if not m:
            return ""
        return f"https://www.youtube.com/embed/{m.group(1)}"


class Topic(models.Model):
    title = models.CharField("Заголовок", max_length=255)
    slug = models.SlugField("Слаг (для ссылки)", unique=True)
    materials = models.ManyToManyField(Material, verbose_name="Материалы", related_name="topics", blank=True)

    class Meta:
        ordering = ["title"]
        verbose_name = "тема / вопрос"
        verbose_name_plural = "Темы и вопросы"

    def __str__(self):
        return self.title
