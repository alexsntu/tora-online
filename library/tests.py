from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from library.admin import _error_report_edit_targets
from library.models import Book, ErrorReport, Material, Verse
from library.thesaurus import find_wrong, normalize


class ThesaurusTests(SimpleTestCase):
    def test_variants_become_canonical(self):
        cases = {
            "Гафтара": "Афтора",
            "Г\u0303афтара Шаббата «Шува»": "Афтора Шаббата «Шува»",
            "Афтара:": "Афтора:",
            "Хафтара": "Афтора",
            "тексты гафтарот": "тексты афторот",
            "Гафторот к датам": "Афторот к датам",
            "стих гафтары": "стих афторы",
            "вкладки с гафтарой": "вкладки с афторой",
            "ГАФТАРА": "АФТОРА",
        }
        for source, expected in cases.items():
            self.assertEqual(normalize(source), expected)

    def test_other_terms(self):
        cases = {
            "Ор hа-Хаим hа-Кадош": "Ор а-Хаим а-Кадош",
            "комментария Ор аХайм аКадош мы": "комментария Ор а-Хаим а-Кадош мы",
            "объяснение Ор hа-Хаима hа-Кадоша": "объяснение Ор а-Хаима а-Кадоша",
            "Ор а-Хайму": "Ор а-Хаиму",
            "по Орахайма": "по Ор а-Хаима",
            "слова hа-Шема, ha-Шем": "слова а-Шема, а-Шем",
            "йецер hа-ра и Олам hа-Ба": "йецер а-ра и Олам а-Ба",
            "слово «Каашер» (каашер)": "слово «ка-ашер» (ка-ашер)",
            "рава Эльхонона Вассермана": "рава Эльханана Вассермана",
            "(хэшер мицва) и hехшер мицвы": "(эхшер мицва) и эхшер мицвы",
            "её скуёт (заслуги)": "её схуйот (заслуги)",
        }
        for source, expected in cases.items():
            self.assertEqual(normalize(source), expected)
            self.assertEqual(normalize(expected), expected)
            self.assertEqual(find_wrong(expected), [])

    def test_canonical_and_lookalikes_untouched(self):
        for text in (
            "Афтора", "Афторот", "афторы", "вышедшие из Кафтора", "кафторим", "Кафторима", "автора",
            "Оhев Исраэль", "Орах Хаим", "Хаим", "из-за скуки", "га-га",
        ):
            self.assertEqual(normalize(text), text)
            self.assertEqual(find_wrong(text), [])


# Манифест статики собирается только collectstatic'ом - в тестах берём файлы как есть.
@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class ErrorReportAdminLinksTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        from django.contrib.auth import get_user_model

        cls.admin_user = get_user_model().objects.create_superuser("root", "root@example.com", "pw")
        cls.book = Book.objects.create(name_ru="Берешит", slug="bereshit")
        verse = Verse.objects.create(book=cls.book, chapter=12, verse=1, text_ru="Текст")
        cls.material = Material.objects.create(title="Почему Лех леха", article_text="<p>Текст</p>")
        cls.material.verses.add(verse)

    def setUp(self):
        self.client.force_login(self.admin_user)

    def test_article_report_links_to_material_edit(self):
        report = ErrorReport.objects.create(
            description="Опечатка", page_url=f"/articles/read/{self.material.article_slug}/",
        )
        edit_url = reverse("admin:library_material_change", args=[self.material.pk])
        for url in (
            reverse("admin:library_errorreport_changelist"),
            reverse("admin:library_errorreport_change", args=[report.pk]),
        ):
            self.assertContains(self.client.get(url), f'href="{edit_url}"')

    def test_chapter_report_links_to_filtered_lists(self):
        targets = dict(_error_report_edit_targets("/bereshit/12/"))
        self.assertEqual(set(targets), {"Материалы этой страницы", "Стихи этой главы"})
        for url in targets.values():
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)  # фильтр принят, без редиректа на ?e=1
            self.assertEqual(response.context["cl"].result_count, 1)

    def test_unknown_page_has_no_links(self):
        for page_url in ("", "/no-such-book/", "/articles/read/no-such-article/", "https://example.com/x"):
            self.assertEqual(_error_report_edit_targets(page_url), [])
        report = ErrorReport.objects.create(description="Что-то", page_url="/calendar/")
        self.assertEqual(self.client.get(reverse("admin:library_errorreport_changelist")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("admin:library_errorreport_change", args=[report.pk])).status_code, 200,
        )
