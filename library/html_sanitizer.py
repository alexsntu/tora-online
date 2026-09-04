from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse


ALLOWED_TAGS = {
    "p", "br", "strong", "b", "em", "i", "u", "h2", "h3",
    "ul", "ol", "li", "blockquote", "a",
}
VOID_TAGS = {"br"}
SAFE_SCHEMES = {"http", "https", "mailto"}


class _SafeHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED_TAGS:
            return
        rendered_attrs = ""
        if tag == "a":
            href = next((value for name, value in attrs if name == "href"), "") or ""
            parsed = urlparse(href.strip())
            if (not parsed.scheme and not href.strip().startswith("//")) or parsed.scheme.lower() in SAFE_SCHEMES:
                rendered_attrs = f' href="{escape(href.strip(), quote=True)}" rel="noopener noreferrer"'
        self.parts.append(f"<{tag}{rendered_attrs}>")

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if tag in ALLOWED_TAGS and tag not in VOID_TAGS:
            self.parts.append(f"</{tag}>")

    def handle_data(self, data):
        self.parts.append(escape(data))


def sanitize_html(value):
    parser = _SafeHTMLParser()
    parser.feed(value or "")
    parser.close()
    return "".join(parser.parts)
