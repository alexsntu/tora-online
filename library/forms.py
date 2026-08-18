from django import forms

from .models import Question


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "asker_name", "asker_email"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 5, "placeholder": "Введите ваш вопрос…"}),
            "asker_name": forms.TextInput(attrs={"placeholder": "Как к вам обращаться"}),
            "asker_email": forms.EmailInput(attrs={"placeholder": "Необязательно, не публикуется"}),
        }
        labels = {
            "text": "Вопрос",
            "asker_name": "Ваше имя",
            "asker_email": "Email",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asker_name"].required = True
