"""Turn raw records into checked rows: type-based cleanup, required fields, dedup, Needs Review split."""

import re

from core.recipe import Recipe

PHONE_CHUNK = re.compile(r"\+?\d[\d\s\-()]{6,}\d")
PINCODE = re.compile(r"(?<!\d)([1-9]\d{2})\s?(\d{3})(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
AT_WORD = re.compile(r"\s*[\[(\{]\s*at\s*[\])\}]\s*", re.I)
DOT_WORD = re.compile(r"\s*[\[(\{]\s*dot\s*[\])\}]\s*", re.I)


def unobfuscate_email(text: str) -> str:
    """name[at]site[dot]com and name (at) site.com, written that way to hide from spam robots."""
    return DOT_WORD.sub(".", AT_WORD.sub("@", text))
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)*")

FIXED_BEFORE = ["Record ID"]
FIXED_AFTER = ["Source URL", "Start Page", "Collected On", "Issues"]


URL_IN_TEXT = re.compile(r"(https?://[^\s,;]+|www\.[^\s,;]+)", re.I)


def normalize_phones(raw, country="91"):
    """Return (numbers in +<country><number> form, rejected fragments).

    Numbers written with + or 00 keep their own country code. Others get `country`; a leading 0 (trunk
    prefix) is dropped first. India (91) keeps the strict 10-digit rule."""
    good, bad = [], []
    for chunk in PHONE_CHUNK.findall(raw or ""):
        text = chunk.strip()
        digits = re.sub(r"\D", "", text)
        if text.startswith("+"):
            full = digits
        elif digits.startswith("00"):
            full = digits[2:]
        elif country == "91" and len(digits) == 12 and digits.startswith("91"):
            full = digits
        elif digits.startswith("0"):
            full = country + digits[1:]
        else:
            full = country + digits
        national = full[len(country):] if full.startswith(country) else None
        if country == "91" and national is not None:
            ok = len(national) == 10 and national[0] != "0"
        else:
            ok = 8 <= len(full) <= 15 and (national is None or len(national) >= 6)
        if ok:
            number = "+" + full
            if number not in good:
                good.append(number)
        else:
            bad.append(text)
    return good, bad


def extract_pincode(text):
    matches = PINCODE.findall(text or "")
    return "".join(matches[-1]) if matches else None


def clean_value(raw, field_type, country="91"):
    """Return (clean value or None, issue or None). Issues only for present-but-unusable values."""
    if raw is None or not str(raw).strip():
        return None, None
    raw = " ".join(str(raw).split())
    if field_type in ("link", "image"):
        if raw.lower().startswith(("http://", "https://")) and " " not in raw:
            return raw, None
        m = URL_IN_TEXT.search(raw)  # a web address written as text, e.g. in a paragraph
        return (m.group(1).rstrip(".)"), None) if m else (raw, None)
    if field_type == "phone":
        good, bad = normalize_phones(raw, country)
        if good:
            return ", ".join(good), None
        return None, f"invalid phone {', '.join(bad) or raw!r}"
    if field_type == "email":
        found = [e.lower() for e in EMAIL.findall(unobfuscate_email(raw))]
        return (", ".join(dict.fromkeys(found)), None) if found else (None, f"invalid email {raw!r}")
    if field_type == "pincode":
        # Usually read from free-text addresses; no pincode there is a blank, not an error.
        return extract_pincode(raw), None
    if field_type == "number":
        m = NUMBER.search(raw)
        return (m.group(0).replace(",", ""), None) if m else (None, f"not a number {raw!r}")
    return raw, None


def columns_for(recipe: Recipe) -> list[str]:
    return FIXED_BEFORE + [f.name for f in recipe.all_fields()] + FIXED_AFTER


def source_url(item_key: str) -> str:
    return item_key.rsplit("#item", 1)[0]


def build_rows(recipe: Recipe, records: list[dict], id_prefix="R"):
    """Split stored records into (ready_rows, review_rows), each a dict keyed by columns_for(recipe).

    A row needs review when a required field is missing/unusable or it duplicates an earlier row by the
    recipe's dedup_keys. Smaller issues stay in the Issues column of ready rows.
    """
    fields = recipe.all_fields()
    ready, review, seen = [], [], {}
    for n, rec in enumerate(records, start=1):
        data = rec["data"]
        row = {"Record ID": f"{id_prefix}-{n:05d}"}
        issues, blocking = [], False
        for f in fields:
            value, issue = clean_value(data.get(f.name), f.type, recipe.phone_country)
            row[f.name] = value
            if issue:
                issues.append(f"{f.name}: {issue}")
            if f.required and value is None:
                blocking = True
                if not issue:
                    issues.append(f"{f.name}: missing")
        if recipe.dedup_keys:
            key = tuple((row.get(k) or "").casefold() for k in recipe.dedup_keys)
            if all(key):
                if key in seen:
                    issues.append(f"duplicate of {seen[key]}")
                    blocking = True
                else:
                    seen[key] = row["Record ID"]
        row["Source URL"] = source_url(rec["item_key"])
        row["Start Page"] = data.get("_start_page")
        row["Collected On"] = (rec.get("collected_at") or "")[:10]
        row["Issues"] = "; ".join(issues) or None
        (review if blocking else ready).append(row)
    return ready, review
