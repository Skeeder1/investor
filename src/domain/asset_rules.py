def map_type_label(tx_type: str) -> str:
    return "Achat" if tx_type in ("buy", "pea") else "Vente"


def map_compte(tx_type: str, name: str) -> str:
    if tx_type == "pea":
        return "PEA"
    if "S&P 500 EUR" in name:
        return "PEA"
    return "CTO"


def map_asset_display(name: str, compte: str) -> str:
    if compte == "PEA" and "S&P 500 EUR" in name:
        return "S&P 500"
    return name


def format_euro(value: float) -> str:
    v = float(value)
    if v == 0.0:
        return "0,00 \u20ac"
    formatted = f"{v:,.2f}".replace(",", " ").replace(".", ",")
    return formatted + " \u20ac"


def format_units(value: float) -> str:
    s = f"{float(value):.6f}".rstrip("0")
    if s.endswith("."):
        s += "0"
    return s.replace(".", ",")


def parse_amount(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    s = text.strip().rstrip("€").strip()
    s = s.replace("\u00a0", "").replace(" ", "")
    s = s.replace(",", ".")
    try:
        return round(float(s), 2)
    except ValueError:
        return 0.0


def parse_units(text: str) -> float:
    if not text or not text.strip():
        return 0.0
    s = text.strip().replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0
