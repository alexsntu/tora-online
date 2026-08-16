from django.urls import path

from . import views

app_name = "library"

urlpatterns = [
    path("", views.home, name="home"),
    path("<slug:book_slug>/<int:chapter>/", views.chapter_view, name="chapter"),
    path("parasha/<slug:parasha_slug>/", views.parasha_view, name="parasha"),
]
