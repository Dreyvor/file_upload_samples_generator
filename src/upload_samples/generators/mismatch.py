from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, expected_behavior_text, write_artifact


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    for logical_extension in config.selected_extensions:
        ext_family = registry.family_for_extension(logical_extension)
        for content_label in config.selected_extensions:
            plugin = registry.plugin_for_content_label(content_label)
            sample = plugin.generate_valid(content_label)
            content_family = registry.canonical_family_for_label(content_label)
            mismatch = ext_family != content_family
            relative_path = f"mismatch/ext-{logical_extension}_content-{content_label}.{logical_extension}"
            write_artifact(config, relative_path, sample.data)
            entries.append(
                build_entry(
                    config=config,
                    category="mismatch",
                    relative_path=relative_path,
                    logical_extension=logical_extension,
                    generated_content_family=content_family,
                    expected_magic=sample.expected_magic,
                    expected_mime=sample.mime,
                    mismatch=mismatch,
                    risk_level="low",
                    generator="mismatch.generate",
                    description=f"Valid {content_label.upper()} bytes saved with .{logical_extension} extension.",
                    expected_behavior=expected_behavior_text(mismatch),
                    data=sample.data,
                )
            )
    return entries
