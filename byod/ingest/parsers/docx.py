from pathlib import Path

from docx import Document
from docx.table import Table

from byod.ingest.normalize import Block


def parse(path: Path) -> list[Block]:
    document = Document(str(path))
    blocks: list[Block] = []
    headings: list[str] = []
    for element in document.iter_inner_content():
        if isinstance(element, Table):
            text = "\n".join(" | ".join(cell.text for cell in row.cells) for row in element.rows)
            blocks.append(
                Block(
                    text,
                    " > ".join(headings) or "Document",
                    len(blocks),
                    "docx",
                    "table",
                    heading_path=tuple(headings),
                    title=path.stem,
                )
            )
            continue
        style = element.style.name if element.style else ""
        depth = int(style[-1]) if style in {f"Heading {i}" for i in range(1, 7)} else 0
        if depth:
            headings = headings[: depth - 1] + [element.text.strip()]
        blocks.append(
            Block(
                element.text,
                " > ".join(headings) or "Document",
                len(blocks),
                "docx",
                "heading" if depth else "body",
                depth,
                tuple(headings),
                path.stem,
            )
        )
    return blocks
