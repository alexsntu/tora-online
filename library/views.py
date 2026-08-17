import json
from itertools import groupby
from pathlib import Path

from django.conf import settings
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .hebrew_calendar import (
    GREGORIAN_MONTH_CHOICES,
    HEBREW_MONTH_CHOICES,
    convert_gregorian_to_hebrew,
    convert_hebrew_to_gregorian,
    today_info,
)
from .models import AnalyticsEvent, Book, Category, Material, Parasha, Sage, Verse


def service_worker(request):
    """Отдаём service worker с корня сайта, чтобы его scope покрывал весь домен."""
    path = Path(settings.BASE_DIR) / "library" / "static" / "library" / "service-worker.js"
    return HttpResponse(path.read_text(encoding="utf-8"), content_type="application/javascript")


def build_nav_data(verses):
    """chapter (str) -> [[verse, has_materials], ...] для каскадных селектов "Глава/Стих"."""
    data = {}
    for v in verses:
        data.setdefault(str(v.chapter), []).append([v.verse, bool(v.materials.all())])
    return data


def attach_parasha_starts(verses, book):
    """Помечает стихи, с которых начинается недельная глава (verse.starts_parasha)."""
    starts = {
        (p.start_verse.chapter, p.start_verse.verse): p
        for p in Parasha.objects.filter(start_verse__book=book).select_related("start_verse")
    }
    verses = list(verses)
    for v in verses:
        v.starts_parasha = starts.get((v.chapter, v.verse))
    return verses


def home(request):
    categories = list(Category.objects.order_by("order"))
    books = list(Book.objects.select_related("category").order_by("order"))

    books_by_category = {}
    for book in books:
        books_by_category.setdefault(book.category_id, []).append(book)

    children_by_parent = {}
    for cat in categories:
        children_by_parent.setdefault(cat.parent_id, []).append(cat)

    for cat in categories:
        cat.child_categories = children_by_parent.get(cat.id, [])
        cat.own_books = books_by_category.get(cat.id, [])

    top_categories = children_by_parent.get(None, [])

    return render(
        request,
        "library/home.html",
        {
            "top_categories": top_categories,
            "today": today_info(),
        },
    )


def book_view(request, book_slug):
    """Страница книги (как на Sefaria): сетка глав + недельные главы этой книги."""
    book = get_object_or_404(Book, slug=book_slug)
    chapters = list(
        Verse.objects.filter(book=book).order_by("chapter").values_list("chapter", flat=True).distinct()
    )
    parashot = list(
        Parasha.objects.filter(start_verse__book=book)
        .select_related("start_verse", "end_verse")
        .order_by("order")
    )
    return render(
        request,
        "library/book.html",
        {"book": book, "chapters": chapters, "parashot": parashot},
    )


def chapter_view(request, book_slug, chapter):
    book = get_object_or_404(Book, slug=book_slug)
    verses = (
        Verse.objects.filter(book=book, chapter=chapter)
        .prefetch_related("materials", "commentaries")
        .order_by("verse")
    )
    if not verses.exists():
        raise Http404("Глава не найдена")

    last_verse = Verse.objects.filter(book=book).order_by("-chapter").first()
    max_chapter = last_verse.chapter if last_verse else chapter

    nav_verses = Verse.objects.filter(book=book).prefetch_related("materials").order_by("chapter", "verse")
    verses = attach_parasha_starts(verses, book)

    AnalyticsEvent.objects.create(event_type=AnalyticsEvent.CHAPTER_VIEW, book=book, chapter=chapter)

    context = {
        "book": book,
        "chapter": chapter,
        "verses": verses,
        "title": f"{book.name_ru}, глава {chapter}",
        "prev_chapter": chapter - 1 if chapter > 1 else None,
        "next_chapter": chapter + 1 if chapter < max_chapter else None,
        "nav_data": build_nav_data(nav_verses),
        "current_chapter": chapter,
    }
    return render(request, "library/chapter.html", context)


def parasha_view(request, parasha_slug):
    parasha = get_object_or_404(Parasha, slug=parasha_slug)
    start, end = parasha.start_verse, parasha.end_verse

    verses = (
        Verse.objects.filter(book=start.book)
        .filter(Q(chapter__gt=start.chapter) | Q(chapter=start.chapter, verse__gte=start.verse))
        .filter(Q(chapter__lt=end.chapter) | Q(chapter=end.chapter, verse__lte=end.verse))
        .order_by("chapter", "verse")
        .prefetch_related("materials", "commentaries")
    )
    verses = attach_parasha_starts(verses, start.book)

    prev_parasha = (
        Parasha.objects.filter(order__lt=parasha.order).order_by("-order").first()
    )
    next_parasha = (
        Parasha.objects.filter(order__gt=parasha.order).order_by("order").first()
    )

    context = {
        "book": start.book,
        "parasha": parasha,
        "verses": verses,
        "title": f"Недельная глава «{parasha.name_ru}»",
        "prev_parasha": prev_parasha,
        "next_parasha": next_parasha,
        "nav_data": build_nav_data(verses),
    }
    return render(request, "library/chapter.html", context)


def topics_view(request):
    """Указатель тем: все наши комментарии (Material) по порядку следования в тексте."""
    materials = Material.objects.prefetch_related("verses__book").all()

    entries = []
    for m in materials:
        for v in m.verses.all():
            entries.append({"verse": v, "material": m})
    entries.sort(key=lambda e: (e["verse"].book.order, e["verse"].chapter, e["verse"].verse))

    grouped = [
        {"book": book, "chapter": chapter, "entries": list(group)}
        for (book, chapter), group in groupby(
            entries, key=lambda e: (e["verse"].book, e["verse"].chapter)
        )
    ]

    return render(request, "library/topics.html", {"grouped": grouped})


def sages_view(request):
    """Указатель мудрецов Торы: комментарии по мудрецу, с раскрывающейся навигацией
    книга -> недельная глава (иначе список комментариев быстро превращается
    в нечитаемую простыню заголовков)."""
    sages = Sage.objects.prefetch_related("materials__verses__book").order_by("name_ru")

    parashot_by_book = {}
    for p in Parasha.objects.select_related("start_verse__book", "end_verse").order_by("order"):
        parashot_by_book.setdefault(p.start_verse.book_id, []).append(p)

    def parasha_for_verse(verse):
        for p in parashot_by_book.get(verse.book_id, []):
            if (p.start_verse.chapter, p.start_verse.verse) <= (verse.chapter, verse.verse) <= (p.end_verse.chapter, p.end_verse.verse):
                return p
        return None

    grouped = []
    for sage in sages:
        entries = []
        for m in sage.materials.all():
            for v in m.verses.all():
                entries.append({"verse": v, "material": m, "parasha": parasha_for_verse(v)})
        if not entries:
            continue
        entries.sort(key=lambda e: (e["verse"].book.order, e["verse"].chapter, e["verse"].verse))

        books = []
        for book, book_entries in groupby(entries, key=lambda e: e["verse"].book):
            parashot = [
                {"parasha": parasha, "entries": list(p_entries)}
                for parasha, p_entries in groupby(book_entries, key=lambda e: e["parasha"])
            ]
            books.append({"book": book, "parashot": parashot})

        grouped.append({"sage": sage, "books": books})

    return render(request, "library/sages.html", {"grouped": grouped})


@csrf_exempt
@require_POST
def track_event(request):
    """Анонимный beacon-эндпоинт для клиентских событий (открытие комментария, клик на видео)."""
    try:
        data = json.loads(request.body)
    except (ValueError, TypeError):
        return HttpResponseBadRequest()

    event_type = data.get("event_type")
    if event_type not in (AnalyticsEvent.MATERIAL_OPEN, AnalyticsEvent.OUTBOUND_CLICK):
        return HttpResponseBadRequest()

    verse = Verse.objects.filter(pk=data.get("verse_id")).first() if data.get("verse_id") else None
    material = Material.objects.filter(pk=data.get("material_id")).first() if data.get("material_id") else None
    if verse and not material:
        material = verse.materials.first()

    AnalyticsEvent.objects.create(
        event_type=event_type,
        verse=verse,
        material=material,
        book=verse.book if verse else None,
        chapter=verse.chapter if verse else None,
        target=data.get("target", "")[:20],
    )
    return HttpResponse(status=204)


@staff_member_required
def analytics_dashboard(request):
    """Контентная аналитика: что читают/смотрят чаще всего (для админки)."""
    top_chapters = (
        AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.CHAPTER_VIEW)
        .values("book__name_ru", "chapter")
        .annotate(views=Count("id"))
        .order_by("-views")[:20]
    )
    top_materials = (
        AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.MATERIAL_OPEN, material__isnull=False)
        .values("material__id", "material__title", "material__type")
        .annotate(opens=Count("id"))
        .order_by("-opens")[:20]
    )
    outbound_totals = (
        AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.OUTBOUND_CLICK)
        .values("target")
        .annotate(clicks=Count("id"))
        .order_by("-clicks")
    )
    totals = {
        "chapter_views": AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.CHAPTER_VIEW).count(),
        "material_opens": AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.MATERIAL_OPEN).count(),
        "outbound_clicks": AnalyticsEvent.objects.filter(event_type=AnalyticsEvent.OUTBOUND_CLICK).count(),
    }

    return render(
        request,
        "library/analytics_dashboard.html",
        {
            "top_chapters": top_chapters,
            "top_materials": top_materials,
            "outbound_totals": outbound_totals,
            "totals": totals,
        },
    )


def calendar_view(request):
    """Календарь: сегодняшняя дата + двусторонний конвертер Григорианский/Еврейский."""
    gregorian_result = None
    gregorian_error = None
    if "gd" in request.GET:
        try:
            gregorian_result = convert_gregorian_to_hebrew(
                int(request.GET["gd"]), int(request.GET["gm"]), int(request.GET["gy"])
            )
        except (ValueError, KeyError):
            gregorian_error = "Такой даты не существует - проверьте день/месяц/год."

    hebrew_result = None
    hebrew_error = None
    if "hd" in request.GET:
        try:
            hebrew_result = convert_hebrew_to_gregorian(
                int(request.GET["hd"]), int(request.GET["hm"]), int(request.GET["hy"])
            )
        except (ValueError, KeyError):
            hebrew_error = "Такой даты не существует в еврейском календаре (например, Адар II бывает только в високосный год) - проверьте день/месяц/год."

    return render(
        request,
        "library/calendar.html",
        {
            "today": today_info(),
            "gregorian_days": range(1, 32),
            "hebrew_days": range(1, 31),
            "gregorian_months": GREGORIAN_MONTH_CHOICES,
            "hebrew_months": HEBREW_MONTH_CHOICES,
            "gregorian_result": gregorian_result,
            "gregorian_error": gregorian_error,
            "hebrew_result": hebrew_result,
            "hebrew_error": hebrew_error,
            "gd": request.GET.get("gd", ""),
            "gm": request.GET.get("gm", ""),
            "gy": request.GET.get("gy", ""),
            "hd": request.GET.get("hd", ""),
            "hm": request.GET.get("hm", ""),
            "hy": request.GET.get("hy", ""),
        },
    )
