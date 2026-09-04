# Tora Online для Бней Ноах

Электронная библиотека текстов Торы и Танаха на русском и иврите, с навигацией по главам/стихам и недельным главам (парашот), подсветкой стихов со ссылками на видеоуроки и статьи.

## Стек
- Python 3.12 / Django
- PostgreSQL в проде, SQLite локально
- Django admin для управления комментариями/ссылками к стихам

## Локальный запуск
```
python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
