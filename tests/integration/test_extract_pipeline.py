from pathlib import Path

from src.app import extract as extract_mod


def test_extract_pipeline_encode_validate_dedup_write_with_quarantine(tmp_path, monkeypatch):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    quarantine_dir = tmp_path / "quarantine"
    output_csv = tmp_path / "out" / "transactions.csv"

    ok_image = input_dir / "ok.png"
    failed_image = input_dir / "failed.png"
    ok_image.write_bytes(b"ok")
    failed_image.write_bytes(b"failed")

    monkeypatch.setattr(extract_mod, "IMAGE_EXTENSIONS", {".png"})
    monkeypatch.setattr(extract_mod, "encode_image", lambda _: ("b64", "image/png"))

    def fake_call_vision(_img_b64, _mime, _api_key, _model):
        if fake_call_vision.calls == 0:
            fake_call_vision.calls += 1
            return {
                "date": "2026-03-01",
                "time": "10:00",
                "asset_name": "Ethreum",
                "asset_price": 100,
                "units": 1,
                "fees": 0,
                "total": 100,
                "type": "buy",
                "status": "completed",
            }
        return {
            "date": "2026-03-01",
            "time": "11:00",
            "asset_name": "Unknown",
            "asset_price": 0,
            "units": 0,
            "fees": 0,
            "total": 0,
            "type": "buy",
            "status": "failed",
        }

    fake_call_vision.calls = 0
    monkeypatch.setattr(extract_mod, "call_vision", fake_call_vision)
    monkeypatch.setattr(extract_mod, "load_known_assets_and_files", lambda _p: (set(), set()))
    monkeypatch.setattr(extract_mod, "normalize_asset_name", lambda *_args, **_kwargs: ("Ethereum", True))
    monkeypatch.setattr(extract_mod.time, "sleep", lambda _d: None)

    captured = {}

    def fake_dedup_and_write(transactions, _csv):
        captured["transactions"] = list(transactions)
        return len(transactions), 0

    monkeypatch.setattr(extract_mod, "deduplicate_and_write", fake_dedup_and_write)

    extract_mod.process_screenshots(
        input_dir=str(input_dir),
        output_csv=str(output_csv),
        api_key="test",
        model="m",
        delay=0.0,
        quarantine_dir=str(quarantine_dir),
    )

    assert "transactions" in captured
    assert len(captured["transactions"]) == 1
    assert captured["transactions"][0].asset_name == "Ethereum"
    assert (quarantine_dir / "ok.png").exists() or (quarantine_dir / "failed.png").exists()
