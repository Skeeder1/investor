from src.domain.asset_rules import (
    format_euro,
    format_units,
    map_asset_display,
    map_compte,
    map_type_label,
    parse_amount,
    parse_units,
)


def test_map_type_label():
    assert map_type_label("buy") == "Achat"
    assert map_type_label("pea") == "Achat"
    assert map_type_label("sell") == "Vente"


def test_map_compte_and_asset_display():
    assert map_compte("pea", "Anything") == "PEA"
    assert map_compte("buy", "Core S&P 500 EUR (Acc)") == "PEA"
    assert map_compte("buy", "Bitcoin") == "CTO"
    assert map_asset_display("Core S&P 500 EUR (Acc)", "PEA") == "S&P 500"
    assert map_asset_display("Bitcoin", "CTO") == "Bitcoin"


def test_format_euro_and_units():
    assert format_euro(0) == "0,00 €"
    assert format_euro(1234.5) == "1 234,50 €"
    assert format_units(0) == "0,0"
    assert format_units(12.340000) == "12,34"


def test_parse_amount_and_units():
    assert parse_amount("1 234,50 €") == 1234.5
    assert parse_amount("  98,1 € ") == 98.1
    assert parse_amount("") == 0.0
    assert parse_amount("invalid") == 0.0

    assert parse_units("1,2345") == 1.2345
    assert parse_units("2.5") == 2.5
    assert parse_units("") == 0.0
    assert parse_units("not-a-number") == 0.0
