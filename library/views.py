from pathlib import Path

from django.conf import settings
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render

from .models import Book, Category, Parasha, Verse


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
    for book in books:
        book.chapters = list(
            Verse.objects.filter(book=book)
            .order_by("chapter")
            .values_list("chapter", flat=True)
            .distinct()
        )

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

    parashot = list(
        Parasha.objects.select_related("start_verse__book", "end_verse").order_by("order")
    )
    parashot_by_book_id = {}
    for p in parashot:
        parashot_by_book_id.setdefault(p.start_verse.book_id, []).append(p)

    parasha_groups = [
        (book, parashot_by_book_id[book.id])
        for book in books
        if book.id in parashot_by_book_id
    ]

    return render(
        request,
        "library/home.html",
        {"top_categories": top_categories, "parasha_groups": parasha_groups},
    )


def chapter_view(request, book_slug, chapter):
    book = get_object_or_404(Book, slug=book_slug)
    verses = (
        Verse.objects.filter(book=book, chapter=chapter)
        .prefetch_related("materials")
        .order_by("verse")
    )
    if not verses.exists():
        raise Http404("Глава не найдена")

    last_verse = Verse.objects.filter(book=book).order_by("-chapter").first()
    max_chapter = last_verse.chapter if last_verse else chapter

    nav_verses = Verse.objects.filter(book=book).prefetch_related("materials").order_by("chapter", "verse")
    verses = attach_parasha_starts(verses, book)

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
        .prefetch_related("materials")
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
