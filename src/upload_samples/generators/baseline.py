from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, expected_behavior_text, write_artifact


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    for extension in config.selected_extensions:
        plugin = registry.get_plugin(registry.family_for_extension(extension))
        sample = plugin.generate_valid(extension)
        relative_path = f"baseline/valid.{extension}"
        write_artifact(config, relative_path, sample.data)
        entries.append(
            build_entry(
                config=config,
                category="baseline",
                relative_path=relative_path,
                logical_extension=extension,
                generated_content_family=sample.content_family,
                expected_magic=sample.expected_magic,
                expected_mime=sample.mime,
                mismatch=False,
                risk_level="info",
                generator="baseline.generate",
                description=f"Valid baseline file for .{extension}.",
                expected_behavior=expected_behavior_text(False),
                data=sample.data,
            )
        )
    return entries
