"""Find & delete a person, and the do-not-collect list (SECURITY.md 4, DPDP erasure requests).

The do-not-collect list keeps only SHA-256 hashes of a deleted person's phone numbers, emails and item key,
never the values themselves, so the list can't be read back as personal data.
"""

import hashlib
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RUN = re.compile(r"\+?\d[\d\s().-]{5,}\d")
PHONE_TAIL = 9  # compare the last 9 digits: ignores country codes and trunk zeros
MIN_QUERY = 3
POSITIONAL_KEY = re.compile(r"#item\d+$")  # core.runner key for items without their own page


def digits(text) -> str:
    return re.sub(r"\D", "", text or "")


def phones_in(text) -> set[str]:
    """Digit strings of the phone-like runs in text (7 or more digits)."""
    return {d for d in (digits(m) for m in PHONE_RUN.findall(text or "")) if len(d) >= 7}


def emails_in(text) -> set[str]:
    return {e.lower().rstrip(".") for e in EMAIL.findall(text or "")}


def _values(data: dict) -> list[str]:
    return [str(v) for k, v in data.items() if v and not str(k).startswith("_")]


def matches(data: dict, query: str) -> bool:
    """Whether a collected record belongs to the person searched for (phone, email or name text)."""
    query = (query or "").strip()
    if len(query) < MIN_QUERY:
        return False
    values = _values(data)
    if "@" in query:
        wanted = query.lower()
        return any(wanted in e for v in values for e in emails_in(v))
    query_digits = digits(query)
    if len(query_digits) >= 7 and len(query_digits) >= 0.7 * len(re.sub(r"[\s+()-]", "", query)):
        tail = query_digits[-PHONE_TAIL:]
        return any(p.endswith(tail) for v in values for p in phones_in(v))
    wanted = query.casefold()
    return any(wanted in v.casefold() for v in values)


def _hash(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def keys_for(recipe_id, recipe, item_key, data: dict) -> list[tuple[str, str]]:
    """(kind, hash) pairs that identify this record's person on later runs."""
    phone_fields = {f.name for f in recipe.all_fields() if f.type == "phone"}
    keys = set()
    positional = bool(POSITIONAL_KEY.search(item_key or ""))
    if not positional:  # an item page address identifies the item; a position on a list page doesn't
        keys.add(("item", f"item:{recipe_id}:{item_key}"))
    for name, value in data.items():
        if not value or str(name).startswith("_"):
            continue
        keys |= {("email", f"email:{e}") for e in emails_in(str(value))}
        if name in phone_fields:
            keys |= {("phone", f"phone:{p[-PHONE_TAIL:]}") for p in phones_in(str(value))}
    if positional and recipe.list_fields:  # no item page: the first column (usually the name) in this recipe
        first = data.get(recipe.list_fields[0].name)
        if first:
            keys.add(("name", f"name:{recipe_id}:{' '.join(str(first).casefold().split())}"))
    return sorted((kind, _hash(key)) for kind, key in keys)


def hashes_for(recipe_id, recipe, item_key, data: dict) -> list[str]:
    return [h for _kind, h in keys_for(recipe_id, recipe, item_key, data)]
