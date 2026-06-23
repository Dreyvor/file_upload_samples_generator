from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import html_active_content_sample, write_recipe


FILENAME_VALUES = [
    "normal.pdf",
    "normal.jpg",
    "file.pdf.",
    "file.pdf ",
    "file..pdf",
    "file%20.pdf",
    "file%0a.pdf",
    "file%0d%0a.pdf",
    "../../file.pdf",
    "..%2f..%2ffile.pdf",
    "%E2%80%AEfdp.jpg",
    '\'"?><img src=x onerror=alert(1)>.jpg',
    "$(sleep 5).png",
    ";sleep 5;.png",
    "CON.jpg",
    "AUX.png",
    "NUL.pdf",
    "very-long-" + ("a" * 240) + ".jpg",
]


def generate_filenames(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    content = [
        "# Filename tests",
        "",
        "Use these raw multipart filename values manually. Do not create them as local paths.",
        "",
        "Placeholders:",
        "- `{{UPLOAD_URL}}`",
        "- `{{FIELD_NAME}}`",
        "- `{{COOKIE_HEADER}}`",
        "- `{{CSRF_TOKEN}}`",
        "- `{{SAMPLE_FILE}}`",
        "",
        "## Candidate filename values",
        "",
    ]
    content.extend(f"- `{value}`" for value in FILENAME_VALUES)
    write_recipe(config, "multipart-recipes/filename-tests.md", "\n".join(content) + "\n")
    return []


def generate_multipart(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    lines = [
        "# Multipart Content-Type confusion",
        "",
        "## Raw multipart example",
        "",
        "```http",
        "Content-Disposition: form-data; name=\"{{FIELD_NAME}}\"; filename=\"sample.pdf\"",
        "Content-Type: image/jpeg",
        "```",
        "",
        "```http",
        "Content-Disposition: form-data; name=\"{{FIELD_NAME}}\"; filename=\"sample.jpg\"",
        "Content-Type: application/pdf",
        "```",
        "",
        "```http",
        "Content-Type: image/jpeg",
        "Content-Type: application/pdf",
        "```",
        "",
        "## Curl template",
        "",
        "```bash",
        "curl -i '{{UPLOAD_URL}}' \\",
        "  -H 'Cookie: {{COOKIE_HEADER}}' \\",
        "  -F '{{FIELD_NAME}}=@{{SAMPLE_FILE}};type=image/jpeg;filename=sample.pdf' \\",
        "  -F 'csrf={{CSRF_TOKEN}}'",
        "```",
    ]
    write_recipe(config, "multipart-recipes/content-type-confusion.md", "\n".join(lines) + "\n")
    write_recipe(config, "multipart-recipes/curl-examples.md", "\n".join(lines[-8:]) + "\n")
    write_recipe(
        config,
        "multipart-recipes/xss-iframe-sample.html",
        html_active_content_sample(),
    )
    return []
