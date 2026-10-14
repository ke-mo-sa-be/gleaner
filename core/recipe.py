"""Recipe model, JSON (de)serialisation and validation (docs/DATABASE.md section 13)."""

import ipaddress
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

import soupsieve

RECIPE_VERSION = 1
FIELD_TYPES = ("text", "link", "phone", "email", "pincode", "number")
PAGINATION_TYPES = ("none", "next_link", "page_param")
MAX_RECIPE_FILE_BYTES = 1_000_000
MAX_START_PAGES = 500

TOP_KEYS = ("version", "name", "start_url", "start_urls", "render_js", "list", "pagination", "detail", "dedup_keys", "limits")
LIST_KEYS = ("item_selector", "fields")
FIELD_KEYS = ("name", "selector", "attr", "type", "required", "label", "label_scope")
PAGINATION_KEYS = ("type", "selector", "text", "param", "start", "max_pages")
DETAIL_KEYS = ("link_field", "fields")
LIMIT_KEYS = ("max_records",)


class RecipeError(ValueError):
    def __init__(self, problems):
        self.problems = list(problems)
        super().__init__("; ".join(self.problems))


@dataclass
class Field:
    name: str
    selector: str | None = None
    attr: str = "text"
    type: str = "text"
    required: bool = False
    label: str | None = None
    label_scope: str | None = None


@dataclass
class Pagination:
    type: str = "none"
    selector: str | None = None
    text: str | None = None  # next_link: only links whose text equals this (e.g. "Next", "»")
    param: str | None = None
    start: int = 1
    max_pages: int = 0


@dataclass
class Detail:
    link_field: str
    fields: list[Field] = field(default_factory=list)


@dataclass
class Recipe:
    name: str
    start_url: str
    item_selector: str
    list_fields: list[Field] = field(default_factory=list)
    pagination: Pagination = field(default_factory=Pagination)
    detail: Detail | None = None
    dedup_keys: list[str] = field(default_factory=list)
    max_records: int = 0
    render_js: bool = False
    version: int = RECIPE_VERSION
    # Several start pages (e.g. one per city). Empty = just start_url. When set, they replace start_url.
    start_urls: list[str] = field(default_factory=list)

    def start_pages(self) -> list[str]:
        return list(self.start_urls) if self.start_urls else [self.start_url]

    def all_fields(self) -> list[Field]:
        return self.list_fields + (self.detail.fields if self.detail else [])

    def to_dict(self) -> dict:
        out = {
            "version": self.version,
            "name": self.name,
            "start_url": self.start_pages()[0],
            "render_js": self.render_js,
            "list": {"item_selector": self.item_selector, "fields": [_field_dict(f) for f in self.list_fields]},
            "pagination": _drop_none(asdict(self.pagination)),
            "dedup_keys": list(self.dedup_keys),
            "limits": {"max_records": self.max_records},
        }
        if self.start_urls:
            out["start_urls"] = list(self.start_urls)
        if self.detail:
            out["detail"] = {
                "link_field": self.detail.link_field,
                "fields": [_field_dict(f) for f in self.detail.fields],
            }
        return out

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


def _drop_none(d: dict) -> dict:
    return {k: v for k, v in d.items() if v is not None}


def _field_dict(f: Field) -> dict:
    return _drop_none(asdict(f))


def _obj(value, allowed, where, problems) -> dict:
    """Return value as a dict limited to allowed keys, recording shape problems."""
    if value is None:
        return {}
    if not isinstance(value, dict):
        problems.append(f"{where} must be an object")
        return {}
    unknown = set(value) - set(allowed)
    if unknown:
        problems.append(f"{where}: unknown keys {sorted(unknown)}")
    return {k: value[k] for k in allowed if k in value}


def _parse_fields(items, where, problems) -> list[Field]:
    if items is None:
        return []
    if not isinstance(items, list):
        problems.append(f"{where} must be a list")
        return []
    fields = []
    for i, raw in enumerate(items):
        data = _obj(raw, FIELD_KEYS, f"{where}[{i}]", problems)
        if "name" not in data:
            problems.append(f"{where}[{i}]: missing name")
            continue
        fields.append(Field(**data))
    return fields


def from_dict(data: dict) -> Recipe:
    """Build a Recipe from its JSON form. Raises RecipeError on shape problems (see validate() for rules)."""
    problems = []
    top = _obj(data, TOP_KEYS, "recipe", problems)
    lst = _obj(top.get("list"), LIST_KEYS, "list", problems)
    pag = _obj(top.get("pagination"), PAGINATION_KEYS, "pagination", problems)
    limits = _obj(top.get("limits"), LIMIT_KEYS, "limits", problems)
    list_fields = _parse_fields(lst.get("fields"), "list.fields", problems)
    detail = None
    if top.get("detail") is not None:
        d = _obj(top["detail"], DETAIL_KEYS, "detail", problems)
        detail = Detail(link_field=d.get("link_field", ""), fields=_parse_fields(d.get("fields"), "detail.fields", problems))
    if problems:
        raise RecipeError(problems)
    start_urls = top.get("start_urls") or []
    if not isinstance(start_urls, list) or not all(isinstance(u, str) for u in start_urls):
        raise RecipeError(["start_urls must be a list of addresses"])
    try:
        return Recipe(
            name=str(top.get("name", "")),
            start_url=str(top.get("start_url") or (start_urls[0] if start_urls else "")),
            start_urls=list(start_urls),
            item_selector=str(lst.get("item_selector", "")),
            list_fields=list_fields,
            pagination=Pagination(**pag),
            detail=detail,
            dedup_keys=list(top.get("dedup_keys") or []),
            max_records=int(limits.get("max_records", 0)),
            render_js=bool(top.get("render_js", False)),
            version=int(top.get("version", RECIPE_VERSION)),
        )
    except (TypeError, ValueError) as exc:
        raise RecipeError([str(exc)]) from exc


def from_json(text: str) -> Recipe:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RecipeError([f"not valid JSON: {exc}"]) from exc
    return from_dict(data)


def load_recipe(path) -> Recipe:
    path = Path(path)
    if path.stat().st_size > MAX_RECIPE_FILE_BYTES:
        raise RecipeError([f"recipe file larger than {MAX_RECIPE_FILE_BYTES} bytes"])
    return from_json(path.read_text(encoding="utf-8"))


def _is_local_host(host: str) -> bool:
    if not host or host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def check_url(url: str, allow_local=False) -> str | None:
    """Return a plain-language problem, or None if the URL is acceptable as a collection target."""
    parts = urlsplit(url or "")
    if parts.scheme not in ("http", "https"):
        return "address must start with http:// or https://"
    if not parts.hostname:
        return "address has no site name"
    if not allow_local and _is_local_host(parts.hostname):
        return "local network addresses are not allowed"
    return None


def _check_selector(sel, where, problems):
    if sel is None or sel.strip() in ("", ":scope"):
        return
    try:
        soupsieve.compile(sel)
    except Exception as exc:  # soupsieve raises several error types for bad CSS
        problems.append(f"{where}: invalid selector {sel!r} ({exc.__class__.__name__})")


def validate(recipe: Recipe, allow_local=False) -> None:
    """Raise RecipeError listing every problem found."""
    problems = []
    if not recipe.name.strip():
        problems.append("name is empty")
    pages = recipe.start_pages()
    for url in pages:
        url_problem = check_url(url, allow_local)
        if url_problem:
            problems.append(f"start page {url!r}: {url_problem}")
    if len(set(pages)) != len(pages):
        problems.append("the same start page is listed twice")
    if len(pages) > MAX_START_PAGES:
        problems.append(f"more than {MAX_START_PAGES} start pages")
    if not recipe.item_selector.strip():
        problems.append("list.item_selector is empty")
    else:
        _check_selector(recipe.item_selector, "list.item_selector", problems)
    if not recipe.list_fields:
        problems.append("list has no fields")

    names = [f.name for f in recipe.all_fields()]
    dupes = sorted({n for n in names if names.count(n) > 1})
    if dupes:
        problems.append(f"duplicate field names {dupes}")

    detail_fields = recipe.detail.fields if recipe.detail else []
    for where, fields, label_ok in (("list", recipe.list_fields, False), ("detail", detail_fields, True)):
        for f in fields:
            w = f"{where} field {f.name!r}"
            if not f.name.strip():
                problems.append(f"{where}: a field has no name")
            if f.type not in FIELD_TYPES:
                problems.append(f"{w}: type must be one of {FIELD_TYPES}")
            if f.label is not None:
                if not label_ok:
                    problems.append(f"{w}: label fields are only allowed on detail pages")
                if not f.label_scope:
                    problems.append(f"{w}: label needs label_scope")
                if f.selector is not None:
                    problems.append(f"{w}: use either selector or label, not both")
                _check_selector(f.label_scope, w, problems)
            else:
                if f.selector is None:
                    problems.append(f"{w}: needs a selector")
                _check_selector(f.selector, w, problems)

    if recipe.detail:
        if recipe.detail.link_field not in [f.name for f in recipe.list_fields]:
            problems.append(f"detail.link_field {recipe.detail.link_field!r} is not a list field")
        if not recipe.detail.fields:
            problems.append("detail has no fields")

    p = recipe.pagination
    if p.type not in PAGINATION_TYPES:
        problems.append(f"pagination.type must be one of {PAGINATION_TYPES}")
    if p.type == "next_link":
        if not p.selector:
            problems.append("pagination next_link needs a selector")
        _check_selector(p.selector, "pagination", problems)
    if p.type == "page_param" and not p.param:
        problems.append("pagination page_param needs param")
    if p.max_pages < 0 or recipe.max_records < 0:
        problems.append("limits cannot be negative")

    for key in recipe.dedup_keys:
        if key not in names:
            problems.append(f"dedup key {key!r} is not a field")

    if problems:
        raise RecipeError(problems)
