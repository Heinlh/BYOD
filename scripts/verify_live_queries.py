"""Opt-in live local-provider acceptance. Prints case outcomes, never document text."""

import argparse
import json
import time
import uuid
from pathlib import Path

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:18765")
    parser.add_argument("--model", default="qwen3.6:latest")
    args = parser.parse_args()
    fixtures = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "queries"
    cases = json.loads((fixtures / "cases.json").read_text(encoding="utf-8"))["supported"]
    with httpx.Client(base_url=args.url, timeout=660, trust_env=False) as client:
        response = client.post(
            "/api/workspaces", json={"name": "Live acceptance " + uuid.uuid4().hex}
        )
        response.raise_for_status()
        workspace = response.json()["id"]
        try:
            response = client.post(
                f"/api/workspaces/{workspace}/documents", json={"paths": [str(fixtures)]}
            )
            response.raise_for_status()
            job = response.json()["job_id"]
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                status = client.get(f"/api/jobs/{job}").json()
                if status["state"] in {"done", "failed"}:
                    break
                time.sleep(0.5)
            if status["state"] != "done":
                raise RuntimeError("Live fixture ingestion failed")
            client.put(
                "/api/settings",
                json={
                    "workspace_id": workspace,
                    "provider": "ollama",
                    "model": args.model,
                },
            ).raise_for_status()
            documents = client.get(f"/api/workspaces/{workspace}/documents").json()
            for index in [0, 4, 8]:
                case = cases[index]
                document = next(d for d in documents if d["filename"] == case["filename"])
                chat = client.post(f"/api/workspaces/{workspace}/chats").json()["id"]
                started = time.monotonic()
                response = client.post(
                    f"/api/chats/{chat}/messages",
                    json={
                        "content": case["query"] + " Reply in one short sentence with a citation.",
                        "document_ids": [document["id"]],
                    },
                )
                response.raise_for_status()
                frames = [frame.splitlines() for frame in response.text.strip().split("\n\n")]
                last = frames[-1]
                if last[0] != "event: done":
                    raise RuntimeError(f"Live case {index} did not complete")
                data = json.loads(last[1][6:])
                citations = data["citations"]
                if not any(
                    c["filename"] == case["filename"] and c["locator"] == case["locator"]
                    for c in citations
                ):
                    raise RuntimeError(f"Live case {index} missing expected citation")
                messages = client.get(f"/api/chats/{chat}/messages").json()
                answer = messages[-1]["content"].lower()
                terms = {
                    0: ("wage", "earn", "pay"),
                    4: ("narrow", "reduc", "smaller"),
                    8: ("ttl", "cache", "cached"),
                }[index]
                if not any(term in answer for term in terms):
                    raise RuntimeError(f"Live case {index} missing expected fact")
                for citation in citations:
                    client.get(f"/api/chunks/{citation['chunk_id']}").raise_for_status()
                print(
                    json.dumps(
                        {
                            "case": index,
                            "format": document["doc_type"],
                            "passed": True,
                            "seconds": round(time.monotonic() - started, 1),
                        }
                    ),
                    flush=True,
                )
        finally:
            client.delete(f"/api/workspaces/{workspace}").raise_for_status()


if __name__ == "__main__":
    main()
