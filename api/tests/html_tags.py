"""Minimal reading of an HTML fragment for route tests: every tag with attributes and text.

The tests assert what a person would see in the fragment — which link is
active, which tab exists, where a link goes — and not the exact markup, so a
small tag collector is enough and no HTML library is needed.
"""

from __future__ import annotations

from html.parser import HTMLParser

# Tags that never have an end tag: they must not stay "open" collecting text.
VOID_TAGS = frozenset({"area", "base", "br", "col", "hr", "img", "input", "link", "meta", "source"})


class Tag:
    """A start tag: its name, its attributes and the text written inside it."""

    def __init__(self, name: str, attrs: list[tuple[str, str | None]]) -> None:
        self.name = name
        self.attrs: dict[str, str] = {key: value or "" for key, value in attrs}
        self.text = ""

    @property
    def classes(self) -> set[str]:
        """The CSS classes of the tag."""
        return set(self.attrs.get("class", "").split())

    def has_class(self, name: str) -> bool:
        """Whether the tag carries the CSS class."""
        return name in self.classes

    def clean_text(self) -> str:
        """The text with the whitespace collapsed, as it reads on screen."""
        return " ".join(self.text.split())


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[Tag] = []
        self._open: list[Tag] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        collected = Tag(tag, attrs)
        self.tags.append(collected)
        if tag not in VOID_TAGS:
            self._open.append(collected)

    def handle_endtag(self, tag: str) -> None:
        for index in range(len(self._open) - 1, -1, -1):
            if self._open[index].name == tag:
                del self._open[index:]
                return

    def handle_data(self, data: str) -> None:
        for tag in self._open:
            tag.text += data


def parse_tags(html: str) -> list[Tag]:
    """Every start tag of the fragment, in document order."""
    collector = _Collector()
    collector.feed(html)
    collector.close()
    return collector.tags


def find_all(tags: list[Tag], name: str | None = None, css_class: str | None = None) -> list[Tag]:
    """The tags with the given name and/or CSS class."""
    return [
        tag
        for tag in tags
        if (name is None or tag.name == name) and (css_class is None or tag.has_class(css_class))
    ]


def find_by_id(tags: list[Tag], element_id: str) -> Tag | None:
    """The tag with the given id, or ``None``."""
    return next((tag for tag in tags if tag.attrs.get("id") == element_id), None)
