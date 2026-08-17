from django.contrib import admin
from django.urls import path

from axes.admin import AccessAttemptAdmin, IsLockedOutFilter
from axes.models import AccessAttempt

from .models import AnalyticsEvent, Book, Category, Verse, Parasha, Material, Sage, Topic
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


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "created_at")
    list_filter = ("type", "sages")
    search_fields = ("title", "body")
    filter_horizontal = ("verses",)
    # sages - обычный select (не filter_horizontal), по просьбе пользователя


@admin.register(Sage)
class SageAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "slug")
    prepopulated_fields = {"slug": ("name_ru",)}


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("materials",)


@admin.register(AnalyticsEvent)
class AnalyticsEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "book", "chapter", "verse", "material", "target", "created_at")
    list_filter = ("event_type", "book")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
