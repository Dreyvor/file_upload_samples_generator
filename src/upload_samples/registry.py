from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata

from .plugins import builtins as builtin_plugins


@dataclass(frozen=True)
class FamilySelection:
    families: tuple[str, ...]
    extensions: tuple[str, ...]
    content_labels: tuple[str, ...]


class FamilyRegistry:
    def __init__(self) -> None:
        self._families: dict[str, object] = {}
        self._extension_to_family: dict[str, str] = {}

    def register(self, plugin: object) -> None:
        family_id = getattr(plugin, "family_id")
        self._families[family_id] = plugin
        for extension in getattr(plugin, "default_extensions"):
            self._extension_to_family[extension] = family_id

    def load_builtins(self) -> None:
        for plugin in builtin_plugins.load_plugins():
            self.register(plugin)

    def load_entry_points(self) -> list[str]:
        warnings: list[str] = []
        try:
            entry_points = metadata.entry_points(group="upload_samples.file_families")
        except TypeError:
            entry_points = metadata.entry_points().get("upload_samples.file_families", [])
        for entry_point in entry_points:
            try:
                plugin = entry_point.load()()
                self.register(plugin)
            except Exception as exc:  # pragma: no cover - defensive path
                warnings.append(f"failed to load plugin {entry_point.name}: {exc}")
        return warnings

    def families(self) -> tuple[str, ...]:
        return tuple(sorted(self._families))

    def extensions(self) -> tuple[str, ...]:
        return tuple(sorted(self._extension_to_family))

    def get_plugin(self, family_id: str):
        return self._families[family_id]

    def family_for_extension(self, extension: str) -> str:
        try:
            return self._extension_to_family[extension]
        except KeyError as exc:
            raise KeyError(f"unknown logical extension: {extension}") from exc

    def select(self, families: list[str] | None = None, extensions: list[str] | None = None) -> FamilySelection:
        selected_families = tuple(families or self.families())
        for family_id in selected_families:
            if family_id not in self._families:
                raise KeyError(f"unknown family: {family_id}")

        if extensions:
            selected_extensions = tuple(extensions)
        else:
            selected_extensions = tuple(
                extension
                for extension in self.extensions()
                if self.family_for_extension(extension) in selected_families
            )

        for extension in selected_extensions:
            self.family_for_extension(extension)

        return FamilySelection(
            families=selected_families,
            extensions=selected_extensions,
            content_labels=selected_extensions,
        )

    def plugin_for_content_label(self, content_label: str):
        return self.get_plugin(self.family_for_extension(content_label))

    def canonical_family_for_label(self, label: str) -> str:
        if label in self._families:
            return label
        return self.family_for_extension(label)
