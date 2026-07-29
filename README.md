# CRAG — Corrective RAG (Phase 1)

Retrieve → grade → correct (rewrite + re-retrieve) → generate **or refuse**.

Stack (locked): **Bun · Hono · LangGraph.js · MiMo V2.5 · LanceDB · Qwen3-Embedding-0.6B**.

See [`AGENTS.md`](./AGENTS.md) for rules agents must follow.

## Quick start

### 1. Dependencies

```bash
bun install

# Embed server (Python + PyTorch / transformers)
python3 -m venv embed-server/.venv
embed-server/.venv/bin/pip install -r embed-server/requirements.txt
```

### 2. Environment

Copy `.env.example` → `.env` and set `MIMO_API_KEY`.

### 3. Embedding server

```bash
# First run downloads Qwen/Qwen3-Embedding-0.6B (~1GB+)
embed-server/.venv/bin/python embed-server/server.py
# → http://127.0.0.1:8090/v1/embeddings
```

### 4. Ingest corpus into LanceDB (with vectors)

```bash
bun run ingest
# reads data/crag_corpus.jsonl → data/lancedb table `documents`
```

### 5. API + UI

```bash
bun run dev
# UI   http://127.0.0.1:5173/crag.html
# API  POST http://127.0.0.1:5173/api/query
#      body: { "query": "How do I install the Pulse Web SDK?" }
```

Demo mock UI (no backend): `http://127.0.0.1:5173/crag.html?mock=1`

## API

`POST /api/query`

```json
{ "query": "What is the Growth plan REST rate limit?" }
```

Response concepts:

| Field | Meaning |
|-------|---------|
| `status` | `answered` \| `refused` \| `error` |
| `documents[]` | Retrieved docs with `grade` |
| `rewrites` | Query rewrites from the correct path |
| `answer` / `refusal` | Final text |
| `stages` | Trace of retrieve / grade / correct / generate / refuse |

Weak evidence after max **2** correction attempts → **`refused`** (no degraded answer).

## Layout

```text
src/
  index.ts       Hono entry + /api/query
  pipeline.ts    whole CRAG run (start here)
  llm.ts         MiMo chat
  embed.ts       local Qwen3 HTTP client
  retrieve.ts    LanceDB top-k=6
  decide.ts      grades → strong|weak
  ingest.ts      JSONL → vectors → LanceDB
embed-server/    local embedding HTTP server
data/crag_corpus.jsonl
crag.html
tests/
```

Code style: plain functions, no factories/DI (see `AGENTS.md`).

## Tests

```bash
bun test tests/decide.test.ts tests/pipeline.test.ts   # pure helpers
node tests/crag-ui.test.mjs                            # UI static + smoke (mock mode)
```

## Pipeline (Phase 1)

1. **Retrieve** — dense ANN, k=6  
2. **Grade** — each doc `relevant` | `ambiguous` | `irrelevant` (MiMo)  
3. **Decide** — strong if `(relevant≥1 ∧ irrelevant=0) ∨ relevant≥2`  
4. **Correct** — rewrite → re-retrieve LanceDB only (no web)  
5. **Generate** or **Refuse** after at most 2 corrections  

Phase 2 (agentic tool loop) is **out of scope** until Phase 1 is done and evaluated.
