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
    path("track/", views.track_event, name="track_event"),
    path("calendar/", views.calendar_view, name="calendar"),
    path("<slug:book_slug>/<int:chapter>/", views.chapter_view, name="chapter"),
    path("<slug:book_slug>/", views.book_view, name="book"),
    path("parasha/<slug:parasha_slug>/", views.parasha_view, name="parasha"),
]
