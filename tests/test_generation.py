from __future__ import annotations

import json
import os
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
    assert len({entry["id"] for entry in manifest["entries"]}) == len(manifest["entries"])

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


def test_html_recipe_sample_is_generated(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "multipart-recipes")
    assert result.returncode == 0, result.stderr

    html_sample = (out_dir / "multipart-recipes" / "xss-iframe-sample.html").read_text(encoding="utf-8")
    assert "<h1>Upload Sample HTML Test</h1>" in html_sample
    assert "alert('XSS sample triggered');" in html_sample
    assert "<iframe" in html_sample


def test_html_mismatch_helpers_are_generated(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "mismatch")
    assert result.returncode == 0, result.stderr

    notes = (out_dir / "mismatch" / "html-content-notes.md").read_text(encoding="utf-8")
    assert "HTML content mismatch helpers" in notes

    helper = (out_dir / "mismatch" / "manual-html-content-as-jpg.jpg").read_text(encoding="utf-8")
    assert "<h1>Upload Sample HTML Test</h1>" in helper
    assert "alert('XSS sample triggered');" in helper


def test_html_polyglot_helper_seed_is_generated_without_mitra(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "polyglots")
    assert result.returncode == 0, result.stderr

    html_seed = (out_dir / "polyglots" / "manual-html-seed.html").read_text(encoding="utf-8")
    notes = (out_dir / "polyglots" / "html-manual-test-notes.md").read_text(encoding="utf-8")
    assert "<h1>Upload Sample HTML Test</h1>" in html_seed
    assert "forced blob payload" in notes


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


def test_metadata_markers_are_distinct_and_field_specific(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir), "--category", "metadata")
    assert result.returncode == 0, result.stderr

    pdf_marker = (out_dir / "metadata" / "pdf-title-marker.pdf").read_bytes()
    pdf_probe = (out_dir / "metadata" / "pdf-title-reflection-probe.pdf").read_bytes()
    png_marker = (out_dir / "metadata" / "png-text-marker.png").read_bytes()
    png_probe = (out_dir / "metadata" / "png-text-reflection-probe.png").read_bytes()
    tiff_marker = (out_dir / "metadata" / "tiff-description-marker.tiff").read_bytes()

    assert b"UPLOAD_SAMPLE_MARKER__PDF-TITLE-MARKER__TITLE__001" in pdf_marker
    assert b"UPLOAD_SAMPLE_MARKER__PDF-TITLE-MARKER__SUBJECT__002" in pdf_marker
    assert b'data-upload-sample="pdf-title-reflection-probe"' in pdf_probe
    assert b'data-upload-field="title"' in pdf_probe
    assert b"UPLOAD_SAMPLE_MARKER__PNG-TEXT-MARKER__COMMENT__001" in png_marker
    assert b'data-upload-sample="png-text-reflection-probe"' in png_probe
    assert b'data-upload-field="comment"' in png_probe
    assert b"UPLOAD_SAMPLE_MARKER__TIFF-DESCRIPTION-MARKER__IMAGE-DESCRIPTION__001" in tiff_marker


def test_manifest_ids_are_unique_with_repeated_filenames(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    result = run_cli("generate", "--out", str(out_dir))
    assert result.returncode == 0, result.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    ids = [entry["id"] for entry in manifest["entries"]]
    assert len(ids) == len(set(ids))


def test_polyglot_generation_collects_mitra_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    mitra_dir = tmp_path / "mitra"
    mitra_dir.mkdir()
    fake_mitra = mitra_dir / "mitra.py"
    fake_mitra.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] == '-f':\n"
        "    args = args[1:]\n"
        "out = Path.cwd() / 'poly-result.bin'\n"
        "out.write_bytes(Path(args[0]).read_bytes() + b'POLYGLOT' + Path(args[1]).read_bytes())\n",
        encoding="utf-8",
    )

    result = run_cli(
        "generate",
        "--out",
        str(out_dir),
        "--category",
        "polyglots",
        "--mitra-path",
        str(fake_mitra),
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    poly_entries = [entry for entry in manifest["entries"] if entry["category"] == "polyglots"]
    assert poly_entries
    assert any(entry["relative_path"].endswith("poly-result.bin") for entry in poly_entries)
    assert (out_dir / "polyglots" / "pdf-jpg" / "mitra-features.log").exists()
    assert (out_dir / "polyglots" / "png-html" / "mitra.log").exists()


def test_polyglot_generation_collects_nested_mitra_outputs(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    mitra_dir = tmp_path / "mitra"
    mitra_dir.mkdir()
    fake_mitra = mitra_dir / "mitra.py"
    fake_mitra.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] == '-f':\n"
        "    args = args[1:]\n"
        "nested = Path.cwd() / 'nested'\n"
        "nested.mkdir(exist_ok=True)\n"
        "(nested / 'poly-result.bin').write_bytes(b'POLY')\n",
        encoding="utf-8",
    )

    result = run_cli(
        "generate",
        "--out",
        str(out_dir),
        "--category",
        "polyglots",
        "--mitra-path",
        str(fake_mitra),
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    poly_entries = [entry for entry in manifest["entries"] if entry["category"] == "polyglots"]
    assert poly_entries


def test_polyglot_generation_supports_png_html_via_forced_blob(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    mitra_dir = tmp_path / "mitra"
    mitra_dir.mkdir()
    fake_mitra = mitra_dir / "mitra.py"
    fake_mitra.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "forced = False\n"
        "if args and args[0] == '-f':\n"
        "    forced = True\n"
        "    args = args[1:]\n"
        "seed1 = Path(args[0])\n"
        "seed2 = Path(args[1])\n"
        "if seed2.suffix == '.html':\n"
        "    assert forced, 'expected -f for HTML payload'\n"
        "    Path.cwd().joinpath('P(10-40)-PNG[BIN].deadbeef..png..html').write_bytes(seed1.read_bytes() + seed2.read_bytes())\n"
        "else:\n"
        "    Path.cwd().joinpath('poly-result.bin').write_bytes(seed1.read_bytes() + b'POLYGLOT' + seed2.read_bytes())\n",
        encoding="utf-8",
    )

    result = run_cli(
        "generate",
        "--out",
        str(out_dir),
        "--category",
        "polyglots",
        "--mitra-path",
        str(fake_mitra),
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8"))
    html_poly_entries = [
        entry
        for entry in manifest["entries"]
        if entry["category"] == "polyglots" and entry["generated_content_family"] == "png-html"
    ]
    assert html_poly_entries
    assert any(entry["relative_path"].endswith("P(10-40)-PNG[BIN].deadbeef..png..html") for entry in html_poly_entries)
    assert (out_dir / "polyglots" / "png-html" / "mitra-features.log").exists()


def test_polyglot_generation_builds_all_ordered_pairs_plus_html_payload(tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    mitra_dir = tmp_path / "mitra"
    mitra_dir.mkdir()
    fake_mitra = mitra_dir / "mitra.py"
    fake_mitra.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "forced = False\n"
        "if args and args[0] == '-f':\n"
        "    forced = True\n"
        "    args = args[1:]\n"
        "assert forced\n"
        "seed1 = Path(args[0])\n"
        "seed2 = Path(args[1])\n"
        "Path.cwd().joinpath('poly-result.bin').write_bytes(seed1.read_bytes() + seed2.read_bytes())\n",
        encoding="utf-8",
    )

    result = run_cli(
        "generate",
        "--out",
        str(out_dir),
        "--category",
        "polyglots",
        "--mitra-path",
        str(fake_mitra),
    )
    assert result.returncode == 0, result.stderr

    expected_dirs = {
        "pdf-jpg",
        "pdf-jpeg",
        "pdf-png",
        "pdf-tiff",
        "pdf-html",
        "jpg-pdf",
        "jpg-jpeg",
        "jpg-png",
        "jpg-tiff",
        "jpg-html",
        "jpeg-pdf",
        "jpeg-jpg",
        "jpeg-png",
        "jpeg-tiff",
        "jpeg-html",
        "png-pdf",
        "png-jpg",
        "png-jpeg",
        "png-tiff",
        "png-html",
        "tiff-pdf",
        "tiff-jpg",
        "tiff-jpeg",
        "tiff-png",
        "tiff-html",
    }
    actual_dirs = {path.name for path in (out_dir / "polyglots").iterdir() if path.is_dir() and path.name != "__pycache__"}
    assert expected_dirs.issubset(actual_dirs)


def test_polyglot_generation_cleans_empty_mitra_dirs_unless_debug(tmp_path: Path) -> None:
    mitra_dir = tmp_path / "mitra"
    mitra_dir.mkdir()
    fake_mitra = mitra_dir / "mitra.py"
    fake_mitra.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args and args[0] == '-f':\n"
        "    args = args[1:]\n"
        "# produce no output files on purpose\n",
        encoding="utf-8",
    )

    out_clean = tmp_path / "out-clean"
    result_clean = run_cli(
        "generate",
        "--out",
        str(out_clean),
        "--category",
        "polyglots",
        "--mitra-path",
        str(fake_mitra),
    )
    assert result_clean.returncode == 0, result_clean.stderr
    assert not (out_clean / "polyglots" / "pdf-jpg").exists()

    out_debug = tmp_path / "out-debug"
    result_debug = run_cli(
        "generate",
        "--out",
        str(out_debug),
        "--category",
        "polyglots",
        "--mitra-path",
        str(fake_mitra),
        "--debug",
    )
    assert result_debug.returncode == 0, result_debug.stderr
    debug_pair_dir = out_debug / "polyglots" / "pdf-jpg"
    assert debug_pair_dir.exists()
    assert (debug_pair_dir / "mitra.log").exists()
