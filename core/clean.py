"""Turn raw records into checked rows: type-based cleanup, required fields, dedup, Needs Review split."""

import re

from core.recipe import Recipe

PHONE_CHUNK = re.compile(r"\+?\d[\d\s\-()]{6,}\d")
PINCODE = re.compile(r"(?<!\d)([1-9]\d{2})\s?(\d{3})(?!\d)")
EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
NUMBER = re.compile(r"-?\d+(?:[.,]\d+)*")

FIXED_BEFORE = ["Record ID"]
FIXED_AFTER = ["Source URL", "Start Page", "Collected On", "Issues"]


def normalize_phones(raw):
    """Return (list of '+91XXXXXXXXXX' numbers, list of rejected fragments)."""
    good, bad = [], []
    for chunk in PHONE_CHUNK.findall(raw or ""):
        digits = re.sub(r"\D", "", chunk)
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        if len(digits) == 10 and digits[0] != "0":
            number = "+91" + digits
            if number not in good:
                good.append(number)
        else:
            bad.append(chunk.strip())
    return good, bad


def extract_pincode(text):
    matches = PINCODE.findall(text or "")
    return "".join(matches[-1]) if matches else None


def clean_value(raw, field_type):
    """Return (clean value or None, issue or None). Issues only for present-but-unusable values."""
    if raw is None or not str(raw).strip():
        return None, None
    raw = " ".join(str(raw).split())
    if field_type == "phone":
        good, bad = normalize_phones(raw)
        if good:
            return ", ".join(good), None
        return None, f"invalid phone {', '.join(bad) or raw!r}"
    if field_type == "email":
        found = [e.lower() for e in EMAIL.findall(raw)]
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
            value, issue = clean_value(data.get(f.name), f.type)
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
