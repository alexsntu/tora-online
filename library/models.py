import io
import re
from pathlib import Path

from PIL import Image

from django.core.files.base import ContentFile
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
    description_ru = models.CharField(
        "Краткое описание", max_length=255, blank=True,
        help_text="Одна строка о содержании книги - показывается на главной, как на Sefaria",
    )
    meta_title = models.CharField(
        "SEO-заголовок страницы", max_length=255, blank=True,
        help_text="Заголовок вкладки браузера и сниппета в поиске. Пусто - формируется автоматически из названия книги.",
    )
    meta_description = models.CharField(
        "SEO-описание страницы", max_length=300, blank=True,
        help_text="Показывается в сниппете поисковой выдачи. Пусто - берётся краткое описание книги (или формируется автоматически).",
    )

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
    text_ru = models.TextField("Текст (рус., классический перевод)", blank=True)
    text_ru_slivniak = models.TextField(
        "Текст (рус., перевод Д. Сливняка)", blank=True,
        help_text="Da Project, 2011, CC BY-NC, с Sefaria",
    )

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
    meta_title = models.CharField(
        "SEO-заголовок страницы", max_length=255, blank=True,
        help_text="Пусто - формируется автоматически из названия недельной главы.",
    )
    meta_description = models.CharField(
        "SEO-описание страницы", max_length=300, blank=True,
        help_text="Показывается в сниппете поисковой выдачи. Пусто - формируется автоматически из книги и диапазона стихов.",
    )

    class Meta:
        ordering = ["order"]
        verbose_name = "недельная глава"
        verbose_name_plural = "Недельные главы"

    def __str__(self):
        return self.name_ru


class Haftarah(models.Model):
    """Гафтара недельной главы - отдельный раздел, не часть обычного текста Танаха
    (книги Пророков-источники не добавляются как Book, весь текст живёт только здесь,
    см. HaftarahVerse)."""
    TRADITION_ASHKENAZI = "ashkenazi"
    TRADITION_SEPHARDI = "sephardi"
    TRADITION_CHOICES = [
        (TRADITION_ASHKENAZI, "Ашкеназская"),
        (TRADITION_SEPHARDI, "Сефардская"),
    ]

    parasha = models.ForeignKey(
        Parasha, verbose_name="Недельная глава", related_name="haftarot", on_delete=models.CASCADE,
    )
    tradition = models.CharField("Традиция", max_length=20, choices=TRADITION_CHOICES)
    book_name_ru = models.CharField("Книга-источник (рус.)", max_length=100)
    book_name_he = models.CharField("Книга-источник (иврит)", max_length=100, blank=True)

    class Meta:
        ordering = ["parasha__order", "tradition"]
        unique_together = ("parasha", "tradition")
        verbose_name = "гафтара"
        verbose_name_plural = "Гафтарот"

    def __str__(self):
        return f"{self.parasha.name_ru} ({self.get_tradition_display()})"

    @property
    def range_display(self):
        """Например "Йешаяу 42:5-43:10" - книга и диапазон глав:стихов, чтобы
        было понятно, какой именно текст, не открывая саму гафтару."""
        verses = list(self.verses.all())
        if not verses:
            return self.book_name_ru
        first, last = verses[0], verses[-1]
        if first.chapter == last.chapter:
            span = f"{first.chapter}:{first.verse}-{last.verse}"
        else:
            span = f"{first.chapter}:{first.verse}-{last.chapter}:{last.verse}"
        return f"{self.book_name_ru} {span}"


class HaftarahVerse(models.Model):
    haftarah = models.ForeignKey(Haftarah, verbose_name="Гафтара", related_name="verses", on_delete=models.CASCADE)
    chapter = models.PositiveSmallIntegerField("Глава")
    verse = models.PositiveSmallIntegerField("Стих")
    text_he = models.TextField("Текст (иврит)", blank=True)
    text_ru = models.TextField("Текст (рус.)", blank=True)

    class Meta:
        ordering = ["chapter", "verse"]
        unique_together = ("haftarah", "chapter", "verse")
        verbose_name = "стих гафтары"
        verbose_name_plural = "Стихи гафтары"

    def __str__(self):
        return f"{self.haftarah} {self.chapter}:{self.verse}"


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
    sages = models.ManyToManyField(
        "Sage", verbose_name="Мудрецы Торы (на чьё учение опирается)",
        related_name="materials", blank=True,
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)

    # Закешированные lower()-версии title/body - чтобы поиск (_search_materials в views.py)
    # фильтровал на уровне БД (icontains), а не грузил все материалы и сравнивал в Python
    # (SQLite icontains не регистронезависим для кириллицы, отсюда и .lower() на записи).
    title_lower = models.CharField(max_length=255, editable=False, blank=True)
    body_lower = models.TextField(editable=False, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "материал"
        verbose_name_plural = "Материалы (комментарии)"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.title_lower = self.title.lower()
        self.body_lower = self.body.lower()
        super().save(*args, **kwargs)

    @property
    def youtube_embed_url(self):
        if self.type != self.TYPE_VIDEO or not self.url:
            return ""
        m = YOUTUBE_ID_RE.search(self.url)
        if not m:
            return ""
        return f"https://www.youtube.com/embed/{m.group(1)}"


class Commentary(models.Model):
    """Классический комментарий (Раши и т.п.), подтягиваемый с Sefaria - только на иврите."""

    verse = models.ForeignKey(Verse, verbose_name="Стих", related_name="commentaries", on_delete=models.CASCADE)
    source = models.CharField("Источник", max_length=100, help_text="Например, Раши")
    text_he = models.TextField("Текст (иврит)")
    sefaria_ref = models.CharField("Ссылка на Sefaria (тех.)", max_length=255, blank=True)

    class Meta:
        ordering = ["verse", "source"]
        verbose_name = "классический комментарий"
        verbose_name_plural = "Классические комментарии (Раши и т.п.)"

    def __str__(self):
        return f"{self.source} — {self.verse}"


class AnalyticsEvent(models.Model):
    """Лёгкий лог просмотров/кликов для контентной аналитики в админке."""

    CHAPTER_VIEW = "chapter_view"
    MATERIAL_OPEN = "material_open"
    OUTBOUND_CLICK = "outbound_click"
    EVENT_CHOICES = [
        (CHAPTER_VIEW, "Просмотр главы"),
        (MATERIAL_OPEN, "Открытие комментария"),
        (OUTBOUND_CLICK, "Переход по внешней ссылке"),
    ]

    event_type = models.CharField("Тип события", max_length=20, choices=EVENT_CHOICES)
    book = models.ForeignKey(Book, verbose_name="Книга", null=True, blank=True, on_delete=models.CASCADE)
    chapter = models.PositiveSmallIntegerField("Глава", null=True, blank=True)
    verse = models.ForeignKey(Verse, verbose_name="Стих", null=True, blank=True, on_delete=models.CASCADE)
    material = models.ForeignKey(Material, verbose_name="Материал", null=True, blank=True, on_delete=models.CASCADE)
    target = models.CharField("Куда", max_length=20, blank=True, help_text="youtube / rutube / article")
    created_at = models.DateTimeField("Когда", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "событие аналитики"
        verbose_name_plural = "Аналитика: события"

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.created_at:%Y-%m-%d %H:%M}"


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


class Sage(models.Model):
    """Мудрец Торы (комментатор), на чьё учение опирается материал -
    Зера Шимшон, Ор аХаим аКадош и т.п. Отдельный указатель, как у тем.
    Связь с Material - через Material.sages (related_name="materials")."""

    name_ru = models.CharField("Имя", max_length=255)
    slug = models.SlugField("Слаг (для ссылки)", unique=True)
    bio = models.TextField("Биография", blank=True, help_text="Короткая справка: кто это и когда жил")
    meta_title = models.CharField(
        "SEO-заголовок страницы", max_length=255, blank=True,
        help_text="Пусто - формируется автоматически из имени мудреца.",
    )
    meta_description = models.CharField(
        "SEO-описание страницы", max_length=300, blank=True,
        help_text="Показывается в сниппете поисковой выдачи. Пусто - берётся начало биографии.",
    )

    class Meta:
        ordering = ["name_ru"]
        verbose_name = "мудрец Торы"
        verbose_name_plural = "Мудрецы Торы (комментаторы)"

    def __str__(self):
        return self.name_ru


class Question(models.Model):
    """Вопрос от посетителя сайта автору. Отвечен = заполнено поле answer.
    Опубликован = отдельная галочка is_published (показывается на /questions/)."""

    text = models.TextField("Текст вопроса")
    title = models.CharField(
        "Заголовок (для публикации)", max_length=255, blank=True,
        help_text="Показывается на сайте вместо текста вопроса - заполняется при публикации",
    )
    asker_name = models.CharField("Имя (не публикуется)", max_length=255, blank=True)
    asker_email = models.EmailField("Email (не публикуется, для связи)", blank=True)
    answer = models.TextField("Ответ", blank=True)
    is_published = models.BooleanField("Опубликовать на сайте", default=False)
    created_at = models.DateTimeField("Дата вопроса", auto_now_add=True)
    answered_at = models.DateTimeField("Дата ответа", null=True, blank=True)
    meta_title = models.CharField(
        "SEO-заголовок страницы", max_length=255, blank=True,
        help_text="Пусто - формируется автоматически из заголовка вопроса.",
    )
    meta_description = models.CharField(
        "SEO-описание страницы", max_length=300, blank=True,
        help_text="Показывается в сниппете поисковой выдачи. Пусто - берётся начало ответа.",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "вопрос"
        verbose_name_plural = "Вопросы и ответы"

    def __str__(self):
        return self.title or self.text[:60]

    @property
    def is_answered(self):
        return bool(self.answer)

    @property
    def display_title(self):
        return self.title or self.text

    def save(self, *args, **kwargs):
        if self.answer and not self.answered_at:
            from django.utils import timezone
            self.answered_at = timezone.now()
        elif not self.answer:
            self.answered_at = None
        super().save(*args, **kwargs)


class ErrorReport(models.Model):
    """Сообщение об ошибке от посетителя (опечатка, неточность и т.п.),
    отправляется прямо со страницы, где её заметили."""

    description = models.TextField("Описание ошибки")
    page_url = models.CharField("Страница", max_length=500, blank=True)
    is_resolved = models.BooleanField("Обработано", default=False)
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "сообщение об ошибке"
        verbose_name_plural = "Сообщения об ошибках"

    def __str__(self):
        return self.description[:60]


class SiteSettings(models.Model):
    """Настройки сайта - одна запись (синглтон). Пока только robots.txt,
    остальное (User-agent/Allow/Sitemap) собирается автоматически в коде."""

    robots_extra = models.TextField(
        "Дополнительные строки robots.txt", blank=True,
        help_text="По одной директиве на строку, например: Disallow: /heaven/ - "
        "добавляются в конец robots.txt после основных правил.",
    )

    class Meta:
        verbose_name = "настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return "Настройки сайта"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class WeeklyPost(models.Model):
    """Еженедельный пост о новом уроке по недельной главе - тот же пост, что
    публикуется в Telegram-канале (картинка + текст + ссылки на видео).
    Показывается блоком на главной странице (последний опубликованный)."""

    title = models.CharField(
        "Заголовок", max_length=255,
        help_text="Например: Ки Теце - Парашат а-Шавуа 5786/2026",
    )
    image = models.ImageField("Картинка", upload_to="weekly_posts/", blank=True)
    body = models.TextField(
        "Текст поста", help_text="Можно выделять текст и делать жирным/курсивом/подчёркнутым.",
    )
    url_youtube = models.URLField("Ссылка на YouTube", blank=True)
    url_rutube = models.URLField("Ссылка на RuTube", blank=True)
    url_vk = models.URLField("Ссылка на VK Видео", blank=True)
    is_published = models.BooleanField("Опубликовать на сайте", default=True)
    created_at = models.DateTimeField("Дата публикации", auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "еженедельный пост"
        verbose_name_plural = "Еженедельные посты (главная страница)"

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        if self.image and not self.image.name.lower().endswith(".webp"):
            img = Image.open(self.image)
            img = img.convert("RGBA" if img.mode in ("RGBA", "LA", "P") else "RGB")
            img.thumbnail((1200, 1200))
            buffer = io.BytesIO()
            img.save(buffer, format="WEBP", quality=85)
            webp_name = Path(self.image.name).stem + ".webp"
            self.image.save(webp_name, ContentFile(buffer.getvalue()), save=False)
        super().save(*args, **kwargs)
