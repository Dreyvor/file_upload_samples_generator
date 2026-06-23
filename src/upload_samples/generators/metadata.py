from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, write_artifact, write_recipe


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    for family_id in config.selected_families:
        plugin = registry.get_plugin(family_id)
        samples = plugin.generate_metadata_samples()
        if not samples:
            recipe_path = f"metadata/{family_id}-metadata-recipe.md"
            write_recipe(
                config,
                recipe_path,
                f"# {family_id} metadata recipe\n\nThis family has no native metadata generator in v1.\nUse a safe external workflow to add marker metadata if needed.\n",
            )
            continue
        for filename, data, description in samples:
            logical_extension = filename.rsplit(".", 1)[1]
            relative_path = f"metadata/{filename}"
            write_artifact(config, relative_path, data)
            entries.append(
                build_entry(
                    config=config,
                    category="metadata",
                    relative_path=relative_path,
                    logical_extension=logical_extension,
                    generated_content_family=family_id,
                    expected_magic=plugin.magic_prefixes[0],
                    expected_mime=plugin.mime_type,
                    mismatch=False,
                    risk_level="low",
                    generator="metadata.generate",
                    description=description,
                    expected_behavior="Metadata should be stored safely and escaped before any UI reflection.",
                    data=data,
                )
            )
    return entries
