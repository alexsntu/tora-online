import json
import random
from itertools import groupby
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.text import Truncator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from .forms import ErrorReportForm, QuestionForm
from .hebrew_calendar import (
    GREGORIAN_MONTH_CHOICES,
    HEBREW_MONTH_CHOICES,
    convert_gregorian_to_hebrew,
    convert_hebrew_to_gregorian,
    today_info,
)
from .models import (
    AnalyticsEvent, Book, Category, ErrorReport, Haftarah, Material, Parasha, Question, Sage, SiteSettings, Verse,
    WeeklyPost,
)


def ru_plural(n, one, few, many):
    """Русское склонение по числу: 1 комментарий / 2 комментария / 5 комментариев."""
    n = abs(n) % 100
    n1 = n % 10
    if 10 < n < 20:
        return many
    if 1 < n1 < 5:
        return few
    if n1 == 1:
        return one
    return many


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


SITE_TAGLINE = "Уроки Торы для Бней Ноах от Дмитрия Калашника"
AUTHOR_DESCRIPTION = "Авторские уроки на основе комментариев мудрецов с лингвистическим анализом"
AUTHOR_PERSON_LD = {"@type": "Person", "name": "Дмитрий Калашник", "description": AUTHOR_DESCRIPTION}


def resolve_meta(manual_title, manual_description, fallback_title, fallback_description):
    """SEO-заголовок/описание страницы: ручное поле из админки, если заполнено,
    иначе - автоматически сформированное из содержимого (fallback_*)."""
    title = (manual_title or "").strip() or fallback_title
    description = (manual_description or "").strip() or fallback_description
    return title, Truncator(description).chars(300) if description else ""


def breadcrumbs_ld(request, items):
    """items: [(название, path), ...] от главной к текущей странице -> узел BreadcrumbList."""
    return {
        "@type": "BreadcrumbList",
        "itemListElement": [
            {
                "@type": "ListItem",
                "position": i + 1,
                "name": name,
                "item": request.build_absolute_uri(path),
            }
            for i, (name, path) in enumerate(items)
        ],
    }


def structured_data_json(*graph_items):
    """Оборачивает один или несколько узлов schema.org в единый JSON-LD <script>."""
    return json.dumps({"@context": "https://schema.org", "@graph": list(graph_items)}, ensure_ascii=False)


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

    questions_preview = Question.objects.filter(is_published=True).exclude(answer="")[:3]
    weekly_post = WeeklyPost.objects.filter(is_published=True).first()

    website_ld = {
        "@type": "WebSite",
        "name": "Tora Online для Бней Ноах",
        "description": f"{SITE_TAGLINE}: {AUTHOR_DESCRIPTION.lower()}.",
        "url": request.build_absolute_uri(reverse("library:home")),
        "author": AUTHOR_PERSON_LD,
        "potentialAction": {
            "@type": "SearchAction",
            "target": request.build_absolute_uri(reverse("library:topics_search")) + "?q={search_term_string}",
            "query-input": "required name=search_term_string",
        },
    }

    return render(
        request,
        "library/home.html",
        {
            "top_categories": top_categories,
            "today": today_info(),
            "questions_preview": questions_preview,
            "weekly_post": weekly_post,
            "structured_data_json": structured_data_json(website_ld),
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
    meta_title, meta_description = resolve_meta(
        book.meta_title, book.meta_description,
        f"{book.name_ru} — Tora Online",
        book.description_ru or f"Текст книги {book.name_ru} на иврите с параллельным переводом на русский.",
    )
    book_url = reverse("library:book", args=[book.slug])
    breadcrumbs = breadcrumbs_ld(request, [
        ("Оглавление", reverse("library:home")),
        (book.name_ru, book_url),
    ])
    book_ld = {
        "@type": "Book",
        "name": book.name_ru,
        "alternateName": book.name_he,
        "description": meta_description,
        "url": request.build_absolute_uri(book_url),
        "inLanguage": ["he", "ru"],
    }
    return render(
        request,
        "library/book.html",
        {
            "book": book, "chapters": chapters, "parashot": parashot,
            "meta_title": meta_title, "meta_description": meta_description,
            "structured_data_json": structured_data_json(breadcrumbs, book_ld),
        },
    )


def chapter_view(request, book_slug, chapter):
    book = get_object_or_404(Book, slug=book_slug)
    verses = (
        Verse.objects.filter(book=book, chapter=chapter)
        .prefetch_related("materials__sages", "commentaries")
        .order_by("verse")
    )
    if not verses.exists():
        raise Http404("Глава не найдена")

    last_verse = Verse.objects.filter(book=book).order_by("-chapter").first()
    max_chapter = last_verse.chapter if last_verse else chapter

    nav_verses = Verse.objects.filter(book=book).prefetch_related("materials").order_by("chapter", "verse")
    verses = attach_parasha_starts(verses, book)

    AnalyticsEvent.objects.create(event_type=AnalyticsEvent.CHAPTER_VIEW, book=book, chapter=chapter)

    first_verse_text = verses[0].text_ru if verses else ""
    title = f"{book.name_ru}, глава {chapter}"
    breadcrumbs = breadcrumbs_ld(request, [
        ("Оглавление", reverse("library:home")),
        (book.name_ru, reverse("library:book", args=[book.slug])),
        (f"Глава {chapter}", reverse("library:chapter", args=[book.slug, chapter])),
    ])
    context = {
        "book": book,
        "chapter": chapter,
        "verses": verses,
        "title": title,
        "prev_chapter": chapter - 1 if chapter > 1 else None,
        "next_chapter": chapter + 1 if chapter < max_chapter else None,
        "nav_data": build_nav_data(nav_verses),
        "current_chapter": chapter,
        "meta_title": f"{title} — Tora Online",
        "meta_description": Truncator(f"{title} на иврите с параллельным переводом. {first_verse_text}").chars(300),
        "structured_data_json": structured_data_json(breadcrumbs),
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
        .prefetch_related("materials__sages", "commentaries")
    )
    verses = attach_parasha_starts(verses, start.book)

    prev_parasha = (
        Parasha.objects.filter(order__lt=parasha.order).order_by("-order").first()
    )
    next_parasha = (
        Parasha.objects.filter(order__gt=parasha.order).order_by("order").first()
    )

    title = f"Недельная глава «{parasha.name_ru}»"
    meta_title, meta_description = resolve_meta(
        parasha.meta_title, parasha.meta_description,
        f"{title} — Tora Online",
        f"Недельная глава «{parasha.name_ru}»: {start.book.name_ru} {start.chapter}:{start.verse} — "
        f"{end.chapter}:{end.verse}, текст на иврите и русском.",
    )
    breadcrumbs = breadcrumbs_ld(request, [
        ("Оглавление", reverse("library:home")),
        (start.book.name_ru, reverse("library:book", args=[start.book.slug])),
        (parasha.name_ru, reverse("library:parasha", args=[parasha.slug])),
    ])
    context = {
        "book": start.book,
        "parasha": parasha,
        "verses": verses,
        "title": title,
        "prev_parasha": prev_parasha,
        "next_parasha": next_parasha,
        "nav_data": build_nav_data(verses),
        "meta_title": meta_title,
        "meta_description": meta_description,
        "structured_data_json": structured_data_json(breadcrumbs),
    }
    return render(request, "library/chapter.html", context)


def _parashot_by_book():
    """book_id -> [Parasha, ...] по порядку - для определения, в какую недельную
    главу попадает произвольный стих (используется указателями тем/мудрецов)."""
    result = {}
    for p in Parasha.objects.select_related("start_verse__book", "end_verse").order_by("order"):
        result.setdefault(p.start_verse.book_id, []).append(p)
    return result


def _parasha_for_verse(verse, parashot_by_book):
    for p in parashot_by_book.get(verse.book_id, []):
        if (p.start_verse.chapter, p.start_verse.verse) <= (verse.chapter, verse.verse) <= (p.end_verse.chapter, p.end_verse.verse):
            return p
    return None


def _group_entries_by_parasha(entries, parashot_by_book):
    """entries (отсортированные по chapter/verse) -> [{"parasha": Parasha|None, "entries": [...]}, ...]."""
    for e in entries:
        e["parasha"] = _parasha_for_verse(e["verse"], parashot_by_book)
    return [
        {"parasha": parasha, "entries": list(group)}
        for parasha, group in groupby(entries, key=lambda e: e["parasha"])
    ]


def topics_view(request):
    """Указатель тем: карточки книг, в которых есть наши комментарии (как в библиотеке) -
    раскрытие по недельным главам живёт на отдельной странице книги."""
    books = (
        Book.objects.annotate(materials_count=Count("verses__materials", distinct=True))
        .filter(materials_count__gt=0)
        .order_by("order")
    )
    for book in books:
        book.materials_word = ru_plural(book.materials_count, "комментарий", "комментария", "комментариев")
    return render(request, "library/topics.html", {"books": books})


def _search_materials(query):
    """Регистронезависимый поиск материалов по заголовку темы и тексту комментария
    (имя мудреца НЕ участвует в поиске - по просьбе пользователя).

    SQLite LIKE (а значит и icontains) не умеет игнорировать регистр для кириллицы -
    поэтому фильтруем по title_lower/body_lower (кешируются в Material.save()), уже
    приведённым к нижнему регистру, вместо загрузки всех материалов и сравнения в Python."""
    query = query.lower()
    return list(
        Material.objects.filter(Q(title_lower__icontains=query) | Q(body_lower__icontains=query))
        .distinct()
        .prefetch_related("verses__book", "sages")
    )


def _search_entries(query):
    entries = []
    for m in _search_materials(query):
        for v in m.verses.all():
            entries.append({"verse": v, "material": m})
    entries.sort(key=lambda e: (e["verse"].book.order, e["verse"].chapter, e["verse"].verse))
    return entries


def topics_search_view(request):
    """Поиск по темам: ищет в заголовке темы и тексте комментария."""
    query = request.GET.get("q", "").strip()
    entries = _search_entries(query) if query else []

    entries_word = ru_plural(len(entries), "результат", "результата", "результатов")
    return render(
        request,
        "library/topics_search.html",
        {"query": query, "entries": entries, "entries_word": entries_word},
    )


def topics_search_json_view(request):
    """Живой поиск (для выпадающей подсказки): те же данные в JSON, максимум 8 совпадений."""
    query = request.GET.get("q", "").strip()
    results = []
    if len(query) >= 3:
        for entry in _search_entries(query)[:8]:
            v, m = entry["verse"], entry["material"]
            url = reverse("library:chapter", args=[v.book.slug, v.chapter]) + f"#v-{v.chapter}-{v.verse}"
            sage = ", ".join(s.name_ru for s in m.sages.all())
            results.append({"key": f"{m.id}-{v.id}", "title": m.title, "verse": str(v), "sage": sage, "url": url})
    return JsonResponse({"results": results})


def topics_book_view(request, book_slug):
    """Указатель тем внутри одной книги: комментарии по недельным главам."""
    book = get_object_or_404(Book, slug=book_slug)
    materials = Material.objects.filter(verses__book=book).distinct().prefetch_related("verses")

    entries = []
    for m in materials:
        for v in m.verses.filter(book=book):
            entries.append({"verse": v, "material": m})
    entries.sort(key=lambda e: (e["verse"].chapter, e["verse"].verse))

    parashot = _group_entries_by_parasha(entries, _parashot_by_book())
    return render(request, "library/topics_book.html", {"book": book, "parashot": parashot})


def sages_view(request):
    """Указатель мудрецов Торы: карточки мудрецов, у кого есть комментарии -
    раскрытие по книгам/недельным главам живёт на отдельной странице мудреца."""
    sages = (
        Sage.objects.filter(materials__isnull=False)
        .distinct()
        .order_by("name_ru")
    )
    return render(request, "library/sages.html", {"sages": sages})


def sage_detail_view(request, sage_slug):
    """Комментарии одного мудреца, сгруппированные по книге и недельной главе."""
    sage = get_object_or_404(Sage, slug=sage_slug)

    entries = []
    for m in sage.materials.all().prefetch_related("verses__book"):
        for v in m.verses.all():
            entries.append({"verse": v, "material": m})
    entries.sort(key=lambda e: (e["verse"].book.order, e["verse"].chapter, e["verse"].verse))

    parashot_by_book = _parashot_by_book()
    books = []
    for book, book_entries in groupby(entries, key=lambda e: e["verse"].book):
        parashot = _group_entries_by_parasha(list(book_entries), parashot_by_book)
        books.append({"book": book, "parashot": parashot})

    meta_title, meta_description = resolve_meta(
        sage.meta_title, sage.meta_description,
        f"{sage.name_ru} — Tora Online",
        sage.bio or f"Комментарии к Торе, опирающиеся на учение {sage.name_ru}.",
    )
    return render(
        request,
        "library/sage_detail.html",
        {"sage": sage, "books": books, "meta_title": meta_title, "meta_description": meta_description},
    )


def haftarot_view(request):
    """Указатель гафтарот: отдельный раздел, не часть обычного текста Танаха -
    список по недельным главам (как и читаются гафтарот - глава за главой)."""
    parashot = Parasha.objects.order_by("order").prefetch_related("haftarot")
    meta_title, meta_description = resolve_meta(
        "", "",
        "Афторот (гафтарот) — Tora Online",
        "Гафтарот (чтения из книг Пророков) для каждой недельной главы Торы, ашкеназская и сефардская традиции.",
    )
    return render(request, "library/haftarot.html", {
        "parashot": parashot,
        "title": "Афторот",
        "meta_title": meta_title,
        "meta_description": meta_description,
    })


def haftarah_view(request, parasha_slug, tradition):
    parasha = get_object_or_404(Parasha, slug=parasha_slug)
    haftarah = get_object_or_404(Haftarah, parasha=parasha, tradition=tradition)
    other_haftarot = parasha.haftarot.exclude(pk=haftarah.pk)

    title = f"Гафтара «{parasha.name_ru}» ({haftarah.get_tradition_display()})"
    meta_title, meta_description = resolve_meta(
        "", "",
        f"{title} — Tora Online",
        f"Гафтара недельной главы «{parasha.name_ru}» ({haftarah.get_tradition_display()} традиция), "
        f"из книги {haftarah.book_name_ru}, текст на иврите и русском.",
    )
    return render(request, "library/haftarah.html", {
        "parasha": parasha,
        "haftarah": haftarah,
        "verses": haftarah.verses.all(),
        "other_haftarot": other_haftarot,
        "title": title,
        "meta_title": meta_title,
        "meta_description": meta_description,
    })


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


def info_view(request):
    return render(request, "library/info.html", {"title": "О портале"})


def robots_txt_view(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    extra = SiteSettings.load().robots_extra.strip()
    if extra:
        lines.append("")
        lines.extend(line.strip() for line in extra.splitlines() if line.strip())
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml_view(request):
    """Простая карта сайта (без django.contrib.sitemaps - список URL невелик
    и не меняется настолько часто, чтобы городить отдельное приложение)."""
    url_names = ["home", "topics", "sages", "questions", "calendar", "info"]
    paths = [reverse(f"library:{name}") for name in url_names]

    for book in Book.objects.all():
        paths.append(reverse("library:book", args=[book.slug]))
        chapters = (
            Verse.objects.filter(book=book).order_by("chapter").values_list("chapter", flat=True).distinct()
        )
        for chapter in chapters:
            paths.append(reverse("library:chapter", args=[book.slug, chapter]))

    for parasha in Parasha.objects.all():
        paths.append(reverse("library:parasha", args=[parasha.slug]))

    books_with_materials = Book.objects.annotate(materials_count=Count("verses__materials", distinct=True)).filter(
        materials_count__gt=0
    )
    for book in books_with_materials:
        paths.append(reverse("library:topics_book", args=[book.slug]))

    for sage in Sage.objects.filter(materials__isnull=False).distinct():
        paths.append(reverse("library:sage_detail", args=[sage.slug]))

    for question in Question.objects.filter(is_published=True).exclude(answer=""):
        paths.append(reverse("library:question_detail", args=[question.pk]))

    urls = "".join(f"<url><loc>{request.build_absolute_uri(p)}</loc></url>" for p in paths)
    xml = f'<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>'
    return HttpResponse(xml, content_type="application/xml")


def questions_view(request):
    """Вопросы и ответы: опубликованные вопросы по дате, новые сверху."""
    questions = Question.objects.filter(is_published=True).exclude(answer="")
    return render(request, "library/questions.html", {"questions": questions})


def question_detail_view(request, pk):
    question = get_object_or_404(Question, pk=pk, is_published=True)
    meta_title, meta_description = resolve_meta(
        question.meta_title, question.meta_description,
        f"{Truncator(question.display_title).words(12)} — Tora Online",
        question.answer or question.display_title,
    )
    breadcrumbs = breadcrumbs_ld(request, [
        ("Оглавление", reverse("library:home")),
        ("Вопросы и ответы", reverse("library:questions")),
        (Truncator(question.display_title).words(8), reverse("library:question_detail", args=[question.pk])),
    ])
    qa_ld = {
        "@type": "QAPage",
        "mainEntity": {
            "@type": "Question",
            "name": question.display_title,
            "text": question.text,
            "answerCount": 1,
            "acceptedAnswer": {
                "@type": "Answer",
                "text": question.answer,
                "author": AUTHOR_PERSON_LD,
            },
        },
    }
    return render(
        request,
        "library/question_detail.html",
        {
            "question": question, "meta_title": meta_title, "meta_description": meta_description,
            "structured_data_json": structured_data_json(breadcrumbs, qa_ld),
        },
    )


def _new_captcha(request):
    target = random.randint(1, 9)
    decoys = random.sample([n for n in range(1, 10) if n != target], 2)
    options = [target] + decoys
    random.shuffle(options)
    request.session["question_captcha"] = target
    return target, options


def question_ask_view(request):
    if request.method == "POST":
        if request.POST.get("website", "").strip():
            # honeypot - для бота делаем вид, что всё прошло успешно, но ничего не сохраняем
            return redirect("library:question_ask_done")

        form = QuestionForm(request.POST)
        expected = request.session.get("question_captcha")
        captcha_ok = expected is not None and request.POST.get("captcha") == str(expected)

        if form.is_valid() and captcha_ok:
            form.save()
            request.session.pop("question_captcha", None)
            return redirect("library:question_ask_done")

        if not captcha_ok:
            form.add_error(None, "Неверно выбрана цифра - попробуйте ещё раз.")
    else:
        form = QuestionForm()

    target, options = _new_captcha(request)
    return render(
        request,
        "library/question_ask.html",
        {"form": form, "captcha_target": target, "captcha_options": options},
    )


def question_ask_done_view(request):
    return render(request, "library/question_ask_done.html")


@require_POST
def report_error_view(request):
    page_url = request.POST.get("page_url", "")
    fallback = page_url if page_url.startswith("/") and not page_url.startswith("//") else reverse("library:home")

    if request.POST.get("website", "").strip():
        # honeypot - для бота делаем вид, что всё прошло успешно, но ничего не сохраняем
        return redirect(fallback)

    form = ErrorReportForm(request.POST)
    if form.is_valid():
        report = form.save(commit=False)
        report.page_url = page_url
        report.save()
        messages.success(request, "Спасибо! Сообщение об ошибке отправлено.")
    else:
        messages.error(request, "Не удалось отправить - опишите ошибку текстом.")

    return redirect(fallback)
