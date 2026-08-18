from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path

from axes.admin import AccessAttemptAdmin, IsLockedOutFilter
from axes.models import AccessAttempt

from .models import AnalyticsEvent, Book, Category, Verse, Parasha, Material, ErrorReport, Question, Sage, Topic
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


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    form = MaterialForm
    list_display = ("title", "type", "created_at")
    list_filter = ("type", "sages")
    search_fields = ("title", "body")
    # verses - выбор через виджет Книга/Глава/Стих (см. admin-verse-picker.js), не filter_horizontal;
    # обязательность (хотя бы 1 стих) проверяется в MaterialForm.clean_verses, не через model.blank=False -
    # required=True на самом (скрытом display:none) select дал бы невидимую браузерную HTML5-валидацию.
    # sages - выбор через виджет "выбрать + Добавить" (см. admin-sage-picker.js), не filter_horizontal/ctrl+click

    class Media:
        css = {"all": ("library/admin-extra.css",)}
        js = ("library/admin-verse-picker.js", "library/admin-sage-picker.js")

    def get_urls(self):
        custom_urls = [
            path(
                "verse-picker-data.json/",
                self.admin_site.admin_view(_verse_picker_data),
                name="library_material_verse_picker_data",
            ),
        ]
        return custom_urls + super().get_urls()

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
    fields = ("text", "asker_name", "asker_email", "created_at", "answer", "title", "is_published", "answered_at")
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


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "book", "chapter", "verse", "material", "target", "created_at")
    list_filter = ("event_type", "book")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
