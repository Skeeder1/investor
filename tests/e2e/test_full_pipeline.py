from pathlib import Path

from src.app import extract as extract_mod
from src.infra.csv_store import read_csv


def test_full_pipeline_single_image_then_idempotent_rerun(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    output_csv = tmp_path / "output" / "transactions.csv"
    quarantine_dir = tmp_path / "output" / "quarantine"
    input_dir.mkdir(parents=True)

    image = input_dir / "tx1.png"
    image.write_bytes(b"fake image")

    monkeypatch.setattr(extract_mod, "IMAGE_EXTENSIONS", {".png"})
    monkeypatch.setattr(extract_mod, "encode_image", lambda _p: ("b64", "image/png"))
    monkeypatch.setattr(
        extract_mod,
        "call_vision",
        lambda *_args, **_kwargs: {
            "date": "2026-03-05",
            "time": "14:20",
            "asset_name": "Bitcoin",
            "asset_price": 50000,
            "units": 0.002,
            "fees": 0,
            "total": 100,
            "type": "buy",
            "status": "completed",
        },
    )
    monkeypatch.setattr(extract_mod, "normalize_asset_name", lambda name, *_args, **_kwargs: (name, False))
    monkeypatch.setattr(extract_mod.time, "sleep", lambda _d: None)

    extract_mod.process_screenshots(
        input_dir=str(input_dir),
        output_csv=str(output_csv),
        api_key="test",
        model="m",
        delay=0.0,
        test_mode=False,
        quarantine_dir=str(quarantine_dir),
    )

    rows = read_csv(Path(output_csv))
    assert len(rows) == 1
    assert rows[0]["asset_name"] == "Bitcoin"
    assert rows[0]["date"] == "2026-03-05"
    assert rows[0]["source_file"] == "tx1.png"

    extract_mod.process_screenshots(
        input_dir=str(input_dir),
        output_csv=str(output_csv),
        api_key="test",
        model="m",
        delay=0.0,
        test_mode=False,
        quarantine_dir=str(quarantine_dir),
    )

    rows_after = read_csv(Path(output_csv))
    assert len(rows_after) == 1
