from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Book, Parasha, Verse


def home(request):
    books = list(Book.objects.all())
    for book in books:
        book.chapters = (
            Verse.objects.filter(book=book)
            .order_by("chapter")
            .values_list("chapter", flat=True)
            .distinct()
        )
    parashot = Parasha.objects.select_related("start_verse", "end_verse").all()
    return render(request, "library/home.html", {"books": books, "parashot": parashot})


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

    context = {
        "book": book,
        "chapter": chapter,
        "verses": verses,
        "title": f"{book.name_ru}, глава {chapter}",
        "prev_chapter": chapter - 1 if chapter > 1 else None,
        "next_chapter": chapter + 1 if chapter < max_chapter else None,
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

    context = {
        "book": start.book,
        "parasha": parasha,
        "verses": verses,
        "title": f"Недельная глава «{parasha.name_ru}»",
    }
    return render(request, "library/chapter.html", context)
