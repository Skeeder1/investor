from typing import Optional

from .datetime_utils import normalize_date_iso, normalize_time_hhmm
from .models import Transaction


def validate_transaction(data: dict, filename: str) -> tuple[Optional[Transaction], list[str]]:
    """Validate extracted data and return Transaction or errors."""
    warnings = []

    # Skip non-transactions
    if data.get("status") == "not_a_transaction":
        return None, [f"SKIP {filename}: not a transaction screenshot"]

    # Accept completed and executed as valid statuses
    valid_statuses = ("completed", "executed")
    if data.get("status") not in valid_statuses:
        return None, [f"SKIP {filename}: status is '{data.get('status')}' (not valid)"]

    # Validate type
    tx_type = data.get("type", "unknown")
    if tx_type not in ("buy", "sell", "pea"):
        warnings.append(f"WARN {filename}: type is '{tx_type}', defaulting to 'buy'")
        tx_type = "buy"

    # Validate numbers
    try:
        total = float(data.get("total", 0))
        units = float(data.get("units", 0))
        price = float(data.get("asset_price", 0))
        fees = float(data.get("fees", 0))
    except (ValueError, TypeError) as e:
        return None, [f"ERROR {filename}: invalid numeric value - {e}"]

    # Cross-check: buy -> units*price + fees ~= total / sell -> units*price - fees ~= total
    # PEA transactions n'ont pas de ligne Transaction (units/price = 0)
    expected = units * price + fees if tx_type == "buy" else units * price - fees
    if tx_type != "pea" and total > 0 and abs(expected - total) / total > 0.05:
        warnings.append(
            f"WARN {filename}: math check failed - "
            f"{units} x {price} {'+ ' if tx_type == 'buy' else '- '}{fees} = {expected:.2f} != {total:.2f}"
        )

    # Confidence check
    if data.get("confidence") == "low":
        warnings.append(f"WARN {filename}: low confidence extraction")

    # Notes from LLM
    if data.get("notes"):
        warnings.append(f"NOTE {filename}: {data['notes']}")

    raw_date = data.get("date", "")
    raw_time = data.get("time", "")
    try:
        date_value = normalize_date_iso(raw_date)
    except ValueError as e:
        return None, [f"ERROR {filename}: invalid date '{raw_date}' - {e}"]

    try:
        time_value = normalize_time_hhmm(raw_time)
    except ValueError as e:
        return None, [f"ERROR {filename}: invalid time '{raw_time}' - {e}"]

    tx = Transaction(
        date=date_value,
        time=time_value,
        asset_name=data.get("asset_name", ""),
        asset_price=price,
        units=units,
        fees=fees,
        total=total,
        type=tx_type,
        status=data.get("status", "completed"),
        source_file=filename,
    )

    return tx, warnings
