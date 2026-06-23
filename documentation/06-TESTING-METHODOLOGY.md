# Testing Methodology

## Purpose

Use the generated corpus to map how a web application handles file type signals across the full upload lifecycle.

## Signals to record

For every sample, record:

- upload accepted or rejected;
- server-side validation message;
- stored filename;
- stored extension;
- displayed type;
- detected MIME/type in UI;
- preview generated or not;
- OCR/text extracted or not;
- metadata displayed or not;
- AV/CDR status if visible;
- download headers;
- browser rendering behavior;
- error messages;
- processing time;
- file size after storage;
- whether the original bytes are preserved.

## Download headers to capture

```http
Content-Type
Content-Disposition
X-Content-Type-Options
Cache-Control
Content-Security-Policy
```

## Secure expected behavior

For a strict upload pipeline:

- extension and content type must correspond;
- invalid minimal-header samples must be rejected;
- user-supplied `Content-Type` must not be trusted;
- dangerous filenames must be normalized or replaced;
- metadata must be sanitized or escaped before display;
- files should be served with safe headers;
- previews should be generated in hardened isolated workers.

## Interesting weak behaviors

### Independent allowlist validation

Example:

```text
.pdf extension is allowed
JPEG magic bytes are allowed
=> accepted as .pdf
```

Expected finding:

```text
Insufficient file type consistency validation.
```

### Parser confusion

Example:

```text
Validator labels file as PDF.
Thumbnailer successfully parses it as JPEG.
Download endpoint serves it as application/pdf.
```

Expected finding:

```text
Inconsistent type interpretation across upload pipeline.
```

### Metadata reflection

Example:

```text
PDF title or PNG text chunk appears unescaped in admin UI.
```

Expected finding:

```text
Stored XSS via uploaded-file metadata.
```

### Header confusion

Example:

```text
Multipart Content-Type says image/jpeg, extension says .pdf, magic bytes say PDF.
Different layers choose different types.
```

Expected finding:

```text
Content-Type trust boundary confusion.
```

### Filename handling flaw

Example:

```text
Filename is reflected unescaped, path-normalized incorrectly, logged unsafely, or used in shell commands.
```

Expected finding:

```text
Unsafe uploaded filename handling.
```

## Recommended test order

1. Upload baseline valid files.
2. Upload mismatch matrix.
3. Upload minimal magic-byte files.
4. Upload malformed bounded samples.
5. Upload metadata samples.
6. Test filename recipes manually via Burp/curl.
7. Test multipart Content-Type recipes.
8. Test bounded stress samples.
9. Test Mitra-generated polyglots.
10. Compare results against manifest expectations.

## Evidence to keep

For each interesting sample:

- original sample file;
- manifest entry;
- upload request;
- upload response;
- UI screenshot;
- download request/response;
- server-side error if available;
- preview/OCR evidence;
- timestamps;
- hash of uploaded and downloaded file.

## Finding template

```text
Title:
Insufficient file type consistency validation in upload pipeline

Observation:
The application accepts files where the filename extension and detected file content do not correspond.

Example:
A file named `ext-pdf_content-jpg.pdf` containing valid JPEG bytes was accepted.

Impact:
This can cause downstream components to process the same uploaded object as different file types. Depending on the pipeline, this may bypass content-specific controls, AV/CDR routing, preview isolation, metadata sanitization, or parser hardening.

Expected behavior:
The application should enforce a strict mapping between extension, detected MIME/signature, and successful parser validation for the declared type.

Recommendation:
Reject extension/content mismatches, generate server-side filenames, serve files with safe headers, and perform parser validation in isolated workers.
```
