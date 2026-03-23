from src.domain.validation import validate_transaction


def _base_payload() -> dict:
    return {
        "date": "2026-03-01",
        "time": "09:30:20",
        "asset_name": "Ethereum",
        "asset_price": 2000,
        "units": 0.05,
        "fees": 1,
        "total": 101,
        "type": "buy",
        "status": "completed",
        "confidence": "high",
        "notes": "",
    }


def test_validate_transaction_valid_completed():
    tx, warnings = validate_transaction(_base_payload(), "ok.png")
    assert tx is not None
    assert tx.date == "2026-03-01"
    assert tx.time == "09:30"
    assert tx.type == "buy"
    assert warnings == []


def test_validate_transaction_valid_executed_status():
    payload = _base_payload()
    payload["status"] = "executed"

    tx, warnings = validate_transaction(payload, "ok2.png")
    assert tx is not None
    assert tx.status == "executed"
    assert warnings == []


def test_validate_transaction_invalid_status_skipped():
    payload = _base_payload()
    payload["status"] = "failed"

    tx, warnings = validate_transaction(payload, "bad.png")
    assert tx is None
    assert any("status is 'failed'" in w for w in warnings)


def test_validate_transaction_invalid_numeric_value():
    payload = _base_payload()
    payload["total"] = "abc"

    tx, warnings = validate_transaction(payload, "num.png")
    assert tx is None
    assert any("invalid numeric value" in w for w in warnings)


def test_validate_transaction_unknown_type_defaults_to_buy():
    payload = _base_payload()
    payload["type"] = "mystery"

    tx, warnings = validate_transaction(payload, "type.png")
    assert tx is not None
    assert tx.type == "buy"
    assert any("defaulting to 'buy'" in w for w in warnings)


def test_validate_transaction_math_warning_edge_case():
    payload = _base_payload()
    payload["total"] = 150

    tx, warnings = validate_transaction(payload, "math.png")
    assert tx is not None
    assert any("math check failed" in w for w in warnings)


def test_validate_transaction_low_confidence_and_notes():
    payload = _base_payload()
    payload["confidence"] = "low"
    payload["notes"] = "OCR unsure"

    tx, warnings = validate_transaction(payload, "warn.png")
    assert tx is not None
    assert any("low confidence" in w for w in warnings)
    assert any("NOTE warn.png: OCR unsure" == w for w in warnings)


def test_validate_transaction_invalid_date():
    payload = _base_payload()
    payload["date"] = "31-02-2026"

    tx, warnings = validate_transaction(payload, "date.png")
    assert tx is None
    assert any("invalid date" in w for w in warnings)


def test_validate_transaction_invalid_time():
    payload = _base_payload()
    payload["time"] = "25:99"

    tx, warnings = validate_transaction(payload, "time.png")
    assert tx is None
    assert any("invalid time" in w for w in warnings)
