"""Apply a recipe to page HTML: list items, field values, detail fields, next-page URL."""

from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from core.recipe import Field, Recipe

URL_ATTRS = ("href", "src")


def parse(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def _norm(text) -> str:
    return " ".join((text or "").split())


def _norm_label(text) -> str:
    return _norm(text).rstrip(":").strip().casefold()


def _select_one(scope, selector):
    # Empty or ":scope" means the item element itself (soupsieve's select_one(":scope") returns None).
    if selector is None or selector.strip() in ("", ":scope"):
        return scope
    return scope.select_one(selector)


def _value(el, attr, base_url):
    if el is None:
        return None
    if attr == "text":
        return _norm(el.get_text(" ")) or None
    value = el.get(attr)
    if isinstance(value, list):  # multi-valued attributes such as class
        value = " ".join(value)
    if value is None and attr in URL_ATTRS and el.name != "a":
        # Picked a button or cell inside a link: use the enclosing link.
        parent = el.find_parent("a")
        value = parent.get("href") if parent else None
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return urljoin(base_url, value) if attr in URL_ATTRS else value


def _label_value(soup, field: Field):
    """Value in the row whose first cell text equals the label (e.g. "Phone Number | 98...")."""
    wanted = _norm_label(field.label)
    for row in soup.select(field.label_scope):
        cells = row.find_all(True, recursive=False)
        if len(cells) >= 2 and _norm_label(cells[0].get_text(" ")) == wanted:
            return _norm(cells[1].get_text(" ")) or None
        if _norm_label(row.get_text(" ")) == wanted:  # <dt>Label</dt><dd>Value</dd> style
            sibling = row.find_next_sibling()
            return (_norm(sibling.get_text(" ")) or None) if sibling else None
    return None


def field_value(scope, field: Field, base_url: str):
    if field.label is not None:
        return _label_value(scope, field)
    return _value(_select_one(scope, field.selector), field.attr, base_url)


def extract_list(html: str, recipe: Recipe, page_url: str) -> list[dict]:
    """One dict per list item. Items where no field matched (e.g. a table header row) are dropped."""
    soup = parse(html)
    rows = [{f.name: field_value(item, f, page_url) for f in recipe.list_fields}
            for item in soup.select(recipe.item_selector)]
    return [row for row in rows if any(v is not None for v in row.values())]


def extract_detail(html: str, recipe: Recipe, page_url: str) -> dict:
    soup = parse(html)
    return {f.name: field_value(soup, f, page_url) for f in recipe.detail.fields}


def with_query_param(url: str, param: str, value) -> str:
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True) if k != param]
    query.append((param, str(value)))
    return urlunsplit(parts._replace(query=urlencode(query)))


def next_page_url(html: str, recipe: Recipe, page_url: str, pages_done: int) -> str | None:
    """URL of the page after `pages_done` pages, or None when there is no next page."""
    p = recipe.pagination
    if p.max_pages and pages_done >= p.max_pages:
        return None
    if p.type == "page_param":
        return with_query_param(page_url, p.param, p.start + pages_done)
    if p.type == "next_link":
        candidates = parse(html).select(p.selector)
        if p.text:
            wanted = _norm(p.text).casefold()
            candidates = [el for el in candidates if _norm(el.get_text(" ")).casefold() == wanted]
        href = _value(candidates[0], "href", page_url) if candidates else None
        return href if href and href != page_url else None
    return None
