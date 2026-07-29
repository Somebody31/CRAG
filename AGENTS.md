# AGENTS.md — Corrective RAG (CRAG)

## What this project is

A Corrective RAG system: **retrieve → grade relevance → correct (rewrite + re-retrieve) when retrieval is weak → generate or refuse**. Portfolio project, built for depth of understanding, not breadth of features.

**Phase 1** is a working baseline pipeline (local).  
**Phase 2** (agentic tool-calling loop) is **strictly sequenced after Phase 1 is complete and evaluated** — do not start Phase 2 work, and do not suggest merging the two, until told otherwise.

---

## Phase rules

### Phase 1 is “done” when

1. End-to-end path works on a few **manual** queries (real LanceDB + local embeddings + MiMo), and  
2. Graph logic is **unit tested** with mocked LLM / retrieve / embed (no live services required for unit tests).

Do **not** block Phase 1 on a full gold-label eval harness or on finishing the incomplete LLM corpus generator.

### Phase 1 environment

- **Local-only.** Bun API + local Qwen3 embedding HTTP server + on-disk LanceDB.
- **GCP Cloud Run** is the eventual deploy target — do not require deploy for Phase 1 done.
- **Upstash Redis** is on the stack list for later (cache / rate limit / run state). **Do not wire Upstash in Phase 1.**

### Phase 2

Forbidden until Phase 1 is complete **and** evaluated, and you are explicitly told to start.

---

## Stack (locked — do not substitute)

| Concern | Choice |
|--------|--------|
| Runtime | **Bun** |
| Web framework | **Hono** |
| Orchestration | **LangGraph.js** |
| LLM | **MiMo V2.5** (chat/completions via OpenAI-compatible HTTP / `fetch`) |
| Embeddings | **Qwen3-Embedding-0.6B** via a **local HTTP embed server**; Bun calls it with `fetch` |
| Vector store | **LanceDB** (dense vectors only in Phase 1) |
| Cache/queue | **Upstash Redis** — listed only; **not used in Phase 1** |
| Deploy target | **GCP Cloud Run** — later; not a Phase 1 gate |
| Language | **TypeScript** |

Do not introduce a different framework, ORM, vector DB, embedding model family, or LLM provider without explicit sign-off, even if it seems like a strict improvement.

Prefer **`fetch`** over a heavy SDK wrapper when a plain HTTP call works (MiMo, embed server).

---

## Existing assets (do not throw away blindly)

| Asset | Phase 1 role |
|-------|----------------|
| `crag.html` | Keep. Replace the **mock** pipeline with real `POST /api/query`. |
| `data/crag_corpus.jsonl` | Source corpus for ingest (one row per doc). |
| `data/crag_queries.jsonl` | Optional later eval; not required for Phase 1 done. |
| `data/lancedb/` | Rebuilt by **TS ingest** with a real vector column. |
| `scripts/*.py` | Legacy data tooling. **Archive** (move aside / keep in git history) once TS ingest works — **do not hard-delete** without asking. Incomplete MiMo corpus generator stays available only via archive/history until gold labels are revisited. |

---

## Directory layout (Phase 1)

Plain, flat-ish `src/`. One concern per file. No multi-package monorepo.

```text
AGENTS.md
README.md                 # run instructions (update when implementing)
crag.html                 # UI
data/
  crag_corpus.jsonl
  crag_queries.jsonl
  lancedb/                # LanceDB table(s)
src/
  index.ts                # Bun entry — mount Hono
  types.ts                # shared narrow types
  llm.ts                  # MiMo chat (narrow functions)
  embed.ts                # call local Qwen3 HTTP embed server
  retrieve.ts             # LanceDB dense top-k
  decide.ts               # pure: grades → strong | weak
  api/
    query.ts              # POST /api/query handler
  graph/
    ...                   # LangGraph nodes + graph assembly
  ingest/
    load.ts               # JSONL → embed → LanceDB
tests/                    # graph unit tests with mocks
```

Optional later: a small `embed-server/` or documented one-liner to run Qwen3-Embedding-0.6B as HTTP. Pick the concrete server (TEI, sentence-transformers, etc.) on **first implement** — not a reason to stall AGENTS.

### Naming (ports-and-adapters idea, plain names)

- Mentally treat `llm.ts` / `embed.ts` / `retrieve.ts` as **ports**: graph code depends on **narrow function signatures**, not SDK types.
- **Do not** create `*Adapter` classes, DI containers, or factory theater.
- Prefer: `completeChat(...)`, `embedTexts(...)`, `retrieveSimilar(...)`.

---

## Phase 1 pipeline (baseline)

Treat node boundaries as refinable, but **behavior** is locked:

1. **Retrieve** — embed the user query (local Qwen3 HTTP) → LanceDB dense ANN → **top-k = 6**.
2. **Grade** — LLM grades **each** of the 6 docs as `relevant` | `ambiguous` | `irrelevant` (plus short reason optional).
3. **Decide** — aggregate grades (see rule below) → `strong` or `weak`.
4. **Correct** (only if weak) — **rewrite the query** (LLM) → **re-retrieve LanceDB only** (same k=6). **No web search in Phase 1.**
5. **Re-grade / re-decide** after each correction.
6. **Generate** if strong; **Refuse** if still weak after max corrections.

### Correction limits

- **Max correction attempts: 2** (aligns with prior UI `MAX_CORRECTION_ATTEMPTS`).
- Correction = rewrite + re-retrieve files in LanceDB. No external web, no multi-index.

### Decide aggregation (locked default)

Given the multiset of labels for the current doc set:

| Outcome | Rule |
|--------|------|
| **Strong** | At least **one** `relevant` and **zero** `irrelevant` (ambiguous allowed), **or** ≥ **two** `relevant` (even if some irrelevant — rare edge; prefer the first clause when possible). Prefer implementing as: `relevantCount >= 1 && irrelevantCount === 0` **OR** `relevantCount >= 2`. |
| **Weak** | Everything else, including **zero documents**. |

### After final attempt still weak

- **Do not** produce a degraded “best effort” answer.
- Return **`status: "refused"`** with a short **“I don’t know” / cannot answer from the knowledge base** style message, and **still return graded sources** so the UI can show what was retrieved.

### Conversation

- **Single-turn only** in Phase 1. API body is the current query string. Ignore multi-turn history / UI context toggle until a later phase.

### Retrieval mode

- **Dense vector only** (Qwen3 query embedding → ANN).
- No hybrid BM25/FTS in Phase 1. Revisit only after baseline eval if entity recall is weak.

### Chunking / ingest

- **One LanceDB row per source document** (no sub-chunking).
- Embed a single text per doc: prefer `title + "\n\n" + content` (or equivalent).
- Preserve useful metadata on the row: `id`, `cluster_id`, `role`, `title`, `content`, `date`, chain/fragment/contradiction ids as present in JSONL.

---

## API contract (Phase 1)

**`POST /api/query`**

Request:

```json
{ "query": "string" }
```

Response (shape may grow fields, but keep these concepts):

```json
{
  "status": "answered" | "refused" | "error",
  "query": "…",
  "rewrites": ["…"],
  "correctionAttempts": 0,
  "documents": [
    {
      "id": "…",
      "title": "…",
      "snippet": "…",
      "grade": "relevant" | "ambiguous" | "irrelevant",
      "fromCorrection": false
    }
  ],
  "answer": "markdown or plain text when status=answered",
  "refusal": "short message when status=refused",
  "stages": [
    { "name": "retrieve" | "grade" | "correct" | "generate" | "refuse", "ok": true }
  ]
}
```

- **No SSE / streaming** in Phase 1. One JSON response after the graph finishes.
- Cancel mid-flight can wait until streaming exists; not required for Phase 1 done.

---

## UI contract (`crag.html`)

When wiring the real backend:

1. Call **`POST /api/query`** instead of the mock stage machine for the primary path.
2. Replace the **degraded generate** path with a **refuse** state (message + sources).
3. **Single-turn**: hide or ignore conversation-context toggle for Phase 1.
4. Keep the existing stage labels conceptually: retrieving → grading → correcting → generating / refused.
5. Mock scenario keyword routing (`timeout`, `degraded`, etc.) is **demo legacy** — do not preserve it as product behavior once the backend is real.

Static file serving can stay simple (Bun/Hono static or separate `python -m http.server` during transition). Prefer eventually serving UI from the same Hono app for one-port local demos.

---

## Architecture rules

- **LangGraph.js** owns control flow (retrieve / grade / decide / correct / generate / refuse).
- Graph nodes call **only** narrow helpers from `llm.ts`, `embed.ts`, `retrieve.ts`, `decide.ts`.
- Graph nodes must **not** import LanceDB client types, MiMo SDK types, or embed-server client types directly.
- **Plain functions** over classes. Minimal dependencies.
- No speculative generality. Build what Phase 1 needs.

### LLM usage (MiMo V2.5)

Typical calls in Phase 1:

| Call | Purpose |
|------|---------|
| Grade | Per-doc (or batched carefully) relevance label |
| Rewrite | Produce a retrieval-oriented rewrite of the user query |
| Generate | Final answer grounded **only** in kept sources |
| Refuse | Optional: fixed template is fine; no need for an LLM call |

Use structured output or strict JSON parsing with a small repair/retry — keep it simple.

### Embeddings (local)

- Model: **Qwen3-Embedding-0.6B**.
- Bun **never** loads the model in-process.
- Local HTTP server exposes embeddings; `embed.ts` uses `fetch`.
- Same embed path for **ingest** and **query** (must match).

---

## Testing / eval

### Required for Phase 1

- Unit tests for graph / decide with **mocked** `completeChat`, `embedTexts`, `retrieveSimilar`.
- A handful of **manual** E2E queries against real services.

### After Phase 1 baseline works

- Eval harness in the spirit of the Multi-Agent project (grading accuracy, correction trigger precision/recall, answer quality) — **do not over-build before the baseline pipeline works end-to-end**.
- Gold labels on `crag_queries.jsonl` are desirable later; live queries today may lack production gold fields — that is OK for Phase 1.

---

## What NOT to do

- Don’t start the **Phase 2** tool-calling loop before Phase 1 is done and evaluated.
- Don’t add **LangSmith / Langfuse** (or similar) tracing yet.
- Don’t add **web search** as a correction fallback in Phase 1.
- Don’t wire **Upstash** in Phase 1.
- Don’t require **Cloud Run** deploy for Phase 1 done.
- Don’t add **SSE/streaming**, multi-turn memory, or hybrid FTS unless Phase 1 is done and you are asked.
- Don’t reopen CRAG-vs-other-project-idea.
- Don’t substitute stack pieces without sign-off.
- Don’t introduce Adapter/Factory/DI class hierarchies for one call site.
- Don’t hard-delete `scripts/` — **archive** after TS ingest works.
- Don’t build a large eval framework before the pipeline runs E2E.

---

## Closed decisions (former open items)

| Topic | Decision |
|-------|----------|
| Layout | `src/` as above |
| Chunking | One row per source doc |
| Correction fallback | Rewrite → re-retrieve LanceDB only (files) |
| Embeddings | Qwen3-Embedding-0.6B, local HTTP, Bun `fetch` |
| top-k | 6, grade all |
| Weak evidence policy | Refuse + show sources (not degraded answer) |
| UI | Real API; refuse replaces degraded |
| API | Single JSON `POST /api/query` |
| Conversation | Single-turn |
| Upstash | Listed; not Phase 1 |
| Deploy | Local Phase 1; Cloud Run later |
| Python scripts | Archive after TS ingest |
| Phase 1 done | Manual E2E + mocked unit tests |

---

## Still open — ask before assuming

These are deliberately **not** locked; confirm with Sathwik on first implement:

1. **Exact local embed server recipe** (TEI vs sentence-transformers vs other) and port/URL env vars.  
2. **Refusal copy** and whether refused requests use HTTP 200 + `status: "refused"` (recommended) vs a non-2xx.  
3. **MiMo base URL / model id env names** (mirror existing `.env` style where sensible; do not invent a second secrets pattern).  
4. **Whether generate may use only `relevant` docs** vs `relevant` + `ambiguous` (recommend: **relevant + ambiguous**, never `irrelevant`).  
5. **GitHub remote / repo init** when first committing the TS stack.

---

## Build philosophy (reminder)

- Small, reviewable steps. One concern per change.
- Minimal dependencies. Prefer `fetch` and plain functions.
- No speculative generality. Build what the current phase needs.
- When in doubt: match this file over older README claims (e.g. “pipeline is simulated”, “web search correction”, “degraded answer”). Update README when implementing so humans are not misled.
