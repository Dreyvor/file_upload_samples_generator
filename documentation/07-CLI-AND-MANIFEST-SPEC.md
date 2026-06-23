# CLI and Manifest Specification

## CLI

### Generate everything

```bash
python -m upload_samples generate --out out
```

### Generate selected categories

```bash
python -m upload_samples generate --category baseline --out out
python -m upload_samples generate --category mismatch --out out
python -m upload_samples generate --category metadata --out out
```

Multiple categories:

```bash
python -m upload_samples generate \
  --category baseline \
  --category mismatch \
  --category malformed \
  --out out
```

### Verify output

```bash
python -m upload_samples verify --out out
```

### List categories

```bash
python -m upload_samples list-categories
```

### Mitra integration

```bash
python -m upload_samples generate \
  --category polyglots \
  --mitra-path ../mitra/mitra.py \
  --out out
```

### Options

```text
--out PATH
--category NAME
--seed INT
--max-file-size-mb INT
--max-total-output-mb INT
--max-pixels INT
--mitra-path PATH
--skip-existing
--overwrite
--format json|csv|both
--verbose
```

## Categories

```text
baseline
mismatch
minimal-headers
malformed
metadata
filenames
multipart-recipes
stress-bounded
pdf-structures
polyglots
reference-import
```

## Manifest JSON schema

Top-level:

```json
{
  "schema_version": "1.0",
  "generated_at": "ISO-8601 timestamp",
  "tool_version": "0.1.0",
  "config": {},
  "entries": []
}
```

Entry:

```json
{
  "id": "string",
  "category": "string",
  "relative_path": "string",
  "filename": "string",
  "logical_extension": "string",
  "generated_content_family": "string",
  "expected_mime": "string",
  "expected_magic_hex": "string",
  "mismatch": true,
  "risk_level": "low",
  "generator": "string",
  "description": "string",
  "expected_behavior": "string",
  "sha256": "hex string",
  "size_bytes": 0,
  "created_at": "ISO-8601 timestamp",
  "provenance": {}
}
```

## Manifest CSV columns

```text
id
category
relative_path
filename
logical_extension
generated_content_family
expected_mime
expected_magic_hex
mismatch
risk_level
generator
description
expected_behavior
sha256
size_bytes
created_at
provenance_json
```

## ID naming convention

Use stable IDs:

```text
baseline-valid-pdf
mismatch-ext-pdf-content-jpg
minimal-header-png
metadata-pdf-title-xss-probe
filename-recipe-rtlo
polyglot-pdf-jpg-as-pdf
```

## MIME mapping

```python
MIME_BY_FAMILY = {
    "pdf": "application/pdf",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "png": "image/png",
    "tiff": "image/tiff",
}
```
