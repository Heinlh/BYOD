# Whole-workspace latency investigation

The benchmark separates candidate resolution, query embedding, vector search,
context assembly, and provider time to first token. Reports contain counts and
durations, never queries or document/context text. Failed provider waits are not
successful TTFT samples. Cold embedding/tokenizer initialization and provider
warm-up are reported separately.

## Reproduce

```sh
uv run --no-sync python scripts/bench_scale.py build
uv run --no-sync python scripts/bench_scale.py run --runs 20
uv run --no-sync python scripts/bench_scale.py run --runs 1 --cases 7 --llm qwen3.6:latest
byod --data-dir <tier-directory> debug bench bench "<query>" --runs 20 --no-llm
```

The default corpus embeds at least 5,000 real-shaped chunks, then replicates
indexed documents and their actual vectors to reach 25,000. The resulting tiers
contain 1,189, 5,061, and 25,265 chunks. They include the labeled query fixtures.
Copies exercise storage/filtering scale but are not 25,000 distinct semantic
passages. Use `build --real-chunks 25000` for a fully embedded corpus. Build output
belongs to the benchmark cache; it does not modify the user's course library.

## Before: retrieval

Recorded on 2026-09-13, CPU-only i7-1270P laptop, approximately 32 GB RAM.
Three labeled cases (0, 3, 7), 20 measured repetitions per cell, provider unloaded.
Each cell shows median of query medians / worst query p95, in milliseconds.
Retrieval excludes query embedding and provider time.

| Chunks | Scope | Candidates | Embedding | Search | Assembly | Retrieval |
|---|---|---:|---:|---:|---:|---:|
| 1,189 | Workspace | 7.0 / 16.8 | 9.8 / 34.7 | 6.8 / 15.9 | 134.8 / 439.1 | 148.7 / 471.9 |
| 1,189 | Document | 5.5 / 7.8 | 9.8 / 13.0 | 5.5 / 8.1 | 24.2 / 36.5 | 36.2 / 53.1 |
| 5,061 | Workspace | 25.2 / 44.8 | 22.9 / 50.1 | 36.4 / 67.7 | 301.1 / 711.9 | 363.5 / 753.4 |
| 5,061 | Document | 8.7 / 11.4 | 12.9 / 16.0 | 17.6 / 23.8 | 30.6 / 106.5 | 56.7 / 169.4 |
| 25,265 | Workspace | 110.5 / 237.5 | 30.5 / 71.8 | 205.9 / 596.2 | 395.7 / 727.6 | 734.3 / 1270.5 |
| 25,265 | Document | 30.1 / 215.3 | 28.6 / 133.2 | 152.5 / 434.1 | 48.1 / 261.3 | 230.4 / 763.3 |

Assembly dominates retrieval in this baseline. Candidate resolution enumerates
chunk IDs twice. Filtered sqlite-vec searches still grow with total index size.
Workspace context medians are 6,886 / 7,555 / 7,415 tokens; document context median
is 154 tokens at each size. These are embedding-tokenizer counts, not exact counts
for the selected reasoning model.

## Provider measurement

The selected local Ollama model is qwen3.6:latest, 36B Q4_K_M, approximately 23 GB
loaded, no GPU offload. One measured repetition of case 7 per size/scope is a
diagnostic observation, not a statistically meaningful tail-latency estimate.
The benchmark varies a marker before the context to avoid a reused prefix hiding
prompt processing. Source retrieval measurements under the loaded model are
memory-contended and must not be compared to the unloaded retrieval table.

| Chunks | Workspace context tokens | Workspace TTFT | Document context tokens | Document TTFT |
|---|---:|---:|---:|---:|
| 1,189 | 7,777 | 429.4 s | 415 | 39.8 s |
| 5,061 | 7,948 | Timeout; interrupted sample | 415 | 42.5 s |
| 25,265 | 7,982 | Timeout; interrupted sample | 415 | 48.1 s |

The run spanned a host interruption: a requested 45-second wait lasted 13,989.5
seconds. The raw failed waits (3,176.5 s and 14,163.6 s) are invalid as prefill
measurements. The exact interruption cause could not be verified from system
power events. Do not present these failures as successful TTFT or meaningful p95.

## Status and required next measurement

Stage 0 is incomplete: repeat the 5k/25k whole-workspace provider probes with
uninterrupted host uptime. No latency fix has been applied, so there is no
after-change table or claimed acceptance-target pass. At 25k, the unloaded
734.3 ms retrieval median exceeds the 150 ms target. Workspace/document retrieval
ratios are approximately 4.1, 6.4, and 3.2 at the three sizes.

The successful 1k provider pair identifies context volume as the first candidate
for Fix A; it does not justify changing vector search while provider processing
dominates. The relevance threshold remains 0.70. Parsers, normalization, chunking,
provider implementation, and data schema have not been changed for this task.

The spec's CLI appendix should eventually document `debug bench`. Retrieval
section 7.1 needs no amendment until a measured context-policy fix is implemented.

Verification on 2026-09-14: `pytest -q` passed all 38 tests in 54.36 seconds,
including the 15 labeled retrieval/rejection cases and metadata filters;
`ruff check .` passed; `mypy .` passed on 57 files. The benchmark timeout regression
uses real ingestion and mocks only the provider. `git diff --check` passed.
