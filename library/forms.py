from django import forms
from django.utils.html import format_html, format_html_join

from .models import ErrorReport, Question


class DatalistTextInput(forms.TextInput):
    """Обычное текстовое поле с выпадающей подсказкой (HTML <datalist>) -
    можно выбрать один из вариантов или вписать своё значение вручную."""

    def __init__(self, choices=(), attrs=None):
        super().__init__(attrs)
        self.choices = choices

    def render(self, name, value, attrs=None, renderer=None):
        list_id = f"{name}-datalist"
        final_attrs = {**(attrs or {}), "list": list_id}
        input_html = super().render(name, value, final_attrs, renderer)
        options_html = format_html_join("", "<option value=\"{}\">", ((c,) for c in self.choices))
        return format_html('{}<datalist id="{}">{}</datalist>', input_html, list_id, options_html)


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "asker_name", "asker_email", "wants_email_reply", "is_anonymous"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 5, "placeholder": "Введите ваш вопрос…"}),
            "asker_name": forms.TextInput(attrs={"placeholder": "Как к вам обращаться"}),
            "asker_email": forms.EmailInput(attrs={"placeholder": "Необязательно, не публикуется"}),
            "wants_email_reply": forms.CheckboxInput(),
            "is_anonymous": forms.CheckboxInput(),
        }
        labels = {
            "text": "Вопрос",
            "asker_name": "Ваше имя",
            "asker_email": "Email",
            "wants_email_reply": "Ответить мне на почту",
            "is_anonymous": "Опубликовать ответ анонимно (без указания моего имени)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asker_name"].required = True

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("wants_email_reply") and not cleaned_data.get("asker_email"):
            self.add_error("asker_email", "Укажите email, если хотите получить ответ на почту.")
        return cleaned_data


class ErrorReportForm(forms.ModelForm):
    class Meta:
        model = ErrorReport
        fields = ["description"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Опишите, что не так…"}),
        }
        labels = {
            "description": "Описание ошибки",
        }
