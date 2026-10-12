"""Внутренний тезаурус портала: единое написание терминов, у которых в русском
языке ходит несколько вариантов транслитерации. Один термин - одна запись в
THESAURUS: каноническое написание + регулярка, которая ловит все остальные.

Проверка сайта (шаблоны, код, база) - `python manage.py check_thesaurus`,
исправление базы - `python manage.py check_thesaurus --fix`.

Латинские идентификаторы в коде и адресах (Haftarah, /haftarot/) сюда не
относятся - тезаурус только про русский текст."""
import re
from dataclasses import dataclass

# Буква, после/перед которой слово продолжается: по ней отличаем термин от
# похожего куска другого слова ("Кафтора" - это остров Кафтор, а не афтора).
_LETTER = "а-яё"


@dataclass(frozen=True)
class Term:
    canonical: str        # единственное число, как пишем на сайте
    plural: str           # множественное число
    hebrew: str
    meaning: str
    wrong: tuple          # примеры написаний, которые НЕ используем (для справки)
    stem: str             # каноническая основа, к ней приклеивается окончание
    pattern: re.Pattern   # ловит любые написания; группы stem и end

    def normalize(self, text: str) -> str:
        return self.pattern.sub(self._replace, text)

    def find_wrong(self, text: str) -> list:
        return [m.group(0) for m in self.pattern.finditer(text) if self._replace(m) != m.group(0)]

    def _replace(self, match: re.Match) -> str:
        found = match.group(0)
        fixed = self.stem + (match.group("end") or "").lower()
        if len(found) > 1 and found.isupper():
            return fixed.upper()
        if found[0].isupper():
            return fixed[0].upper() + fixed[1:]
        return fixed


THESAURUS = (
    Term(
        canonical="Афтора",
        plural="Афторот",
        hebrew="הפטרה",
        meaning="Отрывок из книг Пророков (Невиим), который читают после недельной главы Торы.",
        wrong=("Гафтара", "Гафтора", "Г̃афтара", "Афтара", "Хафтара", "Гафтарот", "Гафторот"),
        stem="афтор",
        # Необязательная первая "г/х/h" (в т.ч. "Г̃" с тильдой), "а" или "о" в основе,
        # русское падежное окончание либо ивритское множественное "-от".
        pattern=re.compile(
            rf"(?<![{_LETTER}])(?P<stem>(?:[гґѓхh]̃?)?афт[ао]р)"
            rf"(?P<end>ами|ам|ах|ой|ою|от|а|ы|е|у)(?![{_LETTER}̃])",
            re.IGNORECASE,
        ),
    ),
)


def normalize(text: str) -> str:
    """Приводит все термины тезауруса в тексте к каноническому написанию."""
    for term in THESAURUS:
        text = term.normalize(text)
    return text


def find_wrong(text: str) -> list:
    """Все встреченные в тексте написания, которые расходятся с тезаурусом."""
    found = []
    for term in THESAURUS:
        found.extend(term.find_wrong(text))
    return found
