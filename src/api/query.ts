// POST /api/query handler.

import type { Context } from "hono";
import { runCrag } from "../graph/pipeline.ts";

export async function handleQuery(c: Context) {
  let body: unknown;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'Body must be JSON { "query": "..." }' }, 400);
  }

  const query =
    body &&
    typeof body === "object" &&
    "query" in body &&
    typeof (body as { query: unknown }).query === "string"
      ? (body as { query: string }).query
      : null;

  if (query === null || query.trim() === "") {
    return c.json({ error: 'Body must be { "query": "..." }' }, 400);
  }

  try {
    const result = await runCrag(query.trim());
    // Always HTTP 200 for answered/refused; 500 only for hard errors.
    if (result.status === "error") {
      return c.json(result, 500);
    }
    return c.json(result, 200);
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return c.json(
      {
        status: "error",
        query: query.trim(),
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
}
