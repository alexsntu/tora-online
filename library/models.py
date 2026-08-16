import re

from django.db import models

YOUTUBE_ID_RE = re.compile(r"(?:v=|youtu\.be/|embed/)([A-Za-z0-9_-]{11})")


class Category(models.Model):
    """Раздел библиотеки: Танах, Тора/Невиим/Ктувим внутри него, Талмуд и т.д. (как на Sefaria)."""

    name_ru = models.CharField(max_length=100)
    name_he = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(unique=True)
    parent = models.ForeignKey(
        "self", null=True, blank=True, related_name="children", on_delete=models.CASCADE
    )
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name_ru


class Book(models.Model):
    category = models.ForeignKey(
        Category, related_name="books", on_delete=models.PROTECT, null=True, blank=True
    )
    name_ru = models.CharField(max_length=100)
    name_he = models.CharField(max_length=100, blank=True)
    slug = models.SlugField(unique=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name_ru


class Verse(models.Model):
    book = models.ForeignKey(Book, related_name="verses", on_delete=models.CASCADE)
    chapter = models.PositiveSmallIntegerField()
    verse = models.PositiveSmallIntegerField()
    text_he = models.TextField(blank=True)
    text_ru = models.TextField(blank=True)

    class Meta:
        ordering = ["book", "chapter", "verse"]
        unique_together = ("book", "chapter", "verse")

    def __str__(self):
        return f"{self.book.name_ru} {self.chapter}:{self.verse}"


class Parasha(models.Model):
    slug = models.SlugField(unique=True)
    name_ru = models.CharField(max_length=100)
    name_he = models.CharField(max_length=100, blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    start_verse = models.ForeignKey(
        Verse, related_name="parasha_start_of", on_delete=models.PROTECT
    )
    end_verse = models.ForeignKey(
        Verse, related_name="parasha_end_of", on_delete=models.PROTECT
    )

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name_ru


class Material(models.Model):
    TYPE_VIDEO = "video"
    TYPE_ARTICLE = "article"
    TYPE_CHOICES = [
        (TYPE_VIDEO, "Видеоурок"),
        (TYPE_ARTICLE, "Статья"),
    ]

    type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    url = models.URLField(blank=True, help_text="Ссылка на YouTube (для видеоурока)")
    body = models.TextField(blank=True, help_text="Текст статьи или комментарий")
    verses = models.ManyToManyField(Verse, related_name="materials", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

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
    title = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    materials = models.ManyToManyField(Material, related_name="topics", blank=True)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title
