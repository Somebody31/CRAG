# CRAG

Corrective retrieval-augmented generation: retrieve documents, grade relevance, rewrite and re-retrieve when evidence is weak, then answer — or refuse when the knowledge base cannot support a confident response.

**Stack:** Bun · Hono · LangGraph.js · DeepSeek V4 Flash · LanceDB · Qwen3-Embedding-0.6B  
**UI:** `crag.html` (served by the same process as the API)  
**Start here:** [`src/pipeline.ts`](src/pipeline.ts) · Agent rules: [`AGENTS.md`](AGENTS.md)

## How it works

```
query → retrieve (k=6) → grade each doc → decide
              ↑                              │
              └── rewrite + re-retrieve ─────┤  (max 2 corrections)
                                             ↓
                                    strong → generate
                                    weak   → refuse
```

| Stage | Behavior |
|-------|----------|
| Retrieve | Dense ANN over LanceDB (query embedded with Qwen3) |
| Grade | DeepSeek labels each doc `relevant` / `ambiguous` / `irrelevant` |
| Decide | Strong if ≥1 relevant and 0 irrelevant, or ≥2 relevant |
| Correct | LLM rewrites the query; search LanceDB again (files only — no web) |
| Generate / refuse | Answer from relevant + ambiguous sources, or refuse after 2 weak rounds |

## Setup

```bash
bun install

# Local embedding server (first run downloads ~0.6B model weights)
python3 -m venv embed-server/.venv
embed-server/.venv/bin/pip install -r embed-server/requirements.txt

cp .env.example .env
# set DEEPSEEK_API_KEY=
```

## Run

Use three terminals (or background processes):

```bash
# 1) Embeddings — http://127.0.0.1:8090
bun run embed-server

# 2) Index the corpus (once, or after corpus changes)
bun run ingest

# 3) API + UI — http://127.0.0.1:5173
bun run dev
```

| URL | Purpose |
|-----|---------|
| http://127.0.0.1:5173/crag.html | Chat UI (live backend) |
| http://127.0.0.1:5173/crag.html?mock=1 | UI-only demo (no backend) |
| `GET /health` | Liveness |

## API

```bash
curl -s http://127.0.0.1:5173/api/query \
  -H 'content-type: application/json' \
  -d '{"query":"How do I install the Pulse Web SDK?"}'
```

| Field | Description |
|-------|-------------|
| `status` | `answered` · `refused` · `error` |
| `documents` | Retrieved docs with relevance grades |
| `rewrites` | Query rewrites from the correction path |
| `answer` / `refusal` | Final text |
| `stages` | Pipeline trace |

Refused answers use HTTP 200 with `status: "refused"`. Hard failures return 500.

## Project layout

```text
src/
  pipeline.ts    CRAG graph (entry for the run)
  index.ts       HTTP server
  llm.ts         DeepSeek
  embed.ts       Local embedding client
  retrieve.ts    LanceDB search
  decide.ts      Strong / weak aggregation
  ingest.ts      Corpus → vectors → LanceDB
embed-server/    Qwen3-Embedding-0.6B HTTP service
data/            Northline Pulse corpus (JSONL)
crag.html        UI
tests/
```

## Tests

```bash
bun test          # decide + routing helpers
bun run test:ui   # static UI contracts + browser smoke (mock mode)
```

## Data

The default corpus is a fictional B2B product knowledge base (**Northline Pulse**): ~400 documents and labeled query categories for later eval. Optional regeneration: `scripts/generate_crag_eval_llm.py` (DeepSeek).

## Scope

Phase 1 is a local baseline pipeline. Agentic tool-calling, remote deploy, and a full eval harness are intentionally deferred — see [`AGENTS.md`](AGENTS.md).
