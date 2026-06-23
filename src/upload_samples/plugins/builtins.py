from __future__ import annotations

import base64
import io
import struct
import zlib
from dataclasses import dataclass

from PIL import Image

from ..models import FamilySample


def marker_value(sample_id: str, field: str, index: int = 1) -> str:
    return f"UPLOAD_SAMPLE_MARKER__{sample_id.upper()}__{field.upper()}__{index:03d}"


def reflection_probe(sample_id: str, field: str) -> str:
    return (
        '\"><img src=x onerror=alert(1337) '
        f'data-upload-sample="{sample_id}" data-upload-field="{field}">'
    )


def _png_chunk(chunk_type: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + chunk_type + payload + struct.pack(">I", zlib.crc32(chunk_type + payload) & 0xFFFFFFFF)


def _png_bytes(text_chunks: list[tuple[str, str]] | None = None, width: int = 1, height: int = 1) -> bytes:
    signature = bytes.fromhex("89504E470D0A1A0A")
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = b"\x00" + (b"\x88\xcc\x22" * width)
    idat = zlib.compress(scanline * height, level=9)
    chunks = [signature, _png_chunk(b"IHDR", ihdr)]
    for key, value in text_chunks or []:
        chunks.append(_png_chunk(b"tEXt", key.encode("latin-1") + b"\x00" + value.encode("utf-8")))
    chunks.extend([_png_chunk(b"IDAT", idat), _png_chunk(b"IEND", b"")])
    return b"".join(chunks)


def _pdf_literal(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_bytes(title: str = "Upload Sample", author: str = "upload-samples", subject: str = "baseline") -> bytes:
    objects = [
        "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        "2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n",
        "3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n",
        "4 0 obj\n<< /Length 44 >>\nstream\nBT /F1 12 Tf 36 96 Td (Upload Sample) Tj ET\nendstream\nendobj\n",
        "5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
        f"6 0 obj\n<< /Title ({_pdf_literal(title)}) /Author ({_pdf_literal(author)}) /Subject ({_pdf_literal(subject)}) >>\nendobj\n",
    ]
    parts = ["%PDF-1.4\n"]
    offsets: list[int] = [0]
    cursor = len(parts[0].encode("utf-8"))
    for obj in objects:
        offsets.append(cursor)
        parts.append(obj)
        cursor += len(obj.encode("utf-8"))
    xref_offset = cursor
    xref = [f"xref\n0 {len(offsets)}\n", "0000000000 65535 f \n"]
    for offset in offsets[1:]:
        xref.append(f"{offset:010d} 00000 n \n")
    trailer = f"trailer\n<< /Size {len(offsets)} /Root 1 0 R /Info 6 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n"
    return "".join(parts + xref + [trailer]).encode("utf-8")


JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQAAAQABAAD/2wCEAAkGBxAQEBAQEA8QDw8QEA8QEA8PDw8QFREWFhURFRUYHSggGBolGxUVITEhJSkrLi4uFx8zODMsNygtLisBCgoKDg0OGxAQGy8lICYtLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLS0tLf/AABEIAAEAAQMBIgACEQEDEQH/xAAXAAADAQAAAAAAAAAAAAAAAAAAAQMC/8QAFBABAAAAAAAAAAAAAAAAAAAAAP/aAAwDAQACEAMQAAAB9gD/xAAXEAADAQAAAAAAAAAAAAAAAAABAhEh/9oACAEBAAEFAiYf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAwEBPwEf/8QAFBEBAAAAAAAAAAAAAAAAAAAAEP/aAAgBAgEBPwEf/8QAGhAAAgMBAQAAAAAAAAAAAAAAAREAITFBUf/aAAgBAQAGPwJ2pW0f/8QAFxABAQEBAAAAAAAAAAAAAAAAAQARIf/aAAgBAQABPyHsVFDaP//aAAwDAQACAAMAAAAQ8//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQMBAT8QH//EABQRAQAAAAAAAAAAAAAAAAAAABD/2gAIAQIBAT8QH//EABwQAQACAgMBAAAAAAAAAAAAAAEAESExQVFhcf/aAAgBAQABPxBjk4rDVQt2iL0O4TrhYqf/2Q=="
)


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (8, 8), color=(136, 204, 34))
    image.save(buffer, format="JPEG", quality=92, optimize=False, progressive=False)
    return buffer.getvalue()


def _tiff_ascii_entry(tag: int, value: str, data_offset: int) -> bytes:
    return struct.pack("<HHII", tag, 2, len(value) + 1, data_offset)


def _tiff_short_entry(tag: int, value: int) -> bytes:
    return struct.pack("<HHII", tag, 3, 1, value)


def _tiff_long_entry(tag: int, value: int) -> bytes:
    return struct.pack("<HHII", tag, 4, 1, value)


def _tiff_rational_entry(tag: int, data_offset: int) -> bytes:
    return struct.pack("<HHII", tag, 5, 1, data_offset)


def _tiff_bytes(description: str = "Upload Sample") -> bytes:
    buffer = io.BytesIO()
    image = Image.new("RGB", (8, 8), color=(136, 204, 34))
    image.save(
        buffer,
        format="TIFF",
        compression="raw",
        tiffinfo={270: description},
        dpi=(72, 72),
    )
    return buffer.getvalue()


@dataclass
class BasePlugin:
    family_id: str
    default_extensions: tuple[str, ...]
    magic_prefixes: tuple[bytes, ...]
    mime_type: str
    capabilities: frozenset[str]

    def supports(self, capability: str) -> bool:
        return capability in self.capabilities

    def generate_metadata_samples(self) -> list[tuple[str, bytes, str]]:
        return []

    def generate_stress_samples(self, max_pixels: int, max_tiff_pages: int) -> list[tuple[str, bytes, str]]:
        return []

    def generate_structure_samples(self) -> list[tuple[str, bytes, str]]:
        return []


class PdfPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__("pdf", ("pdf",), (bytes.fromhex("25504446"),), "application/pdf", frozenset({"baseline", "metadata", "stress", "structures"}))

    def generate_valid(self, logical_extension: str) -> FamilySample:
        data = _pdf_bytes()
        return FamilySample(self.family_id, logical_extension, data, self.magic_prefixes[0], self.mime_type)

    def generate_metadata_samples(self) -> list[tuple[str, bytes, str]]:
        return [
            (
                "pdf-title-marker.pdf",
                _pdf_bytes(
                    title=marker_value("pdf-title-marker", "title", 1),
                    subject=marker_value("pdf-title-marker", "subject", 2),
                ),
                "PDF title metadata marker.",
            ),
            (
                "pdf-title-reflection-probe.pdf",
                _pdf_bytes(
                    title=reflection_probe("pdf-title-reflection-probe", "title"),
                    subject=marker_value("pdf-title-reflection-probe", "subject-reflection", 2),
                ),
                "PDF title reflection probe.",
            ),
        ]

    def generate_stress_samples(self, max_pixels: int, max_tiff_pages: int) -> list[tuple[str, bytes, str]]:
        marker_lines = "\\n".join(
            marker_value("pdf-stress", f"subject-line-{index}", index + 1)
            for index in range(100)
        )
        return [
            (
                "many-metadata-fields.pdf",
                _pdf_bytes(
                    title=marker_value("pdf-many-metadata-fields", "title", 1),
                    author=marker_value("pdf-many-metadata-fields", "author", 2),
                    subject=marker_lines,
                ),
                "PDF with many benign metadata values.",
            )
        ]

    def generate_structure_samples(self) -> list[tuple[str, bytes, str]]:
        form_text = "%PDF-1.4\n1 0 obj\n<< /Type /Catalog /AcroForm << /Fields [6 0 R] >> /Pages 2 0 R >>\nendobj\n2 0 obj\n<< /Type /Pages /Count 1 /Kids [3 0 R] >>\nendobj\n3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Annots [6 0 R] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n4 0 obj\n<< /Length 37 >>\nstream\nBT /F1 12 Tf 36 96 Td (Form field sample) Tj ET\nendstream\nendobj\n5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n6 0 obj\n<< /Type /Annot /Subtype /Widget /FT /Tx /T (field1) /Rect [36 36 180 56] >>\nendobj\nxref\n0 7\n0000000000 65535 f \n0000000009 00000 n \n0000000078 00000 n \n0000000135 00000 n \n0000000274 00000 n \n0000000361 00000 n \n0000000431 00000 n \ntrailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n512\n%%EOF\n"
        return [
            ("pdf-with-form-field.pdf", form_text.encode("utf-8"), "Benign PDF with an AcroForm-like structure."),
            (
                "pdf-with-embedded-text-marker.pdf",
                _pdf_bytes(
                    title=marker_value("pdf-with-embedded-text-marker", "title", 1),
                    subject=marker_value("pdf-with-embedded-text-marker", "subject", 2),
                ),
                "PDF carrying an embedded text marker.",
            ),
        ]


class JpegPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__("jpg", ("jpg", "jpeg"), (bytes.fromhex("FFD8FF"),), "image/jpeg", frozenset({"baseline", "malformed"}))

    def generate_valid(self, logical_extension: str) -> FamilySample:
        return FamilySample(self.family_id, logical_extension, _jpeg_bytes(), self.magic_prefixes[0], self.mime_type)


class PngPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__("png", ("png",), (bytes.fromhex("89504E470D0A1A0A"),), "image/png", frozenset({"baseline", "metadata", "stress"}))

    def generate_valid(self, logical_extension: str) -> FamilySample:
        data = _png_bytes()
        return FamilySample(self.family_id, logical_extension, data, self.magic_prefixes[0], self.mime_type)

    def generate_metadata_samples(self) -> list[tuple[str, bytes, str]]:
        return [
            (
                "png-text-marker.png",
                _png_bytes([("Comment", marker_value("png-text-marker", "comment", 1))]),
                "PNG tEXt marker sample.",
            ),
            (
                "png-text-reflection-probe.png",
                _png_bytes([("Comment", reflection_probe("png-text-reflection-probe", "comment"))]),
                "PNG tEXt reflection probe.",
            ),
        ]

    def generate_stress_samples(self, max_pixels: int, max_tiff_pages: int) -> list[tuple[str, bytes, str]]:
        width = max(1, min(max_pixels, 5000))
        height = max(1, max_pixels // width)
        return [("large-dim-small-png.png", _png_bytes(width=width, height=height), "PNG with bounded large dimensions.")]


class TiffPlugin(BasePlugin):
    def __init__(self) -> None:
        super().__init__("tiff", ("tiff",), (bytes.fromhex("49492A00"), bytes.fromhex("4D4D002A")), "image/tiff", frozenset({"baseline", "metadata", "stress"}))

    def generate_valid(self, logical_extension: str) -> FamilySample:
        data = _tiff_bytes()
        return FamilySample(self.family_id, logical_extension, data, self.magic_prefixes[0], self.mime_type)

    def generate_metadata_samples(self) -> list[tuple[str, bytes, str]]:
        return [
            (
                "tiff-description-marker.tiff",
                _tiff_bytes(marker_value("tiff-description-marker", "image-description", 1)),
                "TIFF ImageDescription marker sample.",
            )
        ]

    def generate_stress_samples(self, max_pixels: int, max_tiff_pages: int) -> list[tuple[str, bytes, str]]:
        return [("multipage-small-tiff.tiff", _tiff_bytes(f"pages={max_tiff_pages}"), "TIFF stress marker describing a bounded multipage target." )]


def load_plugins() -> list[object]:
    return [PdfPlugin(), JpegPlugin(), PngPlugin(), TiffPlugin()]
