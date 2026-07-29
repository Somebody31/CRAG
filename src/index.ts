// Bun entry: Hono API + static UI (crag.html).

import { Hono } from "hono";
import { cors } from "hono/cors";
import { serveStatic } from "hono/bun";
import { handleQuery } from "./api/query.ts";

const app = new Hono();

app.use(
  "*",
  cors({
    origin: "*",
    allowMethods: ["GET", "POST", "OPTIONS"],
  }),
);

app.get("/health", (c) =>
  c.json({
    ok: true,
    phase: 1,
    service: "crag",
  }),
);

app.post("/api/query", handleQuery);

// Root → UI
app.get("/", (c) => c.redirect("/crag.html"));

// Static files from project root (crag.html, etc.)
app.use("/*", serveStatic({ root: "./" }));

const port = Number(process.env.PORT || 5173);

console.log(`CRAG Phase 1 listening on http://127.0.0.1:${port}`);
console.log(`  UI    http://127.0.0.1:${port}/crag.html`);
console.log(`  POST  http://127.0.0.1:${port}/api/query`);
console.log(`  GET   http://127.0.0.1:${port}/health`);

export default {
  port,
  fetch: app.fetch,
};
