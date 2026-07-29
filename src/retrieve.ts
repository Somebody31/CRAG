// LanceDB dense retrieval. Graph only sees retrieveSimilar.

import * as lancedb from "@lancedb/lancedb";
import { embedText } from "./embed.ts";
import type { RetrievedDoc } from "./types.ts";

const DEFAULT_DB = "data/lancedb";
const TABLE = "documents";
const DEFAULT_K = 6;

export type RetrieveOptions = {
  /** How many neighbors (default 6). */
  k?: number;
  /** Mark docs as coming from a correction re-query. */
  fromCorrection?: boolean;
  /** Override DB path (tests). */
  dbPath?: string;
};

function snippetFrom(content: string, max = 220): string {
  const oneLine = content.replace(/\s+/g, " ").trim();
  if (oneLine.length <= max) return oneLine;
  return oneLine.slice(0, max - 1) + "…";
}

/**
 * Embed query (or use provided vector) and return top-k docs from LanceDB.
 */
export async function retrieveSimilar(
  query: string,
  options: RetrieveOptions = {},
): Promise<RetrievedDoc[]> {
  const k = options.k ?? DEFAULT_K;
  const fromCorrection = options.fromCorrection ?? false;
  const dbPath = options.dbPath ?? process.env.LANCEDB_PATH ?? DEFAULT_DB;

  const vector = await embedText(query);
  const db = await lancedb.connect(dbPath);
  const table = await db.openTable(TABLE);

  const rows = await table.search(vector).limit(k).toArray();

  return rows.map((row) => {
    const r = row as Record<string, unknown>;
    const content = String(r.content ?? "");
    const title = String(r.title ?? "");
    // LanceDB may expose _distance for ANN results.
    const dist = r._distance;
    const score =
      typeof dist === "number" ? dist : dist == null ? null : Number(dist);

    return {
      id: String(r.id ?? ""),
      title,
      content,
      snippet: snippetFrom(content),
      score: Number.isFinite(score as number) ? (score as number) : null,
      clusterId: r.cluster_id == null ? null : String(r.cluster_id),
      role: r.role == null ? null : String(r.role),
      fromCorrection,
    };
  });
}

export type RetrieveSimilarFn = (
  query: string,
  options?: RetrieveOptions,
) => Promise<RetrievedDoc[]>;
