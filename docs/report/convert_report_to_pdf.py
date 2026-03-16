#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import re
import textwrap


def _strip_markdown(markdown: str) -> list[str]:
    lines: list[str] = []
    in_code = False

    for raw in markdown.splitlines():
        line = raw.rstrip("\n")
        if line.strip().startswith("```"):
            in_code = not in_code
            lines.append("")
            continue

        if in_code:
            lines.append(f"    {line}")
            continue

        # Links: [label](url) -> label (url)
        line = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", line)

        # Headings: remove # markers
        line = re.sub(r"^\s{0,3}#{1,6}\s*", "", line)

        # Emphasis/code markers
        line = line.replace("**", "").replace("__", "").replace("`", "")

        # Bullets
        line = re.sub(r"^\s*[-*+]\s+", "- ", line)
        line = re.sub(r"^\s*\d+\.\s+", "- ", line)

        lines.append(line)

    wrapped: list[str] = []
    for line in lines:
        if not line.strip():
            wrapped.append("")
            continue

        if line.startswith("    "):
            wrapped.extend(textwrap.wrap(line, width=96, replace_whitespace=False, drop_whitespace=False))
            continue

        wrapped.extend(textwrap.wrap(line, width=96))

    return wrapped


def _pdf_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _build_content_stream(lines: list[str], page_num: int, total_pages: int) -> bytes:
    ops: list[str] = [
        "BT",
        "/F1 11 Tf",
        "50 760 Td",
        "14 TL",
    ]

    for line in lines:
        safe = _pdf_escape(line)
        ops.append(f"({safe}) Tj")
        ops.append("T*")

    # Footer page number
    ops.extend(
        [
            "ET",
            "BT",
            "/F1 9 Tf",
            "280 30 Td",
            f"(Page {page_num} of {total_pages}) Tj",
            "ET",
        ]
    )

    return "\n".join(ops).encode("latin-1", errors="replace")


def _build_pdf(pages: list[list[str]]) -> bytes:
    objects: list[bytes] = []

    # 1: Catalog
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")

    # 2: Pages (filled after object ids are known)
    page_obj_ids = [4 + i * 2 for i in range(len(pages))]
    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_obj_ids)
    pages_obj = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii")
    objects.append(pages_obj)

    # 3: Font
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    total_pages = len(pages)
    for i, page_lines in enumerate(pages, start=1):
        page_obj_id = 4 + (i - 1) * 2
        content_obj_id = page_obj_id + 1

        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_obj_id} 0 R >>"
        ).encode("ascii")
        objects.append(page_obj)

        stream = _build_content_stream(page_lines, i, total_pages)
        content_obj = b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream"
        objects.append(content_obj)

    # Serialize PDF
    output = bytearray()
    output.extend(b"%PDF-1.4\n")
    offsets: list[int] = []

    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n".encode("ascii"))
        output.extend(obj)
        output.extend(b"\nendobj\n")

    xref_start = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f \n")
    for off in offsets:
        output.extend(f"{off:010d} 00000 n \n".encode("ascii"))

    output.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_start}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def convert_markdown_to_pdf(source: Path, target: Path) -> None:
    text = source.read_text(encoding="utf-8")
    wrapped_lines = _strip_markdown(text)

    lines_per_page = 48
    pages = [wrapped_lines[i : i + lines_per_page] for i in range(0, len(wrapped_lines), lines_per_page)]
    if not pages:
        pages = [[""]]

    pdf_bytes = _build_pdf(pages)
    target.write_bytes(pdf_bytes)


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert Markdown report to a basic PDF")
    parser.add_argument("input", nargs="?", default="docs/report/PROJECT_REPORT.md")
    parser.add_argument("output", nargs="?", default="docs/report/PROJECT_REPORT.pdf")
    args = parser.parse_args()

    source = Path(args.input)
    target = Path(args.output)
    if not source.exists():
        raise SystemExit(f"Input file not found: {source}")

    target.parent.mkdir(parents=True, exist_ok=True)
    convert_markdown_to_pdf(source, target)
    print(f"Generated PDF: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
