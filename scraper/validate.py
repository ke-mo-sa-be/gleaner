"""Turn raw records into clean, checked rows: phone/pincode normalising, role mapping, dedup."""

import re

# First match wins. Applied to specialization / designation text.
ROLE_RULES = [
    (re.compile(r"radiolog|radio-?diagnos", re.I), "Radiologist"),
    (re.compile(r"bio-?medical|\bBME\b", re.I), "BME"),
    (re.compile(r"purchase|procurement|stores officer", re.I), "Purchase"),
    (re.compile(r"\bPRO\b|public relation", re.I), "PRO"),
    (re.compile(r"admin|superintendent|director|\bCEO\b|\bCOO\b|manager", re.I), "Admin"),
]

PHONE_CHUNK = re.compile(r"\+?\d[\d\s\-()]{6,}\d")
PINCODE = re.compile(r"(?<!\d)([1-9]\d{2})\s?(\d{3})(?!\d)")

COLUMNS = [
    "Record ID", "Name", "Role", "Specialization", "Degree", "Clinic / Hospital", "Address", "Area",
    "District", "State", "Pincode", "Phone", "Medical Council", "Registration No", "Practicing Since",
    "Source", "Source URL", "Collected On", "Issues",
]


def normalize_role(text, default="Doctor"):
    for pattern, role in ROLE_RULES:
        if text and pattern.search(text):
            return role
    return default


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


def extract_pincode(address):
    matches = PINCODE.findall(address or "")
    return "".join(matches[-1]) if matches else None


def clean_record(rec):
    """Merge listing row + profile into one output row (dict keyed by COLUMNS) and list its issues."""
    profile = rec.get("profile") or {}

    def pick(key):
        return profile.get(key) or rec.get(key)

    issues = []
    if not profile:
        issues.append("profile page missing")

    phones, rejected = normalize_phones(profile.get("phone"))
    if not phones:
        issues.append("no valid phone" if not rejected else f"invalid phone: {', '.join(rejected)}")
    elif rejected:
        issues.append(f"ignored phone fragment: {', '.join(rejected)}")

    address = profile.get("address")
    pincode = extract_pincode(address)
    if not address:
        issues.append("no address")
    elif not pincode:
        issues.append("no pincode in address")

    specialization = pick("specialization")
    row = {
        "Name": pick("name"),
        "Role": normalize_role(specialization),
        "Specialization": specialization,
        "Degree": pick("degree"),
        "Clinic / Hospital": profile.get("facility_name"),
        "Address": address,
        "Area": profile.get("area"),
        "District": profile.get("district") or rec.get("city"),
        "State": pick("state"),
        "Pincode": pincode,
        "Phone": ", ".join(phones) or None,
        "Medical Council": profile.get("medical_council"),
        "Registration No": profile.get("registration_number"),
        "Practicing Since": profile.get("practicing_since"),
        "Source": rec.get("source"),
        "Source URL": rec.get("source_url"),
        "Collected On": (rec.get("collected_at") or "")[:10],
    }
    return row, issues


def dedup_key(row):
    if row["Registration No"]:
        return ("reg", (row["Medical Council"] or "").upper(), row["Registration No"].upper().replace(" ", ""))
    if row["Phone"]:
        return ("phone", row["Phone"].split(",")[0])
    return ("name", (row["Name"] or "").upper(), (row["District"] or "").upper())


def build_rows(records, id_prefix="DRD"):
    """Split records into (contacts, needs_review). A row needs review when it has no
    usable phone or duplicates an earlier row; smaller issues stay in the Issues column."""
    contacts, review, seen = [], [], {}
    for n, rec in enumerate(records, start=1):
        row, issues = clean_record(rec)
        row["Record ID"] = f"{id_prefix}-{n:05d}"
        key = dedup_key(row)
        if key in seen:
            issues.append(f"duplicate of {seen[key]}")
        else:
            seen[key] = row["Record ID"]
        row["Issues"] = "; ".join(issues) or None
        blocking = not row["Phone"] or any(i.startswith("duplicate") for i in issues)
        (review if blocking else contacts).append(row)
    return contacts, review
