from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.home, name="home"),
    path("topics/", views.topics_view, name="topics"),
    path("topics/search/", views.topics_search_view, name="topics_search"),
    path("topics/search.json/", views.topics_search_json_view, name="topics_search_json"),
    path("topics/<slug:book_slug>/", views.topics_book_view, name="topics_book"),
    path("sages/", views.sages_view, name="sages"),
    path("sages/<slug:sage_slug>/", views.sage_detail_view, name="sage_detail"),
    path("questions/", views.questions_view, name="questions"),
    path("questions/ask/", views.question_ask_view, name="question_ask"),
    path("questions/ask/done/", views.question_ask_done_view, name="question_ask_done"),
    path("questions/<int:pk>/", views.question_detail_view, name="question_detail"),
    path("report-error/", views.report_error_view, name="report_error"),
    path("track/", views.track_event, name="track_event"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("info/", views.info_view, name="info"),
    path("haftarot/", views.haftarot_view, name="haftarot"),
    path("haftarot/date/<slug:occasion_slug>/<str:tradition>/", views.haftarah_occasion_view, name="haftarah_occasion"),
    path("haftarot/<slug:parasha_slug>/<str:tradition>/", views.haftarah_view, name="haftarah"),
    path("<slug:book_slug>/<int:chapter>/", views.chapter_view, name="chapter"),
    path("<slug:book_slug>/", views.book_view, name="book"),
    path("parasha/<slug:parasha_slug>/", views.parasha_view, name="parasha"),
]
