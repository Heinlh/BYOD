"""BYOD command-line entry point."""

import argparse
import json
import math
import socket
import statistics
import threading
import time
import uuid
import webbrowser
from collections.abc import Generator
from dataclasses import asdict
from pathlib import Path
from typing import cast

import uvicorn

from byod.app import create_app
from byod.config import Config
from byod.db.migrations import connect, initialize
from byod.db.queries import create_workspace, list_workspaces
from byod.index.embed import Embedder
from byod.ingest.chunk import chunk
from byod.ingest.jobs import JobQueue
from byod.ingest.normalize import parse
from byod.llm.base import Message, ProviderError
from byod.llm.chat import SYSTEM
from byod.llm.keys import KeyStore
from byod.llm.providers import provider_for
from byod.retrieve.search import Retriever
from byod.tokenize import TokenCounter


def bench(
    config: Config,
    workspace_id: int,
    query: str,
    document_ids: list[int] | None,
    runs: int,
    use_llm: bool,
) -> dict[str, object]:
    """Time the chat path phase by phase. Reports durations and counts, never text."""
    retriever = Retriever(config, Embedder(config))
    counter = TokenCounter(config)
    selection = config.preferences().selection(workspace_id)
    provider = None
    warmup = None
    errors: list[str] = []
    if use_llm and selection.provider and selection.model:
        provider = provider_for(selection.provider, KeyStore().get(selection.provider))
        started = time.perf_counter()
        # Load the model outside the timed runs so load and prefill are reported apart.
        warm = cast(
            Generator[str, None, None],
            provider.stream([Message("user", "Reply with exactly OK.")], "", selection.model),
        )
        try:
            next(warm, None)
        except ProviderError as exc:
            errors.append(exc.code)
        warm.close()
        warmup = round((time.perf_counter() - started) * 1000, 1)
    samples: dict[str, list[float]] = {}
    cold: dict[str, float] = {}
    counts: dict[str, int] = {}
    for run in range(runs + 1):  # Run 0 loads the embedder and tokenizer; reported as cold.
        stats: dict[str, float] = {}
        results = retriever.search(workspace_id, query, document_ids, stats=stats)
        started = time.perf_counter()
        context, included = retriever.context(results)
        stats["assembly"] = stats.get("hydrate", 0.0) + time.perf_counter() - started
        stats["retrieval"] = (
            stats.get("candidates", 0.0) + stats.get("search", 0.0) + stats["assembly"]
        )
        if run and provider and selection.model and included:
            # A per-run marker after the fixed system text keeps a provider's prefix cache
            # from hiding context prefill, as for a new question in a real chat.
            system = f"{SYSTEM}\n\nRun {uuid.uuid4().hex}\n\nEXCERPTS:\n{context}"
            started = time.perf_counter()
            tokens = cast(
                Generator[str, None, None],
                provider.stream([Message("user", query)], system, selection.model),
            )
            try:
                first = next(tokens, None)
                if first is not None:
                    stats["ttft"] = time.perf_counter() - started
            except ProviderError as exc:
                errors.append(exc.code)
                # A failed wait is a lower bound, not a successful first-token sample.
                stats["provider_failed_wait"] = time.perf_counter() - started
            tokens.close()
        counts = {
            "candidates": int(stats.get("candidate_count", 0)),
            "results": len(results),
            "chunks": len(included),
            "context_tokens": counter.count(context) if context else 0,
        }
        for phase in (
            "candidates", "embed", "search", "assembly", "retrieval", "ttft",
            "provider_failed_wait",
        ):
            if phase in stats and run:
                samples.setdefault(phase, []).append(stats[phase])
            elif phase in stats:
                cold[phase] = stats[phase]
    return {
        "runs": runs,
        "scope": "documents" if document_ids else "workspace",
        **counts,
        "provider": selection.provider if provider else None,
        "provider_warmup_ms": warmup,
        "provider_errors": errors,
        "cold_ms": {phase: round(value * 1000, 1) for phase, value in cold.items()},
        "ms": {
            phase: {
                "median": round(statistics.median(values) * 1000, 1),
                # Nearest-rank percentile; with few runs this is the slowest run.
                "p95": round(sorted(values)[math.ceil(0.95 * len(values)) - 1] * 1000, 1),
                "samples": len(values),
            }
            for phase, values in samples.items()
        },
    }


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
    timing = debug_commands.add_parser("bench", help="Phase latency; prints durations and counts")
    timing.add_argument("workspace")
    timing.add_argument("query")
    timing.add_argument("--doc", type=int, action="append", dest="document_ids")
    timing.add_argument("--runs", type=int, default=5)
    timing.add_argument("--no-llm", action="store_true", help="Skip provider time to first token")
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
        if args.debug_command in {"search", "bench"}:
            with connect(config) as db:
                row = db.execute(
                    "SELECT id FROM workspaces WHERE name=?", (args.workspace,)
                ).fetchone()
            if row is None:
                parser.error("Workspace not found")
        if args.debug_command == "bench":
            if args.runs < 1:
                parser.error("--runs must be at least 1")
            report = bench(
                config, int(row[0]), args.query, args.document_ids, args.runs, not args.no_llm
            )
            print(json.dumps(report, indent=2))
            return
        if args.debug_command == "search":
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
