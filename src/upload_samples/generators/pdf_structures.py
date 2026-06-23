from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, write_artifact


def generate(config: GeneratorConfig, registry: FamilyRegistry) -> list:
    entries = []
    if "pdf" not in config.selected_families:
        return entries
    plugin = registry.get_plugin("pdf")
    for filename, data, description in plugin.generate_structure_samples():
        relative_path = f"pdf-structures/{filename}"
        write_artifact(config, relative_path, data)
        entries.append(
            build_entry(
                config=config,
                category="pdf-structures",
                relative_path=relative_path,
                logical_extension="pdf",
                generated_content_family="pdf",
                expected_magic=plugin.magic_prefixes[0],
                expected_mime=plugin.mime_type,
                mismatch=False,
                risk_level="info",
                generator="pdf_structures.generate",
                description=description,
                expected_behavior="The application should treat these PDFs as benign documents and avoid unsafe active-content assumptions.",
                data=data,
            )
        )
    return entries
