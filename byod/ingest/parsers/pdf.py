import os
from dataclasses import replace
from pathlib import Path
from statistics import median
from typing import Any

import pymupdf

from byod.errors import ByodError
from byod.ingest.normalize import Block, BlockType

# Keep parser diagnostics from contaminating debug JSON or exposing source data.
os.environ["PYMUPDF_SUGGEST_LAYOUT_ANALYZER"] = "0"
pymupdf.TOOLS.mupdf_display_errors(False)
pymupdf.TOOLS.mupdf_display_warnings(False)


def parse(path: Path) -> list[Block]:
    blocks: list[Block] = []
    scanned = 0
    headings: list[str] = []
    with pymupdf.open(path) as document:
        unit_count = len(document)
        if document.needs_pass:
            raise ByodError("PARSE_FAILED")
        for number, page in enumerate(document, 1):
            locator = f"p. {number}"
            if len(page.get_text().strip()) < 30:
                scanned += 1
            tables = page.find_tables().tables
            rectangles = [pymupdf.Rect(table.bbox) for table in tables]
            detailed = page.get_text("dict")["blocks"]
            sizes = [
                span["size"]
                for b in detailed
                if b["type"] == 0
                for line in b["lines"]
                for span in line["spans"]
            ]
            typical = median(sizes) if sizes else 12
            entries: list[tuple[float, float, str, BlockType, int]] = []
            for raw in page.get_text("blocks", sort=True):
                if raw[6] != 0 or any(rect.contains(pymupdf.Rect(raw[:4])) for rect in rectangles):
                    continue
                detail: dict[str, Any] = next((b for b in detailed if b["number"] == raw[5]), {})
                spans = [s for line in detail.get("lines", []) for s in line["spans"]]
                dominant = max(spans, key=lambda s: len(s["text"]))["size"] if spans else typical
                depth = (1 if dominant >= typical * 1.5 else 2) if dominant >= typical * 1.2 else 0
                entries.append((raw[1], raw[0], raw[4], "heading" if depth else "body", depth))
            for table in tables:
                text = "\n".join(" | ".join(cell or "" for cell in row) for row in table.extract())
                entries.append((table.bbox[1], table.bbox[0], text, "table", 0))
            for _, _, text, kind, depth in sorted(entries):
                if depth:
                    headings = headings[: depth - 1] + [text.strip()]
                blocks.append(
                    Block(
                        text, locator, len(blocks), "pdf", kind, depth, tuple(headings), path.stem
                    )
                )
        if scanned > len(document) / 2:
            raise ByodError("SCANNED_PDF")
    # Recognize adjacent repeated-header table continuations across page breaks.
    joined: list[Block] = []
    for block in blocks:
        if joined and block.block_type == joined[-1].block_type == "table":
            previous = joined[-1]
            if (
                int(block.locator.split()[-1]) == int(previous.locator.split()[-1]) + 1
                and block.text.splitlines()[0] == previous.text.splitlines()[0]
            ):
                joined[-1] = replace(
                    previous, text=previous.text + "\n" + "\n".join(block.text.splitlines()[1:])
                )
                continue
        joined.append(block)
    return [replace(block, unit_count=unit_count) for block in joined]
