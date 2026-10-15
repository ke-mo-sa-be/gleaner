"""Apply a recipe to page HTML: list items, field values, detail fields, next-page URL."""

import copy
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup, NavigableString, Tag

from core.recipe import Field, Recipe

URL_ATTRS = ("href", "src")
HEADING_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6")
BLOCK_TAGS = {"p", "div", "li", "tr", "section", "article", "header", "footer", "ul", "ol", "table", "dd", "dt",
              "blockquote", "address", "h1", "h2", "h3", "h4", "h5", "h6"}
SKIP_TAGS = {"script", "style", "noscript", "template"}
# "Phone: ..." / "E-mail - ..." at the start of a line.
LABEL_LINE = re.compile(r"^\s*([^\W\d_][\w .'/&()-]{0,30}?)\s*[:\-\u2013]\s*(.*)$")


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
    if attr == "src" and el.name == "img":
        value = _image_source(el) or value
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return urljoin(base_url, value) if attr in URL_ATTRS else value


def _image_source(img):
    """Real address of a picture, including lazy-loaded ones whose src is a placeholder."""
    src = (img.get("src") or "").strip()
    if src and not src.startswith("data:"):
        return src
    for attr in ("data-src", "data-lazy-src", "data-original", "data-url"):
        if img.get(attr):
            return img[attr].strip()
    srcset = img.get("srcset") or img.get("data-srcset") or ""
    return srcset.split(",")[0].strip().split(" ")[0] or None


def block_lines(tag) -> list[str]:
    """Visible text of a tag as lines: <br> and block elements break lines, scripts are skipped."""
    parts = []

    def walk(node):
        for child in node.children:
            if isinstance(child, NavigableString):
                if type(child) is NavigableString:  # not comments, CDATA etc.
                    parts.append(str(child))
            elif isinstance(child, Tag):
                if child.name in SKIP_TAGS:
                    continue
                if child.name == "br":
                    parts.append("\n")
                    continue
                block = child.name in BLOCK_TAGS
                if block:
                    parts.append("\n")
                walk(child)
                if block:
                    parts.append("\n")

    walk(tag)
    return [line for line in (" ".join(x.split()) for x in "".join(parts).split("\n")) if line]


def label_line_value(lines: list[str], label: str):
    """Value written after "Label:" in a block of lines. A value ending in a comma continues on the next line
    ("Email: a@x.com," / "b@x.com"); a label alone on its line takes the next line."""
    wanted = _norm_label(label)
    for i, line in enumerate(lines):
        m = LABEL_LINE.match(line)
        if not m or _norm_label(m.group(1)) != wanted:
            continue
        value = m.group(2).strip()
        j = i + 1
        if not value and j < len(lines) and not LABEL_LINE.match(lines[j]):
            value, j = lines[j], j + 1
        while value.endswith(",") and j < len(lines) and not LABEL_LINE.match(lines[j]):
            value, j = f"{value} {lines[j]}", j + 1
        return value.rstrip(",").strip() or None
    return None


def _heading_level(tag) -> int:
    return int(tag.name[1]) if tag.name in HEADING_TAGS else 99


def sections(soup, heading_selector) -> list[Tag]:
    """One detached <div> per heading: the heading plus its following siblings up to the next heading of the
    list (or any heading of the same or a higher level)."""
    heads = soup.select(heading_selector)
    head_ids = {id(h) for h in heads}
    wrappers = []
    for head in heads:
        wrapper = BeautifulSoup("<div></div>", "html.parser").div.extract()  # detached: no parent
        wrapper.append(copy.copy(head))
        node = head.next_sibling
        while node is not None:
            if isinstance(node, Tag) and (id(node) in head_ids or _heading_level(node) <= _heading_level(head)):
                break
            if not (isinstance(node, Tag) and node.name in SKIP_TAGS):
                wrapper.append(copy.copy(node))
            node = node.next_sibling
        wrappers.append(wrapper)
    return wrappers


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
        if field.label_scope:
            return _label_value(scope, field)
        return label_line_value(block_lines(scope), field.label)  # "Label: value" lines in a section
    el = _select_one(scope, field.selector)
    if field.attr == "text" and el is not None and el is scope and scope.name == "div" and scope.parent is None:
        return " ".join(block_lines(el)) or None  # a whole section: keep line breaks as spaces
    return _value(el, field.attr, base_url)


def list_items(soup, recipe: Recipe):
    if recipe.item_mode == "sections":
        return sections(soup, recipe.item_selector)
    return soup.select(recipe.item_selector)


def extract_list(html: str, recipe: Recipe, page_url: str) -> list[dict]:
    """One dict per list item. Items where no field matched (e.g. a table header row) are dropped."""
    soup = parse(html)
    rows = [{f.name: field_value(item, f, page_url) for f in recipe.list_fields}
            for item in list_items(soup, recipe)]
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
