from datetime import datetime


FRENCH_MONTHS = {
    1: "janvier",
    2: "fevrier",
    3: "mars",
    4: "avril",
    5: "mai",
    6: "juin",
    7: "juillet",
    8: "aout",
    9: "septembre",
    10: "octobre",
    11: "novembre",
    12: "decembre",
}

_FRENCH_MONTH_ALIASES = {
    "f\u00e9vrier": "fevrier",
    "ao\u00fbt": "aout",
    "d\u00e9cembre": "decembre",
}

FRENCH_MONTHS_REV = {v: k for k, v in FRENCH_MONTHS.items()}
FRENCH_MONTHS_REV.update(
    {
        alias: FRENCH_MONTHS_REV[canonical]
        for alias, canonical in _FRENCH_MONTH_ALIASES.items()
    }
)


def parse_date_any(value: str) -> datetime:
    """Parse common date formats used by legacy and current data flows."""
    text = (value or "").strip()
    if not text:
        raise ValueError("empty date")

    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    raise ValueError(f"unsupported date format: {value}")


def normalize_date_iso(value: str) -> str:
    return parse_date_any(value).strftime("%Y-%m-%d")


def normalize_time_hhmm(value: str) -> str:
    text = (value or "").strip()
    if not text:
        return ""

    for fmt in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M")
        except ValueError:
            continue

    # Fallback for single-digit hour like 8:05
    parts = text.split(":")
    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
        hour = int(parts[0])
        minute = int(parts[1])
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"

    raise ValueError(f"unsupported time format: {value}")


def to_french_date_label(value: str) -> str:
    dt = parse_date_any(value)
    return f"{dt.day:02d} {FRENCH_MONTHS[dt.month]} {dt.year}"


def parse_french_date(text: str) -> datetime:
    """Parse french date labels like '26 mai 2025' into datetime."""
    parts = (text or "").strip().split()
    if len(parts) != 3:
        raise ValueError(f"unsupported french date format: {text}")

    day = int(parts[0])
    month_text = parts[1].lower()
    month = FRENCH_MONTHS_REV.get(month_text)
    if not month:
        raise ValueError(f"unsupported french month: {parts[1]}")

    year = int(parts[2])
    return datetime(year, month, day)
