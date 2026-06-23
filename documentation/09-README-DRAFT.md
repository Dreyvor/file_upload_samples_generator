# README Draft for the Future Project

# File Upload Sample Generator

A local generator for benign file upload security test samples.

It creates a structured corpus for testing upload forms that accept files such as:

- PDF
- JPEG/JPG
- PNG
- TIFF

The project is especially useful when an application validates filename extension and magic bytes independently, but does not enforce that the two agree.

## Authorized use only

Use this tool only on systems you own or are explicitly authorized to test.

This project intentionally avoids web shells, malware, reverse shells, destructive decompression bombs, and public RCE exploit payloads.

## Quickstart

```bash
python -m pip install -e ".[dev]"
python -m upload_samples generate --out out
python -m upload_samples verify --out out
python -m upload_samples report-init --out out
python -m upload_samples report-ui --out out --host 127.0.0.1 --port 8765
```

## Generate selected categories

```bash
python -m upload_samples generate --category mismatch --out out
python -m upload_samples generate --category metadata --out out
python -m upload_samples generate --category stress-bounded --out out
```

## Output

```text
out/
  manifest.json
  manifest.csv
  baseline/
  mismatch/
  malformed/
  metadata/
  filenames/
  polyglots/
  stress-bounded/
  multipart-recipes/
  reporting/
```

## Reporting workflow

The project includes a local reporting workflow for pentesters:

- initialize reporting from the generated corpus
- fill results in a browser UI
- autosave progress to SQLite
- export a standalone HTML report and JSON/Markdown summaries

Commands:

```bash
python -m upload_samples generate --out out --init-reporting
python -m upload_samples report-init --out out
python -m upload_samples report-ui --out out --host 127.0.0.1 --port 8765
python -m upload_samples report-status --out out
python -m upload_samples report-export --out out
```

## Core categories

### Baseline

Valid minimal files.

### Mismatch

Files whose extension and actual content type intentionally differ.

Example:

```text
ext-pdf_content-jpg.pdf
```

This is a valid JPEG saved with a `.pdf` extension.

### Minimal headers

Files with only magic bytes/signatures.

These help identify superficial magic-byte validation.

### Metadata

Valid files with marker strings in metadata fields.

These help test metadata extraction, reflection, indexing, and escaping.

### Filename recipes

Markdown recipes for raw multipart filenames that should not be created as local files.

### Multipart recipes

Raw request examples with conflicting `Content-Type`, filename extension, and file bytes.

Also includes `multipart-recipes/xss-iframe-sample.html` for inline HTML rendering checks.

### Bounded stress

Safe resource-handling samples, such as large-dimension images and multipage TIFFs, within strict limits.

### Polyglots

Optional Mitra-generated polyglot samples from benign seeds.

## Mitra integration

Clone Mitra separately:

```bash
git clone https://github.com/corkami/mitra ../mitra
```

Then run:

```bash
python -m upload_samples generate \
  --category polyglots \
  --mitra-path ../mitra/mitra.py \
  --out out
```

Behavior:

- every selected host extension is paired against every other selected extension plus `html`
- Mitra is always called with `-f`, so file 2 is treated as a forced blob payload
- Mitra output filenames are preserved
- empty pair directories that contain only `mitra.log` are removed unless `--debug` is used

Debug mode:

```bash
python -m upload_samples generate \
  --category polyglots \
  --mitra-path ../mitra/mitra.py \
  --out out \
  --debug
```

## Interpreting results

A strict upload implementation should reject extension/content mismatches.

Weak behavior:

```text
The application accepts .pdf filename + JPEG bytes.
```

More serious behavior:

```text
The upload validator treats the file as PDF, but thumbnailing treats it as JPEG, while the download endpoint serves it as application/pdf.
```

That indicates parser/type confusion across the pipeline.
