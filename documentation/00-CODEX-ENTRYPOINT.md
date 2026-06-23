# Codex Entrypoint: File Upload Sample Generator

## Goal

Build a local project that generates **benign but security-relevant file upload test samples** for authorized web application testing.

The primary target scenario is a web upload form that claims to accept only:

- `pdf`
- `jpg`
- `jpeg`
- `png`
- `tiff`

The observed behavior is that validation is currently implemented as two independent checks:

1. filename extension is in the allowlist;
2. magic bytes/signature belong to one of the allowed file types.

The application does **not** enforce consistency between the extension and detected content. For example, a file named `sample.pdf` containing JPEG bytes is accepted.

The project should generate extensive test files to help pentesters determine whether different downstream components disagree about file type, including:

- upload validator
- storage layer
- antivirus/sandbox/CDR
- thumbnailer
- image converter
- PDF renderer
- OCR service
- metadata extractor
- indexing/search pipeline
- browser download/viewer endpoint

## Safety boundary

This project must focus on **benign test samples** and **parser-confusion validation**.

Do not include:

- web shells;
- reverse shells;
- credential stealers;
- malware;
- destructive decompression bombs;
- public exploit payloads intended to trigger RCE;
- payloads that cause uncontrolled denial of service.

It may include:

- minimal valid files;
- intentionally malformed files with valid headers;
- extension/content mismatch samples;
- metadata reflection probes;
- bounded stress files;
- PDF/image polyglot experiments;
- safe SSRF-marker references only if disabled by default and clearly labeled.

## Primary deliverable

Create a CLI tool that outputs a structured corpus:

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
```

Every generated sample must have a manifest entry describing:

- file path
- logical extension
- actual generated content type
- expected magic bytes
- whether extension/content intentionally mismatch
- generation method
- intended test category
- risk level
- expected application behavior
- notes for tester
- sha256
- size_bytes

## Suggested tech stack

Prefer Python 3.11+.

Recommended libraries:

- `Pillow` for JPG/PNG/TIFF generation
- `pypdf` or `reportlab` for PDF generation
- `exiftool` integration optional, not required
- `python-magic` optional for local detection, with fallback to internal signature checks
- `argparse` or `typer` for CLI
- `pytest` for generator tests

Keep the first implementation dependency-light. It should work without system packages where possible.

## Commands to implement

```bash
python -m upload_samples generate --out out
python -m upload_samples generate --category mismatch --out out
python -m upload_samples manifest --out out
python -m upload_samples verify --out out
python -m upload_samples list-categories
```

Optional:

```bash
python -m upload_samples mitra --mitra-path ../mitra/mitra.py --out out/polyglots
python -m upload_samples import-polydet --src ../polyglot-database/files --out out/reference-polyglots
```

Reporting workflow:

```bash
python -m upload_samples generate --out out --init-reporting
python -m upload_samples report-init --out out
python -m upload_samples report-ui --out out --host 127.0.0.1 --port 8765
python -m upload_samples report-status --out out
python -m upload_samples report-export --out out
```

## Work order for Codex

1. Read all Markdown files in this folder.
2. Create a Python package skeleton.
3. Implement core sample builders.
4. Implement manifest writing and verification.
5. Implement safe baseline/mismatch/malformed/metadata generators.
6. Add optional Mitra integration.
7. Add test suite.
8. Add README with usage examples.
