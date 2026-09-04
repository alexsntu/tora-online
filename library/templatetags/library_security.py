from django import template
from django.utils.safestring import mark_safe

from library.html_sanitizer import sanitize_html

register = template.Library()


@register.filter
def safe_richtext(value):
    return mark_safe(sanitize_html(value))
