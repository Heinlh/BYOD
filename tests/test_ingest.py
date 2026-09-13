import shutil
from pathlib import Path

import pytest
from docx import Document

from byod.config import Config
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace
from byod.errors import ByodError
from byod.ingest.chunk import chunk
from byod.ingest.jobs import JobQueue
from byod.ingest.normalize import Block, normalize, parse
from byod.tokenize import TokenCounter

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize("name", ["reading.pdf", "notes.docx", "lecture.pptx"])
def test_native_parsers_and_chunk_budgets(name: str, counter: TokenCounter) -> None:
    blocks = parse(FIXTURES / name)
    assert blocks
    assert all(b.locator and b.text.strip() for b in blocks)
    assert [b.order for b in blocks] == sorted({b.order for b in blocks})
    assert any(b.block_type == "table" for b in blocks)
    chunks = chunk(blocks, blocks[0].doc_type, counter)
    assert all(20 <= c.token_count <= (1200 if name.endswith("pptx") else 600) for c in chunks)
    assert all(c.token_count == counter.count(c.text) and c.locator for c in chunks)
    for table in (b for b in blocks if b.block_type == "table"):
        assert any(table.text in c.text for c in chunks)
    if name.endswith("pptx"):
        assert blocks[0].unit_count == 5
        assert {b.locator for b in blocks if b.block_type == "notes"} == {"slide 2", "slide 4"}
        assert sum("Speaker notes:" in c.text for c in chunks) == 2
        assert len(chunks) == 4  # Diagram-only fifth slide has no text to index.
        slide3 = next(c.text for c in chunks if c.locator == "slide 3")
        assert slide3.index("Left column") < slide3.index("Right column")
    elif name.endswith("docx"):
        assert max(len(b.heading_path) for b in blocks) == 3
    else:
        assert blocks[0].unit_count == 3
        assert {b.locator for b in blocks} == {"p. 1", "p. 2", "p. 3"}
        assert any(b.block_type == "heading" for b in blocks)
        tables = [b for b in blocks if b.block_type == "table"]
        assert len(tables) == 1  # A repeated-header table spans pages 1 and 2.
        assert len(tables[0].text.splitlines()) == 7


def test_scanned_and_corrupt_documents(tmp_path: Path) -> None:
    with pytest.raises(ByodError) as error:
        parse(FIXTURES / "scanned.pdf")
    assert error.value.code == "SCANNED_PDF"
    corrupt = tmp_path / "broken.docx"
    corrupt.write_bytes(b"broken")
    with pytest.raises(ByodError) as error:
        parse(corrupt)
    assert error.value.code == "PARSE_FAILED"


def test_normalization_and_oversized_tables(counter: TokenCounter) -> None:
    blocks = normalize(
        [Block(" \x00Cafe\u0301  text ", "p. 1", 0, "pdf"), Block("123 !!!", "p. 1", 1, "pdf")]
    )
    assert len(blocks) == 1 and blocks[0].text == "Café text"
    with pytest.raises(ValueError):
        normalize([blocks[0], blocks[0]])
    with pytest.raises(ByodError) as error:
        chunk([Block("cell content " * 700, "p. 1", 0, "pdf", "table")], "pdf", counter)
    assert error.value.code == "BLOCK_TOO_LARGE"


def test_queue_idempotency_and_failure_atomicity(ingest_config: Config) -> None:
    initialize(ingest_config)
    folder = ingest_config.data_dir / "source-fixtures"
    folder.mkdir()
    for name in ("reading.pdf", "notes.docx", "lecture.pptx", "scanned.pdf"):
        shutil.copyfile(FIXTURES / name, folder / name)
    with connect(ingest_config) as db:
        workspace = create_workspace(db, "Biology")
    jobs = JobQueue(ingest_config)
    try:
        identifier = jobs.submit(workspace, [str(folder)])
        jobs.wait()
        first = jobs.snapshot(identifier)
        assert first and first["completed"] == 3 and first["failed"] == 1
        identifier = jobs.submit(workspace, [str(folder)])
        jobs.wait()
        second = jobs.snapshot(identifier)
        assert second and second["skipped"] == 3 and second["failed"] == 1
        with connect(ingest_config) as db:
            assert db.execute("SELECT count(*) FROM documents").fetchone()[0] == 4
            assert (
                db.execute(
                    "SELECT count(*) FROM chunks c JOIN documents d ON d.id=c.document_id "
                    "WHERE d.status='failed'"
                ).fetchone()[0]
                == 0
            )
            assert db.execute("SELECT count(*) FROM chunks").fetchone()[0] > 3
        assert jobs.snapshot("absent") is None
    finally:
        jobs.close()


def test_reindex_modified_source_keeps_document_identity(ingest_config: Config) -> None:
    initialize(ingest_config)
    source = ingest_config.data_dir / "source.docx"
    shutil.copyfile(FIXTURES / "notes.docx", source)
    with connect(ingest_config) as db:
        workspace = create_workspace(db, "Biology")
    jobs = JobQueue(ingest_config)
    try:
        jobs.submit(workspace, [str(source)])
        jobs.wait()
        with connect(ingest_config) as db:
            original = db.execute("SELECT id,content_hash FROM documents").fetchone()
        doc = Document(str(source))
        doc.add_paragraph("Additional biological processes are discussed in the next laboratory.")
        doc.save(str(source))
        identifier = jobs.submit(workspace, [str(source)], reindex=True)
        jobs.wait()
        result = jobs.snapshot(identifier)
        assert result and result["state"] == "done"
        with connect(ingest_config) as db:
            rows = db.execute("SELECT id,content_hash FROM documents").fetchall()
            assert len(rows) == 1 and rows[0]["id"] == original["id"]
            assert rows[0]["content_hash"] != original["content_hash"]
    finally:
        jobs.close()
