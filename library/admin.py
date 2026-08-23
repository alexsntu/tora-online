from django import forms
from django.contrib import admin
from django.http import HttpResponseRedirect, JsonResponse
from django.urls import path, reverse

from axes.admin import AccessAttemptAdmin, IsLockedOutFilter
from axes.models import AccessAttempt

from .models import (
    AnalyticsEvent, Book, Category, Verse, Parasha, Haftarah, HaftarahOccasion, HaftarahVerse, Material, ErrorReport,
    Question, Sage, SiteSettings, Topic, WeeklyPost,
)
from .views import analytics_dashboard

admin.site.site_header = "Tora Online — панель управления"
admin.site.site_title = "Tora Online"
admin.site.index_title = "Управление сайтом"

_default_get_urls = admin.site.get_urls


def _get_urls_with_analytics():
    return [
        path("analytics/", admin.site.admin_view(analytics_dashboard), name="analytics_dashboard"),
    ] + _default_get_urls()


admin.site.get_urls = _get_urls_with_analytics

_default_index = admin.site.index


def _index_with_question_badge(request, extra_context=None):
    extra_context = extra_context or {}
    extra_context["unanswered_questions_count"] = Question.objects.filter(answer="").count()
    return _default_index(request, extra_context)


admin.site.index = _index_with_question_badge

_default_each_context = admin.site.each_context


def _each_context_with_error_badge(request):
    context = _default_each_context(request)
    context["unresolved_errors_count"] = ErrorReport.objects.filter(is_resolved=False).count()
    return context


admin.site.each_context = _each_context_with_error_badge


class _RuIsLockedOutFilter(IsLockedOutFilter):
    """axes не перевёл строку "Locked Out" в своём ru-каталоге - переопределяем."""

    title = "Заблокирован"


if admin.site.is_registered(AccessAttempt):
    admin.site.unregister(AccessAttempt)


@admin.register(AccessAttempt)
class RuAccessAttemptAdmin(AccessAttemptAdmin):
    list_filter = [
        _RuIsLockedOutFilter if f is IsLockedOutFilter else f
        for f in AccessAttemptAdmin.list_filter
    ]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_he", "slug", "parent", "order")
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_he", "slug", "category", "order")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(Verse)
class VerseAdmin(admin.ModelAdmin):
    list_display = ("book", "chapter", "verse")
    list_filter = ("book", "chapter")
    search_fields = ("text_ru", "text_he")


@admin.register(Parasha)
class ParashaAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_he", "slug", "order", "start_verse", "end_verse")
    prepopulated_fields = {"slug": ("name_ru",)}


class HaftarahVerseInline(admin.TabularInline):
    model = HaftarahVerse
    extra = 0
    ordering = ("order",)


@admin.register(HaftarahOccasion)
class HaftarahOccasionAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_he", "slug", "category", "order")
    list_filter = ("category",)
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(Haftarah)
class HaftarahAdmin(admin.ModelAdmin):
    list_display = ("__str__", "parasha", "occasion", "tradition", "range_display")
    list_filter = ("tradition", "occasion__category")
    inlines = [HaftarahVerseInline]


def _verse_picker_data(request):
    """Данные для виджета выбора стиха (Книга/Глава/Стих) на странице материала - см. admin-verse-picker.js."""
    books = list(Book.objects.order_by("order").values("id", "name_ru"))
    verses_by_book = {}
    for book_id, chapter, verse_id, verse_num in Verse.objects.order_by(
        "book", "chapter", "verse"
    ).values_list("book_id", "chapter", "id", "verse"):
        verses_by_book.setdefault(str(book_id), {}).setdefault(str(chapter), []).append(
            [verse_id, verse_num]
        )
    return JsonResponse({"books": books, "verses": verses_by_book})


class MaterialForm(forms.ModelForm):
    class Meta:
        model = Material
        fields = "__all__"

    def clean_verses(self):
        verses = self.cleaned_data.get("verses")
        if not verses:
            raise forms.ValidationError("Нужно выбрать хотя бы один стих, прежде чем сохранить материал.")
        return verses


def _format_verse_refs(verses):
    """Группирует стихи материала в компактную ссылку вида "Берешит 1:26-27; Шмот 2:3" для колонки в списке."""
    groups = {}
    order_by_group = {}
    for v in verses:
        key = (v.book_id, v.chapter)
        groups.setdefault(key, []).append(v.verse)
        order_by_group[key] = (v.book.order, v.book.name_ru, v.chapter)

    parts = []
    for key in sorted(groups, key=lambda k: order_by_group[k]):
        _, book_name, chapter = order_by_group[key]
        nums = sorted(set(groups[key]))
        ranges = []
        start = prev = nums[0]
        for n in nums[1:]:
            if n == prev + 1:
                prev = n
                continue
            ranges.append((start, prev))
            start = prev = n
        ranges.append((start, prev))
        range_str = ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in ranges)
        parts.append(f"{book_name} {chapter}:{range_str}")
    return "; ".join(parts)


class MaterialBookFilter(admin.SimpleListFilter):
    title = "Книга"
    parameter_name = "book"

    def lookups(self, request, model_admin):
        book_ids = Material.objects.filter(verses__isnull=False).values_list("verses__book_id", flat=True).distinct()
        books = Book.objects.filter(id__in=book_ids).order_by("order")
        return [(b.id, b.name_ru) for b in books]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(verses__book_id=self.value()).distinct()
        return queryset

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name, "chapter", "verse"]),
            "display": "Все",
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": str(self.value()) == str(lookup),
                "query_string": changelist.get_query_string({self.parameter_name: lookup}, remove=["chapter", "verse"]),
                "display": title,
            }


class MaterialChapterFilter(admin.SimpleListFilter):
    title = "Глава"
    parameter_name = "chapter"

    def lookups(self, request, model_admin):
        book_id = request.GET.get("book")
        if not book_id:
            return []
        chapters = (
            Material.objects.filter(verses__book_id=book_id)
            .values_list("verses__chapter", flat=True)
            .distinct()
            .order_by("verses__chapter")
        )
        return [(c, str(c)) for c in chapters]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(verses__chapter=self.value()).distinct()
        return queryset

    def choices(self, changelist):
        yield {
            "selected": self.value() is None,
            "query_string": changelist.get_query_string(remove=[self.parameter_name, "verse"]),
            "display": "Все",
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": str(self.value()) == str(lookup),
                "query_string": changelist.get_query_string({self.parameter_name: lookup}, remove=["verse"]),
                "display": title,
            }


class MaterialVerseFilter(admin.SimpleListFilter):
    title = "Стих"
    parameter_name = "verse"

    def lookups(self, request, model_admin):
        book_id = request.GET.get("book")
        chapter = request.GET.get("chapter")
        if not book_id or not chapter:
            return []
        verse_nums = (
            Material.objects.filter(verses__book_id=book_id, verses__chapter=chapter)
            .values_list("verses__verse", flat=True)
            .distinct()
            .order_by("verses__verse")
        )
        return [(v, str(v)) for v in verse_nums]

    def queryset(self, request, queryset):
        if self.value():
            return queryset.filter(
                verses__book_id=request.GET.get("book"),
                verses__chapter=request.GET.get("chapter"),
                verses__verse=self.value(),
            ).distinct()
        return queryset


MATERIAL_PAGE_SIZES = (10, 25, 50)


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    form = MaterialForm
    change_list_template = "admin/library/material/change_list.html"
    list_display = ("title", "type", "verses_display", "created_at")
    list_filter = ("type", MaterialBookFilter, MaterialChapterFilter, MaterialVerseFilter, "sages")
    search_fields = ("title", "body")
    list_per_page = MATERIAL_PAGE_SIZES[1]  # 25 по умолчанию
    # verses - выбор через виджет Книга/Глава/Стих (см. admin-verse-picker.js), не filter_horizontal;
    # обязательность (хотя бы 1 стих) проверяется в MaterialForm.clean_verses, не через model.blank=False -
    # required=True на самом (скрытом display:none) select дал бы невидимую браузерную HTML5-валидацию.
    # sages - выбор через виджет "выбрать + Добавить" (см. admin-sage-picker.js), не filter_horizontal/ctrl+click

    class Media:
        css = {"all": ("library/admin-extra.css",)}
        js = ("library/admin-verse-picker.js", "library/admin-sage-picker.js")

    def changelist_view(self, request, extra_context=None):
        # list_per_page переопределяется на инстансе (singleton ModelAdmin) из query-параметра -
        # безопасно в рамках одного request/response цикла, значение пересчитывается заново на каждый запрос.
        try:
            per_page = int(request.GET.get("list_per_page", self.list_per_page))
        except (TypeError, ValueError):
            per_page = self.list_per_page
        if per_page not in MATERIAL_PAGE_SIZES:
            per_page = MATERIAL_PAGE_SIZES[1]
        self.list_per_page = per_page

        # ChangeList трактует любой незнакомый GET-параметр как lookup по полю модели
        # (FieldError) - list_per_page не поле, поэтому убираем его из GET до вызова super().
        if "list_per_page" in request.GET:
            request.GET = request.GET.copy()
            del request.GET["list_per_page"]

        extra_context = extra_context or {}
        extra_context["material_page_sizes"] = MATERIAL_PAGE_SIZES
        extra_context["material_current_page_size"] = per_page
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        custom_urls = [
            path(
                "verse-picker-data.json/",
                self.admin_site.admin_view(_verse_picker_data),
                name="library_material_verse_picker_data",
            ),
        ]
        return custom_urls + super().get_urls()

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related("verses__book")

    @admin.display(description="Стихи")
    def verses_display(self, obj):
        return _format_verse_refs(obj.verses.all()) or "—"

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "title":
            field.widget.attrs["style"] = "width: 95%; max-width: 900px; font-size: 1.1em;"
        if db_field.name in ("verses", "sages"):
            # выбор идёт через виджет "выбрать + Добавить" - подсказка про Ctrl/Command неактуальна
            field.help_text = ""
        return field


@admin.register(Sage)
class SageAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("materials",)


class QuestionStatusFilter(admin.SimpleListFilter):
    title = "статус"
    parameter_name = "status"

    def lookups(self, request, model_admin):
        return (
            ("new", "Новые (без ответа)"),
            ("answered", "Отвечены"),
            ("published", "Опубликованы"),
        )

    def queryset(self, request, queryset):
        if self.value() == "new":
            return queryset.filter(answer="")
        if self.value() == "answered":
            return queryset.exclude(answer="")
        if self.value() == "published":
            return queryset.filter(is_published=True)
        return queryset


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("text_preview", "is_answered", "is_published", "created_at", "answered_at")
    list_filter = (QuestionStatusFilter,)
    search_fields = ("text", "answer", "asker_name", "asker_email")
    fields = (
        "text", "asker_name", "asker_email", "created_at", "answer", "title", "is_published", "answered_at",
        "meta_title", "meta_description",
    )
    readonly_fields = ("asker_name", "asker_email", "created_at", "answered_at")

    @admin.display(description="Вопрос")
    def text_preview(self, obj):
        return obj.display_title[:80]

    @admin.display(description="Отвечен", boolean=True)
    def is_answered(self, obj):
        return obj.is_answered


@admin.register(ErrorReport)
class ErrorReportAdmin(admin.ModelAdmin):
    list_display = ("description_preview", "page_url", "is_resolved", "created_at")
    list_filter = ("is_resolved",)
    search_fields = ("description", "page_url")
    fields = ("description", "page_url", "created_at", "is_resolved")
    readonly_fields = ("description", "page_url", "created_at")

    @admin.display(description="Описание")
    def description_preview(self, obj):
        return obj.description[:80]


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    """Синглтон - одна запись на весь сайт, нельзя добавить вторую или удалить единственную."""

    fields = ("robots_extra",)

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        obj = SiteSettings.load()
        return HttpResponseRedirect(reverse("admin:library_sitesettings_change", args=[obj.pk]))


@admin.register(WeeklyPost)
class WeeklyPostAdmin(admin.ModelAdmin):
    list_display = ("title", "is_published", "created_at")
    list_filter = ("is_published",)
    fields = ("title", "image", "body", "url_youtube", "url_rutube", "url_vk", "is_published", "created_at")
    readonly_fields = ("created_at",)

    class Media:
        css = {"all": ("library/admin-extra.css",)}
        js = ("library/admin-richtext.js",)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "book", "chapter", "verse", "material", "target", "created_at")
    list_filter = ("event_type", "book")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
