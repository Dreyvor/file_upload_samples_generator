# Context and References

## Why this project exists

File upload features often validate only superficial attributes. In the target scenario, the application accepts a file when:

- the filename extension is one of `pdf`, `jpg`, `jpeg`, `png`, `tiff`; and
- the file's magic bytes match any one allowed type.

The weakness is that it does not enforce a mapping such as:

```text
.pdf  -> PDF bytes
.jpg  -> JPEG bytes
.jpeg -> JPEG bytes
.png  -> PNG bytes
.tiff -> TIFF bytes
```

This project generates a corpus that makes this inconsistency visible and reproducible.

## External references to study

### OWASP File Upload Cheat Sheet

Use OWASP as the defensive baseline. Important ideas:

- allow only business-required extensions;
- do not trust `Content-Type`;
- validate file signature;
- do not rely on file signature alone;
- generate server-side filenames;
- restrict filename length and characters;
- set size limits;
- store outside the webroot or serve through an indirection handler;
- run AV/sandbox/CDR where applicable;
- keep parser libraries up to date.

### PayloadsAllTheThings: Upload Insecure Files

Use this as a methodology checklist, especially:

- upload tricks;
- filename vulnerabilities;
- MIME/content-type manipulation;
- picture compression;
- picture metadata;
- ImageMagick/converter pipeline awareness.

Do **not** copy dangerous web-shell payloads into this project. Translate the methodology into safe samples that stay within allowed extensions.

Relevant source:
- `https://github.com/swisskyrepo/PayloadsAllTheThings/blob/master/Upload%20Insecure%20Files/README.md`

### Mitra by corkami

Use Mitra as an optional integration for weird files:

- polyglots;
- near-polyglots;
- parasite layouts;
- stack/appended-data layouts;
- cavity layouts;
- zipper layouts.

Relevant source:
- `https://github.com/corkami/mitra`

### Polydet polyglot database

Optional reference corpus for validating detectors and comparing generated output.

Relevant source:
- `https://github.com/Polydet/polyglot-database`

### Other optional reference projects

Search for current projects before implementing advanced features. Good search terms:

```text
file upload vulnerability scanner github
polyglot file generator github pdf png jpg
magic bytes bypass file upload github
upload security test corpus github
```

Treat external payload repositories as references, not as content to blindly vendor.

## Important design principle

Generate samples that answer this question:

> Which part of the application trusts which type signal?

Signals include:

- filename extension;
- multipart `Content-Type`;
- detected MIME;
- magic bytes;
- full parser validation;
- generated thumbnail;
- preview renderer;
- download headers;
- browser behavior.
