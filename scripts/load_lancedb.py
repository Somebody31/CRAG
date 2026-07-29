#!/usr/bin/env python3
"""
Load data/crag_corpus.jsonl into a local LanceDB table (text only, no embeddings).

Table: documents
URI:   data/lancedb/

Run: .venv/bin/python scripts/load_lancedb.py
"""
from __future__ import annotations

import json
from pathlib import Path

import lancedb
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "crag_corpus.jsonl"
DB_URI = ROOT / "data" / "lancedb"
TABLE = "documents"


def load_rows() -> list[dict]:
    rows = []
    with CORPUS.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            d = json.loads(line)
            # LanceDB-friendly flat types (nulls OK as None)
            rows.append({
                "id": d["id"],
                "cluster_id": d.get("cluster_id"),
                "role": d["role"],
                "title": d["title"],
                "content": d["content"],
                "date": d["date"],
                "validation_note": d.get("validation_note"),
                "contradiction_id": d.get("contradiction_id"),
                "version_chain_id": d.get("version_chain_id"),
                "version_number": d.get("version_number"),
                "fragment_group_id": d.get("fragment_group_id"),
            })
    return rows


def main() -> None:
    if not CORPUS.exists():
        raise SystemExit(f"Missing corpus: {CORPUS}")

    rows = load_rows()
    print(f"Loaded {len(rows)} docs from {CORPUS}")

    schema = pa.schema([
        ("id", pa.string()),
        ("cluster_id", pa.string()),
        ("role", pa.string()),
        ("title", pa.string()),
        ("content", pa.string()),
        ("date", pa.string()),
        ("validation_note", pa.string()),
        ("contradiction_id", pa.string()),
        ("version_chain_id", pa.string()),
        ("version_number", pa.int32()),
        ("fragment_group_id", pa.string()),
    ])

    DB_URI.mkdir(parents=True, exist_ok=True)
    db = lancedb.connect(str(DB_URI))

    # Drop/recreate for idempotent loads
    try:
        names = set(db.list_tables())
    except Exception:
        names = set(db.table_names())
    if TABLE in names:
        db.drop_table(TABLE)
        print(f"Dropped existing table {TABLE}")

    table = db.create_table(TABLE, data=rows, schema=schema)
    count = table.count_rows()
    print(f"Created {DB_URI} table={TABLE} rows={count}")
    print("Sample:", rows[0]["id"], "|", rows[0]["title"][:70])
    print("Done (text-only; add vector column when embedding model is chosen).")


if __name__ == "__main__":
    main()
