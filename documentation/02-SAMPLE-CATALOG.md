# Sample Catalog

This document defines the required sample classes.

## Allowed extensions

```python
ALLOWED_EXTENSIONS = ["pdf", "jpg", "jpeg", "png", "tiff"]
```

## Logical file types

```python
CONTENT_TYPES = ["pdf", "jpg", "jpeg", "png", "tiff"]
```

Treat `jpg` and `jpeg` as the same JPEG content family but generate both filename extensions.

## Category A: Baseline valid samples

Generate valid minimal files:

```text
baseline/valid.pdf
baseline/valid.jpg
baseline/valid.jpeg
baseline/valid.png
baseline/valid.tiff
```

Purpose:

- establish what the application accepts under normal conditions;
- establish expected preview/OCR/metadata behavior;
- establish baseline headers on download.

## Category B: Extension/content mismatch matrix

Generate every allowed extension with every allowed content type.

Example:

```text
mismatch/ext-pdf_content-jpg.pdf
mismatch/ext-pdf_content-png.pdf
mismatch/ext-jpg_content-pdf.jpg
mismatch/ext-tiff_content-pdf.tiff
```

Required matrix:

| Extension | Content families |
|---|---|
| `.pdf` | pdf, jpg, jpeg, png, tiff |
| `.jpg` | pdf, jpg, jpeg, png, tiff |
| `.jpeg` | pdf, jpg, jpeg, png, tiff |
| `.png` | pdf, jpg, jpeg, png, tiff |
| `.tiff` | pdf, jpg, jpeg, png, tiff |

Mark rows where extension and content family mismatch.

Special case:

- `.jpg` and `.jpeg` with JPEG content are not mismatches.
- `.jpg` with `.jpeg` content and `.jpeg` with `.jpg` content should be treated as equivalent JPEG content.
- also generate manual HTML-content helpers saved under allowed extensions, for example `mismatch/manual-html-content-as-jpg.jpg`, to test MIME sniffing and unsafe preview behavior outside the manifest-backed binary matrix.

## Category C: Minimal magic-byte files

Generate files that contain only enough bytes to trigger superficial signature checks.

Examples:

```text
malformed/minimal-pdf-header.pdf
malformed/minimal-jpeg-header.jpg
malformed/minimal-png-signature.png
malformed/minimal-tiff-le.tiff
malformed/minimal-tiff-be.tiff
```

Suggested bytes:

```text
PDF:  25 50 44 46 2D 31 2E 33 0A      # %PDF-1.3\n
JPEG: FF D8 FF
PNG:  89 50 4E 47 0D 0A 1A 0A
TIFF little endian: 49 49 2A 00
TIFF big endian:    4D 4D 00 2A
```

Purpose:

- detect header-only validation;
- trigger safe parser failures downstream;
- distinguish magic-byte checking from real decoding.

## Category D: Truncated and malformed but bounded files

Generate samples such as:

```text
malformed/truncated-valid.pdf
malformed/truncated-valid.jpg
malformed/truncated-valid.png
malformed/truncated-valid.tiff
malformed/random-tail-after-valid-header.pdf
malformed/random-tail-after-valid-header.jpg
```

Rules:

- keep files small;
- do not attempt public RCE CVE payloads;
- do not include exploit strings copied from advisories;
- ensure failures are safe and controlled.

## Category E: Metadata reflection probes

Generate valid files with metadata fields containing unique markers and benign reflection probes.

Examples:

```text
metadata/jpg-comment-marker.jpg
metadata/png-text-marker.png
metadata/tiff-description-marker.tiff
metadata/pdf-title-marker.pdf
```

Required markers:

```text
UPLOAD_SAMPLE_MARKER_001
UPLOAD_SAMPLE_MARKER_002
```

Benign HTML reflection probe:

```html
"><img src=x onerror=alert(1337)>
```

Use this only as a passive XSS-detection string. Do not include external callbacks.

Potential metadata fields:

- PDF title
- PDF author
- PDF subject
- PDF keywords
- JPEG EXIF comment/user comment
- PNG tEXt/iTXt chunks
- TIFF ImageDescription/Artist

## Category F: Filename/path handling samples

Generate a file content once per filename test, preferably a small valid PNG or JPEG, and write it under safe normalized local filenames. Also generate a separate `multipart-recipes/filename-tests.md` with raw multipart filename values to use in Burp or curl.

Do not create dangerous filesystem paths locally. Instead, represent risky filenames in request recipes.

Filename values to include in recipes:

```text
normal.pdf
normal.jpg
file.pdf.
file.pdf 
file..pdf
file%20.pdf
file%0a.pdf
file%0d%0a.pdf
../../file.pdf
..%2f..%2ffile.pdf
%E2%80%AEfdp.jpg
'"><img src=x onerror=alert(1)>.jpg
$(sleep 5).png
;sleep 5;.png
CON.jpg
AUX.png
NUL.pdf
very-long-<240 chars>.jpg
```

Purpose:

- filename normalization issues;
- reflected/stored XSS in filename;
- logging/admin panel issues;
- path traversal;
- shell command injection indicators;
- Windows reserved name handling.

## Category G: Multipart Content-Type recipes

Create recipe files, not binary samples.

For each baseline file, provide multipart examples with conflicting headers:

```http
Content-Disposition: form-data; name="file"; filename="sample.pdf"
Content-Type: image/jpeg
```

```http
Content-Disposition: form-data; name="file"; filename="sample.jpg"
Content-Type: application/pdf
```

Duplicate header recipe:

```http
Content-Type: image/jpeg
Content-Type: application/pdf
```

Purpose:

- determine whether server trusts multipart header;
- find discrepancies between WAF/backend/application;
- test parser routing.

Also generate a small HTML helper file:

```text
multipart-recipes/xss-iframe-sample.html
```

Contents:

- one visible `<h1>` marker;
- one simple `alert(...)` JavaScript marker;
- one inert `<iframe>`;
- no external callbacks or remote dependencies.

Purpose:

- test unsafe inline serving;
- test browser preview rendering;
- test HTML sanitization assumptions in upload/view flows.

## Category H: Bounded stress samples

Generate only safe bounded stress cases:

```text
stress-bounded/large-dim-small-png.png
stress-bounded/large-dim-small-jpg.jpg
stress-bounded/multipage-small-tiff.tiff
stress-bounded/many-metadata-fields.pdf
```

Rules:

- default max output size: 10 MB;
- default max pixel count: configurable, e.g. 25 MP;
- no decompression bombs by default;
- require `--unsafe-dos` for anything beyond bounded limits, but do not implement this in v1.

Purpose:

- test resource limits safely;
- detect preview/converter memory issues;
- verify size and dimension controls.

## Category I: PDF active-content indicators

Generate benign PDFs that contain recognizable PDF structures but do not execute harmful actions.

Examples:

```text
pdf-structure/pdf-with-form-field.pdf
pdf-structure/pdf-with-metadata.pdf
pdf-structure/pdf-with-embedded-text-marker.pdf
```

Avoid JavaScript actions in v1 unless explicitly enabled as a safe marker-only test.

Purpose:

- test PDF parser routing;
- test metadata extraction;
- test OCR/text indexing;
- test viewer behavior.

## Category J: Polyglot candidates

Integrate optionally with Mitra.

Input seeds are built automatically from the currently selected extensions, plus one HTML seed:

```text
polyglots/manual-html-seed.html
```

Generate ordered host/payload combinations:

```text
polyglots/pdf-jpg/
polyglots/pdf-jpeg/
polyglots/pdf-png/
polyglots/pdf-tiff/
polyglots/pdf-html/
polyglots/jpg-pdf/
polyglots/jpg-html/
polyglots/png-html/
polyglots/tiff-png/
```

Rules:

- host = every selected extension;
- payload = every other selected extension plus `html`;
- skip same-extension pairs;
- always call Mitra with `-f`, so file 2 is treated as a forced blob payload;
- preserve Mitra-generated output filenames exactly;
- store `mitra.log` in each pair directory;
- store `mitra-features.log` when at least one sample is produced;
- delete pair directories that contain only `mitra.log`, unless `--debug` is used.

Notes:

- Mitra has no dedicated HTML parser in its main parser set, so HTML is provided through the forced-blob path.
- The generated samples are still useful because downstream validators, previewers, and browsers may disagree on type handling even when Mitra treats file 2 generically.

Purpose:

- test parser confusion;
- test detector disagreement;
- test AV/CDR routing;
- test downstream component assumptions.
