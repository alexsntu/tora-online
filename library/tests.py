import json

from django.core.cache import cache
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .html_sanitizer import sanitize_html
from .models import AnalyticsEvent, Book, Category, Material, Verse, WeeklyPost


class PublicPageTests(TestCase):
    def test_core_pages_render(self):
        for name in ("home", "topics", "articles", "sages", "questions", "calendar", "info", "haftarot"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(f"library:{name}")).status_code, 200)

    def test_calendar_rejects_unbounded_year(self):
        response = self.client.get(reverse("library:calendar"), {"y": "999999", "m": "1"})
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(response.context["cal_year"], 999999)

    def test_canonical_drops_query_string(self):
        response = self.client.get(reverse("library:calendar"), {"theme": "c", "y": "2026"})
        self.assertContains(response, f'<link rel="canonical" href="http://testserver{reverse("library:calendar")}">')


class RichTextSecurityTests(TestCase):
    def test_sanitizer_preserves_formatting_and_removes_active_content(self):
        value = '<h2>Title</h2><script>alert(1)</script><a href="javascript:alert(2)" onclick="x()">link</a>'
        cleaned = sanitize_html(value)
        self.assertIn("<h2>Title</h2>", cleaned)
        self.assertNotIn("<script", cleaned)
        self.assertNotIn("javascript:", cleaned)
        self.assertNotIn("onclick", cleaned)

    def test_home_sanitizes_weekly_post(self):
        WeeklyPost.objects.create(title="Пост", body='<strong>ok</strong><img src=x onerror="alert(1)">')
        response = self.client.get(reverse("library:home"))
        self.assertContains(response, "<strong>ok</strong>", html=True)
        self.assertNotContains(response, "onerror")


class AnalyticsEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        category = Category.objects.create(name_ru="Тора", slug="torah")
        self.book = Book.objects.create(category=category, name_ru="Берешит", slug="bereshit")
        self.verse = Verse.objects.create(book=self.book, chapter=1, verse=1, text_ru="Начало")
        self.material = Material.objects.create(type=Material.TYPE_VIDEO, title="Урок", url="https://example.com")
        self.material.verses.add(self.verse)
        self.client = Client(enforce_csrf_checks=True)

    def _csrf_token(self):
        self.client.get(reverse("library:home"))
        return self.client.cookies["csrftoken"].value

    def _post(self, payload, token=None):
        return self.client.post(
            reverse("library:track_event"), data=json.dumps(payload), content_type="application/json",
            HTTP_X_CSRFTOKEN=token or "",
        )

    def test_csrf_is_required(self):
        response = self._post({"event_type": AnalyticsEvent.MATERIAL_OPEN, "verse_id": self.verse.pk})
        self.assertEqual(response.status_code, 403)

    def test_valid_event_is_recorded(self):
        response = self._post(
            {"event_type": AnalyticsEvent.MATERIAL_OPEN, "verse_id": self.verse.pk}, self._csrf_token(),
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(AnalyticsEvent.objects.count(), 1)

    def test_invalid_target_is_rejected(self):
        response = self._post(
            {"event_type": AnalyticsEvent.OUTBOUND_CLICK, "material_id": self.material.pk, "target": "evil"},
            self._csrf_token(),
        )
        self.assertEqual(response.status_code, 400)

    def test_rate_limit(self):
        token = self._csrf_token()
        payload = {"event_type": AnalyticsEvent.MATERIAL_OPEN, "verse_id": self.verse.pk}
        for _ in range(60):
            self.assertEqual(self._post(payload, token).status_code, 204)
        self.assertEqual(self._post(payload, token).status_code, 429)
