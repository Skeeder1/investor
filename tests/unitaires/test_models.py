from src.domain.models import Transaction


def test_transaction_instanciation():
    tx = Transaction(
        date="2026-03-01",
        time="10:15",
        asset_name="Bitcoin",
        asset_price=85000.12,
        units=0.001,
        fees=1.0,
        total=86.0,
        type="buy",
        status="completed",
        source_file="img_01.png",
    )

    assert tx.date == "2026-03-01"
    assert tx.time == "10:15"
    assert tx.asset_name == "Bitcoin"
    assert tx.type == "buy"
    assert tx.status == "completed"
    assert tx.source_file == "img_01.png"
