# Adding New File Formats

This project was designed so new file formats can be added without rewriting the generators.

The extension point is the **file family plugin** model. Category generators work from registered families and logical extensions, not from a hardcoded list of formats.

## What “adding a format” means here

There are two related concepts:

- **family**: the canonical content family, for example `jpg` or `pdf`
- **logical extension**: the filename extension exposed to the CLI and manifest, for example `jpg` and `jpeg`

Example:

- JPEG is one family: `jpg`
- it exposes two logical extensions: `jpg`, `jpeg`

If you add a format such as `gif`, you usually add:

- one new family id: `gif`
- one or more logical extensions: `gif`

## Current extension points

The core interfaces are:

- `src/upload_samples/models.py`
- `src/upload_samples/registry.py`
- `src/upload_samples/plugins/builtins.py`

The registry loads:

- built-in plugins from `src/upload_samples/plugins/builtins.py`
- optional external plugins from the Python entry-point group `upload_samples.file_families`

## Plugin contract

A format plugin must satisfy the `FileFamilyPlugin` protocol in `src/upload_samples/models.py`.

Required attributes:

- `family_id`
- `default_extensions`
- `magic_prefixes`
- `mime_type`

Required methods:

- `supports(capability: str) -> bool`
- `generate_valid(logical_extension: str) -> FamilySample`
- `generate_metadata_samples() -> list[tuple[str, bytes, str]]`
- `generate_stress_samples(max_pixels: int, max_tiff_pages: int) -> list[tuple[str, bytes, str]]`
- `generate_structure_samples() -> list[tuple[str, bytes, str]]`

The `FamilySample` returned by `generate_valid(...)` contains:

- canonical content family
- logical extension
- raw file bytes
- expected magic bytes
- MIME type

## Capability model

Not every format must support every category.

Built-in plugins currently use a `BasePlugin` helper with a `capabilities` set in `src/upload_samples/plugins/builtins.py`.

Typical capability meanings:

- `baseline`: can generate a valid small sample
- `metadata`: can generate safe metadata marker samples
- `stress`: can generate bounded resource-handling samples
- `structures`: can generate format-specific structural indicator samples

The malformed, minimal-header, mismatch, and polyglot generators do not require special plugin-side helper methods beyond `generate_valid(...)` and the declared magic bytes.

## Two ways to add a format

### Option 1: add it as a built-in family

Use this when the format should ship with this repository by default.

Steps:

1. Add a new plugin class in `src/upload_samples/plugins/builtins.py`
2. Give it a unique `family_id`
3. Declare its `default_extensions`
4. Declare one or more `magic_prefixes`
5. Declare its `mime_type`
6. Implement `generate_valid(...)`
7. Optionally implement metadata/stress/structure helpers
8. Return the plugin from `load_plugins()`

Minimal example shape:

```python
class GifPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__(
            "gif",
            ("gif",),
            (bytes.fromhex("474946383761"), bytes.fromhex("474946383961")),
            "image/gif",
            frozenset({"baseline"})
        )

    def generate_valid(self, logical_extension: str) -> FamilySample:
        data = build_gif_bytes_somehow()
        return FamilySample(
            self.family_id,
            logical_extension,
            data,
            self.magic_prefixes[0],
            self.mime_type,
        )
```

Then add it to:

```python
def load_plugins() -> list[object]:
    return [PdfPlugin(), JpegPlugin(), PngPlugin(), TiffPlugin(), GifPlugin()]
```

### Option 2: add it as an external plugin package

Use this when the format should live outside this repository.

Your external package must:

1. provide a plugin class implementing the same protocol
2. expose it through the entry-point group `upload_samples.file_families`

Example `pyproject.toml` for the external package:

```toml
[project.entry-points."upload_samples.file_families"]
gif = "my_upload_samples_gif.plugin:GifPlugin"
```

After installing that package in the same environment, this project will attempt to load it through `FamilyRegistry.load_entry_points()`.

## How generators pick up a new format

Once the family is registered, most categories start using it automatically.

### Baseline

`baseline.generate` iterates over `config.selected_extensions`.

If your plugin exposes `gif`, baseline generation will automatically create:

- `baseline/valid.gif`

### Mismatch

`mismatch.generate` iterates over all selected logical extensions.

That means the new extension is automatically added to the mismatch matrix.

### Minimal headers

`minimal_headers.generate` uses each plugin’s `magic_prefixes`.

If your format has multiple common headers, define all of them and decide whether you need special naming logic similar to TIFF.

### Malformed

`malformed.generate` starts from `generate_valid(...)`, then creates truncated and random-tail variants automatically.

### Metadata

If your plugin returns metadata samples from `generate_metadata_samples()`, they are automatically emitted under `metadata/`.

If you return an empty list, the metadata generator writes a recipe note instead.

### Stress-bounded

If your plugin returns stress samples from `generate_stress_samples(...)`, they are automatically emitted under `stress-bounded/`.

### PDF structures

This category is currently PDF-specific.

If you add another format with structure-oriented probes, either:

- create a new category generator for that family, or
- generalize the existing structure model deliberately

Do not force unrelated formats into `pdf-structures`.

### Polyglots

The polyglot generator works from `config.selected_extensions`.

If your new extension is selected:

- it becomes a **host** candidate
- it becomes a **payload** candidate
- it is paired against every other selected extension
- HTML is also added as a payload candidate

Current Mitra behavior is uniform:

- file 1 = host sample for the extension
- file 2 = payload sample
- Mitra is always called with `-f`

This means a new format can participate in polyglot generation immediately, as long as:

- `generate_valid(...)` returns valid seed bytes
- Mitra can do something useful with that host/payload combination

## Choosing family ids and extensions

Follow these rules:

- keep `family_id` canonical and stable
- use lowercase only
- use the most common short family name
- keep `default_extensions` ordered from most common to less common

Examples:

- good: `pdf`, `png`, `gif`
- good alias model: family `jpg` with extensions `("jpg", "jpeg")`
- avoid using two separate families for the same byte-level format unless they are genuinely different

## Magic bytes guidance

The manifest and `verify` command rely on plugin-declared signatures.

Recommendations:

- declare the shortest stable prefix that meaningfully identifies the format
- declare multiple prefixes only if the format genuinely has multiple common signatures
- do not invent weak signatures just to make a format fit

If a format has no reliable header:

- the project can still support it
- but you need to think carefully about how `verify` and `minimal-headers` should behave

## Safe sample design rules

New format plugins must respect the same safety model as the rest of the project.

Do:

- generate small, benign, deterministic samples
- keep malformed samples bounded
- keep metadata markers local and passive
- avoid internet callbacks
- avoid weaponized exploit content

Do not:

- embed malware
- include public RCE payloads
- create uncontrolled bombs
- add format-specific dangerous behavior just because the format supports it

## Testing checklist

When adding a new format, update tests in `tests/test_generation.py`.

Minimum checks:

1. `generate --category baseline` creates a valid sample for the new extension
2. `verify` accepts the generated baseline sample
3. mismatch generation includes the new extension
4. malformed generation produces bounded variants
5. metadata/stress/structure tests exist if the plugin claims those capabilities

Useful command during development:

```bash
python -m upload_samples list-families
python -m upload_samples generate --out out --family YOUR_FAMILY --category baseline --category mismatch
python -m upload_samples verify --out out
pytest -q tests/test_generation.py
```

## Common mistakes

- **Using filename as identity**: do not do this; manifest ids are derived from stable generation inputs and content hash.
- **Adding a new extension without valid bytes**: mismatch and polyglot generation still need a real `generate_valid(...)`.
- **Treating aliases as separate families**: use one family with multiple logical extensions where appropriate.
- **Declaring unsupported capabilities**: if the plugin cannot generate safe metadata or stress samples, leave that capability out.
- **Adding format-specific logic in many generators**: prefer implementing plugin behavior once and letting the generic generators reuse it.

## Decision guide

Before adding a format, answer these questions:

1. Is this a new **family**, or just another **extension alias** for an existing family?
2. Can you generate a small, valid, deterministic sample locally?
3. Does the format have stable magic bytes?
4. Does metadata support make sense for this format?
5. Does stress testing make sense for this format?
6. Does Mitra interaction make sense, or will the format simply be a low-value forced payload?

If the answer to only question 2 is “yes”, you can still add the format as a baseline/mismatch/malformed/polyglot participant and leave metadata/stress/structure support for later.

## Recommended implementation order

1. Add `generate_valid(...)`
2. Register the family and extensions
3. Confirm `baseline`, `mismatch`, and `verify`
4. Add malformed coverage
5. Add metadata/stress/structure support only if it is genuinely useful
6. Add tests
7. Update user-facing documentation if the new format is exposed by default
