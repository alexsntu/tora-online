"""Внутренний тезаурус портала: единое написание терминов, у которых в русском
языке ходит несколько вариантов транслитерации. Один термин - одна запись в
THESAURUS: каноническое написание + регулярка, которая ловит все остальные.

Проверка сайта (шаблоны, код, база) - `python manage.py check_thesaurus`,
исправление базы - `python manage.py check_thesaurus --fix`.

Латинские идентификаторы в коде и адресах (Haftarah, /haftarot/) сюда не
относятся - тезаурус только про русский текст."""
import re
from dataclasses import dataclass
from typing import Callable

# Буква, после/перед которой слово продолжается: по ней отличаем термин от
# похожего куска другого слова ("Кафтора" - это остров Кафтор, а не афтора).
_LETTER = "а-яё"
# Пробел между словами в тексте статьи: обычный, неразрывный или &nbsp; из редактора.
_SPACE = r"(?:\s|&nbsp;)"


def _keep_case(fixed: str, found: str) -> str:
    """Каноническое написание в регистре найденного: ГАФТАРА -> АФТОРА, Гафтара -> Афтора."""
    if len(found) > 1 and found.isupper():
        return fixed.upper()
    if found[0].isupper():
        return fixed[0].upper() + fixed[1:]
    return fixed


def _stem(stem: str):
    """Замена "основа + окончание из текста", регистр - как у найденного слова."""
    def fix(match: re.Match) -> str:
        end = (match.groupdict().get("end") or "").lower()
        return _keep_case(stem + end, match.group(0))
    return fix


def _or_ha_chaim(match: re.Match) -> str:
    fixed = "Ор а-Хаим" + (match.group("end") or "").lower()
    if match.group("kadosh"):
        fixed += " а-Кадош" + (match.group("kend") or "").lower()
    return fixed


@dataclass(frozen=True)
class Term:
    canonical: str        # как пишем на сайте (единственное число)
    hebrew: str
    meaning: str
    wrong: tuple          # примеры написаний, которые НЕ используем (для справки)
    pattern: re.Pattern   # ловит любые написания термина, в т.ч. верное
    fix: Callable[[re.Match], str]  # найденное -> каноническое написание
    plural: str = ""      # множественное число, если употребляется

    def normalize(self, text: str) -> str:
        return self.pattern.sub(self.fix, text)

    def find_wrong(self, text: str) -> list:
        return [m.group(0) for m in self.pattern.finditer(text) if self.fix(m) != m.group(0)]


THESAURUS = (
    Term(
        canonical="Афтора",
        plural="Афторот",
        hebrew="הפטרה",
        meaning="Отрывок из книг Пророков (Невиим), который читают после недельной главы Торы.",
        wrong=("Гафтара", "Гафтора", "Г̃афтара", "Афтара", "Хафтара", "Гафтарот", "Гафторот"),
        # Необязательная первая "г/х/h" (в т.ч. "Г̃" с тильдой), "а" или "о" в основе,
        # русское падежное окончание либо ивритское множественное "-от".
        pattern=re.compile(
            rf"(?<![{_LETTER}])(?:[гґѓхh]̃?)?афт[ао]р"
            rf"(?P<end>ами|ам|ах|ой|ою|от|а|ы|е|у)(?![{_LETTER}̃])",
            re.IGNORECASE,
        ),
        fix=_stem("афтор"),
    ),
    Term(
        canonical="Ор а-Хаим а-Кадош",
        hebrew="אור החיים הקדוש",
        meaning="Рабби Хаим бен Атар и его комментарий к Торе. Склоняется: Ор а-Хаима, Ор а-Хаиму.",
        wrong=("Ор hа-Хаим hа-Кадош", "Ор аХайм аКадош", "Ор а-Хайм", "Ор аХаим", "Орахаим"),
        # Стоит раньше общего правила артикля: ловит и слитные написания ("аХайм",
        # "аКадош", "Орахаим"), которые по одному артиклю не опознать. Без артикля
        # не ловим - "Орах Хаим" это другая книга.
        pattern=re.compile(
            rf"(?<![{_LETTER}])ор{_SPACE}*h?а-?ха[ий]м(?P<end>ом|а|у|е)?(?![{_LETTER}])"
            rf"(?P<kadosh>{_SPACE}+h?а-?кадош(?P<kend>ем|а|у|е)?(?![{_LETTER}]))?",
            re.IGNORECASE,
        ),
        fix=_or_ha_chaim,
    ),
    Term(
        canonical="а- (артикль)",
        hebrew="ה־",
        meaning="Ивритский определённый артикль пишем «а-» через дефис, без «h»: а-Шем, йецер а-ра, Олам а-Ба.",
        wrong=("hа-Шем", "ha-Шем", "hа-ра", "hа-Ба"),
        # Только артикль перед словом; "h" внутри слова (Оhев Исраэль) не трогаем.
        pattern=re.compile(r"(?<![A-Za-zА-Яа-яЁё])[hH][аa]-(?=[А-Яа-яЁё])"),
        fix=lambda match: "А-" if match.group(0)[0] == "H" else "а-",
    ),
    Term(
        canonical="ка-ашер",
        hebrew="כאשר",
        meaning="«Как», «когда», «потому что». Со строчной буквы, предлог через дефис.",
        wrong=("Каашер", "каашер"),
        pattern=re.compile(rf"(?<![{_LETTER}])ка-?ашер(?![{_LETTER}])", re.IGNORECASE),
        fix=lambda match: "ка-ашер",
    ),
    Term(
        canonical="Эльханан",
        hebrew="אלחנן",
        meaning="Имя; на сайте - рав Эльханан Вассерман.",
        wrong=("Эльхонон", "Эльхонона"),
        pattern=re.compile(
            rf"(?<![{_LETTER}])эльх[оа]н[оа]н(?P<end>ом|а|у|е)?(?![{_LETTER}])", re.IGNORECASE,
        ),
        fix=_stem("эльханан"),
    ),
    Term(
        canonical="эхшер мицва",
        hebrew="הכשר מצווה",
        meaning="Подготовка к заповеди - действие, которое делает исполнение заповеди возможным.",
        wrong=("хэшер мицва", "hехшер мицва", "хехшер мицва"),
        pattern=re.compile(
            rf"(?<![{_LETTER}h])(?:хэшер|[hх]?[еэ]хшер){_SPACE}+мицв(?P<end>ой|а|ы|у|е)(?![{_LETTER}])",
            re.IGNORECASE,
        ),
        fix=_stem("эхшер мицв"),
    ),
    Term(
        canonical="схуйот",
        hebrew="זכויות",
        meaning="Заслуги (множественное число от «схут»).",
        wrong=("скуёт", "скует", "зхуйот"),
        pattern=re.compile(rf"(?<![{_LETTER}])(?:ск|сх|зх)у(?:ё|е|йо)т(?![{_LETTER}])", re.IGNORECASE),
        fix=_stem("схуйот"),
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
