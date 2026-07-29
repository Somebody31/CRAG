// Dense top-k search in LanceDB.

import * as lancedb from "@lancedb/lancedb";
import { embedText } from "./embed.ts";
import type { RetrievedDoc } from "./types.ts";

const DEFAULT_DB = "data/lancedb";
const TABLE = "documents";

export type RetrieveOptions = {
  k?: number;
  fromCorrection?: boolean;
  dbPath?: string;
};

function makeSnippet(content: string): string {
  const oneLine = content.replace(/\s+/g, " ").trim();
  if (oneLine.length <= 220) return oneLine;
  return oneLine.slice(0, 219) + "…";
}

/** Embed the query and return the nearest documents. */
export async function retrieveSimilar(
  query: string,
  options: RetrieveOptions = {},
): Promise<RetrievedDoc[]> {
  const k = options.k ?? 6;
  const fromCorrection = options.fromCorrection ?? false;
  const dbPath = options.dbPath ?? process.env.LANCEDB_PATH ?? DEFAULT_DB;

  const vector = await embedText(query);
  const db = await lancedb.connect(dbPath);
  const table = await db.openTable(TABLE);
  const rows = await table.search(vector).limit(k).toArray();

  const docs: RetrievedDoc[] = [];
  for (const row of rows) {
    const r = row as Record<string, unknown>;
    const content = String(r.content ?? "");
    const title = String(r.title ?? "");
    let score: number | null = null;
    if (typeof r._distance === "number") {
      score = r._distance;
    }

    docs.push({
      id: String(r.id ?? ""),
      title: title,
      content: content,
      snippet: makeSnippet(content),
      score: score,
      clusterId: r.cluster_id == null ? null : String(r.cluster_id),
      role: r.role == null ? null : String(r.role),
      fromCorrection: fromCorrection,
    });
  }
  return docs;
}
