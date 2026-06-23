from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from upload_samples.reporting import (
    init_reporting,
    list_findings,
    list_results,
    load_session_state,
    patch_result,
    upsert_finding,
)

def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "upload_samples", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_report_init_status_and_export(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    generate = run_cli("generate", "--out", str(out_dir))
    assert generate.returncode == 0, generate.stderr

    init = run_cli("report-init", "--out", str(out_dir))
    assert init.returncode == 0, init.stderr
    assert (out_dir / "reporting" / "session.sqlite3").exists()
    assert (out_dir / "reporting" / "ui" / "index.html").exists()
    assert "entries=54" in init.stdout

    status = run_cli("report-status", "--out", str(out_dir))
    assert status.returncode == 0, status.stderr
    assert "untested" in status.stdout

    export = run_cli("report-export", "--out", str(out_dir))
    assert export.returncode == 0, export.stderr
    assert (out_dir / "reporting" / "final-report.html").exists()
    assert (out_dir / "reporting" / "report-summary.json").exists()
    assert (out_dir / "reporting" / "report-summary.md").exists()


def test_report_init_import_count_matches_manifest_entries(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    generate = run_cli("generate", "--out", str(out_dir))
    assert generate.returncode == 0, generate.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    init_reporting(out_dir)
    results = list_results(out_dir)
    assert len(results) == len(manifest["entries"])


def test_reporting_storage_persists_updates(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    generate = run_cli("generate", "--out", str(out_dir), "--category", "baseline")
    assert generate.returncode == 0, generate.stderr
    init_reporting(out_dir)

    session = load_session_state(out_dir)
    assert session["total_entries"] > 0

    results = list_results(out_dir)
    sample_id = results[0]["id"]
    updated = patch_result(
        out_dir,
        sample_id,
        {
            "test_status": "accepted",
            "validation_message": "accepted in target",
            "finding_title": "Baseline accepted",
        },
    )
    assert updated["test_status"] == "accepted"

    finding = upsert_finding(
        out_dir,
        {
            "title": "Grouped finding",
            "severity": "low",
            "summary": "summary",
            "recommendation": "recommend",
            "manifest_ids": [sample_id],
        },
    )
    assert finding["title"] == "Grouped finding"

    persisted_results = list_results(out_dir)
    persisted_row = next(item for item in persisted_results if item["id"] == sample_id)
    assert persisted_row["validation_message"] == "accepted in target"
    assert persisted_row["finding_title"] == "Baseline accepted"
    assert any(item["title"] == "Grouped finding" for item in list_findings(out_dir))

    restarted = run_cli("report-export", "--out", str(out_dir))
    assert restarted.returncode == 0, restarted.stderr
    summary = json.loads((out_dir / "reporting" / "report-summary.json").read_text(encoding="utf-8"))
    assert summary["progress"]["accepted"] >= 1
    assert any(item["title"] == "Grouped finding" for item in summary["explicit_findings"])
