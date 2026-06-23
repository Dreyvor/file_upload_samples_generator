from __future__ import annotations

from ..models import GeneratorConfig
from ..registry import FamilyRegistry
from .common import build_entry, expected_behavior_text, html_active_content_sample, write_artifact, write_recipe


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
    html_sample = html_active_content_sample().encode("utf-8")
    for logical_extension in config.selected_extensions:
        write_artifact(
            config,
            f"mismatch/manual-html-content-as-{logical_extension}.{logical_extension}",
            html_sample,
        )
    write_recipe(
        config,
        "mismatch/html-content-notes.md",
        "\n".join(
            [
                "# HTML content mismatch helpers",
                "",
                "These helper files contain active HTML content saved with the selected non-HTML extensions.",
                "They are intentionally kept out of `manifest.json` because HTML is not yet a first-class registered family in this tool.",
                "",
                "Use them to check whether the target:",
                "- trusts the filename extension only",
                "- sniffs content and serves it as `text/html`",
                "- reflects or previews the uploaded file unsafely",
                "- allows download/open flows that execute active browser content",
                "",
                "Generated helper filenames follow `manual-html-content-as-<extension>.<extension>`.",
            ]
        )
        + "\n",
    )
    return entries
