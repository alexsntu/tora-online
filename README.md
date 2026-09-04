# Tora Online для Бней Ноах

Электронная библиотека текстов Торы и Танаха на русском и иврите, с навигацией по главам/стихам и недельным главам (парашот), подсветкой стихов со ссылками на видеоуроки и статьи.

## Стек
- Python 3.12 / Django
- SQLite локально и в проде (достаточно для текущего объёма; требуется регулярный backup)
- Django admin для управления комментариями/ссылками к стихам

## Локальный запуск
```
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
DJANGO_DEBUG=True python manage.py migrate
DJANGO_DEBUG=True python manage.py runserver
```

В production обязательны `DJANGO_SECRET_KEY` и `DJANGO_ALLOWED_HOSTS`; `DJANGO_DEBUG`
должен отсутствовать или иметь значение `False`. HTTPS завершается на reverse proxy,
который должен передавать `X-Forwarded-Proto: https`.
