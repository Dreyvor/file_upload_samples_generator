from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, write_artifact


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    for extension in config.selected_extensions:
        plugin = registry.get_plugin(registry.family_for_extension(extension))
        labels = [f"minimal-header-{extension}"]
        magics = [plugin.magic_prefixes[0]]
        if extension == "tiff" and len(plugin.magic_prefixes) > 1:
            labels = ["minimal-tiff-le", "minimal-tiff-be"]
            magics = list(plugin.magic_prefixes)
        for label, magic in zip(labels, magics):
            relative_path = f"malformed/{label}.{extension}"
            write_artifact(config, relative_path, magic)
            entries.append(
                build_entry(
                    config=config,
                    category="minimal-headers",
                    relative_path=relative_path,
                    logical_extension=extension,
                    generated_content_family=registry.family_for_extension(extension),
                    expected_magic=magic,
                    expected_mime=plugin.mime_type,
                    mismatch=False,
                    risk_level="low",
                    generator="minimal_headers.generate",
                    description=f"Header-only file for .{extension}.",
                    expected_behavior="Strict validators should reject the file because only the magic bytes are present.",
                    data=magic,
                )
            )
    return entries
