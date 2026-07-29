// Load data/crag_corpus.jsonl → embed with local Qwen3 → LanceDB table `documents`.

import { readFileSync } from "node:fs";
import * as lancedb from "@lancedb/lancedb";
import { embedTexts } from "../embed.ts";
import type { CorpusDoc } from "../types.ts";

const CORPUS_PATH = process.env.CORPUS_PATH || "data/crag_corpus.jsonl";
const DB_PATH = process.env.LANCEDB_PATH || "data/lancedb";
const TABLE = "documents";
const BATCH = Number(process.env.EMBED_BATCH || 8);

function readCorpus(path: string): CorpusDoc[] {
  const raw = readFileSync(path, "utf8");
  const docs: CorpusDoc[] = [];
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed) continue;
    const d = JSON.parse(trimmed) as Record<string, unknown>;
    docs.push({
      id: String(d.id),
      cluster_id: d.cluster_id == null ? null : String(d.cluster_id),
      role: String(d.role ?? "canonical"),
      title: String(d.title ?? ""),
      content: String(d.content ?? ""),
      date: String(d.date ?? ""),
      validation_note:
        d.validation_note == null ? null : String(d.validation_note),
      contradiction_id:
        d.contradiction_id == null ? null : String(d.contradiction_id),
      version_chain_id:
        d.version_chain_id == null ? null : String(d.version_chain_id),
      version_number:
        typeof d.version_number === "number" ? d.version_number : null,
      fragment_group_id:
        d.fragment_group_id == null ? null : String(d.fragment_group_id),
    });
  }
  return docs;
}

function embedInput(doc: CorpusDoc): string {
  return `${doc.title}\n\n${doc.content}`;
}

async function main() {
  console.log(`Reading ${CORPUS_PATH}`);
  const docs = readCorpus(CORPUS_PATH);
  console.log(`Loaded ${docs.length} documents`);

  if (docs.length === 0) {
    throw new Error("Corpus is empty");
  }

  console.log("Probing embed server…");
  const [probe] = await embedTexts([embedInput(docs[0])]);
  const dim = probe.length;
  console.log(`Embedding dim=${dim}`);

  const rows: Record<string, unknown>[] = [];

  for (let i = 0; i < docs.length; i += BATCH) {
    const batch = docs.slice(i, i + BATCH);
    const texts = batch.map(embedInput);
    console.log(
      `Embedding ${i + 1}–${Math.min(i + BATCH, docs.length)} / ${docs.length}`,
    );
    const vectors = await embedTexts(texts);
    for (let j = 0; j < batch.length; j++) {
      const d = batch[j];
      rows.push({
        id: d.id,
        cluster_id: d.cluster_id,
        role: d.role,
        title: d.title,
        content: d.content,
        date: d.date,
        validation_note: d.validation_note,
        contradiction_id: d.contradiction_id,
        version_chain_id: d.version_chain_id,
        version_number: d.version_number,
        fragment_group_id: d.fragment_group_id,
        vector: vectors[j],
      });
    }
  }

  console.log(`Writing LanceDB ${DB_PATH} table=${TABLE}`);
  const db = await lancedb.connect(DB_PATH);
  try {
    await db.dropTable(TABLE);
    console.log(`Dropped existing table ${TABLE}`);
  } catch {
    // table may not exist
  }

  await db.createTable(TABLE, rows);
  const table = await db.openTable(TABLE);
  const count = await table.countRows();
  console.log(`Done. rows=${count} dim=${dim}`);
  console.log(`Sample: ${rows[0].id} | ${String(rows[0].title).slice(0, 70)}`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
