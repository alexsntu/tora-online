from django.test import SimpleTestCase

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

    def test_canonical_and_lookalikes_untouched(self):
        for text in ("Афтора", "Афторот", "афторы", "вышедшие из Кафтора", "кафторим", "Кафторима", "автора"):
            self.assertEqual(normalize(text), text)
            self.assertEqual(find_wrong(text), [])
