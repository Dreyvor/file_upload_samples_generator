# Architecture

## Package layout

```text
upload-sample-generator/
  README.md
  pyproject.toml
  src/
    upload_samples/
      __init__.py
      cli.py
      config.py
      manifest.py
      signatures.py
      generators/
        __init__.py
        baseline.py
        mismatch.py
        malformed.py
        metadata.py
        filenames.py
        multipart.py
        stress.py
        pdf_structures.py
        polyglot_mitra.py
        import_reference.py
      utils/
        __init__.py
        files.py
        hashing.py
        detect.py
        safe_names.py
  tests/
    test_manifest.py
    test_signatures.py
    test_generation.py
  docs/
    TESTING-METHODOLOGY.md
    SAMPLE-CATALOG.md
```

## Core abstractions

### SampleSpec

```python
@dataclass
class SampleSpec:
    category: str
    path: Path
    logical_extension: str
    generated_content_family: str
    expected_magic: str
    mismatch: bool
    risk_level: str
    generator: str
    description: str
    expected_behavior: str
    notes: str = ""
```

### ManifestEntry

```python
@dataclass
class ManifestEntry:
    id: str
    category: str
    relative_path: str
    filename: str
    logical_extension: str
    generated_content_family: str
    expected_mime: str
    expected_magic_hex: str
    mismatch: bool
    risk_level: str
    generator: str
    description: str
    expected_behavior: str
    sha256: str
    size_bytes: int
    created_at: str
    provenance: dict
```

## Signature model

Implement internal magic-byte detection:

```python
SIGNATURES = {
    "pdf": [bytes.fromhex("25504446")],
    "jpg": [bytes.fromhex("FFD8FF")],
    "jpeg": [bytes.fromhex("FFD8FF")],
    "png": [bytes.fromhex("89504E470D0A1A0A")],
    "tiff": [
        bytes.fromhex("49492A00"),
        bytes.fromhex("4D4D002A"),
    ],
}
```

For JPEG/JPG:

```python
CONTENT_FAMILY_ALIASES = {
    "jpeg": "jpg",
    "jpg": "jpg",
}
```

## Generator principles

Each generator should:

1. write files only under the output directory;
2. avoid using untrusted filenames as local filesystem paths;
3. return manifest entries;
4. be deterministic where possible;
5. support `--seed`;
6. keep file sizes bounded by default;
7. not require external tools unless the category explicitly depends on them.

## Verification

`verify` should:

- read `manifest.json`;
- confirm every file exists;
- recompute SHA-256;
- confirm size;
- check expected magic prefix;
- confirm mismatch flag correctness;
- optionally run `file`/`python-magic` if available.

## Manifest examples

```json
{
  "id": "mismatch-ext-pdf-content-jpg",
  "category": "mismatch",
  "relative_path": "mismatch/ext-pdf_content-jpg.pdf",
  "filename": "ext-pdf_content-jpg.pdf",
  "logical_extension": "pdf",
  "generated_content_family": "jpg",
  "expected_mime": "image/jpeg",
  "expected_magic_hex": "ffd8ff",
  "mismatch": true,
  "risk_level": "low",
  "generator": "mismatch.generate_matrix",
  "description": "Valid JPEG bytes saved with .pdf extension.",
  "expected_behavior": "Strict validators should reject extension/content mismatch; weak independent allowlist validators may accept.",
  "sha256": "...",
  "size_bytes": 1234,
  "created_at": "2026-06-23T00:00:00Z",
  "provenance": {
    "source": "generated"
  }
}
```
