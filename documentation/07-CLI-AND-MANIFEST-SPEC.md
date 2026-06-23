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

Initialize reporting during generation:

```bash
python -m upload_samples generate --out out --init-reporting
```

### Verify output

```bash
python -m upload_samples verify --out out
```

### Reporting

```bash
python -m upload_samples report-init --out out
python -m upload_samples report-init --out out --reset
python -m upload_samples report-ui --out out --host 127.0.0.1 --port 8765
python -m upload_samples report-status --out out
python -m upload_samples report-export --out out
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

Keep empty Mitra pair directories for debugging:

```bash
python -m upload_samples generate \
  --category polyglots \
  --mitra-path ../mitra/mitra.py \
  --out out \
  --debug
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
--debug
--skip-existing
--overwrite
--format json|csv|both
--init-reporting
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

## ID convention

Manifest ids are stable UUIDv5-style identifiers derived from category, relative path, logical extension, content family, and file content hash. They are not based on filenames alone.

```text
f4aa83ea-6f35-5826-b735-7f0870a78f2f
```

## Polyglot behavior notes

- host extension = each selected extension
- payload extension = each other selected extension plus `html`
- Mitra is always called with `-f`
- Mitra-generated filenames are preserved exactly
- empty pair directories containing only `mitra.log` are deleted unless `--debug` is set

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
