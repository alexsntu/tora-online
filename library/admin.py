from django.contrib import admin

from .models import Book, Category, Verse, Parasha, Material, Topic

admin.site.site_header = "Tora Online — панель управления"
admin.site.site_title = "Tora Online"
admin.site.index_title = "Управление сайтом"


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
    list_filter = ("type",)
    search_fields = ("title", "body")
    filter_horizontal = ("verses",)


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ("title", "slug")
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ("materials",)
