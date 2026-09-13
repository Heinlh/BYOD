"""BYOD command-line entry point."""

import argparse
import json
import socket
import threading
import webbrowser
from dataclasses import asdict
from pathlib import Path

import uvicorn

from byod.app import create_app
from byod.config import Config
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace, list_workspaces
from byod.index.embed import Embedder
from byod.ingest.chunk import chunk
from byod.ingest.jobs import JobQueue
from byod.ingest.normalize import parse
from byod.llm.base import Message
from byod.llm.keys import KeyStore
from byod.llm.providers import provider_for
from byod.retrieve.search import Retriever
from byod.tokenize import TokenCounter


def main() -> None:
    parser = argparse.ArgumentParser(prog="byod")
    parser.add_argument("--data-dir", type=Path, help="Override local application data directory")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create local data directories and database")
    serve = commands.add_parser("serve", help="Start BYOD on loopback")
    serve.add_argument("--port", type=int, default=0)
    serve.add_argument("--no-open", action="store_true")
    listing = commands.add_parser("ls", help="List workspaces or documents")
    listing.add_argument("workspace", nargs="?")
    add = commands.add_parser("add", help="Add files or folders; create workspace if needed")
    add.add_argument("workspace")
    add.add_argument("paths", nargs="+")
    debug = commands.add_parser("debug")
    debug_commands = debug.add_subparsers(dest="debug_command", required=True)
    for name in ("parse", "chunk"):
        subcommand = debug_commands.add_parser(name)
        subcommand.add_argument("file", type=Path)
    embedding = debug_commands.add_parser("embed")
    embedding.add_argument("text")
    search = debug_commands.add_parser("search")
    search.add_argument("workspace")
    search.add_argument("query")
    search.add_argument("--doc", type=int, action="append", dest="document_ids")
    search.add_argument("--type", dest="doc_type")
    llm = debug_commands.add_parser("llm")
    llm.add_argument("--provider", required=True, choices=["openai", "anthropic", "ollama"])
    llm.add_argument("--model")
    reindex = commands.add_parser("reindex", help="Re-index all documents in a workspace")
    reindex.add_argument("workspace")
    args = parser.parse_args()
    config = Config.resolve(args.data_dir)
    initialize(config)
    if args.command == "init":
        print(f"Initialized {config.database}")
    elif args.command == "ls":
        with connect(config) as db:
            if args.workspace:
                rows = db.execute(
                    "SELECT d.filename,d.status,d.chunk_count FROM documents d "
                    "JOIN workspaces w ON w.id=d.workspace_id WHERE w.name=?",
                    (args.workspace,),
                )
                print(json.dumps([dict(row) for row in rows], indent=2))
            else:
                print(json.dumps(list_workspaces(db), indent=2))
    elif args.command == "debug":
        if args.debug_command == "llm":
            provider = provider_for(args.provider, KeyStore().get(args.provider))
            models = provider.list_models()
            if not models:
                parser.error("No model available. Configure the provider and try again.")
            for token in provider.stream(
                [Message("user", "Reply with exactly OK.")],
                "Return one short line.",
                args.model or models[0],
            ):
                print(token, end="", flush=True)
            print()
            return
        if args.debug_command == "search":
            with connect(config) as db:
                row = db.execute(
                    "SELECT id FROM workspaces WHERE name=?", (args.workspace,)
                ).fetchone()
            if row is None:
                parser.error("Workspace not found")
            results = Retriever(config, Embedder(config)).search(
                int(row[0]), args.query, args.document_ids, args.doc_type
            )
            print(
                json.dumps(
                    [
                        {
                            "chunk_id": r.chunk_id,
                            "document_id": r.document_id,
                            "filename": r.filename,
                            "locator": r.locator,
                            "score": r.score,
                        }
                        for r in results
                    ],
                    indent=2,
                )
            )
            return
        if args.debug_command == "embed":
            vector = Embedder(config).embed([args.text])[0]
            print(json.dumps({"dimensions": len(vector), "norm": float((vector @ vector) ** 0.5)}))
            return
        blocks = parse(args.file)
        items = (
            blocks
            if args.debug_command == "parse"
            else chunk(blocks, blocks[0].doc_type, TokenCounter(config))
        )
        print(json.dumps([asdict(item) for item in items], indent=2, ensure_ascii=True))
    elif args.command in {"add", "reindex"}:
        with connect(config) as db:
            row = db.execute("SELECT id FROM workspaces WHERE name=?", (args.workspace,)).fetchone()
            workspace = int(row[0]) if row else create_workspace(db, args.workspace)
            paths = (
                args.paths
                if args.command == "add"
                else [
                    str(r[0])
                    for r in db.execute(
                        "SELECT path FROM documents WHERE workspace_id=?", (workspace,)
                    )
                ]
            )
        jobs = JobQueue(config, Embedder(config).index_document)
        try:
            identifier = jobs.submit(workspace, paths, reindex=args.command == "reindex")
            jobs.wait()
            result = jobs.snapshot(identifier)
            print(json.dumps(result, indent=2))
            if result and result["failed"]:
                raise SystemExit(1)
        finally:
            jobs.close()
    elif args.command == "serve":
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", args.port))
            port = sock.getsockname()[1]
            url = f"http://127.0.0.1:{port}"
            print(f"BYOD: {url}")
            timer = None
            if not args.no_open:
                timer = threading.Timer(1, webbrowser.open, args=(url,))
                timer.daemon = True
                timer.start()
            try:
                server = uvicorn.Server(
                    uvicorn.Config(
                        create_app(config),
                        host="127.0.0.1",
                        port=port,
                        access_log=False,
                    )
                )
                server.run(sockets=[sock])
            finally:
                if timer:
                    timer.cancel()


if __name__ == "__main__":
    main()
