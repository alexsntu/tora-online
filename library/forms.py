from django import forms

from .models import ErrorReport, Question


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
