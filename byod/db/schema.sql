CREATE TABLE workspaces (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL UNIQUE CHECK(length(trim(name)) > 0),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE documents (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    path TEXT NOT NULL,
    doc_type TEXT NOT NULL CHECK(doc_type IN ('pdf','docx','pptx')),
    content_hash TEXT NOT NULL,
    unit_count INTEGER,
    chunk_count INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','indexed','failed','missing')),
    error TEXT,
    embed_model TEXT,
    embed_version TEXT,
    ingested_at TEXT,
    UNIQUE(workspace_id, content_hash)
);
CREATE TABLE chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ordinal INTEGER NOT NULL,
    text TEXT NOT NULL,
    locator TEXT NOT NULL,
    block_type TEXT NOT NULL,
    token_count INTEGER NOT NULL CHECK(token_count >= 20),
    UNIQUE(document_id, ordinal)
);
CREATE INDEX idx_chunks_document ON chunks(document_id);
CREATE VIRTUAL TABLE chunk_vectors USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[768]
);
CREATE TRIGGER delete_chunk_vector AFTER DELETE ON chunks BEGIN
    DELETE FROM chunk_vectors WHERE chunk_id = OLD.id;
END;
CREATE TABLE chats (
    id INTEGER PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'Untitled',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE messages (
    id INTEGER PRIMARY KEY,
    chat_id INTEGER NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK(role IN ('user','assistant')),
    content TEXT NOT NULL,
    provider TEXT,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_messages_chat ON messages(chat_id, id);
CREATE TABLE citations (
    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chunk_id INTEGER NOT NULL REFERENCES chunks(id) ON DELETE CASCADE,
    rank INTEGER NOT NULL,
    PRIMARY KEY(message_id, chunk_id)
);
CREATE TABLE schema_version (version INTEGER NOT NULL);
INSERT INTO schema_version VALUES (1);
