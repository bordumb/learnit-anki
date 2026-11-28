"""Render Anki fields without loading external resources or executable markup."""

import base64
import html
import mimetypes
import re
from html.parser import HTMLParser
from urllib.parse import unquote

SOUND = re.compile(r"\[sound:([^\]\r\n]+)\]")
RUBY = re.compile(r"(?:^|[ \u3000])([^<>\s\[\]]+)\[([^\[\]\r\n]+)\]")
READING_ANNOTATION = re.compile(r"[\[\]［］]|<\s*/?\s*(?:ruby|rt|rp)\b", re.IGNORECASE)
BLOCK = {"br", "div", "li", "ol", "p", "table", "tr", "ul", "hr"}
TAGS = BLOCK | {"a", "b", "em", "i", "img", "ruby", "rt", "rp", "s", "strong", "sub", "sup", "td", "th", "u"}
VOID = {"br", "hr", "img"}
HIDDEN = {"script", "style", "iframe", "object", "video", "audio"}
IMAGE_TYPES = {"image/gif", "image/jpeg", "image/png", "image/webp", "image/avif", "image/bmp"}


class FieldParser(HTMLParser):
    def __init__(self, *, markup=False, media=None, ruby=False, keep_sound=False):
        super().__init__()
        self.markup = markup
        self.media = media
        self.ruby = ruby
        self.keep_sound = keep_sound
        self.parts = []
        self.media_names = set()
        self.hidden = []
        self.open_tags = []

    def handle_starttag(self, tag, attrs):
        if self.hidden or tag in HIDDEN:
            if tag in HIDDEN:
                self.hidden.append(tag)
            return
        values = dict(attrs)
        if tag == "img":
            name = unquote(values.get("src") or "")
            if name:
                self.media_names.add(name)
            mime = mimetypes.guess_type(name)[0]
            if self.media and mime in IMAGE_TYPES and (data := self.media(name)):
                encoded = base64.b64encode(data).decode("ascii")
                alt = html.escape(values.get("alt") or "")
                self.parts.append(f'<img src="data:{mime};base64,{encoded}" alt="{alt}">')
            elif not self.markup and values.get("alt"):
                self.parts.append(values["alt"])
            return
        if self.markup and tag in TAGS:
            if tag == "a":
                href = values.get("href") or ""
                scheme = href.split(":", 1)[0].lower()
                if scheme not in {"dict", "https", "http"}:
                    return
                self.parts.append(f'<a href="{html.escape(href)}">')
            else:
                self.parts.append(f"<{tag}>")
            if tag not in VOID:
                self.open_tags.append(tag)
        elif not self.markup and tag in BLOCK and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]:
                self.hidden.pop()
            return
        if self.markup and tag in self.open_tags:
            while self.open_tags:
                current = self.open_tags.pop()
                self.parts.append(f"</{current}>")
                if current == tag:
                    break
        elif not self.markup and tag in BLOCK and self.parts and not self.parts[-1].endswith("\n"):
            self.parts.append("\n")

    def handle_data(self, data):
        if self.hidden:
            return
        self.media_names.update(SOUND.findall(data))
        if not self.keep_sound:
            data = SOUND.sub("", data)
        if not self.markup:
            self.parts.append(data)
            return
        if self.ruby:
            cursor = 0
            for match in RUBY.finditer(data):
                self.parts.append(html.escape(data[cursor:match.start()]))
                self.parts.append(f"<ruby>{html.escape(match[1])}<rt>{html.escape(match[2])}</rt></ruby>")
                cursor = match.end()
            data = data[cursor:]
        self.parts.append(html.escape(data))

    def result(self):
        return "".join(self.parts) + "".join(f"</{tag}>" for tag in reversed(self.open_tags))


def parse(value: str, **options):
    parser = FieldParser(**options)
    parser.feed(value)
    parser.close()
    return parser


def plain(value: str, keep_sound=False) -> str:
    return parse(value, keep_sound=keep_sound).result().strip()


def unbracketed_reading(value: str) -> bool:
    if not value or READING_ANNOTATION.search(value):
        return False
    text = plain(value)
    return bool(text and not READING_ANNOTATION.search(text))


def render(value: str, media, *, ruby=False) -> str:
    return parse(value, markup=True, media=media, ruby=ruby).result()


def media_names(*values: str) -> set[str]:
    return set().union(*(parse(value).media_names for value in values))
