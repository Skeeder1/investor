from __future__ import annotations

import io
import sys
import traceback
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

import pytest


class DetailedResultsPlugin:
    def __init__(self) -> None:
        self.test_order: list[str] = []
        self.reports: dict[str, dict[str, object]] = {}

    def pytest_runtest_logreport(self, report) -> None:  # pytest hook
        if report.nodeid not in self.test_order:
            self.test_order.append(report.nodeid)
        record = self.reports.setdefault(report.nodeid, {})
        record[report.when] = report


def _summarize_test(record: dict[str, object]) -> tuple[str, float, str]:
    setup = record.get("setup")
    call = record.get("call")
    teardown = record.get("teardown")

    duration = 0.0
    for phase in (setup, call, teardown):
        if phase is not None:
            duration += float(getattr(phase, "duration", 0.0))

    if setup is not None and getattr(setup, "failed", False):
        return "ERROR_SETUP", duration, str(getattr(setup, "longrepr", ""))

    if call is None:
        if setup is not None and getattr(setup, "skipped", False):
            return "SKIPPED", duration, str(getattr(setup, "longrepr", ""))
        return "UNKNOWN", duration, ""

    if getattr(call, "passed", False):
        return "PASSED", duration, ""
    if getattr(call, "skipped", False):
        return "SKIPPED", duration, str(getattr(call, "longrepr", ""))
    if getattr(call, "failed", False):
        return "FAILED", duration, str(getattr(call, "longrepr", ""))

    return "UNKNOWN", duration, ""


def _sheet_dry_run_preview() -> tuple[list[str], str]:
    """Return all row lines that would be added to sheet in dry-run mode."""
    try:
        from src.app.sync import sync_csv_to_sheet

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            sync_csv_to_sheet(mode="dry-run")

        output = buffer.getvalue()
        preview_lines = []
        for raw_line in output.splitlines():
            line = raw_line.strip()
            if "→ ligne" in line and "[" in line and "/" in line:
                preview_lines.append(line)
        return preview_lines, ""
    except (OSError, ImportError, ValueError):
        return [], traceback.format_exc()


def _write_report(report_text: str) -> Path:
    reports_dir = Path("tests") / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = reports_dir / f"test_report_{timestamp}.txt"
    out_path.write_text(report_text, encoding="utf-8")
    return out_path


def main() -> int:
    plugin = DetailedResultsPlugin()
    pytest_exit = pytest.main(["tests", "-q"], plugins=[plugin])

    status_counts: dict[str, int] = {
        "PASSED": 0,
        "FAILED": 0,
        "SKIPPED": 0,
        "ERROR_SETUP": 0,
        "UNKNOWN": 0,
    }

    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("RAPPORT DETAILLE DES TESTS")
    lines.append("=" * 72)
    lines.append(f"Date: {datetime.now().isoformat(timespec='seconds')}")
    lines.append("")
    lines.append("[DETAIL PAR TEST]")

    for nodeid in plugin.test_order:
        record = plugin.reports.get(nodeid, {})
        status, duration, details = _summarize_test(record)
        status_counts[status] = status_counts.get(status, 0) + 1
        lines.append(f"- {status:<11} {nodeid} ({duration:.4f}s)")
        if details and status in {"FAILED", "ERROR_SETUP"}:
            compact = str(details).splitlines()
            max_lines = 6
            lines.append("  detail:")
            for dline in compact[:max_lines]:
                lines.append(f"    {dline}")
            if len(compact) > max_lines:
                lines.append("    ...")

    lines.append("")
    lines.append("[SYNTHESE]")
    lines.append(f"- total: {len(plugin.test_order)}")
    lines.append(f"- passed: {status_counts.get('PASSED', 0)}")
    lines.append(f"- failed: {status_counts.get('FAILED', 0)}")
    lines.append(f"- skipped: {status_counts.get('SKIPPED', 0)}")
    lines.append(f"- error_setup: {status_counts.get('ERROR_SETUP', 0)}")
    lines.append(f"- unknown: {status_counts.get('UNKNOWN', 0)}")
    lines.append("")

    preview_lines, preview_error = _sheet_dry_run_preview()
    lines.append("[LIGNES QUI SERAIENT AJOUTEES DANS LE SHEET (DRY-RUN)]")
    if preview_error:
        lines.append("- impossible de recuperer le preview dry-run:")
        for err_line in preview_error.splitlines()[:10]:
            lines.append(f"  {err_line}")
    elif not preview_lines:
        lines.append("- aucune ligne a ajouter")
    else:
        lines.append(f"- nombre de lignes: {len(preview_lines)}")
        for row_line in preview_lines:
            lines.append(f"  {row_line}")

    lines.append("")
    lines.append("Note: le dry-run ne modifie ni le CSV ni Google Sheets.")

    report_text = "\n".join(lines) + "\n"
    report_path = _write_report(report_text)

    print(report_text)
    print(f"Rapport sauvegarde: {report_path}")

    return int(pytest_exit)


if __name__ == "__main__":
    raise SystemExit(main())
