#!/usr/bin/env python3
"""Validate live CRAG eval JSONL (production schema with gold labels)."""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "data" / "crag_corpus.jsonl"
QUERIES = ROOT / "data" / "crag_queries.jsonl"

FORBIDDEN_PAD = re.compile(
    r"(##\s*Ownership and review|##\s*How to use this guidance|"
    r"This page is owned by the responsible Northline team)",
    re.I,
)
VALID_ACTIONS = {"none", "rewrite", "refine", "discard"}
VALID_CATS = {
    "easy", "ambiguous_distractor_prone", "versioned", "multi_hop",
    "contradiction_aware", "unanswerable", "multi_cluster",
}


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def validate_corpus(docs: list[dict]) -> list[str]:
    errors: list[str] = []
    ids = [d["id"] for d in docs]
    if len(ids) != len(set(ids)):
        errors.append("duplicate document ids")
    clusters = {d["cluster_id"] for d in docs if d.get("cluster_id")}
    if len(clusters) < 30:
        errors.append(f"only {len(clusters)} clusters (want ≥30)")
    if len(docs) < 250:
        errors.append(f"only {len(docs)} docs (want ≥250 for production)")

    by_vc: dict[str, list] = defaultdict(list)
    by_cx: dict[str, list] = defaultdict(list)
    by_fg: dict[str, list] = defaultdict(list)
    for d in docs:
        if d.get("version_chain_id"):
            by_vc[d["version_chain_id"]].append(d)
        if d.get("contradiction_id"):
            by_cx[d["contradiction_id"]].append(d)
        if d.get("fragment_group_id"):
            by_fg[d["fragment_group_id"]].append(d)

    for vc, members in by_vc.items():
        ordered = sorted(members, key=lambda x: (x.get("version_number") or 0, x.get("date") or ""))
        if [m["date"] for m in ordered] != sorted(m["date"] for m in ordered):
            errors.append(f"version chain {vc} date order mismatch")
        if ordered and ordered[-1].get("role") != "canonical":
            errors.append(f"version chain {vc} latest not canonical")
    for cx, members in by_cx.items():
        if len(members) < 2:
            errors.append(f"contradiction {cx} has <2 docs")
    for fg, members in by_fg.items():
        if len(members) < 2:
            errors.append(f"fragment {fg} has <2 docs")

    pad_n = sum(1 for d in docs if FORBIDDEN_PAD.search(d.get("content") or ""))
    if pad_n:
        errors.append(f"{pad_n} docs contain forbidden boilerplate padding")

    short = [d["id"] for d in docs if len((d.get("content") or "").split()) < 100]
    if short:
        errors.append(f"{len(short)} docs <100 words e.g. {short[:5]}")

    roles = Counter(d.get("role") for d in docs)
    print("Corpus stats:")
    print(f"  docs={len(docs)} clusters={len(clusters)} roles={dict(roles)}")
    print(f"  version_chains={len(by_vc)} fragments={len(by_fg)} contradictions={len(by_cx)}")
    return errors


def validate_queries(queries: list[dict], docs: list[dict]) -> list[str]:
    errors: list[str] = []
    clusters = {d["cluster_id"] for d in docs if d.get("cluster_id")}
    doc_ids = {d["id"] for d in docs}
    vcs = {d["version_chain_id"] for d in docs if d.get("version_chain_id")}
    fgs = {d["fragment_group_id"] for d in docs if d.get("fragment_group_id")}
    cxs = {d["contradiction_id"] for d in docs if d.get("contradiction_id")}

    if len({q["id"] for q in queries}) != len(queries):
        errors.append("duplicate query ids")
    if len(queries) < 100:
        errors.append(f"query count {len(queries)} < 100")

    cats = Counter(q.get("category") for q in queries)
    prod = all(
        "gold_doc_ids" in q and "expected_answer" in q and "expected_action" in q
        and "should_trigger_correction" in q
        for q in queries
    )
    if not prod:
        errors.append("queries missing production gold fields (gold_doc_ids/expected_answer/expected_action/should_trigger_correction)")

    missing_gold = missing_ans = bad_gold = 0
    for q in queries:
        cat = q.get("category")
        if cat not in VALID_CATS:
            errors.append(f"{q.get('id')} bad category {cat}")
        for cid in q.get("target_cluster_ids") or []:
            if cid not in clusters:
                errors.append(f"{q.get('id')} unknown cluster {cid}")
        ref = q.get("reference_ids") or {}
        if ref.get("version_chain_id") and ref["version_chain_id"] not in vcs:
            errors.append(f"{q.get('id')} bad version_chain_id")
        if ref.get("fragment_group_id") and ref["fragment_group_id"] not in fgs:
            errors.append(f"{q.get('id')} bad fragment_group_id")
        if ref.get("contradiction_id") and ref["contradiction_id"] not in cxs:
            errors.append(f"{q.get('id')} bad contradiction_id")
        if cat == "unanswerable" and q.get("target_cluster_ids"):
            errors.append(f"{q.get('id')} unanswerable should not target clusters")
        if cat == "multi_cluster" and (not q.get("target_cluster_ids") or len(q["target_cluster_ids"]) < 2):
            errors.append(f"{q.get('id')} multi_cluster needs 2+ clusters")
        if cat == "versioned" and not ref.get("version_chain_id"):
            errors.append(f"{q.get('id')} versioned missing version_chain_id")
        if cat == "multi_hop" and not ref.get("fragment_group_id"):
            errors.append(f"{q.get('id')} multi_hop missing fragment_group_id")
        if cat == "contradiction_aware" and not ref.get("contradiction_id"):
            errors.append(f"{q.get('id')} contradiction_aware missing contradiction_id")

        gold = q.get("gold_doc_ids") or []
        if cat != "unanswerable":
            if not gold:
                missing_gold += 1
            for g in gold:
                if g not in doc_ids:
                    bad_gold += 1
            if not (q.get("expected_answer") or "").strip():
                missing_ans += 1
        if q.get("expected_action") not in VALID_ACTIONS:
            errors.append(f"{q.get('id')} bad expected_action {q.get('expected_action')}")
        if not isinstance(q.get("should_trigger_correction"), bool):
            errors.append(f"{q.get('id')} should_trigger_correction not bool")

    if missing_gold > max(5, len(queries) // 5):
        errors.append(f"too many answerable queries missing gold_doc_ids: {missing_gold}")
    if missing_ans > max(5, len(queries) // 5):
        errors.append(f"too many answerable queries missing expected_answer: {missing_ans}")
    if bad_gold:
        errors.append(f"{bad_gold} invalid gold_doc_ids")

    print("Query stats:")
    print(f"  queries={len(queries)} categories={dict(cats)}")
    print(f"  production_schema={prod} missing_gold={missing_gold} missing_ans={missing_ans}")
    return errors


def main() -> None:
    if not CORPUS.exists() or not QUERIES.exists():
        raise SystemExit(f"Missing {CORPUS} or {QUERIES}")
    docs = read_jsonl(CORPUS)
    queries = read_jsonl(QUERIES)
    cerr = validate_corpus(docs)
    qerr = validate_queries(queries, docs)
    if cerr or qerr:
        for e in cerr + qerr:
            print("ERROR:", e)
        raise SystemExit(1)
    print("All production validation checks passed.")


if __name__ == "__main__":
    main()
