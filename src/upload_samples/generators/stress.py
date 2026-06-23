from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, write_artifact


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    for family_id in config.selected_families:
        plugin = registry.get_plugin(family_id)
        for filename, data, description in plugin.generate_stress_samples(config.max_pixels, config.max_tiff_pages):
            logical_extension = filename.rsplit(".", 1)[1]
            relative_path = f"stress-bounded/{filename}"
            write_artifact(config, relative_path, data)
            entries.append(
                build_entry(
                    config=config,
                    category="stress-bounded",
                    relative_path=relative_path,
                    logical_extension=logical_extension,
                    generated_content_family=family_id,
                    expected_magic=plugin.magic_prefixes[0],
                    expected_mime=plugin.mime_type,
                    mismatch=False,
                    risk_level="medium",
                    generator="stress.generate",
                    description=description,
                    expected_behavior="The application should enforce bounded resource handling without crashing or exhausting memory.",
                    data=data,
                )
            )
    return entries
