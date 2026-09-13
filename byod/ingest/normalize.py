"""Shared normalized document model and ingestion format boundary."""

import re
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Literal

from byod.errors import ByodError

DocType = Literal["pdf", "docx", "pptx"]
BlockType = Literal["heading", "body", "table", "notes"]


@dataclass(frozen=True)
class Block:
    text: str
    locator: str
    order: int
    doc_type: DocType
    block_type: BlockType = "body"
    depth: int = 0
    heading_path: tuple[str, ...] = ()
    title: str = ""
    unit_count: int | None = None


def normalize(blocks: list[Block]) -> list[Block]:
    result = []
    last_order = -1
    for block in blocks:
        if block.doc_type not in {"pdf", "docx", "pptx"}:
            raise ValueError("Unknown document type")
        if block.block_type not in {"heading", "body", "table", "notes"}:
            raise ValueError("Unknown block type")
        if block.order <= last_order or not block.locator:
            raise ValueError("Invalid block order or locator")
        last_order = block.order
        text = unicodedata.normalize("NFC", block.text)
        text = "".join(
            c if c in "\n\t" or not unicodedata.category(c).startswith("C") else "" for c in text
        )
        # Preserve table rows while collapsing whitespace within each row.
        text = "\n".join(re.sub(r"\s+", " ", row).strip() for row in text.splitlines())
        text = re.sub(r"\n+", "\n", text).strip()
        if any(c.isalpha() for c in text):
            result.append(replace(block, text=text))
    return result


def document_type(path: Path) -> DocType:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf"
    if suffix == ".docx":
        return "docx"
    if suffix == ".pptx":
        return "pptx"
    raise ByodError("UNSUPPORTED_TYPE")


def parse(path: Path) -> list[Block]:
    from byod.ingest.parsers import docx, pdf, pptx

    if not path.is_file():
        raise ByodError("FILE_NOT_FOUND")
    kind = document_type(path)
    try:
        blocks = normalize({"pdf": pdf.parse, "docx": docx.parse, "pptx": pptx.parse}[kind](path))
    except ByodError:
        raise
    except Exception:
        raise ByodError("PARSE_FAILED") from None
    if not blocks:
        raise ByodError("EMPTY_DOCUMENT")
    return blocks
