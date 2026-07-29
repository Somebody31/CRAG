#!/usr/bin/env python3
"""
Production-grade CRAG eval corpus + queries via Xiaomi MiMo (mimo-v2.5-pro).

Hardening vs v1:
  - Never destroy live corpus until a new build is complete (staging dir)
  - One cluster per API call (quality over speed; tokens OK)
  - HTTP timeouts + retries + unbuffered progress logging
  - Structural gates per cluster (roles, chains, contradictions, word counts)
  - Repair loop with validation feedback before append
  - Production queries with gold labels:
      expected_answer, gold_doc_ids, expected_action, should_trigger_correction
  - Resume-safe state machine

Usage:
  .venv/bin/python -u scripts/generate_crag_eval_llm.py --smoke
  .venv/bin/python -u scripts/generate_crag_eval_llm.py --pilot 2   # first 2 clusters only
  .venv/bin/python -u scripts/generate_crag_eval_llm.py            # full production run
  .venv/bin/python -u scripts/generate_crag_eval_llm.py --resume
  .venv/bin/python -u scripts/generate_crag_eval_llm.py --queries-only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

# Force line-buffered stdout even when piped
try:
    sys.stdout.reconfigure(line_buffering=True)  # type: ignore[attr-defined]
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STAGING = DATA / "staging"
LIVE_CORPUS = DATA / "crag_corpus.jsonl"
LIVE_QUERIES = DATA / "crag_queries.jsonl"
STATE_PATH = DATA / ".llm_gen_state.json"
BATCH_LOG = DATA / "llm_batches"
GEN_LOG = DATA / "llm_gen.log"

DOMAIN = """Company: Northline (fictional mid-size B2B SaaS).
Product: Northline Pulse — product analytics + feature flags + experimentation platform.
Corpus covers: product docs, engineering process, HR/company policy, security/compliance, support.
Keep this domain consistent. Invent realistic internal details; no real third-party confidential data.
All content must be self-contained and fact-dense. Never pad with generic "Ownership and review",
"How to use this guidance", or boilerplate support sections. Every paragraph must add unique policy/product facts.
"""

# 38 clusters with special-structure flags
CLUSTER_PLAN: list[dict[str, Any]] = [
    {"id": "c01", "topic": "Pulse Web SDK installation & init", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c02", "topic": "Event taxonomy & naming standards", "version_chain": False, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c03", "topic": "Identity resolution (anonymous → known)", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c04", "topic": "Feature flag defaults & targeting", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": True},
    {"id": "c05", "topic": "Experiment guardrails & design", "version_chain": True, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c06", "topic": "Dashboard sharing & permissions", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c07", "topic": "Event data retention policy", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c08", "topic": "Outbound webhooks & signatures", "version_chain": False, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c09", "topic": "REST API rate limits & exports", "version_chain": True, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c10", "topic": "Session replay privacy & sampling", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c11", "topic": "Cohorts (dynamic/static) & export", "version_chain": False, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c12", "topic": "Seat-based billing & overage", "version_chain": False, "fragments": True, "contradiction": True, "contradiction_chain": False},
    {"id": "c13", "topic": "Primary on-call expectations & ACK SLAs", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c14", "topic": "Incident severity & customer comms timing", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c15", "topic": "Release freeze policy", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c16", "topic": "RFC process & security review gate", "version_chain": False, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c17", "topic": "Code review SLA & approvals", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c18", "topic": "Staging environment access", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c19", "topic": "Database migration process & lock timeouts", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": True},
    {"id": "c20", "topic": "Secrets management & rotation", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c21", "topic": "Service ownership (SCORE catalog)", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c22", "topic": "Postmortem process", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c23", "topic": "Access review cadence (SailPoint)", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c24", "topic": "Production breakglass access", "version_chain": False, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c25", "topic": "Data classification standard", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c26", "topic": "Vendor security review process", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c27", "topic": "SOC 2 evidence collection", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c28", "topic": "PTO / paid time off policy", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c29", "topic": "Remote work stipend", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c30", "topic": "Expense reimbursement policy", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c31", "topic": "Parental leave policy", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c32", "topic": "Laptop refresh cycle", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c33", "topic": "Security awareness training requirements", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c34", "topic": "Visitor & guest Wi-Fi policy", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c35", "topic": "Open source contribution policy", "version_chain": False, "fragments": False, "contradiction": False, "contradiction_chain": False},
    {"id": "c36", "topic": "Customer support escalation path", "version_chain": False, "fragments": True, "contradiction": False, "contradiction_chain": False},
    {"id": "c37", "topic": "Service uptime SLA & credits", "version_chain": False, "fragments": False, "contradiction": True, "contradiction_chain": False},
    {"id": "c38", "topic": "Quarterly planning & OKR process", "version_chain": True, "fragments": False, "contradiction": False, "contradiction_chain": False},
]

REQUIRED_DOC_FIELDS = [
    "id", "cluster_id", "role", "title", "content", "date",
    "validation_note", "contradiction_id", "version_chain_id",
    "version_number", "fragment_group_id",
]

VALID_ROLES = {
    "canonical", "distractor", "versioned", "multi_hop_fragment",
    "contradicting", "contradiction_chain", "near_noise", "far_noise",
}

VALID_ACTIONS = {"none", "rewrite", "refine", "discard"}
VALID_QUERY_CATS = {
    "easy", "ambiguous_distractor_prone", "versioned", "multi_hop",
    "contradiction_aware", "unanswerable", "multi_cluster",
}

# Defaults for CRAG action labels by category (model may override with justification in content)
DEFAULT_ACTION = {
    "easy": ("none", False),
    "ambiguous_distractor_prone": ("rewrite", True),
    "versioned": ("refine", True),
    "multi_hop": ("rewrite", True),
    "contradiction_aware": ("refine", True),
    "unanswerable": ("discard", True),
    "multi_cluster": ("rewrite", True),
}

API_TIMEOUT_S = float(os.getenv("MIMO_TIMEOUT", "300"))
MAX_RETRIES = int(os.getenv("MIMO_RETRIES", "4"))
CLUSTER_ATTEMPTS = int(os.getenv("CLUSTER_ATTEMPTS", "4"))


def log(msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        GEN_LOG.parent.mkdir(parents=True, exist_ok=True)
        with GEN_LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def _fmt_dur(seconds: float) -> str:
    if seconds < 0 or seconds != seconds:  # NaN
        return "?"
    s = int(round(seconds))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{sec:02d}s"
    if m:
        return f"{m}m{sec:02d}s"
    return f"{sec}s"


class ApiStats:
    """Process-wide API usage / throughput tracker."""

    def __init__(self) -> None:
        self.t0 = time.time()
        self.calls = 0
        self.errors = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.total_tokens = 0
        self.reasoning_tokens = 0
        self.cached_tokens = 0
        self.content_chars = 0
        self.reasoning_chars = 0
        self.wall_api_s = 0.0  # sum of successful call latencies
        self.last: dict[str, Any] = {}

    def record_success(
        self,
        *,
        elapsed_s: float,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        reasoning_tokens: int,
        cached_tokens: int,
        content_chars: int,
        reasoning_chars: int,
        finish_reason: str | None,
        model: str,
    ) -> dict[str, Any]:
        self.calls += 1
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += total_tokens
        self.reasoning_tokens += reasoning_tokens
        self.cached_tokens += cached_tokens
        self.content_chars += content_chars
        self.reasoning_chars += reasoning_chars
        self.wall_api_s += elapsed_s

        def rate(n: float, secs: float) -> float:
            return (n / secs) if secs > 0 else 0.0

        snap = {
            "elapsed_s": elapsed_s,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "reasoning_tokens": reasoning_tokens,
            "cached_tokens": cached_tokens,
            "content_chars": content_chars,
            "reasoning_chars": reasoning_chars,
            "finish_reason": finish_reason,
            "model": model,
            "tok_per_s": rate(completion_tokens, elapsed_s),
            "total_tok_per_s": rate(total_tokens, elapsed_s),
            "chars_per_s": rate(content_chars, elapsed_s),
            "prompt_tok_per_s": rate(prompt_tokens, elapsed_s),
        }
        self.last = snap
        return snap

    def record_error(self) -> None:
        self.errors += 1

    def summary_line(self) -> str:
        wall = time.time() - self.t0
        avg_call = (self.wall_api_s / self.calls) if self.calls else 0.0
        avg_tps = (self.completion_tokens / self.wall_api_s) if self.wall_api_s > 0 else 0.0
        run_tps = (self.completion_tokens / wall) if wall > 0 else 0.0
        return (
            f"run: calls={self.calls} errors={self.errors} wall={_fmt_dur(wall)} "
            f"api_time={_fmt_dur(self.wall_api_s)} avg_call={avg_call:.1f}s | "
            f"tokens prompt={self.prompt_tokens:,} completion={self.completion_tokens:,} "
            f"total={self.total_tokens:,} reasoning={self.reasoning_tokens:,} "
            f"cached={self.cached_tokens:,} | "
            f"avg {avg_tps:.1f} completion-tok/s (api) / {run_tps:.1f} tok/s (wall) | "
            f"content_chars={self.content_chars:,} reasoning_chars={self.reasoning_chars:,}"
        )

    def eta_line(self, remaining_units: int, unit_name: str = "clusters") -> str:
        """Estimate ETA from average successful-call time (1 call ≈ 1 unit for cluster gen)."""
        if self.calls <= 0 or remaining_units <= 0:
            return f"ETA: n/a ({remaining_units} {unit_name} left)"
        avg = self.wall_api_s / self.calls
        # clusters often need 1 attempt; pad 15% for retries
        eta = remaining_units * avg * 1.15
        return (
            f"ETA ~{_fmt_dur(eta)} for {remaining_units} {unit_name} "
            f"(avg {avg:.0f}s/call × 1.15 retry pad)"
        )


STATS = ApiStats()


def load_env() -> None:
    load_dotenv(ROOT / ".env")
    if not os.getenv("MIMO_API_KEY"):
        raise SystemExit("MIMO_API_KEY missing. Put it in .env (see .env.example).")


def client() -> OpenAI:
    load_env()
    return OpenAI(
        api_key=os.environ["MIMO_API_KEY"],
        base_url=os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1"),
        timeout=API_TIMEOUT_S,
        max_retries=0,  # we handle retries ourselves
    )


def model_name() -> str:
    return os.getenv("MIMO_MODEL", "mimo-v2.5-pro")


def system_prompt() -> str:
    today = date.today().strftime("%A, %B %d, %Y")
    return (
        f"You are MiMo, an AI assistant developed by Xiaomi. Today's date: {today}. "
        "You generate production-quality synthetic enterprise knowledge-base documents "
        "and evaluation queries for Corrective RAG research. "
        "Follow instructions exactly. Output only the requested format with no surrounding prose."
    )


def _usage_ints(usage: Any) -> tuple[int, int, int, int, int]:
    """Return prompt, completion, total, reasoning, cached token counts."""
    if usage is None:
        return 0, 0, 0, 0, 0
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0)
    completion = int(getattr(usage, "completion_tokens", 0) or 0)
    total = int(getattr(usage, "total_tokens", 0) or (prompt + completion))
    reasoning = 0
    cached = 0
    details = getattr(usage, "completion_tokens_details", None)
    if details is not None:
        reasoning = int(getattr(details, "reasoning_tokens", 0) or 0)
    pdetails = getattr(usage, "prompt_tokens_details", None)
    if pdetails is not None:
        cached = int(getattr(pdetails, "cached_tokens", 0) or 0)
    return prompt, completion, total, reasoning, cached


def chat(
    cl: OpenAI,
    user: str,
    *,
    max_tokens: int = 16000,
    temperature: float = 0.55,
    retries: int = MAX_RETRIES,
    label: str = "",
) -> str:
    last_err: Exception | None = None
    prompt_chars = len(user) + len(system_prompt())
    tag = f"[{label}] " if label else ""
    for attempt in range(1, retries + 1):
        try:
            log(
                f"  {tag}API request attempt {attempt}/{retries} "
                f"model={model_name()} max_tokens={max_tokens} temp={temperature} "
                f"prompt_chars≈{prompt_chars:,}"
            )
            t0 = time.time()
            completion = cl.chat.completions.create(
                model=model_name(),
                messages=[
                    {"role": "system", "content": system_prompt()},
                    {"role": "user", "content": user},
                ],
                max_completion_tokens=max_tokens,
                temperature=temperature,
                top_p=0.9,
                stream=False,
            )
            elapsed = time.time() - t0
            msg = completion.choices[0].message
            content = (msg.content or "").strip()
            reasoning = (getattr(msg, "reasoning_content", None) or "").strip()
            if not content:
                content = reasoning
            if not content:
                raise RuntimeError("empty model content")

            prompt_t, comp_t, total_t, reason_t, cached_t = _usage_ints(
                getattr(completion, "usage", None)
            )
            finish = None
            try:
                finish = completion.choices[0].finish_reason
            except Exception:
                pass

            snap = STATS.record_success(
                elapsed_s=elapsed,
                prompt_tokens=prompt_t,
                completion_tokens=comp_t,
                total_tokens=total_t,
                reasoning_tokens=reason_t,
                cached_tokens=cached_t,
                content_chars=len(content),
                reasoning_chars=len(reasoning),
                finish_reason=finish,
                model=model_name(),
            )

            # Per-call detail
            log(
                f"  {tag}API ok in {elapsed:.1f}s | "
                f"tokens prompt={prompt_t:,} completion={comp_t:,} total={total_t:,} "
                f"reasoning={reason_t:,} cached={cached_t:,} | "
                f"{snap['tok_per_s']:.1f} completion-tok/s  "
                f"{snap['total_tok_per_s']:.1f} total-tok/s  "
                f"{snap['chars_per_s']:.0f} content-chars/s | "
                f"content_chars={len(content):,} reasoning_chars={len(reasoning):,} "
                f"finish={finish}"
            )
            # Cumulative
            log(f"  {tag}{STATS.summary_line()}")
            return content
        except Exception as e:
            STATS.record_error()
            last_err = e
            wait = min(60, 2 ** attempt)
            log(
                f"  {tag}API error attempt {attempt}/{retries}: "
                f"{type(e).__name__}: {e} (sleep {wait}s) | errors_total={STATS.errors}"
            )
            time.sleep(wait)
    raise RuntimeError(f"API failed after {retries} retries: {last_err}")


def parse_jsonl_blob(text: str) -> list[dict]:
    text = text.strip()
    if "```" in text:
        parts = re.findall(r"```(?:jsonl?|json)?\s*([\s\S]*?)```", text, flags=re.I)
        if parts:
            text = "\n".join(parts)

    rows: list[dict] = []
    try:
        maybe = json.loads(text)
        if isinstance(maybe, list):
            return [r for r in maybe if isinstance(r, dict)]
        if isinstance(maybe, dict):
            if "documents" in maybe and isinstance(maybe["documents"], list):
                return [r for r in maybe["documents"] if isinstance(r, dict)]
            if "queries" in maybe and isinstance(maybe["queries"], list):
                return [r for r in maybe["queries"] if isinstance(r, dict)]
            return [maybe]
    except json.JSONDecodeError:
        pass

    buf = ""
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("//") or s.startswith("#"):
            continue
        if s in ("```", "```json", "```jsonl"):
            continue
        try:
            obj = json.loads(s)
            if isinstance(obj, dict):
                rows.append(obj)
                buf = ""
            continue
        except json.JSONDecodeError:
            pass
        buf = (buf + "\n" + s) if buf else s
        try:
            obj = json.loads(buf)
            if isinstance(obj, dict):
                rows.append(obj)
            buf = ""
        except json.JSONDecodeError:
            if len(buf) > 250_000:
                buf = ""
    return rows


def normalize_doc(raw: dict, *, default_cluster: str | None = None) -> dict:
    d = {k: raw.get(k) for k in REQUIRED_DOC_FIELDS}
    for k in ("validation_note", "contradiction_id", "version_chain_id", "fragment_group_id", "cluster_id"):
        if d.get(k) in ("", "null", "None"):
            d[k] = None
    if d.get("version_number") in ("", "null", "None", None):
        d["version_number"] = None
    else:
        try:
            d["version_number"] = int(d["version_number"])
        except (TypeError, ValueError):
            d["version_number"] = None
    if not d.get("cluster_id") and default_cluster and d.get("role") not in ("near_noise", "far_noise"):
        d["cluster_id"] = default_cluster
    d["title"] = str(d.get("title") or "").strip()
    d["content"] = str(d.get("content") or "").strip()
    d["role"] = str(d.get("role") or "canonical").strip()
    d["date"] = str(d.get("date") or "2026-01-01")[:10]
    d["id"] = str(d.get("id") or "").strip()
    return d


def append_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {
        "version": 2,
        "completed_clusters": [],
        "noise_done": False,
        "query_batches_done": [],
        "queries_done": False,
        "promoted": False,
    }


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATE_PATH)


def reassign_unique_ids(rows: list[dict], prefix: str, used: set[str]) -> list[dict]:
    out = []
    i = 0
    for r in rows:
        i += 1
        rid = str(r.get("id") or "").strip()
        if not rid or rid in used:
            rid = f"{prefix}-{i:03d}"
            while rid in used:
                i += 1
                rid = f"{prefix}-{i:03d}"
        r["id"] = rid
        used.add(rid)
        out.append(r)
    return out


# ─── Prompts ──────────────────────────────────────────────────────────────────

def cluster_prompt(cluster: dict, used_ids: set[str], repair: str | None = None) -> str:
    cid = cluster["id"]
    flags: list[str] = []
    if cluster["version_chain"]:
        flags.append(
            "VERSION_CHAIN (required): 3 sequential versions of ONE document family. "
            f"version_chain_id = \"vc-{cid}\". version_number 1,2,3 with ascending dates. "
            "ONLY the latest is role=canonical; earlier are role=versioned with validation_note "
            "explaining what fact changed and the old value. Each version must state the differing "
            "checkable fact explicitly in the body (numbers/API fields/thresholds)."
        )
    if cluster["fragments"]:
        flags.append(
            f"MULTI_HOP_FRAGMENTS (required): exactly 2 docs with fragment_group_id=\"fg-{cid}\", "
            "role=multi_hop_fragment. Each alone is incomplete for a natural combined question; "
            "together they fully answer it. Do not put the full answer in either fragment."
        )
    if cluster["contradiction"]:
        flags.append(
            f"CONTRADICTING_PAIR (required): 2 docs with contradiction_id=\"cx-{cid}\" that disagree "
            "on ONE concrete checkable fact (number/date/rule) stated explicitly in BOTH bodies. "
            "One role=canonical (truth), one role=contradicting with validation_note naming both values."
        )
    if cluster["contradiction_chain"]:
        flags.append(
            f"CONTRADICTION_CHAIN (required): 3 docs, contradiction_id=\"cx-{cid}-chain\", "
            "three different values for the same fact. One role=canonical (current truth), "
            "two role=contradiction_chain with validation_note. All three state their value in body text."
        )

    flags.append(
        "CANONICAL: at least 2 role=canonical docs covering different facets of the topic "
        "(if version_chain exists, the latest version counts as one canonical)."
    )
    flags.append(
        "DISTRACTORS: at least 3 role=distractor docs. Heavy vocabulary overlap with canonicals; "
        "wrong/outdated/adjacent facts. Each MUST have validation_note explaining the specific error. "
        "The wrong fact must appear in the document body."
    )

    repair_block = ""
    if repair:
        repair_block = f"""
PREVIOUS ATTEMPT FAILED VALIDATION. Fix ALL issues below and regenerate the FULL cluster from scratch:
{repair}
"""

    return f"""Generate production-grade internal KB documents for ONE cluster of a Corrective RAG eval corpus.

{DOMAIN}

CLUSTER: id={cid}
TOPIC: {cluster['topic']}

REQUIREMENTS:
{chr(10).join('- ' + f for f in flags)}

DOCUMENT SCHEMA (every line is one JSON object; null when N/A):
  id, cluster_id, role, title, content, date,
  validation_note, contradiction_id, version_chain_id, version_number, fragment_group_id

RULES:
- Output JSONL only. No markdown fences. No commentary.
- cluster_id MUST be "{cid}" for all docs in this cluster.
- id format: "{cid}-" + unique suffix (e.g. {cid}-canon-01). Avoid ids: {sorted(list(used_ids))[:15]}
- content: 180–380 words, fact-dense professional KB writing. Vary structure (prose, bullets, tables-as-text, Q&A).
- FORBIDDEN: generic padding sections titled Ownership and review, How to use this guidance,
  Support, Applicability, Related resources, Change history used as filler.
- FORBIDDEN: "as mentioned in another doc", placeholders, TODO, meta notes about being synthetic.
- Dates ISO YYYY-MM-DD.
- Target 9–14 documents total for this cluster.
{repair_block}
OUTPUT: JSONL only.
"""


def noise_prompt(used_ids: set[str], repair: str | None = None) -> str:
    repair_block = f"\nFIX THESE ISSUES:\n{repair}\n" if repair else ""
    return f"""Generate noise documents for Northline Pulse CRAG retrieval evaluation.

{DOMAIN}

Generate EXACTLY:
1) 20 NEAR-DOMAIN noise docs — Northline-ish but OFF-TOPIC for product/policy clusters
   (office facilities, design system tokens, recruiting events, social clubs, cafeteria, branding).
   role=near_noise, cluster_id=null. Must NOT answer SDK/flags/on-call/PTO/security policy questions.
2) 15 FAR-DOMAIN noise docs — unrelated topics (cooking, sports rules, hiking, municipal guides).
   role=far_noise, cluster_id=null.

Each: id (prefix noise-), cluster_id null, role, title, content (180–350 words fact-dense, NO boilerplate pads),
date, validation_note null, contradiction_id null, version_chain_id null, version_number null, fragment_group_id null.

Avoid ids: {list(used_ids)[:12]}
{repair_block}
OUTPUT: JSONL only.
"""


def queries_batch_prompt(
    docs: list[dict],
    batch_name: str,
    categories: list[str],
    n_target: int,
    id_start: int,
    existing_texts: set[str],
) -> str:
    by_c: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d.get("cluster_id"):
            by_c[d["cluster_id"]].append(d)

    inv_lines = []
    for cid in sorted(by_c):
        parts = []
        for d in by_c[cid][:8]:
            note = ""
            if d.get("role") == "canonical":
                note = " [GOLD-CANDIDATE]"
            parts.append(f"{d['id']}|{d['role']}|{d['title'][:60]}{note}")
        inv_lines.append(f"{cid}: " + " ;; ".join(parts))

    vcs = sorted({d["version_chain_id"] for d in docs if d.get("version_chain_id")})
    fgs = sorted({d["fragment_group_id"] for d in docs if d.get("fragment_group_id")})
    cxs = sorted({d["contradiction_id"] for d in docs if d.get("contradiction_id")})

    # Short fact snippets from canonicals for answer grounding
    snippets = []
    for d in docs:
        if d.get("role") == "canonical" and len(snippets) < 40:
            body = re.sub(r"\s+", " ", d.get("content") or "")[:220]
            snippets.append(f"{d['id']}: {body}")

    cat_help = {
        "easy": "Single fact; gold_doc_ids = one canonical; expected_action=none; should_trigger_correction=false",
        "ambiguous_distractor_prone": "Wording that could retrieve a distractor; gold = canonical id(s); expected_action=rewrite; should_trigger_correction=true",
        "versioned": "Needs LATEST version; set reference_ids.version_chain_id; gold_doc_ids = latest canonical in chain; expected_action=refine; should_trigger_correction=true",
        "multi_hop": "Needs both fragments; set reference_ids.fragment_group_id; gold_doc_ids = both fragment ids; expected_action=rewrite; should_trigger_correction=true",
        "contradiction_aware": "Hits conflicting docs; set reference_ids.contradiction_id; gold_doc_ids = the canonical truth doc only; expected_action=refine; should_trigger_correction=true",
        "unanswerable": "Plausible Northline question with NO answer in corpus; target_cluster_ids=null; gold_doc_ids=[]; expected_answer empty or 'UNANSWERABLE'; expected_action=discard; should_trigger_correction=true",
        "multi_cluster": "Needs two clusters; target_cluster_ids length 2; gold_doc_ids from both; expected_action=rewrite; should_trigger_correction=true",
    }

    return f"""Generate production CRAG evaluation queries grounded in an EXISTING corpus.

{DOMAIN}

BATCH: {batch_name}
Generate ~{n_target} queries, categories limited to: {categories}
Start ids at q-{id_start:04d}

Use ONLY real IDs from the corpus:
- clusters & docs inventory:
{chr(10).join(inv_lines)}
- version_chain_ids: {vcs}
- fragment_group_ids: {fgs}
- contradiction_ids: {cxs}

Canonical snippets (for expected_answer grounding):
{chr(10).join(snippets[:35])}

Category rules:
{chr(10).join(f'- {c}: {cat_help[c]}' for c in categories if c in cat_help)}

Each query JSON fields (all required):
  id, query_text, category,
  target_cluster_ids (array or null),
  reference_ids: {{contradiction_id, version_chain_id, fragment_group_id}} (nulls when N/A),
  gold_doc_ids (array of real doc ids; empty for unanswerable),
  expected_answer (short factual string grounded in gold docs; "UNANSWERABLE" if unanswerable),
  expected_action (one of: none, rewrite, refine, discard),
  should_trigger_correction (boolean)

Rules:
- JSONL only, no fences, no prose.
- gold_doc_ids MUST be real ids from inventory above.
- expected_answer must be checkable and supported by gold docs (except unanswerable).
- Do not duplicate these query texts: {list(existing_texts)[:12]}
- Prefer concrete numbers/names that appear in the snippets/docs.

OUTPUT: JSONL only.
"""


# ─── Validation gates ─────────────────────────────────────────────────────────

FORBIDDEN_PAD = re.compile(
    r"(##\s*Ownership and review|##\s*How to use this guidance|##\s*Applicability\b|"
    r"This page is owned by the responsible Northline team)",
    re.I,
)


def word_count(s: str) -> int:
    return len((s or "").split())


def validate_cluster_docs(rows: list[dict], cluster: dict) -> list[str]:
    cid = cluster["id"]
    errs: list[str] = []
    if not rows:
        return ["no documents parsed"]

    roles = Counter(r.get("role") for r in rows)
    for r in rows:
        if r.get("cluster_id") != cid:
            errs.append(f"{r.get('id')} cluster_id={r.get('cluster_id')} expected {cid}")
        if r.get("role") not in VALID_ROLES:
            errs.append(f"{r.get('id')} invalid role {r.get('role')}")
        if not r.get("title") or not r.get("content"):
            errs.append(f"{r.get('id')} missing title/content")
        wc = word_count(r.get("content") or "")
        if wc < 120:
            errs.append(f"{r.get('id')} too short ({wc}w)")
        if wc > 450:
            errs.append(f"{r.get('id')} too long ({wc}w)")
        if FORBIDDEN_PAD.search(r.get("content") or ""):
            errs.append(f"{r.get('id')} contains forbidden boilerplate padding")
        if r.get("role") == "distractor" and not r.get("validation_note"):
            errs.append(f"{r.get('id')} distractor missing validation_note")
        if r.get("role") in ("contradicting", "contradiction_chain", "versioned") and not r.get("validation_note"):
            errs.append(f"{r.get('id')} {r.get('role')} missing validation_note")

    n_can = roles.get("canonical", 0)
    n_dist = roles.get("distractor", 0)
    if n_can < 1:
        errs.append(f"need ≥1 canonical, got {n_can}")
    if n_dist < 2:
        errs.append(f"need ≥2 distractors, got {n_dist}")
    if len(rows) < 7:
        errs.append(f"need ≥7 docs, got {len(rows)}")
    if len(rows) > 18:
        errs.append(f"too many docs ({len(rows)}); max 18")

    if cluster["version_chain"]:
        chain = [r for r in rows if r.get("version_chain_id")]
        if len(chain) < 3:
            errs.append(f"version_chain needs ≥3 docs, got {len(chain)}")
        else:
            ordered = sorted(chain, key=lambda x: (x.get("version_number") or 0, x.get("date") or ""))
            dates = [m["date"] for m in ordered]
            if dates != sorted(dates):
                errs.append("version chain dates not chronological with version_number")
            latest = ordered[-1]
            if latest.get("role") != "canonical":
                errs.append(f"latest version must be canonical, got {latest.get('role')}")
            earlier = ordered[:-1]
            if any(m.get("role") != "versioned" for m in earlier):
                errs.append("non-latest chain members must be role=versioned")

    if cluster["fragments"]:
        fr = [r for r in rows if r.get("fragment_group_id")]
        if len(fr) < 2:
            errs.append(f"fragments need ≥2 docs, got {len(fr)}")
        if any(r.get("role") != "multi_hop_fragment" for r in fr):
            errs.append("fragment docs must have role=multi_hop_fragment")

    if cluster["contradiction"] or cluster["contradiction_chain"]:
        cx = [r for r in rows if r.get("contradiction_id")]
        need = 3 if cluster["contradiction_chain"] else 2
        if len(cx) < need:
            errs.append(f"contradiction needs ≥{need} docs, got {len(cx)}")
        if not any(r.get("role") == "canonical" for r in cx):
            # allow one canonical outside if shared — but prefer in-set
            if not any(r.get("role") == "canonical" for r in rows if r.get("contradiction_id")):
                errs.append("contradiction set needs a canonical truth doc")

    return errs


def validate_noise(rows: list[dict]) -> list[str]:
    errs = []
    near = [r for r in rows if r.get("role") == "near_noise"]
    far = [r for r in rows if r.get("role") == "far_noise"]
    if len(near) < 15:
        errs.append(f"near_noise need ≥15, got {len(near)}")
    if len(far) < 10:
        errs.append(f"far_noise need ≥10, got {len(far)}")
    for r in rows:
        if r.get("cluster_id") is not None:
            errs.append(f"{r.get('id')} noise must have cluster_id null")
        if word_count(r.get("content") or "") < 100:
            errs.append(f"{r.get('id')} short noise")
        if FORBIDDEN_PAD.search(r.get("content") or ""):
            errs.append(f"{r.get('id')} noise has boilerplate")
    return errs


def validate_corpus(docs: list[dict]) -> list[str]:
    errors = []
    ids = [d["id"] for d in docs]
    if len(ids) != len(set(ids)):
        errors.append("duplicate document ids")
    clusters = {d["cluster_id"] for d in docs if d.get("cluster_id")}
    if len(clusters) < 30:
        errors.append(f"only {len(clusters)} clusters")

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
        errors.append(f"{pad_n} docs still contain forbidden boilerplate")

    roles = Counter(d["role"] for d in docs)
    log(f"Corpus stats: {len(docs)} docs, {len(clusters)} clusters, {dict(roles)}")
    log(f"  chains={len(by_vc)} fragments={len(by_fg)} contradictions={len(by_cx)}")
    return errors


def normalize_query(raw: dict, doc_ids: set[str], clusters: set[str],
                    vcs: set[str], fgs: set[str], cxs: set[str]) -> dict | None:
    qtext = (raw.get("query_text") or raw.get("query") or "").strip()
    if not qtext:
        return None
    cat = (raw.get("category") or "easy").strip()
    if cat not in VALID_QUERY_CATS:
        cat = "easy"

    tc = raw.get("target_cluster_ids")
    if tc == [] or tc == "null":
        tc = None
    if isinstance(tc, str):
        tc = [tc]
    if tc is not None:
        tc = [c for c in tc if c in clusters]
        if not tc:
            tc = None

    ref_in = raw.get("reference_ids") or {}
    ref = {
        "contradiction_id": ref_in.get("contradiction_id") or raw.get("contradiction_id"),
        "version_chain_id": ref_in.get("version_chain_id") or raw.get("version_chain_id"),
        "fragment_group_id": ref_in.get("fragment_group_id") or raw.get("fragment_group_id"),
    }
    for k, allowed in (
        ("contradiction_id", cxs),
        ("version_chain_id", vcs),
        ("fragment_group_id", fgs),
    ):
        if ref.get(k) in ("", "null", "None"):
            ref[k] = None
        elif ref.get(k) and ref[k] not in allowed:
            ref[k] = None

    gold = raw.get("gold_doc_ids") or raw.get("gold_ids") or []
    if isinstance(gold, str):
        gold = [gold]
    gold = [g for g in gold if g in doc_ids]

    exp = (raw.get("expected_answer") or "").strip()
    action = (raw.get("expected_action") or "").strip().lower()
    if action not in VALID_ACTIONS:
        action, _ = DEFAULT_ACTION.get(cat, ("none", False))

    stc = raw.get("should_trigger_correction")
    if not isinstance(stc, bool):
        _, stc = DEFAULT_ACTION.get(cat, ("none", False))

    # Category-specific repairs
    if cat == "unanswerable":
        tc = None
        gold = []
        if not exp:
            exp = "UNANSWERABLE"
        action = "discard"
        stc = True
    if cat == "versioned" and not ref.get("version_chain_id"):
        # try recover from gold docs later
        pass
    if cat == "easy":
        action = "none"
        stc = False
    if cat == "multi_cluster" and tc and len(tc) < 2:
        cat = "easy"  # demote

    # Default action if still wrong for category
    if cat in DEFAULT_ACTION and action not in VALID_ACTIONS:
        action, stc = DEFAULT_ACTION[cat]

    return {
        "id": str(raw.get("id") or "q-tmp"),
        "query_text": qtext,
        "category": cat,
        "target_cluster_ids": tc,
        "reference_ids": ref,
        "gold_doc_ids": gold,
        "expected_answer": exp,
        "expected_action": action,
        "should_trigger_correction": stc,
    }


def validate_queries(queries: list[dict], docs: list[dict]) -> list[str]:
    errors = []
    clusters = {d["cluster_id"] for d in docs if d.get("cluster_id")}
    doc_ids = {d["id"] for d in docs}
    vcs = {d["version_chain_id"] for d in docs if d.get("version_chain_id")}
    fgs = {d["fragment_group_id"] for d in docs if d.get("fragment_group_id")}
    cxs = {d["contradiction_id"] for d in docs if d.get("contradiction_id")}

    ids = [q["id"] for q in queries]
    if len(ids) != len(set(ids)):
        errors.append("duplicate query ids")
    if len(queries) < 100:
        errors.append(f"query count {len(queries)} < 100")

    cats = Counter(q.get("category") for q in queries)
    missing_gold = 0
    missing_ans = 0
    bad_gold = 0
    for q in queries:
        cat = q.get("category")
        if cat not in VALID_QUERY_CATS:
            errors.append(f"{q.get('id')} bad category {cat}")
        for cid in q.get("target_cluster_ids") or []:
            if cid not in clusters:
                errors.append(f"{q.get('id')} bad cluster {cid}")
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
            else:
                for g in gold:
                    if g not in doc_ids:
                        bad_gold += 1
            if not (q.get("expected_answer") or "").strip():
                missing_ans += 1
        if q.get("expected_action") not in VALID_ACTIONS:
            errors.append(f"{q.get('id')} bad expected_action")
        if not isinstance(q.get("should_trigger_correction"), bool):
            errors.append(f"{q.get('id')} should_trigger_correction not bool")

    if missing_gold > len(queries) * 0.25:
        errors.append(f"too many answerable queries missing gold_doc_ids: {missing_gold}")
    if missing_ans > len(queries) * 0.25:
        errors.append(f"too many answerable queries missing expected_answer: {missing_ans}")
    if bad_gold:
        errors.append(f"{bad_gold} invalid gold_doc_ids")

    log(f"Query stats: {len(queries)} {dict(cats)}")
    log(f"  missing_gold={missing_gold} missing_ans={missing_ans} bad_gold={bad_gold}")
    return errors


def enrich_gold_from_corpus(queries: list[dict], docs: list[dict]) -> list[dict]:
    """Fill missing gold_doc_ids / answers using corpus structure when model omitted them."""
    by_id = {d["id"]: d for d in docs}
    by_c: dict[str, list[dict]] = defaultdict(list)
    by_vc: dict[str, list[dict]] = defaultdict(list)
    by_fg: dict[str, list[dict]] = defaultdict(list)
    by_cx: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d.get("cluster_id"):
            by_c[d["cluster_id"]].append(d)
        if d.get("version_chain_id"):
            by_vc[d["version_chain_id"]].append(d)
        if d.get("fragment_group_id"):
            by_fg[d["fragment_group_id"]].append(d)
        if d.get("contradiction_id"):
            by_cx[d["contradiction_id"]].append(d)

    out = []
    for q in queries:
        q = dict(q)
        cat = q.get("category")
        ref = q.get("reference_ids") or {}
        gold = list(q.get("gold_doc_ids") or [])

        if cat == "versioned" and ref.get("version_chain_id"):
            members = sorted(
                by_vc.get(ref["version_chain_id"], []),
                key=lambda x: (x.get("version_number") or 0, x.get("date") or ""),
            )
            if members:
                latest = members[-1]
                if latest["id"] not in gold:
                    gold = [latest["id"]]
                if not q.get("expected_answer"):
                    # pull a concrete line with numbers/API-ish tokens
                    m = re.search(r"[^\n]{20,160}", members[-1].get("content") or "")
                    q["expected_answer"] = (m.group(0).strip() if m else members[-1]["title"])[:240]

        if cat == "multi_hop" and ref.get("fragment_group_id"):
            fr = by_fg.get(ref["fragment_group_id"], [])
            gold = [d["id"] for d in fr]
            if not q.get("expected_answer") and len(fr) >= 2:
                q["expected_answer"] = (
                    f"Requires both: {fr[0]['title']} and {fr[1]['title']}"
                )[:240]

        if cat == "contradiction_aware" and ref.get("contradiction_id"):
            cxdocs = by_cx.get(ref["contradiction_id"], [])
            can = [d for d in cxdocs if d.get("role") == "canonical"]
            if can:
                gold = [can[0]["id"]]
                if not q.get("expected_answer"):
                    m = re.search(r"\*\*([^*]+)\*\*|(\d+\s*(?:days?|hours?|minutes?|%|approvals?))", can[0].get("content") or "", re.I)
                    q["expected_answer"] = (m.group(0) if m else can[0]["title"])[:240]

        if cat in ("easy", "ambiguous_distractor_prone") and not gold:
            for cid in q.get("target_cluster_ids") or []:
                cans = [d for d in by_c.get(cid, []) if d.get("role") == "canonical"]
                if cans:
                    gold = [cans[0]["id"]]
                    break

        if cat == "multi_cluster" and not gold:
            gold = []
            for cid in q.get("target_cluster_ids") or []:
                cans = [d for d in by_c.get(cid, []) if d.get("role") == "canonical"]
                if cans:
                    gold.append(cans[0]["id"])

        if cat == "unanswerable":
            gold = []
            q["expected_answer"] = q.get("expected_answer") or "UNANSWERABLE"
            q["expected_action"] = "discard"
            q["should_trigger_correction"] = True

        # Drop invalid gold ids
        gold = [g for g in gold if g in by_id]
        q["gold_doc_ids"] = gold

        if not q.get("expected_answer") and gold:
            d0 = by_id[gold[0]]
            m = re.search(r"[^\n]{30,200}", d0.get("content") or "")
            q["expected_answer"] = (m.group(0).strip() if m else d0["title"])[:240]

        da, ds = DEFAULT_ACTION.get(cat, ("none", False))
        if q.get("expected_action") not in VALID_ACTIONS:
            q["expected_action"] = da
        if not isinstance(q.get("should_trigger_correction"), bool):
            q["should_trigger_correction"] = ds

        out.append(q)
    return out


# ─── Pipeline stages ──────────────────────────────────────────────────────────

def staging_corpus_path() -> Path:
    return STAGING / "crag_corpus.jsonl"


def staging_queries_path() -> Path:
    return STAGING / "crag_queries.jsonl"


def init_staging(resume: bool) -> None:
    STAGING.mkdir(parents=True, exist_ok=True)
    BATCH_LOG.mkdir(parents=True, exist_ok=True)
    if not resume:
        # Fresh run: clear staging only; keep LIVE intact until promote
        sp = staging_corpus_path()
        sq = staging_queries_path()
        if sp.exists():
            bak = DATA / f"staging_corpus.bak.{int(time.time())}.jsonl"
            sp.replace(bak)
            log(f"Previous staging corpus moved → {bak.name}")
        if sq.exists():
            sq.unlink()
        state = {
            "version": 2,
            "completed_clusters": [],
            "noise_done": False,
            "query_batches_done": [],
            "queries_done": False,
            "promoted": False,
        }
        save_state(state)
        # truncate gen log for new run
        GEN_LOG.write_text("")
        log("Fresh staging initialized (live corpus preserved until promote)")


def promote_to_live() -> None:
    """Atomic-ish promote: backup live, then move staging → live."""
    sc = staging_corpus_path()
    sq = staging_queries_path()
    if not sc.exists():
        raise SystemExit("No staging corpus to promote")
    DATA.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    if LIVE_CORPUS.exists():
        bak = DATA / f"crag_corpus.bak.{ts}.jsonl"
        LIVE_CORPUS.replace(bak)
        log(f"Backed up live corpus → {bak.name}")
    if LIVE_QUERIES.exists():
        bakq = DATA / f"crag_queries.bak.{ts}.jsonl"
        LIVE_QUERIES.replace(bakq)
        log(f"Backed up live queries → {bakq.name}")

    # copy then write (safer than rename across if same fs)
    write_jsonl(LIVE_CORPUS, read_jsonl(sc))
    if sq.exists():
        write_jsonl(LIVE_QUERIES, read_jsonl(sq))
    log(f"Promoted staging → live: {LIVE_CORPUS} + {LIVE_QUERIES}")


def generate_one_cluster(
    cl: OpenAI,
    cluster: dict,
    used_ids: set[str],
    *,
    index: int = 0,
    total: int = 0,
) -> list[dict]:
    cid = cluster["id"]
    last_errs: list[str] = []
    for attempt in range(1, CLUSTER_ATTEMPTS + 1):
        repair = None
        if last_errs:
            repair = "\n".join(f"- {e}" for e in last_errs[:20])
        pos = f"{index}/{total}" if total else cid
        remaining = max(0, total - index) if total else 0
        log(
            f"=== cluster {cid} ({pos}) attempt {attempt}/{CLUSTER_ATTEMPTS}: "
            f"{cluster['topic']} ==="
        )
        if remaining:
            log(f"  {STATS.eta_line(remaining, 'clusters')}")
        t_cluster = time.time()
        raw = chat(
            cl,
            cluster_prompt(cluster, used_ids, repair=repair),
            max_tokens=20000,
            temperature=0.5 if attempt > 1 else 0.55,
            label=f"{cid}/a{attempt}",
        )
        raw_path = BATCH_LOG / f"{cid}.a{attempt}.raw.txt"
        raw_path.write_text(raw, encoding="utf-8")
        log(f"  wrote raw {raw_path.name} ({len(raw):,} bytes)")
        parsed = parse_jsonl_blob(raw)
        log(f"  parsed {len(parsed)} JSON objects from response")
        rows = [normalize_doc(r, default_cluster=cid) for r in parsed]
        rows = [r for r in rows if r.get("title") and r.get("content")]
        for r in rows:
            r["cluster_id"] = cid
            if r.get("role") in ("near_noise", "far_noise"):
                r["role"] = "distractor"  # not noise in cluster batch
        # local id uniqueness within attempt
        local_used = set(used_ids)
        rows = reassign_unique_ids(rows, f"{cid}", local_used)

        errs = validate_cluster_docs(rows, cluster)
        if errs:
            log(f"  validation failed ({len(errs)}): {errs[:6]}")
            last_errs = errs
            continue

        # commit ids to used
        for r in rows:
            used_ids.add(r["id"])
        wcs = [len((r.get("content") or "").split()) for r in rows]
        avg_w = (sum(wcs) / len(wcs)) if wcs else 0
        log(
            f"  accepted {len(rows)} docs for {cid} in {_fmt_dur(time.time() - t_cluster)} | "
            f"roles={dict(Counter(r['role'] for r in rows))} | "
            f"words min/avg/max={min(wcs) if wcs else 0}/{avg_w:.0f}/{max(wcs) if wcs else 0}"
        )
        return rows

    raise RuntimeError(f"Cluster {cid} failed after {CLUSTER_ATTEMPTS} attempts: {last_errs[:10]}")


def run_corpus(cl: OpenAI, *, resume: bool, pilot: int | None) -> list[dict]:
    state = load_state()
    if not resume:
        init_staging(resume=False)
        state = load_state()
    else:
        STAGING.mkdir(parents=True, exist_ok=True)
        BATCH_LOG.mkdir(parents=True, exist_ok=True)
        log("Resuming corpus generation from staging state")

    path = staging_corpus_path()
    docs = read_jsonl(path)
    used_ids = {d["id"] for d in docs}
    completed = set(state.get("completed_clusters") or [])

    plan = CLUSTER_PLAN
    if pilot is not None:
        plan = CLUSTER_PLAN[:pilot]
        log(f"PILOT mode: only first {pilot} clusters")

    total_plan = len(plan)
    for i, cluster in enumerate(plan, 1):
        cid = cluster["id"]
        if resume and cid in completed:
            log(f"Skip {cid} (resume) [{i}/{total_plan}]")
            continue
        rows = generate_one_cluster(
            cl, cluster, used_ids, index=i, total=total_plan
        )
        append_jsonl(path, rows)
        docs.extend(rows)
        completed.add(cid)
        state["completed_clusters"] = sorted(completed)
        save_state(state)
        log(
            f"  staging corpus total: {len(docs)} docs | "
            f"clusters done {len(completed)}/{total_plan} | "
            f"{STATS.summary_line()}"
        )

    # Noise
    if not (resume and state.get("noise_done")) and pilot is None:
        log("=== noise batch ===")
        last_errs: list[str] = []
        for attempt in range(1, CLUSTER_ATTEMPTS + 1):
            repair = "\n".join(last_errs[:15]) if last_errs else None
            raw = chat(
                cl,
                noise_prompt(used_ids, repair=repair),
                max_tokens=24000,
                temperature=0.65,
                label=f"noise/a{attempt}",
            )
            (BATCH_LOG / f"noise.a{attempt}.raw.txt").write_text(raw, encoding="utf-8")
            parsed = parse_jsonl_blob(raw)
            log(f"  noise parsed {len(parsed)} objects")
            rows = [normalize_doc(r) for r in parsed]
            for r in rows:
                r["cluster_id"] = None
                if r.get("role") not in ("near_noise", "far_noise"):
                    # classify by keyword heuristic if model mislabeled
                    r["role"] = "near_noise" if "northline" in (r.get("title") or "").lower() else "far_noise"
            rows = [r for r in rows if r.get("title") and r.get("content")]
            rows = reassign_unique_ids(rows, "noise", used_ids)
            errs = validate_noise(rows)
            if errs:
                log(f"  noise validation failed: {errs[:6]}")
                last_errs = errs
                continue
            append_jsonl(path, rows)
            docs.extend(rows)
            state["noise_done"] = True
            save_state(state)
            log(f"  accepted {len(rows)} noise docs | {STATS.summary_line()}")
            break
        else:
            raise RuntimeError(f"Noise batch failed: {last_errs}")
    elif pilot is not None:
        log("PILOT: skipping noise batch")

    docs = read_jsonl(path)
    cerr = validate_corpus(docs)
    log(f"Corpus stage finished | {STATS.summary_line()}")
    if cerr and pilot is None:
        log("CORPUS VALIDATION ISSUES:")
        for e in cerr:
            log(f" - {e}")
        # hard fail only on severe issues
        severe = [e for e in cerr if "boilerplate" in e or "duplicate" in e or "only " in e]
        if severe:
            raise SystemExit("Severe corpus validation failures; not promoting")
    elif not cerr:
        log("Corpus validation OK")
    return docs


QUERY_BATCHES = [
    ("easy_amb", ["easy", "ambiguous_distractor_prone"], 50),
    ("version_hop_cx", ["versioned", "multi_hop", "contradiction_aware"], 45),
    ("unans_multi", ["unanswerable", "multi_cluster"], 45),
    ("fill", ["easy", "ambiguous_distractor_prone", "versioned", "multi_hop",
             "contradiction_aware", "unanswerable", "multi_cluster"], 40),
]


def run_queries(cl: OpenAI, docs: list[dict], *, resume: bool) -> list[dict]:
    state = load_state()
    path = staging_queries_path()
    if resume and state.get("queries_done") and path.exists():
        log("Skip queries (resume, already done)")
        return read_jsonl(path)

    doc_ids = {d["id"] for d in docs}
    clusters = {d["cluster_id"] for d in docs if d.get("cluster_id")}
    vcs = {d["version_chain_id"] for d in docs if d.get("version_chain_id")}
    fgs = {d["fragment_group_id"] for d in docs if d.get("fragment_group_id")}
    cxs = {d["contradiction_id"] for d in docs if d.get("contradiction_id")}

    all_q: list[dict] = []
    if resume and path.exists():
        all_q = read_jsonl(path)
        log(f"Loaded {len(all_q)} existing staging queries")

    done_batches = set(state.get("query_batches_done") or [])
    existing_texts = {q.get("query_text", "").lower() for q in all_q}

    for bname, cats, n_target in QUERY_BATCHES:
        if resume and bname in done_batches:
            log(f"Skip query batch {bname} (resume)")
            continue
        log(f"=== query batch {bname} cats={cats} n≈{n_target} ===")
        remaining_batches = len(QUERY_BATCHES) - len(done_batches)
        log(f"  {STATS.eta_line(remaining_batches, 'query-batches')}")
        id_start = len(all_q) + 1
        raw = chat(
            cl,
            queries_batch_prompt(docs, bname, cats, n_target, id_start, existing_texts),
            max_tokens=16000,
            temperature=0.5,
            label=f"queries/{bname}",
        )
        (BATCH_LOG / f"queries_{bname}.raw.txt").write_text(raw, encoding="utf-8")
        parsed = parse_jsonl_blob(raw)
        log(f"  query batch parsed {len(parsed)} objects")
        batch_rows = []
        for r in parsed:
            q = normalize_query(r, doc_ids, clusters, vcs, fgs, cxs)
            if not q:
                continue
            key = q["query_text"].lower()
            if key in existing_texts:
                continue
            existing_texts.add(key)
            batch_rows.append(q)
        all_q.extend(batch_rows)
        # rewrite staging queries fully with enrich + re-id
        enriched = enrich_gold_from_corpus(all_q, docs)
        for i, q in enumerate(enriched, 1):
            q["id"] = f"q-{i:04d}"
        write_jsonl(path, enriched)
        all_q = enriched
        done_batches.add(bname)
        state["query_batches_done"] = sorted(done_batches)
        save_state(state)
        log(
            f"  batch added ~{len(batch_rows)}; staging queries total {len(all_q)} | "
            f"{STATS.summary_line()}"
        )

    all_q = enrich_gold_from_corpus(all_q, docs)
    for i, q in enumerate(all_q, 1):
        q["id"] = f"q-{i:04d}"
    write_jsonl(path, all_q)
    state["queries_done"] = True
    save_state(state)

    qerr = validate_queries(all_q, docs)
    if qerr:
        log("QUERY VALIDATION ISSUES:")
        for e in qerr[:40]:
            log(f" - {e}")
    else:
        log("Query validation OK")
    log(f"Query stage finished | {STATS.summary_line()}")
    return all_q


def run_smoke(cl: OpenAI) -> None:
    log(f"Smoke test model={model_name()} timeout={API_TIMEOUT_S}s")
    text = chat(
        cl,
        'Return exactly this JSON object and nothing else: {"ok": true, "model": "mimo-v2.5-pro"}',
        max_tokens=128,
        temperature=0,
        label="smoke",
    )
    log(f"Response: {text[:300].replace(chr(10), ' ')}")
    rows = parse_jsonl_blob(text)
    if not rows or not rows[0].get("ok"):
        # accept any non-empty as connectivity OK
        if "ok" not in text.lower() and "mimo" not in text.lower():
            raise SystemExit("Smoke parse unexpected")
    log(f"Smoke OK | {STATS.summary_line()}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Production CRAG eval generation via MiMo")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--corpus-only", action="store_true")
    ap.add_argument("--queries-only", action="store_true")
    ap.add_argument("--resume", action="store_true")
    ap.add_argument("--pilot", type=int, default=None, help="Only first N clusters (no promote/noise)")
    ap.add_argument("--no-promote", action="store_true", help="Leave results in data/staging only")
    ap.add_argument("--promote-only", action="store_true", help="Promote existing staging to live")
    args = ap.parse_args()

    if args.promote_only:
        promote_to_live()
        state = load_state()
        state["promoted"] = True
        save_state(state)
        return

    cl = client()
    STATS.t0 = time.time()  # reset wall clock for this process
    log(f"Model: {model_name()}  Base: {os.getenv('MIMO_BASE_URL', 'https://api.xiaomimimo.com/v1')}")
    log(f"Timeout: {API_TIMEOUT_S}s  Retries: {MAX_RETRIES}  Cluster attempts: {CLUSTER_ATTEMPTS}")
    log("Detailed metrics: completion-tok/s, total-tok/s, content-chars/s, cumulative tokens, ETA")

    if args.smoke:
        run_smoke(cl)
        return

    docs: list[dict] = []
    if not args.queries_only:
        docs = run_corpus(cl, resume=args.resume, pilot=args.pilot)
    else:
        # prefer staging, fall back to live
        docs = read_jsonl(staging_corpus_path()) or read_jsonl(LIVE_CORPUS)
        if not docs:
            raise SystemExit("No corpus found in staging or live")

    queries: list[dict] = []
    if not args.corpus_only and args.pilot is None:
        queries = run_queries(cl, docs, resume=args.resume)
    elif args.pilot is not None:
        log("PILOT: skipping query generation")

    if args.pilot is not None:
        log(f"PILOT complete. Staging corpus docs={len(docs)}. Not promoting.")
        log(f"  staging: {staging_corpus_path()}")
        return

    if not args.no_promote and not args.corpus_only:
        # Require minimum bar before promote
        docs = read_jsonl(staging_corpus_path())
        queries = read_jsonl(staging_queries_path())
        if len(docs) < 200:
            raise SystemExit(f"Refuse promote: only {len(docs)} docs")
        if len(queries) < 80:
            raise SystemExit(f"Refuse promote: only {len(queries)} queries")
        promote_to_live()
        state = load_state()
        state["promoted"] = True
        save_state(state)
    elif not args.no_promote and args.corpus_only:
        docs = read_jsonl(staging_corpus_path())
        if len(docs) < 200:
            raise SystemExit(f"Refuse promote: only {len(docs)} docs")
        # promote corpus only; keep old queries until regenerated
        ts = int(time.time())
        if LIVE_CORPUS.exists():
            LIVE_CORPUS.replace(DATA / f"crag_corpus.bak.{ts}.jsonl")
        write_jsonl(LIVE_CORPUS, docs)
        log(f"Promoted corpus only → {LIVE_CORPUS}")

    log("Done.")
    log(f"FINAL {STATS.summary_line()}")
    log(f"  staging corpus:  {staging_corpus_path()}")
    log(f"  staging queries: {staging_queries_path()}")
    log(f"  live corpus:     {LIVE_CORPUS}")
    log(f"  live queries:    {LIVE_QUERIES}")
    log("  reload LanceDB:  .venv/bin/python scripts/load_lancedb.py")


if __name__ == "__main__":
    main()
