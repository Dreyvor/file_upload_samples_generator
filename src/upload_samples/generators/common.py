from __future__ import annotations

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from ..models import GeneratorConfig, ManifestEntry
from ..registry import FamilyRegistry
from ..utils import ensure_within, sha256_bytes, utc_now, write_bytes, write_text


def html_active_content_sample() -> str:
    return "\n".join(
        [
            "<!DOCTYPE html>",
            '<html lang="en">',
            "<head>",
            '  <meta charset="utf-8">',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">',
            "  <title>XSS and IFrame Sample</title>",
            "</head>",
            "<body>",
            "  <h1>Upload Sample HTML Test</h1>",
            "  <script>",
            "    alert('XSS sample triggered');",
            "  </script>",
            '  <iframe src="about:blank" title="Sample iframe" width="420" height="240"></iframe>',
            "</body>",
            "</html>",
            "",
        ]
    )


def build_entry(
    *,
    config: GeneratorConfig,
    category: str,
    relative_path: str,
    logical_extension: str,
    generated_content_family: str,
    expected_magic: bytes,
    expected_mime: str,
    mismatch: bool,
    risk_level: str,
    generator: str,
    description: str,
    expected_behavior: str,
    data: bytes,
    provenance: dict[str, object] | None = None,
) -> ManifestEntry:
    filename = Path(relative_path).name
    entry_id = str(
        uuid5(
            NAMESPACE_URL,
            f"upload-samples:{category}:{relative_path}:{logical_extension}:{generated_content_family}:{sha256_bytes(data)}",
        )
    )
    return ManifestEntry(
        id=entry_id,
        category=category,
        relative_path=relative_path,
        filename=filename,
        logical_extension=logical_extension,
        generated_content_family=generated_content_family,
        expected_mime=expected_mime,
        expected_magic_hex=expected_magic.hex(),
        mismatch=mismatch,
        risk_level=risk_level,
        generator=generator,
        description=description,
        expected_behavior=expected_behavior,
        sha256=sha256_bytes(data),
        size_bytes=len(data),
        created_at=utc_now(),
        provenance=provenance or {"source": "generated"},
    )


def write_artifact(config: GeneratorConfig, relative_path: str, data: bytes) -> None:
    target = ensure_within(config.out_dir, config.out_dir / relative_path)
    write_bytes(target, data, overwrite=config.overwrite, skip_existing=config.skip_existing)


def write_recipe(config: GeneratorConfig, relative_path: str, text: str) -> None:
    target = ensure_within(config.out_dir, config.out_dir / relative_path)
    write_text(target, text, overwrite=config.overwrite, skip_existing=config.skip_existing)


def expected_behavior_text(mismatch: bool) -> str:
    if mismatch:
        return "Strict validators should reject the file because extension and detected content do not correspond."
    return "Strict validators should accept the file if parser validation succeeds and size limits allow it."


def selected_baseline_sample(registry: FamilyRegistry, logical_extension: str):
    plugin = registry.get_plugin(registry.family_for_extension(logical_extension))
    return plugin.generate_valid(logical_extension)
