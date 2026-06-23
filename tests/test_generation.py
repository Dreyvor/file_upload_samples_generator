from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    env = {"PYTHONPATH": str(ROOT / "src")}
    return subprocess.run(
        [sys.executable, "-m", "upload_samples", *args],
        cwd=cwd or ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_generate_and_verify(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir))
    assert result.returncode == 0, result.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "1.0"
    assert len(manifest["entries"]) >= 25

    verify = run_cli("verify", "--out", str(out_dir))
    assert verify.returncode == 0, verify.stderr


def test_mismatch_matrix_count_and_alias_behavior(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "mismatch")
    assert result.returncode == 0, result.stderr
    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["entries"]
    assert len(entries) == 25

    alias_rows = [entry for entry in entries if entry["logical_extension"] == "jpeg" and entry["generated_content_family"] == "jpg"]
    assert any(entry["mismatch"] is False for entry in alias_rows)


def test_risky_filenames_stay_in_recipes(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "filenames")
    assert result.returncode == 0, result.stderr

    filename_recipe = (out_dir / "multipart-recipes" / "filename-tests.md").read_text(encoding="utf-8")
    assert "../../file.pdf" in filename_recipe
    assert not (out_dir / "../../file.pdf").exists()


def test_family_selection_limits_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--family", "pdf", "--category", "baseline", "--category", "mismatch")
    assert result.returncode == 0, result.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    entries = manifest["entries"]
    assert {entry["generated_content_family"] for entry in entries} == {"pdf"}
    assert {entry["logical_extension"] for entry in entries} == {"pdf"}


def test_baseline_images_open_with_pillow(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "baseline")
    assert result.returncode == 0, result.stderr

    for name in ("valid.jpg", "valid.jpeg", "valid.tiff"):
        path = out_dir / "baseline" / name
        with Image.open(path) as image:
            image.load()
            assert image.size == (8, 8)
