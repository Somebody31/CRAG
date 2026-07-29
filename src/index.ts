// HTTP API (Hono) + static UI.
//
//   GET  /health      → { ok: true }
//   POST /api/query   → run CRAG for one question
//   GET  /crag.html   → UI

import { Hono } from "hono";
import { serveStatic } from "hono/bun";
import { runCrag } from "./pipeline.ts";

const app = new Hono();

app.get("/health", (c) => {
  return c.json({ ok: true, phase: 1, service: "crag" });
});

app.post("/api/query", async (c) => {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'Body must be JSON { "query": "..." }' }, 400);
  }

  if (!body || typeof body !== "object") {
    return c.json({ error: 'Body must be { "query": "..." }' }, 400);
  }

  const queryValue = (body as { query?: unknown }).query;
  if (typeof queryValue !== "string" || queryValue.trim() === "") {
    return c.json({ error: 'Body must be { "query": "..." }' }, 400);
  }

  const query = queryValue.trim();

  try {
    const result = await runCrag(query);
    if (result.status === "error") {
      return c.json(result, 500);
    }
    // answered and refused both use HTTP 200
    return c.json(result, 200);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return c.json(
      {
        status: "error",
        query: query,
        rewrites: [],
        correctionAttempts: 0,
        documents: [],
        answer: null,
        refusal: null,
        stages: [],
        error: message,
      },
      500,
    );
  }
});

app.get("/", (c) => c.redirect("/crag.html"));
app.use("/*", serveStatic({ root: "./" }));

const port = Number(process.env.PORT || 5173);

console.log("CRAG Phase 1 listening on http://127.0.0.1:" + port);
console.log("  UI    http://127.0.0.1:" + port + "/crag.html");
console.log("  POST  http://127.0.0.1:" + port + "/api/query");

export default {
  port: port,
  fetch: app.fetch,
};
