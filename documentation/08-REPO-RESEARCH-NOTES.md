# Repository Research Notes

## PayloadsAllTheThings

Repository:

```text
https://github.com/swisskyrepo/PayloadsAllTheThings
```

Relevant path:

```text
Upload Insecure Files/README.md
```

Useful concepts for this project:

- upload test methodology;
- extension tricks;
- filename vulnerabilities;
- MIME/content-type manipulation;
- picture compression;
- picture metadata;
- ImageMagick/converter considerations.

Important adaptation:

The original repository contains many payloads for executable server-side extensions. This project should **not** include web shells or executable payloads. Instead, it should adapt the methodology to the allowed file types only: PDF, JPEG, PNG, TIFF.

## Mitra

Repository:

```text
https://github.com/corkami/mitra
```

Useful concepts:

- polyglots;
- near-polyglots;
- stack layouts;
- parasite layouts;
- cavity layouts;
- zipper layouts;
- command-line generation from two seed files.

Implementation approach:

- do not vendor Mitra by default;
- accept `--mitra-path`;
- run in a timeout-limited subprocess;
- record command and generated outputs in manifest provenance.

## Polydet polyglot database

Repository:

```text
https://github.com/Polydet/polyglot-database
```

Useful concepts:

- reference corpus of files readable as multiple formats;
- includes relevant families such as PDF, JPG, PNG, TIFF among many others.

Implementation approach:

- optional local import only;
- do not redistribute files;
- filter by relevant extension/content families;
- record provenance.

## OWASP File Upload Cheat Sheet

URL:

```text
https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html
```

Use as defensive expectation baseline.

Key expectations to encode in generated-sample descriptions:

- extension allowlist;
- content-type cannot be trusted;
- signature validation is insufficient alone;
- server-generated filenames;
- file size limits;
- secure storage;
- AV/sandbox/CDR;
- hardened and updated parser libraries.
