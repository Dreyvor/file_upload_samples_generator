# File Upload Sample Generator

Generate benign file-upload security test samples for authorized testing.

The tool builds a structured output corpus for upload pipelines that validate
filename extensions and file signatures independently, but may not enforce that
the two agree.

## Authorized use

Use this tool only on systems you own or are explicitly authorized to test.

The generated samples are intentionally bounded and benign. This project does
not generate web shells, malware, public RCE payloads, destructive compression
bombs, or phone-home content.

## Python version

The project supports Python 3.10.12 and newer.

## Installation

Install from the repository root:

```bash
python3 -m pip install -e .
```

Install with development dependencies:

```bash
python3 -m pip install -e ".[dev]"
```

Verify the CLI is available:

```bash
python3 -m upload_samples list-families
python3 -m upload_samples list-categories
```

## Quickstart

```bash
python -m upload_samples generate --out out
python -m upload_samples verify --out out
python -m upload_samples list-families
```

Generate samples and initialize the reporting workspace in one step:

```bash
python -m upload_samples generate --out out --init-reporting
```

## Core categories

- `baseline`: valid small files for each logical extension
- `mismatch`: extension/content mismatch matrix
- `minimal-headers`: header-only magic-byte samples
- `malformed`: truncated and bounded malformed files
- `metadata`: valid files and recipes with marker metadata
- `filenames`: multipart filename recipe markdown
- `multipart-recipes`: multipart `Content-Type` confusion recipes
- `stress-bounded`: safe resource-handling samples
- `pdf-structures`: benign PDF structure indicators
- `polyglots`: optional Mitra-driven generation

## Extensibility model

Built-in file families are registered through a plugin registry. New families
can be added later by implementing a plugin and registering it through the
`upload_samples.file_families` Python entry-point group.

Each family plugin declares:

- canonical family id
- logical extensions it supports
- magic prefixes
- MIME type
- generation capabilities it implements

Category generators operate against plugin capabilities rather than hardcoded
extension lists.

## Selected commands

```bash
python -m upload_samples generate --out out --category mismatch
python -m upload_samples generate --out out --family pdf --family png
python -m upload_samples generate --out out --extension jpg --extension jpeg
python -m upload_samples verify --out out
python -m upload_samples report-init --out out
python -m upload_samples report-ui --out out --host 127.0.0.1 --port 8765
python -m upload_samples report-status --out out
python -m upload_samples report-export --out out
python -m upload_samples list-categories
python -m upload_samples list-families
```

## Reporting workflow

The tool includes a local-first reporting workflow for pentesters. It lets you
record sample-by-sample results in a browser UI, autosaves progress to SQLite,
and exports a standalone final report when testing is complete.

Initialize reporting from an existing generated corpus:

```bash
python -m upload_samples report-init --out out
```

Or initialize it during generation:

```bash
python -m upload_samples generate --out out --init-reporting
```

Start the local reporting UI:

```bash
python -m upload_samples report-ui --out out --host 127.0.0.1 --port 8765
```

Then open `http://127.0.0.1:8765` in your browser.

Inside the UI you can:

- track each generated sample by manifest id and filename
- record accept/reject/error/needs-review outcomes
- add validation messages, notes, evidence paths, and findings
- filter by category, family, extension, status, or findings
- resume incomplete work after a crash or reboot

Check current testing progress from the terminal:

```bash
python -m upload_samples report-status --out out
```

Export the final deliverables:

```bash
python -m upload_samples report-export --out out
```

This creates:

- `out/reporting/session.sqlite3`
- `out/reporting/ui/`
- `out/reporting/final-report.html`
- `out/reporting/report-summary.json`
- `out/reporting/report-summary.md`

## Output

```text
out/
  manifest.json
  manifest.csv
  baseline/
  mismatch/
  malformed/
  metadata/
  multipart-recipes/
  stress-bounded/
  pdf-structures/
  polyglots/
  reporting/
    session.sqlite3
    ui/
    final-report.html
    report-summary.json
    report-summary.md
```
