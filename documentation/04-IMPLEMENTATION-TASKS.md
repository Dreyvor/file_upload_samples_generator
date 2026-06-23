# Implementation Tasks for Codex

## Milestone 1: Project skeleton

Create:

```text
pyproject.toml
README.md
src/upload_samples/
tests/
```

Dependencies:

```toml
[project]
requires-python = ">=3.11"
dependencies = [
  "Pillow>=10",
  "pypdf>=4",
  "reportlab>=4"
]
```

Optional dependencies:

```toml
[project.optional-dependencies]
magic = ["python-magic"]
dev = ["pytest", "ruff"]
```

## Milestone 2: Baseline file generation

Implement:

```python
generate_pdf(path: Path, text: str) -> None
generate_jpeg(path: Path, text: str | None = None) -> None
generate_png(path: Path, text: str | None = None) -> None
generate_tiff(path: Path, text: str | None = None) -> None
```

Requirements:

- valid minimal content;
- deterministic dimensions and metadata;
- small files.

## Milestone 3: Mismatch matrix

Implement:

```python
generate_mismatch_matrix(out: Path) -> list[ManifestEntry]
```

Approach:

1. generate canonical valid content bytes for each content family;
2. write the same bytes using each allowed extension;
3. register each file in the manifest.

## Milestone 4: Minimal magic-byte samples

Implement:

```python
generate_minimal_headers(out: Path) -> list[ManifestEntry]
```

Use static byte strings only.

## Milestone 5: Malformed bounded samples

Implement:

```python
generate_truncated_samples(out: Path) -> list[ManifestEntry]
generate_random_tail_samples(out: Path, seed: int) -> list[ManifestEntry]
```

Rules:

- all random tails deterministic from seed;
- max 4 KiB unless configured;
- no exploit payloads.

## Milestone 6: Metadata samples

Implement valid files with markers:

```python
MARKERS = [
  "UPLOAD_SAMPLE_MARKER_001",
  "\"><img src=x onerror=alert(1337)>"
]
```

For PNG, use Pillow `PngInfo`.

For JPEG/TIFF, use Pillow metadata if practical. If EXIF support is incomplete, create a recipe file explaining how to add EXIF with exiftool, but do not make exiftool mandatory.

For PDF, use `pypdf` metadata APIs or ReportLab + pypdf post-processing.

## Milestone 7: Filename and multipart recipes

Generate Markdown recipe files:

```text
multipart-recipes/filename-tests.md
multipart-recipes/content-type-confusion.md
multipart-recipes/curl-examples.md
```

Include placeholders:

```text
{{UPLOAD_URL}}
{{FIELD_NAME}}
{{COOKIE_HEADER}}
{{CSRF_TOKEN}}
{{SAMPLE_FILE}}
```

Do not hardcode target URLs.

## Milestone 8: Bounded stress samples

Implement:

```python
generate_large_dimension_png(out: Path, max_pixels: int) -> ManifestEntry
generate_large_dimension_jpeg(out: Path, max_pixels: int) -> ManifestEntry
generate_multipage_tiff(out: Path, pages: int) -> ManifestEntry
```

Defaults:

```text
max_pixels = 25_000_000
max_size_mb = 10
tiff_pages = 5
```

Never exceed defaults unless user explicitly passes CLI flags.

## Milestone 9: Mitra integration

Implement optional wrapper:

```python
run_mitra(
    mitra_path: Path,
    seed_a: Path,
    seed_b: Path,
    out_dir: Path,
    timeout_seconds: int = 30,
) -> list[Path]
```

Requirements:

- disabled unless user provides `--mitra-path`;
- run with timeout;
- capture stdout/stderr;
- store command provenance in manifest;
- do not fail entire generation if Mitra cannot produce a specific pair;
- copy generated result under multiple allowed extensions for testing.

Seed pairs:

```text
pdf + jpg
pdf + png
pdf + tiff
jpg + pdf
png + pdf
tiff + pdf
```

## Milestone 10: Verification and tests

Implement tests for:

- manifest schema;
- SHA-256 correctness;
- file existence;
- magic bytes;
- mismatch matrix count;
- no generated path escapes output directory;
- local filenames are safe;
- recipe files contain risky filenames only as text, not real paths.

Expected mismatch matrix count:

```python
5 extensions * 5 content families = 25 files
```

Where jpg/jpeg are equivalent for mismatch calculation.

## Milestone 11: Documentation

README must include:

- authorized-use warning;
- quickstart;
- categories;
- example generation commands;
- how to interpret results;
- how to use with Burp/curl;
- how to integrate Mitra;
- how to add new generators.

## Milestone 12: CI

Optional GitHub Actions:

```yaml
python -m pip install -e ".[dev]"
pytest
python -m upload_samples generate --out /tmp/upload-samples
python -m upload_samples verify --out /tmp/upload-samples
```
