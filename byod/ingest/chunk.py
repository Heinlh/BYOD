"""Format-aware chunking confined to ingestion."""

from dataclasses import dataclass
from itertools import groupby

from byod.errors import ByodError
from byod.ingest.normalize import Block, DocType
from byod.tokenize import TokenCounter


@dataclass(frozen=True)
class Chunk:
    text: str
    locator: str
    ordinal: int
    block_type: str
    token_count: int


def chunk(blocks: list[Block], doc_type: DocType, counter: TokenCounter) -> list[Chunk]:
    result: list[Chunk] = []
    budget = 1200 if doc_type == "pptx" else 600
    groups = groupby(blocks, key=lambda b: b.locator if doc_type == "pptx" else b.heading_path)
    for _, grouped in groups:
        section = list(grouped)
        prefix = section[0].title if doc_type == "pptx" else " > ".join(section[0].heading_path)
        if doc_type == "pptx":
            order = {"heading": 0, "body": 1, "table": 2, "notes": 3}
            section.sort(key=lambda b: (order[b.block_type], b.order))
        prefix_tokens = counter.count(prefix)
        available = budget - prefix_tokens - 4
        if available < 20:
            raise ByodError("BLOCK_TOO_LARGE")
        parts: list[tuple[str, Block]] = []

        def emit(parts: list[tuple[str, Block]], prefix: str) -> None:
            if not parts:
                return
            text = "\n".join(([prefix] if prefix else []) + [p[0] for p in parts])
            tokens = counter.count(text)
            if tokens >= 20:
                if tokens > budget:
                    raise ByodError("BLOCK_TOO_LARGE")
                result.append(
                    Chunk(
                        text,
                        parts[0][1].locator,
                        len(result),
                        "table" if any(b.block_type == "table" for _, b in parts) else "body",
                        tokens,
                    )
                )

        for block in section:
            if block.block_type == "heading" and doc_type != "pptx":
                continue  # Included through the heading path prefix.
            text = ("Speaker notes:\n" if block.block_type == "notes" else "") + block.text
            if block.block_type == "table" and counter.count(text) > available:
                # Both no-table-split and maximum-budget invariants must hold.
                raise ByodError("BLOCK_TOO_LARGE")
            overlap_budget = min(90, available // 4) if doc_type != "pptx" else 0
            pieces = (
                [text]
                if block.block_type == "table"
                else counter.split(text, available - overlap_budget)
            )
            for piece in pieces:
                candidate = "\n".join([prefix] + [p[0] for p in parts] + [piece])
                if parts and counter.count(candidate) > budget:
                    emit(parts, prefix)
                    overlap: list[tuple[str, Block]] = []
                    if doc_type != "pptx" and parts[-1][1].block_type != "table":
                        last_text, last_block = parts[-1]
                        offsets = counter.tokenizer.encode(
                            last_text, add_special_tokens=False
                        ).offsets
                        if offsets:
                            start = offsets[max(0, len(offsets) - int(budget * 0.15))][0]
                            overlap = [(last_text[start:], last_block)]
                    if (
                        counter.count("\n".join([prefix] + [p[0] for p in overlap] + [piece]))
                        > budget
                    ):
                        overlap = []
                    parts = overlap
                parts.append((piece, block))
        emit(parts, prefix)
    if not result:
        raise ByodError("EMPTY_DOCUMENT")
    return result
