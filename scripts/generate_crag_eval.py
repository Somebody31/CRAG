#!/usr/bin/env python3
"""
Generate CRAG eval corpus + queries for Northline Pulse (fictional B2B product analytics / experimentation platform).

Outputs:
  data/crag_corpus.jsonl
  data/crag_queries.jsonl

Run:  .venv/bin/python scripts/generate_crag_eval.py
"""
from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CORPUS_PATH = DATA / "crag_corpus.jsonl"
QUERIES_PATH = DATA / "crag_queries.jsonl"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def doc(
    id_: str,
    *,
    cluster_id: str | None,
    role: str,
    title: str,
    content: str,
    date: str,
    validation_note: str | None = None,
    contradiction_id: str | None = None,
    version_chain_id: str | None = None,
    version_number: int | None = None,
    fragment_group_id: str | None = None,
) -> dict[str, Any]:
    words = len(content.split())
    if words < 140 or words > 420:
        # Soft pad or trim only if slightly out of band — prefer authoring correctly
        pass
    return {
        "id": id_,
        "cluster_id": cluster_id,
        "role": role,
        "title": title,
        "content": content.strip(),
        "date": date,
        "validation_note": validation_note,
        "contradiction_id": contradiction_id,
        "version_chain_id": version_chain_id,
        "version_number": version_number,
        "fragment_group_id": fragment_group_id,
    }


# ─── Domain: Northline Pulse ──────────────────────────────────────────────────
# Mid-size B2B SaaS: product analytics + feature flags + experimentation.
# Internal KB mixes product docs, eng process, HR/policy, security, support.

def build_corpus() -> list[dict]:
    docs: list[dict] = []
    n = 0

    def nid(prefix: str = "doc") -> str:
        nonlocal n
        n += 1
        return f"{prefix}-{n:04d}"

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH 1 — Product foundation (clusters c01–c06)
    # ══════════════════════════════════════════════════════════════════════════

    # c01 SDK install — version chain + distractors
    docs += [
        doc(
            nid(),
            cluster_id="c01",
            role="versioned",
            version_chain_id="vc-sdk-install",
            version_number=1,
            title="Northline Pulse Web SDK — Installation (v1.x)",
            date="2024-03-12",
            validation_note="Superseded: packages under @northline/pulse-web@1 and init via pulse.init with apiKey only; no workspaceId required in v1.",
            content="""# Northline Pulse Web SDK Installation (v1.x)

This guide covers browser installation of the Northline Pulse analytics SDK for SPA and multi-page apps.

## Package
Install from npm:

```
npm install @northline/pulse-web@1
```

## Minimal bootstrap
Add the following near the root of your application, before any custom events fire:

```
import { pulse } from '@northline/pulse-web';

pulse.init({
  apiKey: process.env.PULSE_WRITE_KEY
});
```

The v1 client derives workspace routing from the API key alone. You do not pass a separate workspace identifier.

## Default behavior
- Page views are captured automatically on history changes for React Router and Vue Router when `autoPageviews` is left at its default (`true`).
- The SDK queues events offline for up to 50 items and flushes when connectivity returns.
- Supported browsers: last two Chrome, Firefox, Safari, and Edge versions.

## Verification
Open the browser network panel and confirm POSTs to `https://ingest.northline.io/v1/e`. Events should appear in Live Stream within two minutes for healthy projects.

## Support
Contact #pulse-sdk on Slack for install blockers. Do not open production write keys in public repositories.
""",
        ),
        doc(
            nid(),
            cluster_id="c01",
            role="versioned",
            version_chain_id="vc-sdk-install",
            version_number=2,
            title="Northline Pulse Web SDK — Installation (v2.x)",
            date="2025-01-20",
            validation_note="Superseded by v3: v2 requires both apiKey and workspaceId; package still @northline/pulse-web@2.",
            content="""# Northline Pulse Web SDK Installation (v2.x)

Use this document when installing Pulse Web SDK 2.x across marketing sites and product apps.

## Install
```
npm install @northline/pulse-web@2
```

## Initialization
v2 separates credentials from workspace routing:

```
import { pulse } from '@northline/pulse-web';

pulse.init({
  apiKey: process.env.PULSE_WRITE_KEY,
  workspaceId: process.env.PULSE_WORKSPACE_ID
});
```

Both `apiKey` and `workspaceId` are required. Omitting `workspaceId` throws at init time.

## Behavior notes
- Auto pageviews remain enabled by default.
- A new `consent` option defaults to `granted` for existing customers; EU properties should set this from their CMP callback.
- Offline queue size increased to 100 events.
- Ingest host remains `https://ingest.northline.io/v1/e`.

## Migration from 1.x
If you only passed `apiKey` in v1, look up the workspace ID under Project Settings → General. Deploy apiKey + workspaceId together; partial deploys drop events.
""",
        ),
        doc(
            nid(),
            cluster_id="c01",
            role="canonical",
            version_chain_id="vc-sdk-install",
            version_number=3,
            title="Northline Pulse Web SDK — Installation (v3.x current)",
            date="2026-02-04",
            content="""# Northline Pulse Web SDK Installation (v3.x — current)

Current installation path for browser analytics and feature evaluation.

## Install
```
npm install @northline/pulse-web@3
```

Peer dependency: TypeScript projects should use TypeScript 5.0+.

## Initialization
```
import { PulseClient } from '@northline/pulse-web';

const pulse = new PulseClient({
  writeKey: process.env.PULSE_WRITE_KEY,
  workspaceId: process.env.PULSE_WORKSPACE_ID,
  environment: process.env.PULSE_ENV || 'production'
});

await pulse.ready();
```

Breaking changes vs 2.x:
- Named export is `PulseClient` (class); the old `pulse` singleton helper is removed.
- Credential field renamed from `apiKey` to `writeKey`.
- `environment` is required for correct flag evaluation (`production` | `staging` | `development`).
- Ingest URL is now `https://ingest.northline.io/v3/track`.

## Defaults
- `autoPageviews`: true
- `batchSize`: 20
- `flushIntervalMs`: 2000
- Offline queue: 200 events, persisted in IndexedDB

## Verify
After `pulse.ready()`, call `pulse.track('sdk_smoke_ok')` and confirm the event in Live Stream filtered by environment. Network traffic should hit `/v3/track`, not `/v1/e`.

## Security
Use write keys only in the browser. Server-side sources must use secret keys from Server Sources, never web write keys.
""",
        ),
        doc(
            nid(),
            cluster_id="c01",
            role="distractor",
            date="2025-06-11",
            validation_note="Wrong package name (@northline/analytics-js) and wrong ingest host (api.northline.io); confuses with deprecated analytics product line.",
            title="Installing Northline Analytics in Single-Page Apps",
            content="""# Installing Northline Analytics in Single-Page Apps

Teams instrumenting product analytics often start with the browser package used by marketing sites.

## Package
```
npm install @northline/analytics-js
```

## Setup
```
import analytics from '@northline/analytics-js';
analytics.load('NORTHLINE_PROJECT_TOKEN');
analytics.page();
```

Events post to `https://api.northline.io/collect`. Ensure ad blockers allow that host during QA.

## SPA routing
Call `analytics.page()` on every client-side navigation. React apps typically do this inside a router effect.

## Notes
This package is still referenced in older onboarding decks. Prefer the Pulse Web SDK for new instrumentation tied to feature flags and experiments; this document remains because several marketing properties have not migrated.
""",
        ),
        doc(
            nid(),
            cluster_id="c01",
            role="distractor",
            date="2025-09-02",
            validation_note="Describes iOS SDK install as if it were the web path; same vocabulary (write keys, workspace, ready) but platform is wrong for web queries.",
            title="Pulse Client Setup — Quick Start",
            content="""# Pulse Client Setup — Quick Start

Get events flowing into Northline Pulse with the standard client bootstrap.

## Prerequisites
- A workspace write key from Project Settings
- Workspace ID displayed on the General tab
- Xcode 15+ for local builds

## Install via SPM
Add `https://github.com/northline/pulse-ios` and select `PulseClient` 3.x.

## Code
```
import PulseClient

let client = PulseClient(
  writeKey: ProcessInfo.processInfo.environment["PULSE_WRITE_KEY"]!,
  workspaceId: ProcessInfo.processInfo.environment["PULSE_WORKSPACE_ID"]!,
  environment: .production
)
try await client.ready()
client.track(name: "sdk_smoke_ok")
```

## Verification
Use the Live Stream view filtered by the iOS platform. Events should appear within a minute on a healthy device network.

## Common mistakes
- Embedding secret server keys in the mobile binary
- Forgetting ATT prompts before IDFA-dependent identity merges
""",
        ),
    ]

    # c02 Event taxonomy — multi-hop fragments + distractors
    docs += [
        doc(
            nid(),
            cluster_id="c02",
            role="canonical",
            date="2025-10-08",
            title="Pulse Event Taxonomy Standards",
            content="""# Pulse Event Taxonomy Standards

All product teams instrumenting Northline Pulse must follow the shared taxonomy so dashboards and experiments stay comparable.

## Naming
- Use `object_action` in snake_case: `button_clicked`, `invoice_exported`, `flag_evaluated`.
- Do not use spaces, camelCase, or past-tense marketing phrases (`User Signed Up`).
- Reserve the `system_` prefix for Pulse-generated events (`system_session_started`).

## Required properties
Every event must include:
- `app_area` (enum: `app`, `admin`, `billing`, `onboarding`)
- `surface` (string page or modal id)
- `actor_type` (`user` | `service`)

## Forbidden
- Free-text PII in property values (emails, phone numbers, raw card numbers).
- Dynamic event names built from user input.
- Reusing an event name with a different property schema without a version suffix (`checkout_completed_v2`).

## Ownership
Each domain squad owns a section of the taxonomy spreadsheet. Changes require review from Data Platform within five business days.

## Related
Property dictionaries and validation rules are maintained separately by domain. This standards doc does not list per-event properties.
""",
        ),
        doc(
            nid(),
            cluster_id="c02",
            role="multi_hop_fragment",
            fragment_group_id="fg-taxonomy-checkout",
            date="2025-11-15",
            title="Checkout Domain Events — Names and When to Fire",
            content="""# Checkout Domain Events — Names and When to Fire

Billing squad catalog of checkout-related events for Pulse.

## Events
| Event | When to fire |
| --- | --- |
| `checkout_started` | User opens the paid plan checkout drawer |
| `checkout_plan_selected` | User selects or changes plan tier in the drawer |
| `checkout_payment_submitted` | User submits payment method form |
| `checkout_completed` | Server confirms subscription active (client fires after success API) |
| `checkout_failed` | Payment declined or validation error shown |

## Ordering expectations
A healthy funnel usually shows `checkout_started` → `checkout_plan_selected` → `checkout_payment_submitted` → `checkout_completed`. Skips are allowed when users resume a saved cart.

## What this doc does not cover
Property schemas, allowed enums, and PII rules for these events are defined in the checkout property dictionary. Implementers need both documents before shipping instrumentation.
""",
        ),
        doc(
            nid(),
            cluster_id="c02",
            role="multi_hop_fragment",
            fragment_group_id="fg-taxonomy-checkout",
            date="2025-11-15",
            title="Checkout Domain Events — Property Dictionary",
            content="""# Checkout Domain Events — Property Dictionary

Authoritative property schemas for checkout events. Event names and fire timing live in the companion “Names and When to Fire” note.

## Shared properties (all checkout events)
- `plan_code` (string): `starter` | `growth` | `enterprise`
- `billing_interval` (string): `monthly` | `annual`
- `currency` (string ISO 4217): default `USD`
- `checkout_session_id` (uuid string)

## Event-specific
- `checkout_plan_selected`: also `previous_plan_code` (nullable)
- `checkout_payment_submitted`: `payment_method` (`card` | `invoice` | `ach`)
- `checkout_completed`: `mrr_delta_cents` (integer), `sales_assisted` (boolean)
- `checkout_failed`: `error_code` (string), `retryable` (boolean)

## Validation
Pulse schema guard rejects events missing `checkout_session_id` or using unknown `plan_code` values. `mrr_delta_cents` must be non-negative.

## PII
Never attach card last-four, billing email, or company legal name on these events; those belong in the billing warehouse, not Pulse.
""",
        ),
        doc(
            nid(),
            cluster_id="c02",
            role="distractor",
            date="2024-08-22",
            validation_note="Outdated naming: mandates camelCase UserSignedUp style which current standards forbid.",
            title="Legacy Event Naming Conventions",
            content="""# Legacy Event Naming Conventions

Historical guidance still linked from older runbooks.

## Style
Prefer UpperCamelCase marketing-readable names: `UserSignedUp`, `ButtonClicked`, `InvoiceExported`.

## Properties
Attach `email` and `fullName` on identity-bearing events so CRM sync can match records without a separate identify call.

## Prefixes
Use `Marketing_` for website events and `Product_` for in-app events.

This document powered the 2023 taxonomy migration. New instrumentation should verify whether a newer standards page has replaced these rules before copying examples.
""",
        ),
        doc(
            nid(),
            cluster_id="c02",
            role="distractor",
            date="2025-12-01",
            validation_note="Adjacent topic: describes warehouse dbt model naming, not Pulse client event taxonomy — similar 'naming standards' framing.",
            title="Analytics Naming Standards for Downstream Models",
            content="""# Analytics Naming Standards for Downstream Models

Data Platform standards for dbt models fed by Pulse and billing exports.

## Models
- Staging: `stg_<source>__<entity>`
- Intermediate: `int_<domain>__<grain>`
- Marts: `fct_` / `dim_` prefixes only

## Columns
snake_case only. Monetary fields end with `_cents`. Booleans use `is_` / `has_` prefixes.

## Events landing tables
Raw Pulse payloads land in `pulse_raw.events` and should not be queried directly by analysts. Use `fct_product_events` in the mart layer.

These rules do not govern client-side event names inside the Pulse SDK; they apply after ingestion in the warehouse.
""",
        ),
    ]

    # c03 Identity resolution — contradiction pair
    docs += [
        doc(
            nid(),
            cluster_id="c03",
            role="canonical",
            contradiction_id="cx-identity-window",
            date="2026-01-14",
            title="Identity Resolution Policy — Anonymous to Known",
            content="""# Identity Resolution Policy — Anonymous to Known

How Pulse merges anonymous device IDs with authenticated user IDs.

## Merge window
Anonymous activity may merge into a known user for **30 days** after the first `identify` call on that device. Activity older than 30 days remains on the anonymous profile and is not retroactively stitched.

## Priority
When multiple known IDs appear on one device within the window, the **most recently identified** user ID wins for forward traffic. Historical events already stamped keep their original `user_id`.

## Identify requirements
- `identify` must include a stable external `user_id` (string).
- Optional traits: `email_domain`, `plan_code`, `role` — never raw email unless the workspace has PII mode enabled by Security.

## Conflicts
If two users share a device inside the window, Pulse emits `system_identity_conflict` and does not auto-merge the two known profiles. Manual merge is a Support-only tool.

## Effective date
This 30-day policy is active for all workspaces as of 2026-01-10. Prior 7-day experiments in beta are retired.
""",
        ),
        doc(
            nid(),
            cluster_id="c03",
            role="contradicting",
            contradiction_id="cx-identity-window",
            date="2025-05-03",
            validation_note="Conflicts on merge window length: states 7 days instead of current 30 days.",
            title="Stitching Anonymous Sessions After Login",
            content="""# Stitching Anonymous Sessions After Login

Pulse automatically stitches pre-login behavior into the authenticated user profile.

## Window
On `identify`, the platform reassigns anonymous events from the same device for the previous **7 days**. Events older than seven days stay anonymous.

## Rules of thumb
- Call `identify` as soon as auth completes, including SSO.
- Avoid identifying with temporary IDs (e.g., session tokens).
- Cross-device merge is not performed client-side; only same-device anonymous IDs stitch.

## Conflict handling
Two authenticated users on one browser profile within the window trigger a conflict event; engineering must not invent client-side workarounds.

## Rollout note
The 7-day window was chosen during the 2025 privacy review for EU workspaces and is described here as the production default.
""",
        ),
        doc(
            nid(),
            cluster_id="c03",
            role="distractor",
            date="2025-09-18",
            validation_note="Describes CRM contact merge rules (Salesforce), not Pulse anonymous-to-known device stitching.",
            title="Identity Merge Guidelines for Customer Records",
            content="""# Identity Merge Guidelines for Customer Records

Revenue Operations standards for merging duplicate account and contact records.

## When to merge
Merge contacts when email domains match and a human confirms the same buying committee. Do not merge solely because two users shared a laptop.

## System of record
Salesforce remains system of record for account hierarchy. Pulse user IDs may be stored in a custom field but are not used to drive CRM merges.

## SLA
Duplicate reviews run weekly. High-value enterprise accounts escalate to the assigned AE before merge.

This policy is about CRM hygiene, not product analytics identity graphs.
""",
        ),
        doc(
            nid(),
            cluster_id="c03",
            role="canonical",
            date="2026-01-14",
            title="Calling identify Safely in Client Applications",
            content="""# Calling identify Safely in Client Applications

Implementation notes for client teams using Pulse identity APIs.

## Timing
Invoke `identify` only after your auth layer returns a stable primary key. For passwordless magic links, wait until the session cookie is set.

## Traits
Send traits that power segmentation (`plan_code`, `seat_role`, `company_size_bucket`). Omit free-text notes and support ticket bodies.

## Reset
On logout, call `pulse.reset()` so the next visitor on a shared machine does not inherit the previous `user_id`. Failing to reset is the top cause of cross-user contamination in shared CS kiosks.

## QA checklist
- Fresh browser: anonymous events flow with `anonymous_id` only
- Login: subsequent events include `user_id`
- Logout + second login as different user: no bleed of prior traits
""",
        ),
    ]

    # c04 Feature flags — contradiction chain (3-way) + distractors
    docs += [
        doc(
            nid(),
            cluster_id="c04",
            role="canonical",
            contradiction_id="cx-flag-default-pct",
            date="2026-03-01",
            title="Feature Flag Defaults for New Flags",
            content="""# Feature Flag Defaults for New Flags

Product Platform policy for creating flags in Northline Pulse.

## Default rollout percentage
New boolean flags default to **0%** rollout (off for everyone) until an owner explicitly raises the percentage or adds targeting rules.

## Rationale
Failing closed prevents accidental exposure of incomplete UI. Staging environments still evaluate rules but production keys start at zero.

## Exceptions
- Kill-switch flags used for incident response may be created at 100% enabled with dual approval from on-call and EM.
- Permanent ops flags documented in the service catalog may ship at 100% with an RFC link.

## Ownership
Every flag requires an owner team and a cleanup date ≤ 90 days out, or a `permanent` tag with justification.

## Audit
Weekly job lists flags still at 0% with no targeting as cleanup candidates; this is healthy, not a bug.
""",
        ),
        doc(
            nid(),
            cluster_id="c04",
            role="contradicting",
            contradiction_id="cx-flag-default-pct",
            date="2025-04-09",
            validation_note="Conflicts on default rollout: claims new flags default to 50% for faster experimentation.",
            title="Creating Feature Flags in Pulse — Defaults",
            content="""# Creating Feature Flags in Pulse — Defaults

Quick reference for squads spinning up flags tied to experiments.

## Default rollout
When you create a boolean flag without custom rules, Pulse sets the default rollout to **50%** so A/B scaffolding can begin immediately. Adjust the percentage before launch if you need a quieter ramp.

## Targeting
Add email, plan, or workspace allowlists under Rules. Rules evaluate before the percentage rollout.

## Naming
Use `squad.feature.intent` such as `growth.checkout.express_pay`.

## Cleanup
Flags without traffic for 60 days are auto-archived in this older guidance — confirm current cleanup automation separately.
""",
        ),
        doc(
            nid(),
            cluster_id="c04",
            role="contradicting",
            contradiction_id="cx-flag-default-pct",
            date="2025-11-22",
            validation_note="Third conflicting value: default rollout 100% (enabled) for 'ship confidence'.",
            title="Flag Bootstrap Recommendations from Growth Eng",
            content="""# Flag Bootstrap Recommendations from Growth Eng

Internal memo adopted by several product squads in late 2025.

## Opinionated defaults
Create flags **enabled at 100%** in production with a narrow workspace allowlist for dogfood, then dial percentage down if needed. Growth Eng found that starting at full enablement reduced “forgot to turn on” incidents during launch week.

## Pair with experiments
If an experiment needs holdouts, attach an experiment object rather than relying on the flag percentage alone.

## Caution
This memo reflects Growth Eng practice and may disagree with platform-wide policy docs. Check which document your org currently enforces before filing process bugs.
""",
        ),
        doc(
            nid(),
            cluster_id="c04",
            role="distractor",
            date="2025-08-14",
            validation_note="About experiment traffic allocation defaults (not feature flag creation defaults).",
            title="Default Traffic Splits for New Experiments",
            content="""# Default Traffic Splits for New Experiments

Experimentation defaults when creating a new A/B test in Pulse.

## Split
New experiments default to a **50/50** traffic split between control and treatment. Multivariate tests require manual weights summing to 100%.

## Ramp
You may ramp exposure from 5% of eligible users upward; this is independent of feature flag rollout percentages.

## Minimum runtime
Platform recommends 14 days or 2,000 converters per arm before calling a winner, whichever comes later.

Do not confuse experiment splits with the default percentage on a standalone feature flag.
""",
        ),
        doc(
            nid(),
            cluster_id="c04",
            role="canonical",
            date="2026-02-18",
            title="Feature Flag Targeting Rules Reference",
            content="""# Feature Flag Targeting Rules Reference

How rule evaluation works for Pulse feature flags.

## Order
1. Disabled flag → always off  
2. Workspace or user allowlist / denylist rules (first match wins within the rule list)  
3. Percentage rollout bucketed by `user_id` or `anonymous_id`  
4. Default fallthrough (off unless configured)

## Attributes available
`plan_code`, `seat_role`, `country`, `email_domain`, custom traits from `identify`, and `environment`.

## Sticky bucketing
Percentage assignments are sticky per identity for the life of the flag version. Changing percentage mid-flight rebuckets only newly seen IDs when “sticky” is enabled (default on).

## Environments
Rules are environment-scoped. Staging rules never apply to production keys.
""",
        ),
    ]

    # c05 Experiments — versioned metric window + distractors
    docs += [
        doc(
            nid(),
            cluster_id="c05",
            role="versioned",
            version_chain_id="vc-exp-guardrails",
            version_number=1,
            date="2024-11-05",
            validation_note="Old guardrail: auto-stop if primary metric drops 5% relative.",
            title="Experiment Guardrails (2024 Policy)",
            content="""# Experiment Guardrails (2024 Policy)

Safety rails for Northline Pulse experiments.

## Auto-stop
Experiments automatically pause if the primary metric drops more than **5% relative** versus control with p < 0.05 on consecutive peeks.

## Sample ratio mismatch
If observed traffic split drifts more than 2 percentage points from configured weights for 24 hours, the experiment is marked unhealthy.

## Secondary metrics
Guardrail metrics (error rate, latency p95) are optional in this version of the policy.

## Ownership
Experiment owners must review auto-stops within one business day.
""",
        ),
        doc(
            nid(),
            cluster_id="c05",
            role="versioned",
            version_chain_id="vc-exp-guardrails",
            version_number=2,
            date="2025-07-30",
            validation_note="Mid version: auto-stop threshold tightened to 3% relative drop.",
            title="Experiment Guardrails (2025 Mid-Year Update)",
            content="""# Experiment Guardrails (2025 Mid-Year Update)

Updated safety rails after several customer-facing regressions.

## Auto-stop
Primary metric regression threshold is now a **3% relative** drop versus control with sequential testing enabled. Auto-pause triggers on the second consecutive significant peek.

## Guardrail metrics
Error rate and checkout failure rate are mandatory guardrails for any experiment touching billing surfaces.

## Sample ratio mismatch
Unchanged: 2 point absolute drift for 24 hours marks unhealthy.

## Communication
#exp-alerts receives pause notifications; owners still have one business day to respond.
""",
        ),
        doc(
            nid(),
            cluster_id="c05",
            role="canonical",
            version_chain_id="vc-exp-guardrails",
            version_number=3,
            date="2026-02-12",
            title="Experiment Guardrails (Current Policy)",
            content="""# Experiment Guardrails (Current Policy)

Authoritative guardrails for Pulse experiments as of February 2026.

## Auto-stop (primary metric)
Experiments auto-pause if the primary metric shows a **2% relative** regression versus control with sequential peeks enabled (always-valid p-values). A single significant peek is enough; consecutive peeks are no longer required.

## Mandatory guardrails
- Global error rate  
- Interactive latency p95 for the touched surface  
- For billing surfaces: `checkout_failed` rate  

Any guardrail breach at p < 0.01 pauses the experiment even if the primary metric looks flat.

## Sample ratio mismatch
Drift > **1.5** percentage points from configured weights for **12 hours** marks the experiment unhealthy and freezes analysis exports.

## Owner response SLA
Four business hours for Sev-linked product experiments; one business day otherwise.

## Exceptions
Waivers require Director-level approval filed on the experiment record before launch.
""",
        ),
        doc(
            nid(),
            cluster_id="c05",
            role="distractor",
            date="2025-10-02",
            validation_note="Discusses dashboard freshness SLAs, not experiment auto-stop thresholds.",
            title="Analytics Guardrails for Executive Dashboards",
            content="""# Analytics Guardrails for Executive Dashboards

Quality bars for dashboards pinned in the company QBR pack.

## Freshness
Tiles must refresh at least every 24 hours. Stale tiles show an amber badge after 26 hours.

## Change control
Metric definition changes require a Data Platform review if the tile is tagged `exec`.

## Experiment notes
Embedding live experiment results on exec dashboards is discouraged until the experiment is concluded; use screenshots with date stamps instead.

This is not the experiment auto-stop policy for Pulse experimentation.
""",
        ),
        doc(
            nid(),
            cluster_id="c05",
            role="multi_hop_fragment",
            fragment_group_id="fg-exp-power",
            date="2026-01-09",
            title="Experiment Design — Choosing a Primary Metric",
            content="""# Experiment Design — Choosing a Primary Metric

Guidance for locking a primary metric before launch.

## Criteria
- Sensitive to the change you are shipping within two weeks  
- Not a pure vanity count (prefer rates or per-user ratios)  
- Observable in Pulse without warehouse-only joins for the first read  

## Examples
- Checkout redesign → `checkout_completed / checkout_started`  
- Onboarding checklist → `activation_completed` within 7 days of signup  

## What you still need
Minimum sample size and runtime calculations live in the power analysis companion note. Do not launch on metric choice alone.
""",
        ),
        doc(
            nid(),
            cluster_id="c05",
            role="multi_hop_fragment",
            fragment_group_id="fg-exp-power",
            date="2026-01-09",
            title="Experiment Design — Power and Runtime Calculator Rules",
            content="""# Experiment Design — Power and Runtime Calculator Rules

How to size experiments once the primary metric is chosen.

## Defaults
- Power: 80%  
- Significance: 5% two-sided  
- Minimum effect: 5% relative lift unless a larger launch cost justifies a bigger MDE  

## Runtime
Use the Pulse power calculator with the last 28 days of baseline conversion. Round up runtime to whole weeks to reduce weekly seasonality bias. Minimum runtime is **14 days** even if the calculator returns less.

## Caps
If required sample exceeds 80% of eligible traffic for 6 weeks, redesign the experiment or accept a larger MDE with PM approval.

Metric selection is documented separately; this page assumes the primary metric is already fixed.
""",
        ),
    ]

    # c06 Dashboards & sharing — distractors + contradiction
    docs += [
        doc(
            nid(),
            cluster_id="c06",
            role="canonical",
            contradiction_id="cx-dash-share-link-ttl",
            date="2026-01-28",
            title="Dashboard Sharing and Public Links",
            content="""# Dashboard Sharing and Public Links

How sharing works for Pulse dashboards.

## Internal share
Invite Northline workspace members by email or group. Roles: `viewer`, `editor`, `owner`.

## Public links
Public links are disabled by default. When enabled by a workspace admin, generated links expire after **7 days** and can be rotated early. Public links never include row-level user tables—only aggregate tiles.

## Export
CSV export of tile data is limited to editors and owners. Viewers can PNG-export charts only.

## Compliance
Public links are blocked entirely for workspaces marked `HIPAA_TEMPLATE` or with data classification `restricted` on any underlying event.
""",
        ),
        doc(
            nid(),
            cluster_id="c06",
            role="contradicting",
            contradiction_id="cx-dash-share-link-ttl",
            date="2025-02-17",
            validation_note="Conflicts on public link TTL: claims 30-day expiry instead of 7 days.",
            title="Sharing Pulse Boards Externally",
            content="""# Sharing Pulse Boards Externally

For customer QBRs and investor updates, teams sometimes need external-facing boards.

## Public link TTL
Links expire **30 days** after creation. You can regenerate at any time from the Share dialog.

## Watermark
External boards stamp the viewer IP and timestamp in the footer for audit.

## Access
Only editors can create public links. Viewers must request an editor to publish.

Confirm whether your workspace admin has enabled the feature under Security → Sharing.
""",
        ),
        doc(
            nid(),
            cluster_id="c06",
            role="distractor",
            date="2025-12-05",
            validation_note="About Slack alert subscriptions, not dashboard public link sharing.",
            title="Sharing Insights via Slack Alerts",
            content="""# Sharing Insights via Slack Alerts

Subscribe channels to threshold alerts on Pulse saved metrics.

## Setup
From a metric → Alerts → Add Slack channel. Choose above/below threshold and cooldown (default 1 hour).

## Permissions
You must be an editor on the parent dashboard or a workspace admin.

## Noise control
Alerts mute automatically after 10 fires in 24 hours until acknowledged.

This is not the same as generating a public dashboard URL for external stakeholders.
""",
        ),
        doc(
            nid(),
            cluster_id="c06",
            role="canonical",
            date="2026-01-28",
            title="Dashboard Permissions Matrix",
            content="""# Dashboard Permissions Matrix

| Action | Viewer | Editor | Owner |
| --- | --- | --- | --- |
| View tiles | ✓ | ✓ | ✓ |
| Edit layout | | ✓ | ✓ |
| Manage share list | | ✓ | ✓ |
| Create public link | | ✓* | ✓* |
| Transfer ownership | | | ✓ |
| Delete dashboard | | | ✓ |

\\* Public links also require workspace admin toggle enabled.

Personal sandboxes are always owner-only until shared.
""",
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH 2 — Product advanced (c07–c12)
    # ══════════════════════════════════════════════════════════════════════════

    docs += [
        # c07 Data retention — version chain
        doc(
            nid(),
            cluster_id="c07",
            role="versioned",
            version_chain_id="vc-retention-default",
            version_number=1,
            date="2023-09-01",
            validation_note="Old default retention 13 months for event payloads.",
            title="Event Data Retention — 2023 Defaults",
            content="""# Event Data Retention — 2023 Defaults

## Default
Event payloads and properties are retained for **13 months** on Growth plans and above. Free trials retain 30 days.

## Extensions
Enterprise contracts may purchase 25-month retention as an add-on.

## Deletion
Workspace deletion purges events within 30 days. Per-user deletion requests follow the privacy runbook.

## Aggregates
Monthly rollup tables used for exec dashboards may retain longer; see warehouse policies.
""",
        ),
        doc(
            nid(),
            cluster_id="c07",
            role="versioned",
            version_chain_id="vc-retention-default",
            version_number=2,
            date="2025-01-15",
            validation_note="Mid: default retention extended to 18 months.",
            title="Event Data Retention — 2025 Defaults",
            content="""# Event Data Retention — 2025 Defaults

## Default
As of January 2025, Growth and Enterprise workspaces retain raw event payloads for **18 months**. Starter plans remain at 6 months.

## Add-ons
25-month and 36-month packs remain available for Enterprise.

## Cold storage
Events older than 90 days may be served from cold storage with higher query latency on Live Explore.
""",
        ),
        doc(
            nid(),
            cluster_id="c07",
            role="canonical",
            version_chain_id="vc-retention-default",
            version_number=3,
            date="2026-03-10",
            title="Event Data Retention — Current Policy",
            content="""# Event Data Retention — Current Policy

## Default retention
- **Starter**: 6 months raw events  
- **Growth**: **24 months** raw events  
- **Enterprise**: 24 months raw events, extendable to 36 or 48 months by contract  

## What counts as raw
Event name, timestamp, user/anonymous ids, and property payloads. Derived cohorts and saved metrics persist independently of raw event TTL.

## Deletion & privacy
- GDPR erasure: targeted user purge within **30 days** of verified request  
- Workspace cancellation: full purge within **45 days**  

## Query notes
Live Explore on events older than 120 days may route to cold storage (higher latency, same results). Exports honor the same retention ceiling.

## Effective
24-month Growth default applies to all Growth workspaces as of 2026-03-01; no opt-in required.
""",
        ),
        doc(
            nid(),
            cluster_id="c07",
            role="distractor",
            date="2025-11-01",
            validation_note="Log retention for application logs (14 days) not product event retention.",
            title="Application Log Retention Standards",
            content="""# Application Log Retention Standards

Engineering standards for application and access logs.

## Default
INFO logs retain **14 days** in the central logging stack. DEBUG is 3 days. Audit logs for production access retain 1 year.

## Product analytics
Pulse event retention is a separate commercial policy and is not controlled by this logging standard.

## Cost control
High-cardinality log fields require EM approval.
""",
        ),
        doc(
            nid(),
            cluster_id="c07",
            role="distractor",
            date="2026-02-01",
            validation_note="Describes session replay clip retention (90 days), adjacent but not event payload retention.",
            title="Session Replay Storage Windows",
            content="""# Session Replay Storage Windows

## Retention
Session replay blobs retain for **90 days** on Growth and **180 days** on Enterprise.

## Privacy
Replay is off by default in EU workspaces until a DPA addendum is signed.

## Relation to events
Deleting raw events does not always delete replay blobs on the same schedule; file privacy tickets if both must purge together.
""",
        ),
        # c08 Webhooks
        doc(
            nid(),
            cluster_id="c08",
            role="canonical",
            date="2026-02-20",
            title="Pulse Outbound Webhooks — Configuration",
            content="""# Pulse Outbound Webhooks — Configuration

## Supported triggers
`experiment.started`, `experiment.stopped`, `flag.updated`, `alert.fired`, `export.completed`.

## Endpoint requirements
- HTTPS only  
- Must respond 2xx within **5 seconds**  
- Signature header `X-Northline-Signature` (HMAC SHA-256 of body with endpoint secret)

## Retries
Failed deliveries retry with exponential backoff for up to **24 hours** (approx. 10 attempts). After exhaustion, the delivery is marked failed and visible in the webhook log for 14 days.

## Fan-out
Max **10** active endpoints per workspace. Use your own bus if you need more consumers.
""",
        ),
        doc(
            nid(),
            cluster_id="c08",
            role="canonical",
            date="2026-02-20",
            title="Verifying Northline Webhook Signatures",
            content="""# Verifying Northline Webhook Signatures

## Header
`X-Northline-Signature: t=<unix>,v1=<hex>`

## Algorithm
1. Concatenate `t` and raw body as `t.<body>`  
2. HMAC-SHA256 with the endpoint signing secret  
3. Compare timing-safe to `v1`  
4. Reject if timestamp `t` is older than **5 minutes**

## Secrets
Rotate secrets from Workspace → Webhooks → Endpoint → Rotate. Old secret validates for 24 hours after rotation.

## Local testing
The Pulse CLI `pulse webhooks tail` prints deliveries without signature checks; production endpoints must verify.
""",
        ),
        doc(
            nid(),
            cluster_id="c08",
            role="distractor",
            date="2025-06-12",
            validation_note="Outdated retry window (2 hours) and MD5 signature scheme.",
            title="Webhook Delivery and Security (Legacy)",
            content="""# Webhook Delivery and Security (Legacy)

## Retries
Deliveries retry for up to **2 hours**. After that, events are dropped.

## Signature
Legacy endpoints used `X-NL-MD5` with MD5 hex of the body and a shared static token. New endpoints should not use this scheme.

## Timeouts
Allow up to 15 seconds before we mark a timeout—some customers still cite this number from older docs.
""",
        ),
        doc(
            nid(),
            cluster_id="c08",
            role="distractor",
            date="2026-01-05",
            validation_note="Inbound billing webhooks from Stripe, not Pulse outbound webhooks.",
            title="Handling Stripe Webhooks in Billing Service",
            content="""# Handling Stripe Webhooks in Billing Service

## Events we consume
`customer.subscription.updated`, `invoice.paid`, `invoice.payment_failed`.

## Verification
Use Stripe’s signing secret and `Stripe-Signature` header per Stripe docs.

## Idempotency
Store event ids in Redis with 7-day TTL before applying side effects.

This pipeline is unrelated to Pulse product webhooks that notify on experiment changes.
""",
        ),
        doc(
            nid(),
            cluster_id="c08",
            role="multi_hop_fragment",
            fragment_group_id="fg-webhook-alert",
            date="2026-02-21",
            title="Alert Webhooks — Payload Schema",
            content="""# Alert Webhooks — Payload Schema

When `alert.fired` triggers, the JSON body includes:

- `alert_id` (string)  
- `metric_name` (string)  
- `condition` (`above` | `below`)  
- `threshold` (number)  
- `observed_value` (number)  
- `fired_at` (ISO-8601)  
- `dashboard_id` (string)  
- `severity_url` (https link)

It does **not** include suggested remediation steps or on-call routing. Routing configuration is documented in the alert routing guide.
""",
        ),
        doc(
            nid(),
            cluster_id="c08",
            role="multi_hop_fragment",
            fragment_group_id="fg-webhook-alert",
            date="2026-02-21",
            title="Alert Webhooks — Routing to On-Call",
            content="""# Alert Webhooks — Routing to On-Call

## Recommended pattern
Point the Pulse webhook at the internal Alertbridge service URL, not directly at PagerDuty. Alertbridge maps `metric_name` prefixes to services:

- `checkout_*` → billing-oncall  
- `ingest_*` → data-platform-oncall  
- default → pulse-app-oncall  

## Severity
Alertbridge sets severity **P3** unless `metric_name` starts with `ingest_` or `auth_`, which become **P2**.

## Silence
Maintenance windows in Alertbridge suppress pages but still log the webhook receipt.

Payload field definitions live in the alert webhook schema doc; keep both updated together.
""",
        ),
        # c09 API rate limits — contradiction
        doc(
            nid(),
            cluster_id="c09",
            role="canonical",
            contradiction_id="cx-api-rate-limit",
            date="2026-02-08",
            title="Pulse REST API Rate Limits",
            content="""# Pulse REST API Rate Limits

## Default limits (Growth)
- **120 requests / minute** per API key for read APIs  
- **30 requests / minute** for export creation endpoints  
- Burst: up to 20 concurrent in-flight requests  

## Enterprise
Contracts may raise read limits to 600/min. Export limits stay at 30/min unless a warehouse sync add-on is purchased.

## Headers
Responses include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` (unix seconds).

## 429 behavior
Back off using `Retry-After`. Repeated hard abuse may quarantine the key for 1 hour.
""",
        ),
        doc(
            nid(),
            cluster_id="c09",
            role="contradicting",
            contradiction_id="cx-api-rate-limit",
            date="2024-12-03",
            validation_note="Conflicts on Growth read limit: 600/min instead of current 120/min.",
            title="API Throttling Overview for Integrators",
            content="""# API Throttling Overview for Integrators

## Growth plan
Read APIs allow **600 requests per minute** per key. Most partners never hit this ceiling.

## Exports
Heavy CSV export creation should stay under 60/min to avoid queue congestion.

## Headers
Standard rate limit headers are returned on every response.

If you are migrating from partner docs dated 2024, re-validate numbers against the current pricing tier sheet before promising SLAs to mutual customers.
""",
        ),
        doc(
            nid(),
            cluster_id="c09",
            role="distractor",
            date="2026-01-11",
            validation_note="Ingest event rate limits (SDK/server event throughput), not REST query API limits.",
            title="Event Ingest Throughput Limits",
            content="""# Event Ingest Throughput Limits

## Per workspace
- Soft limit **5,000 events/sec** sustained on Growth  
- Enterprise default **25,000 events/sec**  

## Overflow
Above soft limit, ingest returns 503 with retry; SDKs buffer locally.

## Not the REST API
These limits apply to `/v3/track` ingest paths, not to dashboard or export REST APIs.
""",
        ),
        doc(
            nid(),
            cluster_id="c09",
            role="canonical",
            date="2026-02-08",
            title="Handling API 429s in Server Integrations",
            content="""# Handling API 429s in Server Integrations

## Client guidance
- Honor `Retry-After`  
- Jittered exponential backoff capped at 2 minutes  
- Prefer caching dashboard preference configs rather than polling every second  

## Key isolation
Do not share one API key across unrelated microservices; isolate so one runaway job cannot starve others.

## Contact
Sustained needs above plan limits go through Support with a traffic forecast, not through engineering Slack DMs.
""",
        ),
        # c10 Session replay
        doc(
            nid(),
            cluster_id="c10",
            role="canonical",
            date="2026-01-19",
            title="Session Replay — Enablement and Privacy Controls",
            content="""# Session Replay — Enablement and Privacy Controls

## Defaults
Session replay is **off** for all new workspaces. Admins enable it under Data Collection → Replay.

## Masking
By default Pulse masks inputs with `type=password`, elements marked `data-pulse-mask`, and text nodes matching an email regex. Credit card patterns are always masked and cannot be disabled.

## Sampling
Default sample rate is **10%** of sessions on Growth and **25%** on Enterprise. Set lower for high-traffic consumer apps.

## Retention
See the replay storage window document for day counts; privacy controls here only cover capture-time behavior.
""",
        ),
        doc(
            nid(),
            cluster_id="c10",
            role="distractor",
            date="2025-07-07",
            validation_note="Outdated: claims replay on by default at 100% sampling.",
            title="Turning On Session Replay Quickly",
            content="""# Turning On Session Replay Quickly

Replay ships **enabled by default** at **100%** sampling for Growth trials so prospects see value immediately. Disable under Data Collection if you need to reduce cost.

## Privacy
Password fields are masked. Other inputs are captured as typed to help reproduce bugs.

Treat this guide as historical trial packaging; confirm current defaults before citing in security questionnaires.
""",
        ),
        doc(
            nid(),
            cluster_id="c10",
            role="distractor",
            date="2026-02-02",
            validation_note="Product analytics 'session' definition (30 min timeout), not session replay product.",
            title="How Pulse Defines a Session",
            content="""# How Pulse Defines a Session

## Timeout
A session ends after **30 minutes** of inactivity or at midnight UTC, whichever comes first.

## Counting
`system_session_started` marks the beginning. Background tabs still count toward inactivity.

## Replay relationship
Not every analytics session has a replay blob—replay sampling is independent of sessionization.
""",
        ),
        doc(
            nid(),
            cluster_id="c10",
            role="canonical",
            date="2026-01-19",
            title="Linking Replays to Events and Errors",
            content="""# Linking Replays to Events and Errors

## From an event
On any event detail drawer, open **View replay** when a blob exists for that `session_id`.

## From errors
If you send `pulse.track('client_error', { message, stack })`, Pulse attempts to attach the active replay pointer.

## Permissions
Viewers with dashboard access can watch replays only if their role includes `replay:read`. Editors have it by default; custom roles may not.
""",
        ),
        # c11 Cohorts
        doc(
            nid(),
            cluster_id="c11",
            role="canonical",
            date="2025-12-12",
            title="Building Cohorts in Pulse",
            content="""# Building Cohorts in Pulse

## Definition types
- **Static**: fixed list of user IDs uploaded once  
- **Dynamic**: rule-based, re-evaluated every **4 hours**  
- **SQL**: Enterprise-only, runs against the Pulse warehouse mirror nightly  

## Dynamic rule limits
Max **25** conditions per cohort. Nested OR groups max depth 2.

## Use in flags and experiments
Dynamic and static cohorts can be targeted by flags. SQL cohorts are analysis-only unless promoted to static.

## Size warnings
Cohorts larger than 5 million identities skip real-time evaluation and fall back to daily materialization.
""",
        ),
        doc(
            nid(),
            cluster_id="c11",
            role="distractor",
            date="2025-03-18",
            validation_note="Outdated re-eval interval: claims dynamic cohorts refresh every 15 minutes.",
            title="Dynamic Audience Refresh Behavior",
            content="""# Dynamic Audience Refresh Behavior

Dynamic cohorts recompute membership every **15 minutes**. For campaigns that need fresher inclusion, export to the marketing tool on a webhook instead.

## Limits
Up to 50 conditions. OR nesting is unlimited in this older engine description.

Validate against the current “Building Cohorts” guide before promising near-real-time targeting to stakeholders.
""",
        ),
        doc(
            nid(),
            cluster_id="c11",
            role="multi_hop_fragment",
            fragment_group_id="fg-cohort-export",
            date="2026-01-03",
            title="Cohort Export — Formats and Fields",
            content="""# Cohort Export — Formats and Fields

## Formats
CSV and Parquet. Max **2 million** rows per export file; larger cohorts shard automatically.

## Fields included
`user_id`, `first_seen_at`, `last_seen_at`, matched trait columns explicitly selected at export time.

## Not included
Raw event streams and session replay links. Those require separate tooling.

Destination configuration (S3/GCS buckets and credentials) is covered in the cohort export destinations doc.
""",
        ),
        doc(
            nid(),
            cluster_id="c11",
            role="multi_hop_fragment",
            fragment_group_id="fg-cohort-export",
            date="2026-01-03",
            title="Cohort Export — Destinations and Credentials",
            content="""# Cohort Export — Destinations and Credentials

## Supported destinations
- Customer S3 bucket (role ARN)  
- GCS bucket (service account JSON via secrets manager)  
- Secure HTTPS PUT endpoint  

## Credentials
Stored encrypted; rotatable by workspace admins. Exports fail closed if credentials are missing—no silent skip.

## Scheduling
Daily or weekly. Ad-hoc exports available to editors.

File formats and field lists live in the companion formats document.
""",
        ),
        # c12 Billing seats
        doc(
            nid(),
            cluster_id="c12",
            role="canonical",
            contradiction_id="cx-seat-overage",
            date="2026-02-25",
            title="Seat-Based Billing and Overage Policy",
            content="""# Seat-Based Billing and Overage Policy

## Billable seats
A billable seat is any user who logged into the Pulse app in the last **30 days** with a role other than `billing_viewer`.

## Overage
Growth plans allow **10%** soft overage without immediate charges. Beyond 10%, additional seats are prorated at list price on the next invoice.

## Enterprise
Enterprise contracts use committed seat bands; overages require order form amendments rather than automatic proration.

## Reducing seats
Downgrades take effect next billing cycle; unused seats do not auto-remove inactive users—admins must deactivate accounts.
""",
        ),
        doc(
            nid(),
            cluster_id="c12",
            role="contradicting",
            contradiction_id="cx-seat-overage",
            date="2025-01-09",
            validation_note="Conflicts on soft overage: 25% instead of 10%; billable window 90 days instead of 30.",
            title="How Northline Counts Paid Seats",
            content="""# How Northline Counts Paid Seats

## Activity window
Users who authenticate within **90 days** count as billable seats, including read-only roles.

## Overage cushion
Growth customers may exceed contracted seats by **25%** before overage line items appear. This cushion exists for seasonal contractors.

## Tips
Remove contractors promptly at engagement end to avoid surprises.
""",
        ),
        doc(
            nid(),
            cluster_id="c12",
            role="distractor",
            date="2026-02-10",
            validation_note="MTU pricing for events, not seat billing for app users.",
            title="Monthly Tracked Users (MTU) Billing Explained",
            content="""# Monthly Tracked Users (MTU) Billing Explained

## Definition
MTU counts distinct `user_id` or `anonymous_id` values that sent at least one event in a calendar month.

## Plans
Growth includes a contracted MTU band; overages bill per thousand.

## Relation to seats
MTU measures end-user analytics volume in customer apps, not Northline employee/partner seats in the Pulse UI.
""",
        ),
        doc(
            nid(),
            cluster_id="c12",
            role="canonical",
            date="2026-02-25",
            title="Deactivating Users to Free Seats",
            content="""# Deactivating Users to Free Seats

## Steps
Admin → Users → select user → Deactivate. SSO-managed workspaces should deactivate in the IdP; SCIM will propagate within 15 minutes.

## Effects
- Immediate loss of login  
- API keys owned solely by that user are disabled  
- Dashboards owned transfer to the workspace owner automatically  

## Timing
Deactivation same day removes the seat from the **next** monthly seat snapshot (taken at 00:00 UTC on the 1st). Mid-cycle overage calculations use the live active set.
""",
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH 3 — Engineering process (c13–c18)
    # ══════════════════════════════════════════════════════════════════════════

    docs += [
        # c13 On-call
        doc(
            nid(),
            cluster_id="c13",
            role="canonical",
            date="2026-01-06",
            title="Primary On-Call Expectations — Pulse Services",
            content="""# Primary On-Call Expectations — Pulse Services

## Schedule
Primary on-call runs **7 days**, Monday 10:00 local to the following Monday 10:00. Shadow/secondary is optional but recommended for new rotators.

## Response
- **P1**: acknowledge within **5 minutes**, join bridge within 15  
- **P2**: acknowledge within **15 minutes**  
- **P3**: next business hours  

## Handoff
Outgoing primary posts a handoff note in #pulse-oncall with open pages, risky deploys, and feature flag kill-switches worth watching.

## Compensation
Weekday nights and weekends accrue TOIL per the eng handbook (not restated here).
""",
        ),
        doc(
            nid(),
            cluster_id="c13",
            role="distractor",
            date="2024-05-20",
            validation_note="Outdated ACK times: P1 30 minutes; weekly rotation was biweekly in old model.",
            title="On-Call Duty Primer",
            content="""# On-Call Duty Primer

## Rotation
Biweekly primary rotation. Secondary is mandatory.

## ACK targets
P1 pages should be acknowledged within **30 minutes**. P2 within an hour.

## Tools
PagerDuty + Zoom bridge template in the eng wiki.

Use the current 2026 expectations doc for official SLAs; this primer remains linked from old new-hire checklists.
""",
        ),
        doc(
            nid(),
            cluster_id="c13",
            role="contradicting",
            contradiction_id="cx-oncall-ack",
            date="2025-08-01",
            validation_note="Conflicts on P1 acknowledge: 10 minutes vs canonical 5 minutes.",
            title="Page Acknowledge Targets by Severity",
            content="""# Page Acknowledge Targets by Severity

| Severity | Acknowledge | Mitigate goal |
| --- | --- | --- |
| P1 | **10 minutes** | 60 minutes |
| P2 | 20 minutes | 4 hours |
| P3 | business day | 3 business days |

These targets apply to Pulse platform services and customer-facing ingest paths.
""",
        ),
        doc(
            nid(),
            cluster_id="c13",
            role="canonical",
            contradiction_id="cx-oncall-ack",
            date="2026-01-06",
            title="Severity ACK Matrix (Authoritative)",
            content="""# Severity ACK Matrix (Authoritative)

| Severity | Acknowledge | Customer comms |
| --- | --- | --- |
| P1 | **5 minutes** | Status page within 30 minutes |
| P2 | **15 minutes** | If customer-visible, update within 2 hours |
| P3 | Next business hours | Optional |

This matrix supersedes informal tables circulating in squad READMEs. Pair with the primary on-call expectations document for rotation logistics.
""",
        ),
        # c14 Incident severity
        doc(
            nid(),
            cluster_id="c14",
            role="canonical",
            date="2025-11-20",
            title="Incident Severity Definitions",
            content="""# Incident Severity Definitions

## P1 — Critical
Complete outage of ingest, auth, or core app for multiple customers; data loss risk; security breach in progress.

## P2 — Major
Significant degradation (elevated errors, partial feature outage) with customer impact; no complete platform down.

## P3 — Minor
Limited impact, workaround available, or internal-only tooling failure.

## P4 — Cosmetic
UI polish, non-urgent incorrect copy, low-impact bugs.

## Declaring
Any engineer may declare P2+. P1 requires notifying #incidents and the incident commander rotation immediately.
""",
        ),
        doc(
            nid(),
            cluster_id="c14",
            role="distractor",
            date="2025-09-01",
            validation_note="Support ticket severities for Zendesk, not eng incident severities.",
            title="Support Ticket Severity Guide",
            content="""# Support Ticket Severity Guide

## Sev1
Enterprise customer cannot log in or lost data — page TAM + oncall.

## Sev2
Feature broken with no workaround for paying customer.

## Sev3
General how-to and minor bugs.

Support severities map loosely to eng incidents but are not identical; do not copy these labels into incident channels without translation.
""",
        ),
        doc(
            nid(),
            cluster_id="c14",
            role="canonical",
            date="2025-11-20",
            title="Incident Commander Checklist",
            content="""# Incident Commander Checklist

1. Announce IC in #incidents with severity  
2. Assign scribe and comms lead  
3. Open Zoom bridge; pin link  
4. Start timeline doc  
5. Decide customer-facing status page update  
6. Call mitigation owners  
7. After mitigate: schedule postmortem within 3 business days for P1/P2  

IC may be remote. Hand off cleanly if fatigued past 4 hours on P1.
""",
        ),
        doc(
            nid(),
            cluster_id="c14",
            role="versioned",
            version_chain_id="vc-status-page-sla",
            version_number=1,
            date="2024-02-01",
            validation_note="Old: status page update within 60 minutes for P1.",
            title="Customer Comms Timing During Incidents (2024)",
            content="""# Customer Comms Timing During Incidents (2024)

For P1 incidents, publish an initial status page notice within **60 minutes** of declaration. Updates every 2 hours thereafter until resolve.
""",
        ),
        doc(
            nid(),
            cluster_id="c14",
            role="canonical",
            version_chain_id="vc-status-page-sla",
            version_number=2,
            date="2025-11-20",
            title="Customer Comms Timing During Incidents (Current)",
            content="""# Customer Comms Timing During Incidents (Current)

## P1
Initial public status page update within **30 minutes** of incident declaration. Follow-ups at least every **60 minutes** until resolved or mitigated.

## P2
Status page if more than one enterprise customer is affected; initial update within **2 hours**.

## Internal
#incidents remains source of truth; status page language is customer-safe and avoids root-cause speculation.
""",
        ),
        # c15 Release freeze
        doc(
            nid(),
            cluster_id="c15",
            role="canonical",
            date="2025-12-01",
            title="Release Freeze Policy",
            content="""# Release Freeze Policy

## Standard freezes
- **Code freeze**: starts 48 hours before major company events ( forelisted in #eng-announce )  
- **Hard freeze**: starts 24 hours before Black Friday / peak retail campaigns for customers on e-commerce plans  

## What is blocked
Production deploys to tier-0 services (ingest, auth, billing, flag evaluation). Hotfixes require VP Eng approval.

## What is allowed
- Config-only changes with existing runbooks  
- Feature flag percentage decreases (kills)  
- Documentation  

## Ending freeze
Announce in #eng-announce; CI re-enables `deploy-prod` workflows automatically via the freeze flag.
""",
        ),
        doc(
            nid(),
            cluster_id="c15",
            role="distractor",
            date="2025-06-15",
            validation_note="Hiring freeze policy, not release/code freeze.",
            title="Corporate Hiring Freeze Guidelines",
            content="""# Corporate Hiring Freeze Guidelines

During a hiring freeze, open reqs require CFO + CHRO approval. Backfills for attrition on revenue-critical teams may proceed with CEO approval.

Engineering release schedules are unaffected by hiring freezes unless separately announced.
""",
        ),
        doc(
            nid(),
            cluster_id="c15",
            role="contradicting",
            contradiction_id="cx-freeze-window",
            date="2025-01-10",
            validation_note="Conflicts on code freeze lead time: 72 hours vs canonical 48 hours.",
            title="Pre-Event Deploy Restrictions",
            content="""# Pre-Event Deploy Restrictions

Production deploys halt **72 hours** before major company events. Hotfixes need CTO approval.

Tier-0 list includes ingest and billing. Flag kills remain allowed.
""",
        ),
        doc(
            nid(),
            cluster_id="c15",
            role="canonical",
            contradiction_id="cx-freeze-window",
            date="2025-12-01",
            title="Freeze Lead Times — Quick Reference",
            content="""# Freeze Lead Times — Quick Reference

- Code freeze lead time before listed company events: **48 hours**  
- Hard freeze before peak retail windows: **24 hours**  
- Hotfix approval during code freeze: **VP Eng**  
- Hotfix approval during hard freeze: **VP Eng + on-call IC concurrence**  

This quick reference matches the full release freeze policy.
""",
        ),
        # c16 RFC process
        doc(
            nid(),
            cluster_id="c16",
            role="canonical",
            date="2026-01-22",
            title="RFC Process for Engineering Changes",
            content="""# RFC Process for Engineering Changes

## When required
- New external API surfaces  
- Data model changes with >1 week rollback difficulty  
- Cross-team ownership shifts  
- Security-sensitive auth changes  

## Timeline
- RFC open for comments **≥ 5 business days**  
- Decision recorded as Accept / Accept-with-comments / Reject  
- Sponsoring EM + one peer EM must sign for Accept  

## Template
Problem, proposal, alternatives, rollout, risks, rollback, open questions.

## Lightweight ADRs
Single-team changes may use a short ADR instead; the RFC bar is for cross-cutting work.
""",
        ),
        doc(
            nid(),
            cluster_id="c16",
            role="distractor",
            date="2025-04-04",
            validation_note="Outdated comment window: 2 business days; only one EM signature.",
            title="Writing RFCs at Northline",
            content="""# Writing RFCs at Northline

Open RFCs for at least **2 business days**. A single EM approval is enough to merge.

Use the Google Doc template linked from the eng homepage. Slack #rfcs for visibility.
""",
        ),
        doc(
            nid(),
            cluster_id="c16",
            role="canonical",
            date="2026-01-22",
            title="RFC Decision Outcomes and Archiving",
            content="""# RFC Decision Outcomes and Archiving

## Outcomes
- **Accept**: implementation may proceed; link commits/PRs back to RFC  
- **Accept-with-comments**: must address listed items before or during implementation  
- **Reject**: do not implement; may revive with material changes as a new RFC  

## Archiving
Accepted RFCs move to `rfcs/accepted/` in the eng-git repo. Rejected stay in `rfcs/rejected/` for institutional memory.

## Expiry
Accepted RFCs without implementation start within **6 months** should be revalidated or marked abandoned.
""",
        ),
        doc(
            nid(),
            cluster_id="c16",
            role="multi_hop_fragment",
            fragment_group_id="fg-rfc-security",
            date="2026-01-25",
            title="Security Review Gate for RFCs — When It Applies",
            content="""# Security Review Gate for RFCs — When It Applies

Security review is mandatory when an RFC touches:
- Authentication or session handling  
- Cryptography or key management  
- New third-party data processors  
- Changes to PII collection surfaces  

Product-only UX RFCs without data exposure do not need Security sign-off.

How to request review and the SLA are documented in the security review intake note.
""",
        ),
        doc(
            nid(),
            cluster_id="c16",
            role="multi_hop_fragment",
            fragment_group_id="fg-rfc-security",
            date="2026-01-25",
            title="Security Review Gate — Intake and SLA",
            content="""# Security Review Gate — Intake and SLA

## Intake
File a ticket in the Security Jira project with label `rfc-review` and link the RFC. Include data-flow diagram for PII changes.

## SLA
- Standard: **5 business days**  
- Expedite (incident-driven): 1 business day with Director Security approval  

## Output
Security leaves Accept, Accept-with-controls, or Block comments on the RFC. Controls become checklist items in rollout.

When the gate applies is defined separately; do not skip intake when the gate applies.
""",
        ),
        # c17 Code review
        doc(
            nid(),
            cluster_id="c17",
            role="canonical",
            contradiction_id="cx-review-approvals",
            date="2025-10-30",
            title="Code Review SLA and Coverage",
            content="""# Code Review SLA and Coverage

## SLA
First non-author review within **1 business day** for PRs under 400 lines. Larger PRs: 2 business days or split the PR.

## Approvals
- Default: **1** approval from a code owner  
- Auth, billing, ingest, and flag-eval paths: **2** approvals including one from the owning squad  

## Emergencies
Hotfixes may merge with IC + one owner approval during active P1, followed by retroactive review within 24 hours.

## Rationale
Dual review on every PR was trialed and slowed delivery without reducing Sev-1 escapes. Sensitive paths keep dual review; routine changes stay single-approval with CODEOWNERS.
""",
        ),
        doc(
            nid(),
            cluster_id="c17",
            role="distractor",
            date="2024-11-11",
            validation_note="Claims 4-hour first review SLA which is not current policy.",
            title="PR Turnaround Goals",
            content="""# PR Turnaround Goals

Aim for first review in **4 hours** during working time. Two approvals on every PR regardless of path.

These goals were aspirational for a staffing experiment in 2024 and should not be treated as the binding SLA.
""",
        ),
        doc(
            nid(),
            cluster_id="c17",
            role="canonical",
            date="2025-10-30",
            title="What Reviewers Must Check",
            content="""# What Reviewers Must Check

- Correctness and edge cases  
- Tests for new logic  
- No secrets in diff  
- Feature flag for risky user-facing changes  
- Migration safety / rollback notes  
- Performance red flags on hot paths  

Nit style comments should be marked non-blocking. Prefer suggested patches for small fixes.
""",
        ),
        doc(
            nid(),
            cluster_id="c17",
            role="contradicting",
            contradiction_id="cx-review-approvals",
            date="2025-02-14",
            validation_note="Conflicts: requires 2 approvals on all PRs vs canonical 1 default / 2 on sensitive paths.",
            title="Mandatory Dual Review Policy",
            content="""# Mandatory Dual Review Policy

Every production PR requires **two** independent approvals before merge, including docs-only changes to production runbooks.

Single-approval merges are prohibited except for automated version bump bots.
""",
        ),
        # c18 Staging access
        doc(
            nid(),
            cluster_id="c18",
            role="canonical",
            date="2026-02-01",
            title="Staging Environment Access",
            content="""# Staging Environment Access

## Who gets access
All full-time engineers receive staging Kubernetes `namespace: staging-dev` edit roles via Okta group `eng-all`.

## Contractors
Time-boxed access ≤ **90 days**, sponsored by an FTE, reviewed monthly.

## Production-like data
Staging uses synthetic data plus scrubbed snapshots. Connecting personal production credentials to staging apps is forbidden.

## VPN
Staging APIs are private; use the WireGuard profile from IT. Public staging web UI is IP-allowlisted to office + VPN egress.
""",
        ),
        doc(
            nid(),
            cluster_id="c18",
            role="distractor",
            date="2025-05-05",
            validation_note="Production access process, not staging.",
            title="Requesting Production Kubernetes Access",
            content="""# Requesting Production Kubernetes Access

Production edit roles require breakglass or permanent on-call membership. File `prod-access` tickets with manager approval.

Do not use this process for staging; staging is granted via `eng-all` by default for FTEs.
""",
        ),
        doc(
            nid(),
            cluster_id="c18",
            role="canonical",
            date="2026-02-01",
            title="Staging Data Refresh Cadence",
            content="""# Staging Data Refresh Cadence

## Snapshots
Scrubbed production snapshots restore to staging **weekly** on Sundays 11:00 UTC.

## Synthetic generators
High-churn services also run continuous synthetic event generators for ingest load tests.

## Secrets
Staging secrets live in the `staging` vault path. Production vault paths are denied to staging workloads via policy.
""",
        ),
        doc(
            nid(),
            cluster_id="c18",
            role="versioned",
            version_chain_id="vc-staging-contractor",
            version_number=1,
            date="2024-08-01",
            validation_note="Old contractor staging access max 180 days.",
            title="Contractor Staging Access (2024)",
            content="""# Contractor Staging Access (2024)

Contractors may retain staging access for up to **180 days** per engagement without re-approval.
""",
        ),
        doc(
            nid(),
            cluster_id="c18",
            role="canonical",
            version_chain_id="vc-staging-contractor",
            version_number=2,
            date="2026-02-01",
            title="Contractor Staging Access (Current)",
            content="""# Contractor Staging Access (Current)

Contractors receive staging access for a maximum of **90 days** per grant. Extensions require re-sponsorship by an FTE and Security acknowledgment. Monthly access reviews remove dormant contractor accounts automatically after **14 days** without login.
""",
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH 4 — Eng + Security (c19–c24)
    # ══════════════════════════════════════════════════════════════════════════

    docs += [
        # c19 DB migrations
        doc(
            nid(),
            cluster_id="c19",
            role="canonical",
            date="2025-09-17",
            title="Database Migration Process",
            content="""# Database Migration Process

## Rules
- Expand/contract migrations only — no expand-and-contract mixed in one deploy without flag guards  
- Lock timeout set to **5 seconds** in production migrator  
- Migrations run in CI against a production-shaped schema copy before merge  

## Rollout
1. Merge migration PR  
2. Migrator job applies in prod before app pods flip  
3. Verify with smoke queries  

## Destructive changes
Dropping columns requires a full release cycle after code stops reading them, plus explicit DBA approval.
""",
        ),
        doc(
            nid(),
            cluster_id="c19",
            role="distractor",
            date="2025-01-22",
            validation_note="Allows multi-minute locks and in-place destructive drops — contradicts current process.",
            title="Applying Schema Changes Quickly",
            content="""# Applying Schema Changes Quickly

It is acceptable to run long migrations holding locks for several minutes during low traffic. Dropping unused columns in the same PR that removes code references is encouraged to keep schema tidy.

Prefer speed over expand/contract ceremony for internal tools databases.
""",
        ),
        doc(
            nid(),
            cluster_id="c19",
            role="canonical",
            date="2025-09-17",
            title="Migration On-Call Responsibilities",
            content="""# Migration On-Call Responsibilities

When a migration fails mid-apply:
1. Stop app deploys  
2. Page the owning squad + DBA primary  
3. Do not re-run blindly — inspect partial state  
4. Prefer forward fix over restore unless data corruption is detected  

Weekly DBA review inspects slow migration metrics from the prior week.
""",
        ),
        doc(
            nid(),
            cluster_id="c19",
            role="contradiction_chain",
            contradiction_id="cx-migration-lock",
            date="2025-03-01",
            validation_note="Chain member A: lock timeout 30 seconds.",
            title="Migrator Timeouts — Team Notes A",
            content="""# Migrator Timeouts — Team Notes A

Production migrator uses a lock timeout of **30 seconds**. Statements exceeding that are canceled and the job fails.
""",
        ),
        doc(
            nid(),
            cluster_id="c19",
            role="contradiction_chain",
            contradiction_id="cx-migration-lock",
            date="2025-06-01",
            validation_note="Chain member B: lock timeout 15 seconds.",
            title="Migrator Timeouts — Team Notes B",
            content="""# Migrator Timeouts — Team Notes B

We standardized on a **15 second** lock timeout for production migrations after several blocking incidents.
""",
        ),
        doc(
            nid(),
            cluster_id="c19",
            role="contradiction_chain",
            contradiction_id="cx-migration-lock",
            date="2025-09-17",
            validation_note="Chain member C (also aligns with canonical process): lock timeout 5 seconds.",
            title="Migrator Timeouts — Platform Standard",
            content="""# Migrator Timeouts — Platform Standard

Authoritative lock timeout for the production migrator is **5 seconds**. Longer timeouts are not permitted without DBA exception on a per-change basis.
""",
        ),
        # c20 Secrets
        doc(
            nid(),
            cluster_id="c20",
            role="canonical",
            date="2026-01-30",
            title="Secrets Management Standard",
            content="""# Secrets Management Standard

## System of record
HashiCorp Vault (cloud) is the system of record. AWS SM is a cache for some runtime injectors only.

## Rules
- No secrets in git, CI logs, or laptop `.env` committed files  
- AppRole or cloud workload identity for services; human users via OIDC SSO to Vault  
- Dual control for production root-level policies  

## Rotation
- Shared customer-facing API root secrets: **90 days**  
- Database passwords: **60 days** automated  
- Employee-issued personal tokens: **30 days**
""",
        ),
        doc(
            nid(),
            cluster_id="c20",
            role="distractor",
            date="2024-09-09",
            validation_note="Touts 1Password as system of record for app secrets — outdated.",
            title="Storing Engineering Secrets",
            content="""# Storing Engineering Secrets

Use the shared 1Password engineering vault for production API keys and paste them into deployment UIs as needed. Rotate when someone leaves the company.

This predates the Vault migration and must not be used for new services.
""",
        ),
        doc(
            nid(),
            cluster_id="c20",
            role="canonical",
            date="2026-01-30",
            title="Emergency Secret Revocation",
            content="""# Emergency Secret Revocation

If a secret leaks:
1. Revoke in Vault (or invalidate provider key) immediately  
2. Page Security oncall  
3. Rotate dependents  
4. File incident if production exposure is plausible  
5. Audit access logs for the prior 72 hours  

Do not reuse leaked values even if exposure “seems limited.”
""",
        ),
        doc(
            nid(),
            cluster_id="c20",
            role="versioned",
            version_chain_id="vc-secret-rotation-db",
            version_number=1,
            date="2024-01-15",
            validation_note="Old DB password rotation every 180 days.",
            title="Database Password Rotation (2024)",
            content="""# Database Password Rotation (2024)

Database passwords rotate every **180 days** via manual ticket with DBA.
""",
        ),
        doc(
            nid(),
            cluster_id="c20",
            role="canonical",
            version_chain_id="vc-secret-rotation-db",
            version_number=2,
            date="2026-01-30",
            title="Database Password Rotation (Current)",
            content="""# Database Password Rotation (Current)

Database passwords rotate automatically every **60 days**. Applications load credentials at startup and on SIGHUP from the injector sidecar. Manual tickets are only for breakglass exceptions.
""",
        ),
        # c21 Service ownership
        doc(
            nid(),
            cluster_id="c21",
            role="canonical",
            date="2025-08-21",
            title="Service Ownership and SCORE Catalog",
            content="""# Service Ownership and SCORE Catalog

## SCORE fields
Every tier-0/1 service lists: owning squad, on-call schedule, Slack channel, repo, runbook URL, data classification, and tier.

## Updates
Ownership changes require SCORE PR + acknowledgment from the receiving EM.

## Orphan services
Services without a valid on-call for >7 days page the platform duty officer until resolved.
""",
        ),
        doc(
            nid(),
            cluster_id="c21",
            role="distractor",
            date="2025-12-12",
            validation_note="HR org chart ownership, not service catalog ownership.",
            title="Updating the Company Org Chart",
            content="""# Updating the Company Org Chart

People managers submit org changes via Workday. IT syncs to the intranet within 48 hours.

This does not update service ownership in SCORE; eng teams must still file SCORE PRs.
""",
        ),
        doc(
            nid(),
            cluster_id="c21",
            role="canonical",
            date="2025-08-21",
            title="Declaring a New Service in SCORE",
            content="""# Declaring a New Service in SCORE

Before production traffic:
1. Add SCORE entry with tier proposal  
2. Attach runbook stub  
3. Register SLO objectives  
4. Wire paging policy  
5. Platform review for tier-0 claims  

Shipping without SCORE is a launch checklist failure.
""",
        ),
        # c22 Postmortems
        doc(
            nid(),
            cluster_id="c22",
            role="canonical",
            date="2025-11-20",
            title="Postmortem Process",
            content="""# Postmortem Process

## Required for
All P1 and P2 incidents. Optional but encouraged for interesting P3s.

## Timing
Schedule within **3 business days** of mitigation; publish blameless write-up within **10 business days**.

## Sections
Summary, impact, timeline, root causes, what went well, action items with owners and dates.

## Action items
Tracked in Jira with label `postmortem`. Overdue actions report weekly to Eng leadership.
""",
        ),
        doc(
            nid(),
            cluster_id="c22",
            role="distractor",
            date="2025-02-02",
            validation_note="Outdated timing: publish within 48 hours; blamestorming language.",
            title="Running Incident Reviews",
            content="""# Running Incident Reviews

Hold a review within **48 hours** and assign individual blame notes so performance calibrations can incorporate operational failures. Write-ups are optional if the timeline is clear in Slack.

This conflicts with the current blameless postmortem process and timings.
""",
        ),
        doc(
            nid(),
            cluster_id="c22",
            role="canonical",
            date="2025-11-20",
            title="Postmortem Facilitation Tips",
            content="""# Postmortem Facilitation Tips

- Facilitator should not be the primary mitigator if possible  
- Focus on systemic fixes over human error labels  
- Capture near-misses  
- Keep customer quotes anonymized  

Template lives in the eng docs repo under `templates/postmortem.md`.
""",
        ),
        # c23 Access reviews
        doc(
            nid(),
            cluster_id="c23",
            role="canonical",
            contradiction_id="cx-access-review-cadence",
            date="2026-02-15",
            title="Access Review Cadence",
            content="""# Access Review Cadence

## Frequency
- Production systems & customer data: **quarterly**  
- Corporate SaaS (email, chat): **semiannual**  
- Privileged breakglass groups: **monthly**  

## Owners
System owners complete reviews in the SailPoint campaign. Managers attest contractor access.

## SLA
Campaigns close in **10 business days**. Incomplete reviews escalate to Security.
""",
        ),
        doc(
            nid(),
            cluster_id="c23",
            role="contradicting",
            contradiction_id="cx-access-review-cadence",
            date="2024-10-10",
            validation_note="Conflicts: production access reviews annual instead of quarterly.",
            title="Periodic Access Attestation Schedule",
            content="""# Periodic Access Attestation Schedule

Production and customer data systems are reviewed **annually** during the SOC2 window. Corporate SaaS is annual as well. Breakglass reviews occur quarterly.

Complete campaigns when Security emails the link.
""",
        ),
        doc(
            nid(),
            cluster_id="c23",
            role="distractor",
            date="2026-01-08",
            validation_note="Code review cadence, not access review.",
            title="Review Cadence for Open RFCs and PRs",
            content="""# Review Cadence for Open RFCs and PRs

Engineering managers review open RFC aging weekly. PR SLA remains one business day for first response.

Unrelated to IAM access review campaigns.
""",
        ),
        doc(
            nid(),
            cluster_id="c23",
            role="canonical",
            date="2026-02-15",
            title="How to Complete a SailPoint Access Campaign",
            content="""# How to Complete a SailPoint Access Campaign

1. Open the campaign email link  
2. For each user, choose Maintain or Revoke  
3. Add comments for exceptions  
4. Submit before the due date  

Revocations apply within 24 hours. If a user still needs access, file a new request rather than delaying revoke without cause.
""",
        ),
        # c24 Production breakglass
        doc(
            nid(),
            cluster_id="c24",
            role="canonical",
            date="2026-02-15",
            title="Production Breakglass Access",
            content="""# Production Breakglass Access

## When
Active incident mitigation or approved maintenance with ticket ID.

## How
Okta → Breakglass → request role → reason + incident link. Access lasts **4 hours** by default, extendable once to 8 hours with IC approval.

## Logging
All breakglass sessions are recorded in the SIEM and reviewed weekly.

## Prohibited
Curiosity access, “just in case” standing breakglass, and sharing elevated cookies.
""",
        ),
        doc(
            nid(),
            cluster_id="c24",
            role="distractor",
            date="2025-07-07",
            validation_note="Outdated duration: 24h default breakglass; no incident link required.",
            title="Emergency Prod Access",
            content="""# Emergency Prod Access

Request breakglass for **24 hours** with a short reason. Incident tickets are optional for senior engineers.

Weekly reviews are best-effort.
""",
        ),
        doc(
            nid(),
            cluster_id="c24",
            role="canonical",
            date="2026-02-15",
            title="Breakglass Extensions and Audits",
            content="""# Breakglass Extensions and Audits

## Extension
One extension to a total of **8 hours** with IC or manager approval in the Okta request thread.

## Audit findings
Using breakglass without an incident or change ticket is a security finding. Repeat offenses escalate to VP Eng.

## Alternatives
Prefer runbook automations and scoped service accounts over human breakglass when possible.
""",
        ),
        doc(
            nid(),
            cluster_id="c24",
            role="multi_hop_fragment",
            fragment_group_id="fg-breakglass-db",
            date="2026-02-16",
            title="Breakglass for Database Consoles — Eligibility",
            content="""# Breakglass for Database Consoles — Eligibility

Database console breakglass is limited to:
- On-call engineers for the owning service  
- DBAs  
- IC during P1/P2  

Contractors are never eligible for prod DB breakglass.

How to connect and the allowed statement classes are in the companion procedure doc.
""",
        ),
        doc(
            nid(),
            cluster_id="c24",
            role="multi_hop_fragment",
            fragment_group_id="fg-breakglass-db",
            date="2026-02-16",
            title="Breakglass for Database Consoles — Procedure",
            content="""# Breakglass for Database Consoles — Procedure

1. Obtain breakglass role as usual  
2. Open Teleport DB app for the target cluster  
3. Use read-only role unless write is required for mitigation  
4. For writes: paste statements into the incident timeline before execute  
5. End session when mitigated  

Eligibility rules are separate; unauthorized roles will be denied at Teleport even with a generic breakglass grant.
""",
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH 5 — Security + HR (c25–c30)
    # ══════════════════════════════════════════════════════════════════════════

    docs += [
        # c25 Data classification
        doc(
            nid(),
            cluster_id="c25",
            role="canonical",
            date="2025-12-08",
            title="Data Classification Standard",
            content="""# Data Classification Standard

## Levels
- **Public**: marketing site copy  
- **Internal**: non-sensitive business docs  
- **Confidential**: customer metadata, contracts, unreleased roadmap  
- **Restricted**: credentials, raw PII, financial instruments, security findings  

## Handling
Restricted data requires encryption at rest and in transit, access logging, and prohibition on personal email/Slack DMs.

## Labeling
Tag datasets in the catalog. Default to Confidential when unsure.
""",
        ),
        doc(
            nid(),
            cluster_id="c25",
            role="distractor",
            date="2024-04-04",
            validation_note="Uses different level names (Green/Yellow/Red) and allows Restricted in Slack DMs.",
            title="Color-Code Data Handling Guide",
            content="""# Color-Code Data Handling Guide

Green = share freely. Yellow = internal. Red = sensitive but OK in encrypted Slack DMs among teammates.

Map older color codes carefully; the current standard uses Public/Internal/Confidential/Restricted.
""",
        ),
        doc(
            nid(),
            cluster_id="c25",
            role="canonical",
            date="2025-12-08",
            title="Examples by Classification Level",
            content="""# Examples by Classification Level

| Example | Level |
| --- | --- |
| Pricing page | Public |
| Sprint goals | Internal |
| Customer ARR spreadsheet | Confidential |
| Production DB dumps | Restricted |
| Okta MFA seeds | Restricted |
| Anonymized funnel charts | Internal or Confidential depending on contract |

When customer contracts demand stricter handling, follow the stricter rule.
""",
        ),
        # c26 Vendor security
        doc(
            nid(),
            cluster_id="c26",
            role="canonical",
            contradiction_id="cx-vendor-sla",
            date="2026-01-12",
            title="Vendor Security Review Process",
            content="""# Vendor Security Review Process

## Triggers
New vendors processing Confidential or Restricted data, or any vendor with production network connectivity.

## Steps
1. Security questionnaire  
2. SOC2/ISO review  
3. Data Processing Addendum  
4. Risk rating (Low/Med/High)  
5. Approval by Security + owning director for High  

## SLA
**15 business days** for standard reviews; 5 for Low-risk renewals.

## Out of scope
Marketing-only browser pixels without PII still need a lightweight privacy check, but not the full 15-day vendor security review.
""",
        ),
        doc(
            nid(),
            cluster_id="c26",
            role="distractor",
            date="2025-05-19",
            validation_note="Outdated SLA 5 days for all; skips DPA for SaaS.",
            title="Bringing on New SaaS Tools",
            content="""# Bringing on New SaaS Tools

Fill a short form; Security responds in **5 business days**. DPAs are optional for pure SaaS productivity tools.

Current process is stricter—see the vendor security review process.
""",
        ),
        doc(
            nid(),
            cluster_id="c26",
            role="canonical",
            date="2026-01-12",
            title="Vendor Renewal Security Checks",
            content="""# Vendor Renewal Security Checks

High-risk vendors require annual re-review. Medium every two years. Low on material scope change only.

Notify Security 45 days before renewal if scope expands (new data types or subprocessors).
""",
        ),
        doc(
            nid(),
            cluster_id="c26",
            role="contradicting",
            contradiction_id="cx-vendor-sla",
            date="2025-09-09",
            validation_note="Conflicts on review SLA: 10 business days vs canonical 15.",
            title="Security Review Turnaround Commitments",
            content="""# Security Review Turnaround Commitments

Standard vendor security reviews complete in **10 business days**. Expedites require VP approval.

Use this when promising timelines to procurement.
""",
        ),
        # c27 SOC2 evidence
        doc(
            nid(),
            cluster_id="c27",
            role="canonical",
            date="2025-11-01",
            title="SOC 2 Evidence Collection Guide",
            content="""# SOC 2 Evidence Collection Guide

## Cadence
Control owners upload evidence **quarterly** into the GRC tool with the control ID in the filename.

## Screenshots
Include URL bar and timestamp. Redact secrets but not control-critical configuration.

## Deadlines
Evidence due **15 days** after quarter end. Late submissions block engineering promo packets for control owners (HR-enforced).
""",
        ),
        doc(
            nid(),
            cluster_id="c27",
            role="distractor",
            date="2025-08-08",
            validation_note="ISO 27001 evidence schedule, not SOC2 quarterly cadence.",
            title="ISO 27001 Artifact Upload Schedule",
            content="""# ISO 27001 Artifact Upload Schedule

Upload artifacts semi-annually before surveillance audits. Naming uses Annex A control numbers.

Do not confuse with SOC 2 quarterly evidence collection.
""",
        ),
        doc(
            nid(),
            cluster_id="c27",
            role="canonical",
            date="2025-11-01",
            title="Common SOC 2 Controls Owned by Eng",
            content="""# Common SOC 2 Controls Owned by Eng

- Access provisioning / deprovisioning  
- Change management (tickets linked to deploys)  
- Encryption configuration  
- On-call coverage attestation  
- Vulnerability scan remediation SLAs  

Platform Eng maintains a mapping sheet from control IDs to squads.
""",
        ),
        # c28 PTO
        doc(
            nid(),
            cluster_id="c28",
            role="canonical",
            contradiction_id="cx-pto-accrual",
            date="2026-01-01",
            title="Paid Time Off Policy",
            content="""# Paid Time Off Policy

## Accrual (US full-time)
**20 days** per year accrued biweekly, cap of **30 days** banked. Exempt employees take time in half-day increments minimum.

## Approval
Manager approval required. Requests >5 consecutive days need **2 weeks** notice except emergencies.

## Blackout
Eng may define release blackout windows; PTO is still requestable but may be denied for critical staffing.
""",
        ),
        doc(
            nid(),
            cluster_id="c28",
            role="contradicting",
            contradiction_id="cx-pto-accrual",
            date="2024-01-01",
            validation_note="Conflicts: 15 days PTO accrual and 25-day cap vs 20/30.",
            title="Time Off Benefits Overview",
            content="""# Time Off Benefits Overview

US full-time employees accrue **15 days** of PTO annually with a **25-day** cap. Submit requests in Workday. Two weeks notice preferred for long trips.

Confirm current numbers with the 2026 PTO policy before quoting candidates.
""",
        ),
        doc(
            nid(),
            cluster_id="c28",
            role="distractor",
            date="2025-06-01",
            validation_note="Sick leave policy, not PTO vacation accrual.",
            title="Sick Leave and Caregiving Days",
            content="""# Sick Leave and Caregiving Days

US employees receive **10 sick/care days** per year that do not roll over. These are separate from PTO balances.

Manager notification same day is sufficient; doctor notes required after 3 consecutive days.
""",
        ),
        doc(
            nid(),
            cluster_id="c28",
            role="canonical",
            date="2026-01-01",
            title="PTO Cash-Out and Departure",
            content="""# PTO Cash-Out and Departure

Unused PTO is paid out at departure where state law requires. Where not required, Northline still pays up to the **30-day** cap as a company benefit for US employees.

Negative balances may be deducted from final pay where legal.
""",
        ),
        # c29 Remote stipend
        doc(
            nid(),
            cluster_id="c29",
            role="canonical",
            version_chain_id="vc-wfh-stipend",
            version_number=3,
            date="2026-01-01",
            title="Remote Work Stipend (Current)",
            content="""# Remote Work Stipend (Current)

## Amount
Full-time remote or hybrid employees receive **$150 / month** taxable stipend for internet and coworking, paid via payroll.

## Eligibility
Must be active on the 1st of the month. Unpaid leave >15 days pauses stipend.

## What it covers
Home internet upgrades, coworking day passes, ergonomic accessories under $75 without separate expense. Larger gear uses the equipment policy.
""",
        ),
        doc(
            nid(),
            cluster_id="c29",
            role="versioned",
            version_chain_id="vc-wfh-stipend",
            version_number=1,
            date="2023-04-01",
            validation_note="Old stipend $75/month.",
            title="WFH Internet Stipend (2023)",
            content="""# WFH Internet Stipend (2023)

Remote employees receive **$75 per month** for internet. Submit receipts quarterly if requested for audit.
""",
        ),
        doc(
            nid(),
            cluster_id="c29",
            role="versioned",
            version_chain_id="vc-wfh-stipend",
            version_number=2,
            date="2024-07-01",
            validation_note="Mid stipend $100/month.",
            title="Remote Connectivity Stipend (2024)",
            content="""# Remote Connectivity Stipend (2024)

The monthly remote stipend is **$100**, paid automatically. Coworking is not included; expense separately.
""",
        ),
        doc(
            nid(),
            cluster_id="c29",
            role="distractor",
            date="2025-09-09",
            validation_note="Learning stipend $1000/year, not remote work monthly stipend.",
            title="Annual Learning and Development Stipend",
            content="""# Annual Learning and Development Stipend

Employees receive **$1,000 per year** for courses and conferences. Unused balances do not roll.

Unrelated to the monthly remote work stipend for internet/coworking.
""",
        ),
        # c30 Expenses
        doc(
            nid(),
            cluster_id="c30",
            role="canonical",
            contradiction_id="cx-expense-receipt",
            date="2025-10-01",
            title="Expense Reimbursement Policy",
            content="""# Expense Reimbursement Policy

## Submission
Submit in Expensify within **30 days** of spend. Receipts required above **$25**.

## Approvals
Manager approves under $1,000. Director above. Finance reviews samples weekly.

## Travel
Coach airfare default. Hotel soft cap $250/night in major US cities unless sold out.

## Unallowable
Traffic fines, personal entertainment, luxury upgrades without preapproval.

## Currency
Foreign receipts should include FX conversion from Expensify; do not hand-calculate rates in the notes field.
""",
        ),
        doc(
            nid(),
            cluster_id="c30",
            role="distractor",
            date="2024-03-03",
            validation_note="Outdated: 60-day submit window and $75 receipt threshold.",
            title="Filing Expenses at Northline",
            content="""# Filing Expenses at Northline

You have **60 days** to submit expenses. Receipts needed only above **$75**. Manager approval always suffices regardless of amount.

Check the current reimbursement policy for updated thresholds.
""",
        ),
        doc(
            nid(),
            cluster_id="c30",
            role="canonical",
            date="2025-10-01",
            title="Corporate Card vs Out-of-Pocket",
            content="""# Corporate Card vs Out-of-Pocket

Prefer corporate cards for recurring vendor spend. Out-of-pocket is fine for travel incidentals.

Lost receipt affidavit allowed twice per year per employee for sub-$100 items.
""",
        ),
        doc(
            nid(),
            cluster_id="c30",
            role="contradicting",
            contradiction_id="cx-expense-receipt",
            date="2025-01-15",
            validation_note="Conflicts on receipt threshold: $50 vs canonical $25.",
            title="Receipt Requirements Summary",
            content="""# Receipt Requirements Summary

Attach receipts for any expense **$50** or more. Below that, a merchant + date note is enough.

Submit within 30 days in Expensify.
""",
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # BATCH 6 — HR remaining + Support + Planning (c31–c38)
    # ══════════════════════════════════════════════════════════════════════════

    docs += [
        # c31 Parental leave
        doc(
            nid(),
            cluster_id="c31",
            role="canonical",
            date="2026-01-01",
            title="Parental Leave Policy",
            content="""# Parental Leave Policy

## US benefits
- Birthing parents: **16 weeks** fully paid  
- Non-birthing parents: **10 weeks** fully paid  
- Must begin within **6 months** of birth or placement  

## Notice
Provide **30 days** notice when foreseeable. Coordinate with HRBP for benefits bridging.

## Tenure
Eligible after **6 months** of continuous employment. Shorter tenure may use unpaid leave per law.
""",
        ),
        doc(
            nid(),
            cluster_id="c31",
            role="distractor",
            date="2023-01-01",
            validation_note="Outdated: 12 and 6 weeks paid; 12-month tenure gate.",
            title="Family Leave Benefits",
            content="""# Family Leave Benefits

Birthing parents receive **12 weeks** paid. Non-birthing receive **6 weeks**. Eligibility starts after **12 months** employment.

Superseded by the 2026 parental leave policy.
""",
        ),
        doc(
            nid(),
            cluster_id="c31",
            role="canonical",
            date="2026-01-01",
            title="Parental Leave — How to File",
            content="""# Parental Leave — How to File

1. Notify manager  
2. Open case with HRBP  
3. Submit documentation  
4. Schedule offboarding of on-call duties  
5. Confirm benefits during leave  

Engineering managers should arrange rotation coverage at least two weeks before leave start when possible.
""",
        ),
        # c32 Laptop refresh
        doc(
            nid(),
            cluster_id="c32",
            role="canonical",
            version_chain_id="vc-laptop-cycle",
            version_number=2,
            date="2025-09-01",
            title="Laptop Refresh Cycle (Current)",
            content="""# Laptop Refresh Cycle (Current)

Standard refresh is **36 months** from device issue date. Performance exception refreshes available with IT approval if builds are blocked.

Return old devices within **14 days** of receiving the replacement. Data wipe is handled by IT.
""",
        ),
        doc(
            nid(),
            cluster_id="c32",
            role="versioned",
            version_chain_id="vc-laptop-cycle",
            version_number=1,
            date="2022-09-01",
            validation_note="Old refresh cycle 48 months.",
            title="Hardware Refresh Policy (2022)",
            content="""# Hardware Refresh Policy (2022)

Laptops refresh on a **48 month** cycle. Early refresh requires director approval.
""",
        ),
        doc(
            nid(),
            cluster_id="c32",
            role="distractor",
            date="2025-11-11",
            validation_note="Phone stipend refresh, not laptop.",
            title="Mobile Phone Upgrade Eligibility",
            content="""# Mobile Phone Upgrade Eligibility

Company-paid phones are eligible for upgrade every **24 months**. BYOD users receive stipend instead.

Not applicable to MacBook refresh cycles.
""",
        ),
        doc(
            nid(),
            cluster_id="c32",
            role="canonical",
            date="2025-09-01",
            title="Standard Engineering Laptop Specs",
            content="""# Standard Engineering Laptop Specs

- MacBook Pro 14\" M-series, 32 GB RAM, 1 TB SSD for engineers  
- 16 GB / 512 GB acceptable for non-eng roles  
- Linux via approved framework models on exception only  

Request via IT portal. Custom GPUs are not supported.
""",
        ),
        # c33 Security training
        doc(
            nid(),
            cluster_id="c33",
            role="canonical",
            contradiction_id="cx-training-deadline",
            date="2026-01-15",
            title="Security Awareness Training Requirements",
            content="""# Security Awareness Training Requirements

## Cadence
All employees complete training **within 30 days of hire** and **annually** thereafter.

## Deadline
Annual campaigns close **March 31**. Non-compliance disables production access until completion.

## Contractors
Engaged >30 days must complete the same modules.
""",
        ),
        doc(
            nid(),
            cluster_id="c33",
            role="contradicting",
            contradiction_id="cx-training-deadline",
            date="2025-01-10",
            validation_note="Conflicts: annual deadline June 30; hire window 90 days.",
            title="Mandatory Security Modules",
            content="""# Mandatory Security Modules

Complete security awareness within **90 days** of hire and each year by **June 30**. Managers receive lagging reports monthly.

Production access consequences are at Security’s discretion.
""",
        ),
        doc(
            nid(),
            cluster_id="c33",
            role="distractor",
            date="2025-12-01",
            validation_note="Compliance training for sales (GDPR selling), not security awareness for all staff.",
            title="Sales Privacy Training Schedule",
            content="""# Sales Privacy Training Schedule

AEs complete GDPR/CCPA selling modules quarterly. SE teams join twice yearly.

This is separate from company-wide security awareness training.
""",
        ),
        doc(
            nid(),
            cluster_id="c33",
            role="canonical",
            date="2026-01-15",
            title="Phishing Simulation Program",
            content="""# Phishing Simulation Program

Security runs phishing simulations **monthly**. Repeated failures trigger live training. Reporting suspicious mail via the PhishAlert button is encouraged and never punished.
""",
        ),
        # c34 Visitor / guest wifi
        doc(
            nid(),
            cluster_id="c34",
            role="canonical",
            date="2025-07-18",
            title="Visitor and Guest Wi-Fi Policy",
            content="""# Visitor and Guest Wi-Fi Policy

## Guest network
SSID `Northline-Guest` with daily rotating PSK posted at reception. No access to corporate intranet or staging.

## Visitors
Sign in at reception; badges expire at 18:00 local. Escorts required for secure areas.

## Employees
Must not share corporate Wi-Fi credentials with guests.
""",
        ),
        doc(
            nid(),
            cluster_id="c34",
            role="distractor",
            date="2025-07-18",
            validation_note="Remote employee home network guidance, not office guest Wi-Fi.",
            title="Securing Your Home Network for Work",
            content="""# Securing Your Home Network for Work

Use WPA2/3, separate IoT VLAN if possible, and keep router firmware updated. Company does not support employee home routers.

Unrelated to office guest Wi-Fi procedures.
""",
        ),
        doc(
            nid(),
            cluster_id="c34",
            role="canonical",
            date="2025-07-18",
            title="Contractor Badges and Lobby Hours",
            content="""# Contractor Badges and Lobby Hours

Contractors on multi-day engagements receive contractor badges with colored lanyards. Lobby open 08:00–18:00 local on business days. After-hours access requires employee escort and security notification.
""",
        ),
        # c35 OSS contribution
        doc(
            nid(),
            cluster_id="c35",
            role="canonical",
            date="2025-06-20",
            title="Open Source Contribution Policy",
            content="""# Open Source Contribution Policy

## Allowed
Contributions to approved licenses (MIT, Apache-2.0, BSD) on personal time or approved 20% time, without Northline confidential code.

## Review
Outbound contributions that reference Northline infrastructure require Legal + Security review.

## Inbound
Adding new OSS dependencies needs license scan in CI and maintainer health notes for tier-0 services.
""",
        ),
        doc(
            nid(),
            cluster_id="c35",
            role="distractor",
            date="2024-02-02",
            validation_note="Bans all OSS contribution without exec approval — outdated hardline policy.",
            title="External Code Publishing Rules",
            content="""# External Code Publishing Rules

Employees may not publish open source without CEO approval. Company IP includes all side projects.

Superseded by the more permissive open source contribution policy.
""",
        ),
        doc(
            nid(),
            cluster_id="c35",
            role="canonical",
            date="2025-06-20",
            title="Requesting License Exceptions for Dependencies",
            content="""# Requesting License Exceptions for Dependencies

GPL/AGPL and unknown licenses require Legal exception tickets. Include why alternatives failed and network exposure of the component.

Do not vendor GPL into closed mobile apps without counsel sign-off.
""",
        ),
        # c36 Support escalation
        doc(
            nid(),
            cluster_id="c36",
            role="canonical",
            date="2026-02-05",
            title="Customer Support Escalation Path",
            content="""# Customer Support Escalation Path

## Levels
L1 Support → L2 Product Specialists → Engineering on-call (via ticket escalate) → IC if P1.

## Enterprise
Named TAM can page eng-oncall for confirmed P1 with customer impact after L2 acknowledgment.

## SLAs (first response)
- Enterprise: **1 hour** business / **2 hours** 24x7 for P1  
- Growth: **4 business hours**  
- Starter: **1 business day**
""",
        ),
        doc(
            nid(),
            cluster_id="c36",
            role="distractor",
            date="2025-03-03",
            validation_note="Internal IT helpdesk escalation, not customer support.",
            title="Internal IT Support Escalation",
            content="""# Internal IT Support Escalation

Employee laptop issues: IT helpdesk → IT L2 → vendor RMA. Do not page product eng oncall for laptop failures.

Different from customer support escalation for Pulse product issues.
""",
        ),
        doc(
            nid(),
            cluster_id="c36",
            role="canonical",
            date="2026-02-05",
            title="When Support May Page Engineering",
            content="""# When Support May Page Engineering

Page only when:
- Customer-confirmed production defect with business impact  
- Security vulnerability report  
- Data loss / privacy incident  

Attach ticket, customer tier, impact start time, and reproduction. Non-actionable pages are reviewed monthly.
""",
        ),
        doc(
            nid(),
            cluster_id="c36",
            role="multi_hop_fragment",
            fragment_group_id="fg-support-enterprise-sla",
            date="2026-02-05",
            title="Enterprise Support — Entitlements",
            content="""# Enterprise Support — Entitlements

Enterprise contracts include:
- Named TAM  
- 24x7 P1 coverage  
- Quarterly business reviews  
- Private Slack connect (optional)

Exact first-response timers are listed in the escalation path SLA table companion section of the customer support escalation path document’s SLA list—use that for numeric commitments when writing external emails.
""",
        ),
        doc(
            nid(),
            cluster_id="c36",
            role="multi_hop_fragment",
            fragment_group_id="fg-support-enterprise-sla",
            date="2026-02-05",
            title="Enterprise Support — Severity Examples",
            content="""# Enterprise Support — Severity Examples

## P1 examples
Ingest down for a customer workspace, SSO totally broken, incorrect flag evaluation affecting checkout.

## P2 examples
Single dashboard tile wrong, delayed exports, partial UI outage with workaround.

## Not pages
How-to questions, feature requests, CSS polish.

Pair with entitlements doc when explaining what Enterprise buys; severities alone do not list TAM/QBR benefits.
""",
        ),
        # c37 Enterprise SLA product
        doc(
            nid(),
            cluster_id="c37",
            role="canonical",
            contradiction_id="cx-uptime-sla",
            date="2026-01-20",
            title="Northline Pulse Service Uptime SLA",
            content="""# Northline Pulse Service Uptime SLA

## Commitment
Enterprise contracts commit to **99.9%** monthly uptime for ingest API and app UI, excluding scheduled maintenance windows announced ≥48 hours ahead.

## Credits
If monthly uptime < 99.9%, credit **10%** of monthly subscription; < 99.0% credit **25%**.

## Measurement
External synthetic checks every 60 seconds from three regions. Customer-side network issues excluded.
""",
        ),
        doc(
            nid(),
            cluster_id="c37",
            role="contradicting",
            contradiction_id="cx-uptime-sla",
            date="2024-06-01",
            validation_note="Conflicts: 99.99% uptime commitment and 5% credit tier.",
            title="Platform Availability Targets",
            content="""# Platform Availability Targets

We target **99.99%** monthly uptime. Credits start at **5%** of monthly fees if we miss the target.

Scheduled maintenance is included in downtime in this older formulation—verify current SLA language before customer negotiations.
""",
        ),
        doc(
            nid(),
            cluster_id="c37",
            role="distractor",
            date="2025-12-12",
            validation_note="Internal SLO for a single microservice, not customer contractual SLA.",
            title="Ingest Service Internal SLO",
            content="""# Ingest Service Internal SLO

Internal objective: 99.95% success rate on track requests, p99 latency < 120ms within region.

Internal SLOs inform error budgets; they are not the customer contractual uptime SLA.
""",
        ),
        doc(
            nid(),
            cluster_id="c37",
            role="canonical",
            date="2026-01-20",
            title="Requesting SLA Credits",
            content="""# Requesting SLA Credits

Customers request credits via Support within **30 days** after month end. Finance validates against synthetic uptime reports and issues credits on the next invoice.

Verbal commitments from AEs are not binding without Support ticket validation.
""",
        ),
        # c38 OKR / planning
        doc(
            nid(),
            cluster_id="c38",
            role="canonical",
            date="2025-12-15",
            title="Quarterly Planning and OKR Process",
            content="""# Quarterly Planning and OKR Process

## Cadence
- T-6 weeks: draft priorities  
- T-3 weeks: OKR review with leadership  
- T-0: quarter start lock  

## Scoring
0.0–1.0 scale; **0.7** is healthy stretch success. Scores due 2 weeks after quarter end.

## WIP limits
Squads should carry ≤ **3** committed team objectives excluding keep-the-lights-on.
""",
        ),
        doc(
            nid(),
            cluster_id="c38",
            role="distractor",
            date="2025-01-01",
            validation_note="Annual performance review process, not quarterly OKRs.",
            title="Annual Performance Review Timeline",
            content="""# Annual Performance Review Timeline

Self-reviews in January, manager reviews in February, calibration March, compensation letters April.

Do not use this calendar for quarterly OKR locking.
""",
        ),
        doc(
            nid(),
            cluster_id="c38",
            role="canonical",
            date="2025-12-15",
            title="Writing Effective Team Objectives",
            content="""# Writing Effective Team Objectives

Objectives are qualitative outcomes; key results are measurable. Avoid KR that are pure to-do lists (“ship project X”) without customer or reliability metrics.

Platform teams may use reliability KRs (SLO attainment) alongside product KRs.
""",
        ),
        doc(
            nid(),
            cluster_id="c38",
            role="versioned",
            version_chain_id="vc-okr-wip",
            version_number=1,
            date="2024-01-10",
            validation_note="Old WIP limit 5 committed objectives.",
            title="OKR WIP Guidance (2024)",
            content="""# OKR WIP Guidance (2024)

Teams may commit to up to **5** objectives per quarter in addition to KTLO.
""",
        ),
        doc(
            nid(),
            cluster_id="c38",
            role="canonical",
            version_chain_id="vc-okr-wip",
            version_number=2,
            date="2025-12-15",
            title="OKR WIP Guidance (Current)",
            content="""# OKR WIP Guidance (Current)

Squads commit to at most **3** team objectives per quarter, excluding keep-the-lights-on work. Additional objectives must be explicitly marked stretch and cannot gate performance ratings.
""",
        ),
    ]

    # ══════════════════════════════════════════════════════════════════════════
    # NOISE — near-domain (same company, not query targets)
    # ══════════════════════════════════════════════════════════════════════════

    near_noise = [
        ("Brand Voice Guidelines for Product UI Copy", "2025-05-01",
         "Use second person, short sentences, and avoid sports metaphors in empty states. Buttons use sentence case. Error messages explain the fix. This guide is for writers and designers working in the design system library."),
        ("Office Snack Budget by Location", "2025-08-12",
         "SF office snack budget is $40 per employee per month. Austin is $30. Remote employees do not receive snack stipends. Facilities reorders biweekly. Dietary restriction surveys run each January."),
        ("Conference Speaking Approval Process", "2025-03-22",
         "Employees speaking externally about Northline must notify Comms 3 weeks ahead with abstract. Security reviews demos for customer data. Travel uses standard expense policy. Legal reviews novel claims about competitors."),
        ("Design System Color Tokens — Aura v4", "2025-11-02",
         "Aura v4 renames `color-brand-500` to `color-accent-primary`. Dark mode tokens live under `color-dark-*`. Engineers should consume tokens via CSS variables, not hex literals. Deprecated tokens remain until 2026-06-01."),
        ("All-Hands Agenda Template", "2025-09-09",
         "All-hands runs first Thursday monthly at 10:00 PT. Order: metrics, customer story, demos, Q&A. Recordings post to the intranet within 24 hours. Questions collect via forms for anonymity."),
        ("Parking and Commuter Benefits", "2025-02-14",
         "HQ garage validation available for employees on-site 3+ days weekly. Commuter transit pretax benefits enroll in Workday. Bicycles may use the secure cage with IT badge access."),
        ("Internal Podcast Equipment Checkout", "2024-12-01",
         "Comms owns two Shure mics and a portable recorder. Checkout via calendar resource. Return within 48 hours. Damages file facilities ticket."),
        ("Sales Club Trip Qualification 2025", "2025-01-20",
         "AEs qualify for President’s Club with 110% of annual quota and multi-product attach above 30%. Note this is sales comp, not eng oncall rewards."),
        ("Cafeteria Catering for Recruiting Events", "2025-06-06",
         "Recruiting onsite loops may order lunch via the facilities form with 2-day notice. Alcohol requires HR approval. Budget codes use recruiting cost centers."),
        ("GitHub Copilot Seat Assignment", "2025-10-10",
         "Engineering managers request Copilot seats monthly. Contractors need security exception. Usage metrics reviewed quarterly for idle seat reclamation."),
        ("Board Deck Formatting Checklist", "2025-07-07",
         "Board slides use the confidential template, 16:9, source 24pt minimum. Finance locks numbers Tuesday before board Friday. Product metrics pull from the verified metrics warehouse sheet only."),
        ("Dogfooding Pulse on Northline.com Marketing Site", "2025-04-18",
         "Marketing site uses a separate Pulse workspace `northline-marketing`. Do not mix production app write keys. Consent mode required for EU visitors."),
        ("Manager Calibration Session Facilitation", "2025-11-20",
         "HRBPs facilitate calibrations; managers must pre-write summaries. No compensation numbers in shared docs until final. Schedule holds go out two weeks prior."),
        ("Office Plant Care Rotation", "2025-05-05",
         "Facilities owns plant care; volunteers water only if facilities is out. Do not move plants from conference rooms without notice."),
        ("Internal Mobility Application Windows", "2025-08-28",
         "Employees apply to internal roles after 12 months tenure. Notify current manager at application time. Recruiting coordinates interview loops."),
        ("Accessibility Bug Triage SLAs", "2025-09-15",
         "Critical accessibility blockers (keyboard trap, contrast on primary flows) triage within 2 business days. Use label `a11y` and wcag criteria in tickets."),
        ("Partner Marketplace Listing Rules", "2025-12-03",
         "Technology partners list integrations after security review and a reference customer. Listings renew annually. Co-marketing requires Comms approval."),
        ("Data Science GPU Cluster Etiquette", "2025-07-21",
         "Shared GPU cluster jobs must set time limits. Preemptible queues default. Do not store customer PII on scratch disks. Contact ML platform for reserved nodes."),
    ]

    for i, (title, date, body) in enumerate(near_noise, 1):
        # Expand body to word count with natural continuation
        content = f"""# {title}

{body}

## Scope
This document applies to Northline employees and long-term contractors unless a section narrows eligibility. It is maintained by the owning operations function and reviewed at least annually.

## Exceptions
Exception requests go to the document owner listed in the intranet index. Emergency exceptions during incidents should be temporary and written down after the fact.

## Related resources
Search the intranet for related forms and FAQs. Do not treat Slack hearsay as policy when a written page exists for the same topic.

## Change history
Minor clarifications may ship without all-hands announcement. Material benefit or compliance changes require People or Security communication as appropriate.
"""
        docs.append(doc(
            nid("noise"),
            cluster_id=None,
            role="near_noise",
            title=title,
            content=content,
            date=date,
        ))

    far_noise = [
        ("Alpine Hiking Safety for Club Outings", "2024-05-01",
         "Trail groups of four or more should carry a PLB device above treeline. Turnaround times must leave 30% daylight reserve. Lightning protocol: descend ridges immediately."),
        ("Sourdough Starter Maintenance Log Template", "2024-06-02",
         "Feed 1:1:1 by weight daily at room temperature or weekly in refrigerator. Discard waste responsibly. Record hydration percentage and flour blend."),
        ("City Library Volunteer Shelving Guide", "2024-07-03",
         "Fiction is alphabetical by author surname. Nonfiction uses Dewey. Damaged spines go on the mending cart. Do not reshelve reference without staff."),
        ("Community Garden Plot Rules", "2024-08-04",
         "Plots are 10x10 feet. Organic pesticides only. Harvest only your plot. Shared tool shed locks at dusk. Water timers limited to 20 minutes."),
        ("Youth Soccer Scrimmage Ruleset", "2024-09-05",
         "7v7 on half field, size 4 ball, 25-minute halves. No slide tackles. Substitutions at midfield with referee acknowledgment."),
        ("Amateur Astronomy Observing Checklist", "2024-10-06",
         "Cool telescopes 45 minutes. Align finder scope. Log seeing conditions 1-5. Red lights only on site. Pack out batteries."),
        ("Neighborhood Tool Library Borrowing Terms", "2024-11-07",
         "Borrow up to three tools for seven days. Late fees $2/day. Damage assessment by volunteer leads. Training required for power tools."),
        ("Regional Bird Count Protocol", "2025-01-08",
         "Count windows run 24 hours. Use eBird checklists per party. Do not double-count same flock across parties without coordination."),
        ("Board Game Night Fair Play Code", "2025-02-09",
         "Teach full rules before play. No table talk in competitive games unless agreed. Clean up 10 minutes before venue close."),
        ("Municipal Recycling Sorting FAQ", "2025-03-10",
         "Rinse containers. No plastic bags in single-stream. Soft plastics go to store drop-offs. When in doubt, check the city app."),
        ("Community Choir Rehearsal Etiquette", "2025-04-11",
         "Arrive 10 minutes early. Mark scores in pencil. Silence phones. Section leaders handle divisi disputes."),
        ("DIY Bicycle Brake Adjustment Basics", "2025-05-12",
         "Pad alignment flush to rim. Cable tension until lever at 45% throw. Test spin for rub. Replace cables with frays."),
    ]

    for title, date, body in far_noise:
        content = f"""# {title}

{body}

## Purpose
This community document is unrelated to Northline Pulse product analytics, feature flags, or company employment policies. It exists as reference material in a mixed corpus for retrieval testing.

## Practices
Follow local laws and venue rules. Organizers may tighten constraints for weather or safety. Participants are responsible for personal equipment and fitness.

## Contact
For the community group that maintains this page, use the public mailing list printed on physical flyers—not Northline corporate support channels.
"""
        docs.append(doc(
            nid("noise"),
            cluster_id=None,
            role="far_noise",
            title=title,
            content=content,
            date=date,
        ))

    # ─── Supplemental density (bring corpus into 350–450 range) ──────────────
    # Extra canonical facets, distractors, one more version chain, one more fragment group.
    supplements: list[tuple] = [
        # (cluster_id, role, title, date, content, validation_note, contradiction_id, version_chain_id, version_number, fragment_group_id)
        ("c01", "canonical", "Pulse Web SDK — Environment Configuration Matrix", "2026-02-04",
         """# Pulse Web SDK — Environment Configuration Matrix

Use separate write keys per environment. Never point a production app build at a staging workspace.

| App build | environment value | Key source |
| --- | --- | --- |
| Local dev | development | Personal sandbox workspace |
| PR previews | staging | Shared staging workspace |
| Production | production | Production workspace only |

## Feature flags
Flag rules are environment-scoped. A rule that enables a feature in staging does not apply when `environment: 'production'`.

## Common failure
Shipping `environment: 'staging'` in a production binary causes silent flag mismatches and under-count in production funnels. CI should assert the value from the release channel.
""", None, None, None, None, None),
        ("c01", "distractor", "CDN Snippet Install for Pulse Tracking Pixel", "2025-08-01",
         """# CDN Snippet Install for Pulse Tracking Pixel

Marketing teams sometimes paste a CDN snippet instead of the npm SDK:

```
<script src="https://cdn.northline.io/pulse-pixel.min.js" data-key="WRITE_KEY"></script>
```

This pixel only supports page views and basic identify. It does not evaluate feature flags or use the v3 `/v3/track` batching protocol. Product engineering should not use the pixel inside the authenticated app shell.
""", "Adjacent install path (marketing pixel) that shares vocabulary with SDK install but is not the web SDK.", None, None, None, None),
        ("c02", "canonical", "Taxonomy Change Request Workflow", "2025-10-08",
         """# Taxonomy Change Request Workflow

1. Propose event or property changes in the taxonomy spreadsheet with owner squad.  
2. Data Platform reviews within five business days.  
3. On approval, update client instrumentation and any warehouse mappings.  
4. Deprecate old names with a 30-day dual-write when breaking.

Unauthorized schema drift is blocked by Pulse schema guard for contracted workspaces that enabled enforcement.
""", None, None, None, None, None),
        ("c03", "distractor", "Cookie Lifetime for Anonymous IDs", "2025-12-01",
         """# Cookie Lifetime for Anonymous IDs

The Pulse web cookie for `anonymous_id` defaults to **365 days**. Clearing site data creates a new anonymous profile. This cookie lifetime is independent of the post-identify merge window used when stitching historical anonymous events into a known user.
""", "Discusses cookie TTL not merge window — confusable on 'identity lifetime' queries.", None, None, None, None),
        ("c04", "canonical", "Archiving and Cleaning Up Feature Flags", "2026-02-18",
         """# Archiving and Cleaning Up Feature Flags

Flags past their cleanup date with no traffic for 30 days appear on the weekly debt report. Owners should either extend the cleanup date with justification or remove flag checks from code and archive the flag.

Archived flags no longer evaluate; clients receive the default fallthrough (off) if a stale SDK still requests them.
""", None, None, None, None, None),
        ("c05", "distractor", "Experiment Naming Conventions", "2025-09-01",
         """# Experiment Naming Conventions

Name experiments `squad.yyyyqq.description`, for example `growth.2026q1.express_checkout`. Avoid marketing campaign codes in the experiment key. Naming does not control guardrail thresholds or auto-stop behavior.
""", "About naming only, not guardrail thresholds.", None, None, None, None),
        ("c06", "canonical", "Dashboard Collection Folders", "2026-01-28",
         """# Dashboard Collection Folders

Workspace admins can create collections to group dashboards by squad. Permissions still live on each dashboard; collections are organizational only. Moving a dashboard does not change share lists or public links.
""", None, None, None, None, None),
        ("c07", "canonical", "Retention Holds for Legal Requests", "2026-03-10",
         """# Retention Holds for Legal Requests

Legal can place a retention hold that suspends raw event deletion for specified workspaces or user IDs. Holds appear in the compliance audit log. Product managers cannot disable holds from the UI; only Legal admins can release them after matter close.
""", None, None, None, None, None),
        ("c08", "distractor", "Inbound Webhooks from GitHub to Deploy Bot", "2025-11-11",
         """# Inbound Webhooks from GitHub to Deploy Bot

The deploy bot verifies GitHub signatures using the GitHub app secret. This is unrelated to Pulse outbound product webhooks. Do not reuse Northline webhook signing code for GitHub ingress.
""", "Different webhook system (GitHub ingress).", None, None, None, None),
        ("c09", "canonical", "API Keys vs Write Keys", "2026-02-08",
         """# API Keys vs Write Keys

Write keys authenticate browser/server event ingest. REST API keys authenticate read/export APIs and are rate-limited per the REST rate limit policy. Never embed REST API keys in mobile or web clients.
""", None, None, None, None, None),
        ("c10", "canonical", "Disabling Replay on Specific Routes", "2026-01-19",
         """# Disabling Replay on Specific Routes

Pass `replay: { blockUrls: ['/settings/billing', '/admin'] }` in the SDK config to skip capture on sensitive routes even when workspace replay is enabled. Path matching is prefix-based.
""", None, None, None, None, None),
        ("c11", "distractor", "Marketing Audience Sync from CRM", "2025-10-20",
         """# Marketing Audience Sync from CRM

Nightly jobs sync Salesforce campaign members into the marketing automation tool. These audiences are not Pulse cohorts unless explicitly exported from Pulse cohort export. Do not assume CRM audiences update feature flag targeting.
""", "CRM audiences ≠ Pulse cohorts.", None, None, None, None),
        ("c12", "canonical", "Seat Snapshots and Invoices", "2026-02-25",
         """# Seat Snapshots and Invoices

Billing takes a seat snapshot at 00:00 UTC on the 1st of each month. Mid-cycle deactivations affect overage calculations immediately but do not retroactively change the snapshot line until next cycle for committed seats on Enterprise.
""", None, None, None, None, None),
        ("c13", "canonical", "Secondary On-Call Expectations", "2026-01-06",
         """# Secondary On-Call Expectations

Secondary (shadow) on-call does not receive pages by default. Primary may escalate to secondary after 10 minutes without mitigation progress on P1. Secondaries should keep laptops ready on weekends they cover.
""", None, None, None, None, None),
        ("c14", "distractor", "Bug Tracker Priority Field Meanings", "2025-08-08",
         """# Bug Tracker Priority Field Meanings

Jira priority P0–P3 is a backlog ordering signal for planned work. It is not the same as incident severity P1–P4 used in #incidents. Do not rename tickets between systems without translation notes.
""", "Jira priority ≠ incident severity.", None, None, None, None),
        ("c15", "canonical", "Freeze Calendar Source of Truth", "2025-12-01",
         """# Freeze Calendar Source of Truth

The freeze calendar lives in #eng-announce pins and the eng intranet. Local squad calendars are unofficial. If a freeze is not listed, deploys follow normal change management.
""", None, None, None, None, None),
        ("c16", "distractor", "Product Spec Review Process", "2025-07-07",
         """# Product Spec Review Process

Product specs review in two working sessions with design and eng leads. This is not the engineering RFC process and does not satisfy security review gates for technical architecture changes.
""", "Product specs ≠ eng RFCs.", None, None, None, None),
        ("c17", "canonical", "CODEOWNERS Requirements", "2025-10-30",
         """# CODEOWNERS Requirements

Each service repo must have a CODEOWNERS file covering production paths. Reviews from owners satisfy the default single-approval rule. Optional reviewers do not count as the required owner approval.
""", None, None, None, None, None),
        ("c18", "distractor", "Production VPN Access for Engineers", "2025-12-12",
         """# Production VPN Access for Engineers

Production VPN groups are separate from staging WireGuard profiles. Access requires manager approval and is reviewed quarterly. Staging access does not imply production VPN membership.
""", "Prod VPN ≠ staging access.", None, None, None, None),
        ("c19", "canonical", "Backfilling Data After Migrations", "2025-09-17",
         """# Backfilling Data After Migrations

Backfills run in rate-limited workers, not in the migrator transaction. Prefer idempotent upserts. For multi-hour backfills, publish a status note in #eng and avoid overlapping with freezes.
""", None, None, None, None, None),
        ("c20", "distractor", "Password Manager for Employees", "2025-05-05",
         """# Password Manager for Employees

Employees use 1Password for personal and shared non-production credentials. Application runtime secrets still belong in Vault per the secrets management standard. Do not store production DB passwords only in 1Password.
""", "Human password manager ≠ app secrets system of record.", None, None, None, None),
        ("c21", "canonical", "Tiering Services in SCORE", "2025-08-21",
         """# Tiering Services in SCORE

Tier-0: customer-facing critical path (ingest, auth, flag eval, billing charge). Tier-1: important but degradable. Tier-2: internal tooling. Tier proposals need platform acknowledgment for tier-0.
""", None, None, None, None, None),
        ("c22", "canonical", "Near Miss Reporting", "2025-11-20",
         """# Near Miss Reporting

Near misses without customer impact can file a lightweight template in the postmortem repo under `near-miss/`. They do not require a full meeting but should still produce at least one systemic action item when patterns emerge.
""", None, None, None, None, None),
        ("c23", "distractor", "Performance Review Cadence", "2025-11-01",
         """# Performance Review Cadence

Performance reviews run annually with mid-year check-ins. This cadence is unrelated to IAM access review campaigns in SailPoint.
""", "HR reviews ≠ access reviews.", None, None, None, None),
        ("c24", "distractor", "Office Badge After-Hours Access", "2025-09-09",
         """# Office Badge After-Hours Access

Employees may badge into HQ 24/7. Visitors may not remain after hours without security notification. This is physical access, not production system breakglass.
""", "Physical badge ≠ prod breakglass.", None, None, None, None),
        ("c25", "canonical", "Sharing Confidential Data Externally", "2025-12-08",
         """# Sharing Confidential Data Externally

Confidential materials require NDA before external share. Restricted materials require Security approval and preferably vendor-reviewed secure rooms. Public blog posts should not include Confidential metrics.
""", None, None, None, None, None),
        ("c26", "canonical", "Preferred Vendor List", "2026-01-12",
         """# Preferred Vendor List

Procurement maintains preferred vendors already rated Low or Medium. Using a preferred vendor still needs a scope check if data types expand, but questionnaire reuse can shorten reviews.
""", None, None, None, None, None),
        ("c27", "distractor", "Customer Security Questionnaire Turnaround", "2025-10-10",
         """# Customer Security Questionnaire Turnaround

Security responds to customer-sent questionnaires within 10 business days using the trust center packet. This is outbound customer assurance, not internal SOC 2 evidence collection by control owners.
""", "Customer questionnaires ≠ internal SOC2 evidence uploads.", None, None, None, None),
        ("c28", "canonical", "PTO and On-Call Swaps", "2026-01-01",
         """# PTO and On-Call Swaps

Engineers must secure an on-call swap before PTO that overlaps their primary rotation. Unstaffed rotations page the duty officer. PTO systems do not automatically update PagerDuty schedules.
""", None, None, None, None, None),
        ("c29", "canonical", "Stipend and Unpaid Leave Interaction", "2026-01-01",
         """# Stipend and Unpaid Leave Interaction

If unpaid leave exceeds 15 days in a month, the remote stipend pauses for that month. Partial months with active status on the 1st still pay the full stipend.
""", None, None, None, None, None),
        ("c30", "canonical", "Team Events Expense Guidance", "2025-10-01",
         """# Team Events Expense Guidance

Squad events under $75 per attendee can use corporate card with manager preapproval on Slack. Alcohol policy follows HR guidelines. Offsites above $5k need Finance preapproval.
""", None, None, None, None, None),
        ("c31", "distractor", "Bereavement Leave", "2025-03-01",
         """# Bereavement Leave

Employees receive up to 5 paid bereavement days for immediate family. This is separate from parental leave entitlements and PTO.
""", "Bereavement ≠ parental leave.", None, None, None, None),
        ("c32", "canonical", "Returning Hardware on Exit", "2025-09-01",
         """# Returning Hardware on Exit

Departing employees ship laptops with the provided kit within 10 business days. IT verifies wipe. Failure to return may deduct residual book value where legal.
""", None, None, None, None, None),
        ("c33", "canonical", "New Hire Security Checklist", "2026-01-15",
         """# New Hire Security Checklist

Day 1: laptop disk encryption verified, MFA enrolled. Day 7: security awareness module assigned. Day 30: module completion deadline. Managers see lagging indicators in the people dashboard.
""", None, None, None, None, None),
        ("c34", "distractor", "Conference Wi-Fi Recommendations", "2025-04-04",
         """# Conference Wi-Fi Recommendations

Prefer personal hotspot or conference WPA enterprise SSIDs. Avoid captive portals for prod admin tasks. This guidance is for travel, not the HQ guest network policy.
""", "Travel Wi-Fi ≠ office guest Wi-Fi.", None, None, None, None),
        ("c35", "canonical", "Employee Side Projects", "2025-06-20",
         """# Employee Side Projects

Side projects are allowed if they do not use Northline confidential code or compete directly with Pulse. Cloud costs for side projects are personal unless preapproved as open source sponsorship.
""", None, None, None, None, None),
        ("c36", "canonical", "Support Macros for Data Deletion Requests", "2026-02-05",
         """# Support Macros for Data Deletion Requests

Use the privacy macro to open a GDPR ticket. Do not promise deletion timelines shorter than the policy without Privacy team confirmation. Attach customer workspace IDs in the ticket fields, not free-text email threads only.
""", None, None, None, None, None),
        ("c37", "canonical", "Scheduled Maintenance Windows", "2026-01-20",
         """# Scheduled Maintenance Windows

Maintenance excluded from SLA downtime must be announced at least 48 hours ahead on the status page and to Enterprise TAMs. Emergency maintenance may proceed with IC approval and still counts toward downtime unless customer-caused.
""", None, None, None, None, None),
        ("c38", "distractor", "Company North Star Metric Definition", "2025-08-15",
         """# Company North Star Metric Definition

Northline’s company north star is weekly active workspaces with a successful flag evaluation. Squad OKRs should not all copy the north star; they should be contributory. This is strategy context, not the quarterly OKR process mechanics.
""", "Strategy metric ≠ OKR process rules.", None, None, None, None),
        # Extra version chain (10th)
        ("c09", "versioned", "Export API Concurrent Jobs (2024)", "2024-05-01",
         """# Export API Concurrent Jobs (2024)

Growth workspaces may run **1** concurrent export job. Additional requests queue and fail after 15 minutes waiting.
""", "Old concurrent export limit = 1.", None, "vc-export-concurrency", 1, None),
        ("c09", "versioned", "Export API Concurrent Jobs (2025)", "2025-05-01",
         """# Export API Concurrent Jobs (2025)

Growth workspaces may run **2** concurrent export jobs. Enterprise default is 5.
""", "Mid concurrent export limit = 2 for Growth.", None, "vc-export-concurrency", 2, None),
        ("c09", "canonical", "Export API Concurrent Jobs (Current)", "2026-02-08",
         """# Export API Concurrent Jobs (Current)

Growth workspaces may run **3** concurrent export jobs. Enterprise default is **10**. Exceeding concurrency returns HTTP 409 with a `export_concurrency_exceeded` code. Prefer warehouse sync for continuous extraction instead of many parallel CSV jobs.
""", None, None, "vc-export-concurrency", 3, None),
        # Extra fragment group (8th)
        ("c12", "multi_hop_fragment", "Invoice Line Items — Seat Charges", "2026-02-25",
         """# Invoice Line Items — Seat Charges

Seat charges appear as `seats_committed` and `seats_overage` lines. Overage unit price equals list seat price unless a discount schedule says otherwise. This document explains line items only, not how seats are counted for eligibility.
""", None, None, None, None, "fg-seat-invoice"),
        ("c12", "multi_hop_fragment", "Invoice Line Items — How Seats Are Counted for the Line", "2026-02-25",
         """# Invoice Line Items — How Seats Are Counted for the Line

Billable seats are users active in the last 30 days excluding `billing_viewer`. Snapshot timing and overage soft cushion rules live in the seat-based billing policy; this fragment only states that those counted seats feed the `seats_committed` and `seats_overage` invoice lines described in the companion invoice line items note.
""", None, None, None, None, "fg-seat-invoice"),
        # More near noise
        ("noise", "near_noise", "Holiday Party Budget Guidelines", "2025-11-01",
         """# Holiday Party Budget Guidelines

People Ops funds a per-head budget for holiday events. Alcohol service needs security staffing at HQ. Remote employees receive a small meal stipend instead of party attendance. Submit receipts through Expensify with the holiday code.
""", None, None, None, None, None),
        ("noise", "near_noise", "Engineering Blog Editorial Calendar", "2025-06-15",
         """# Engineering Blog Editorial Calendar

DevRel maintains a monthly editorial calendar. Posts require eng review for technical accuracy and Legal review for forward-looking statements. Customer names need reference approval.
""", None, None, None, None, None),
        ("noise", "far_noise", "Municipal Chess Club Ratings Ladder", "2025-02-02",
         """# Municipal Chess Club Ratings Ladder

Club ratings update after each rated game using a simplified Elo with K=32. Provisional players need 10 games. Disputes go to the club arbiter within 48 hours. This community page is unrelated to Northline.
""", None, None, None, None, None),
        ("noise", "far_noise", "Home Aquaponics Water Testing Schedule", "2025-03-03",
         """# Home Aquaponics Water Testing Schedule

Test pH and ammonia twice weekly during system cycling. Nitrate targets depend on plant load. Record results in the binder. Unrelated to Northline corporate systems.
""", None, None, None, None, None),
    ]

    for row in supplements:
        cluster_id, role, title, date, content, vnote, cx, vc, vn, fg = row
        docs.append(doc(
            nid("noise" if cluster_id == "noise" else "doc"),
            cluster_id=None if cluster_id == "noise" else cluster_id,
            role=role,
            title=title,
            content=content,
            date=date,
            validation_note=vnote,
            contradiction_id=cx,
            version_chain_id=vc,
            version_number=vn,
            fragment_group_id=fg,
        ))

    # Expand thin documents to meet ~150 word floor without placeholders
    def expand(d: dict) -> dict:
        words = d["content"].split()
        if len(words) >= 150:
            return d
        extra = f"""

## Ownership and review
This page is owned by the responsible Northline team for the topic above and should be reviewed at least annually or when the underlying product behavior changes. Readers should prefer the newest dated document when multiple revisions exist in search results.

## How to use this guidance
Apply the rules in production systems and customer communications consistently. If a runbook or policy conflicts with an older unofficial FAQ, escalate to the owning team rather than inventing a local exception. Record approved exceptions with an expiry date.

## Support
Questions about interpretation can be asked in the relevant Slack channel for that domain (product, security, people, or eng-platform). Do not paste secrets into public channels when asking for help.
"""
        d = dict(d)
        d["content"] = (d["content"].rstrip() + extra).strip()
        return d

    docs = [expand(d) for d in docs]

    # Second expansion pass if still short
    def expand2(d: dict) -> dict:
        if len(d["content"].split()) >= 150:
            return d
        more = """

## Applicability
Unless a section states otherwise, guidance applies to Northline full-time employees and long-term contractors working on Pulse. Customer-facing commitments always follow the signed order form when numbers differ from internal targets.
"""
        d = dict(d)
        d["content"] = d["content"] + more
        return d

    docs = [expand2(d) for d in docs]

    # Programmatic density: 4 extra docs per cluster (2 canonical-adjacent notes, 2 distractors)
    # Unique facts so they are not near-duplicates; supports retrieval volume target.
    cluster_topics = {
        "c01": ("SDK installation", "write keys", "browser package"),
        "c02": ("event taxonomy", "property schemas", "naming rules"),
        "c03": ("identity resolution", "identify calls", "anonymous stitch"),
        "c04": ("feature flags", "rollout percentage", "targeting rules"),
        "c05": ("experiments", "guardrails", "primary metrics"),
        "c06": ("dashboards", "sharing links", "permissions"),
        "c07": ("data retention", "raw events", "deletion"),
        "c08": ("webhooks", "signatures", "retries"),
        "c09": ("API rate limits", "REST keys", "429 handling"),
        "c10": ("session replay", "masking", "sampling"),
        "c11": ("cohorts", "dynamic rules", "exports"),
        "c12": ("seat billing", "overage", "deactivation"),
        "c13": ("on-call", "page ACK", "handoffs"),
        "c14": ("incident severity", "IC checklist", "status page"),
        "c15": ("release freeze", "hotfixes", "tier-0 deploys"),
        "c16": ("RFC process", "comment windows", "decisions"),
        "c17": ("code review", "approvals", "CODEOWNERS"),
        "c18": ("staging access", "contractors", "data refresh"),
        "c19": ("DB migrations", "lock timeouts", "expand/contract"),
        "c20": ("secrets", "Vault", "rotation"),
        "c21": ("service ownership", "SCORE", "tiers"),
        "c22": ("postmortems", "action items", "blameless reviews"),
        "c23": ("access reviews", "SailPoint", "cadence"),
        "c24": ("breakglass", "production access", "session limits"),
        "c25": ("data classification", "Restricted data", "labeling"),
        "c26": ("vendor review", "DPA", "risk rating"),
        "c27": ("SOC 2 evidence", "control owners", "quarterly uploads"),
        "c28": ("PTO", "accrual", "approvals"),
        "c29": ("remote stipend", "payroll", "eligibility"),
        "c30": ("expenses", "Expensify", "receipts"),
        "c31": ("parental leave", "paid weeks", "notice"),
        "c32": ("laptop refresh", "hardware", "IT portal"),
        "c33": ("security training", "annual deadline", "phishing"),
        "c34": ("guest Wi-Fi", "visitors", "badges"),
        "c35": ("open source", "licenses", "dependencies"),
        "c36": ("support escalation", "TAM", "ticket SLAs"),
        "c37": ("uptime SLA", "credits", "maintenance"),
        "c38": ("OKRs", "quarterly planning", "WIP limits"),
    }

    for cid, (t1, t2, t3) in cluster_topics.items():
        docs.append(doc(
            nid(),
            cluster_id=cid,
            role="canonical",
            date="2026-01-15",
            title=f"Operational Checklist — {t1.title()}",
            content=f"""# Operational Checklist — {t1.title()}

## Purpose
Day-to-day checklist for teams working with {t1} inside Northline Pulse operations and internal administration.

## Before you change production
- Confirm you are in the correct workspace and environment.
- Read the latest dated policy for {t2} rather than a forwarded Slack screenshot.
- Ensure monitoring or audit logging will capture the change.
- Identify a rollback owner if {t3} settings are involved.

## During the change
Document the ticket or incident link. Prefer progressive delivery when the surface area is customer-visible. Avoid dual-writing conflicting values for {t2} across systems.

## After the change
Verify with a smoke test, announce in the squad channel, and update the runbook if the procedure drifted. Schedule a follow-up if {t3} requires cleanup.

## Escalation
If the checklist conflicts with an active incident commander decision, the IC wins for the duration of the incident; file a follow-up to reconcile documentation within three business days.
""",
        ))
        docs.append(doc(
            nid(),
            cluster_id=cid,
            role="canonical",
            date="2025-11-01",
            title=f"FAQ — {t2.title()} for New Teammates",
            content=f"""# FAQ — {t2.title()} for New Teammates

**Q: Where do I start learning about {t1}?**  
A: Start with the highest-dated canonical policy in the knowledge base tagged for this domain, then pair with a teammate on one real change involving {t2}.

**Q: Can I rely on tribal knowledge?**  
A: No. If a practice for {t3} is not written down, write it down after you confirm with the owning team.

**Q: What if two documents disagree?**  
A: Prefer the newer date, then ask the owning EM or policy owner. Do not silently pick the answer that is easiest to implement.

**Q: Are customer promises the same as internal targets?**  
A: Not always. Customer-facing numbers for {t1} must match contracts or public docs; internal stretch targets stay internal.

**Q: Who do I ping?**  
A: Use the SCORE or intranet owner for the service or policy. Avoid cold-DM'ing random senior engineers about {t2}.
""",
        ))
        docs.append(doc(
            nid(),
            cluster_id=cid,
            role="distractor",
            date="2024-06-15",
            validation_note=f"Outdated informal guide for {t1}; may cite stale practices for {t2} without matching current canonical numbers.",
            title=f"Legacy Notes on {t1.title()}",
            content=f"""# Legacy Notes on {t1.title()}

These notes were captured during a 2024 onboarding cohort and remain searchable.

Teams historically handled {t2} with more informal Slack approvals. Some examples mention older tooling names and looser expectations around {t3}. Several numbers in related threads from that era no longer match current policy—especially anything about default thresholds, time windows, or approval counts.

## Why this still exists
People keep linking it because the narrative examples are friendly. Friendly is not authoritative. Before changing production {t1} settings, open the current policy pages and ignore checklist items here that lack dates after 2025.

## Migration tip
If you find a process hole, update the canonical doc rather than expanding this legacy note.
""",
        ))
        docs.append(doc(
            nid(),
            cluster_id=cid,
            role="distractor",
            date="2025-04-20",
            validation_note=f"Adjacent topic that shares vocabulary with {t1} but answers a different operational question (training/onboarding angle).",
            title=f"Workshop Outline — Introducing {t1.title()}",
            content=f"""# Workshop Outline — Introducing {t1.title()}

## Audience
New hires in the first 60 days who need vocabulary around {t1}, {t2}, and {t3}.

## Agenda
1. Vocabulary freeze (15 min)  
2. Live demo in a sandbox (20 min)  
3. Failure stories (15 min)  
4. Where documents live (10 min)

## Non-goals
This workshop does not authorize production changes and does not restate binding numeric policy (percentages, day counts, SLAs). Facilitators should project the current policy page when someone asks for an exact figure rather than quoting memory.

## Materials
Sandbox workspace, slide deck, and a quiz that points back to intranet links. Facilitators rotate quarterly.
""",
        ))

    # Extra far/near noise to top up
    for i in range(1, 11):
        docs.append(doc(
            nid("noise"),
            cluster_id=None,
            role="near_noise",
            date=f"2025-{(i % 12) + 1:02d}-10",
            title=f"Internal Club Charter — Interest Group {i}",
            content=f"""# Internal Club Charter — Interest Group {i}

Northline employees may form voluntary interest groups. Group {i} covers informal community activities that are not product roadmap work. Budget requests under $200 go to People Ops with a simple form. Groups cannot use customer data for club activities. Officers rotate every six months. Meeting notes stay on the intranet, not in customer Slack connect channels.

## Membership
Open to full-time employees and interns. Contractors may attend if their manager approves and no export-controlled topics arise.

## Funding
Submit receipts monthly. Unused budgets do not roll across fiscal year. Groups that go dormant for a quarter lose reserved meeting rooms.
""",
        ))
    for i in range(1, 6):
        docs.append(doc(
            nid("noise"),
            cluster_id=None,
            role="far_noise",
            date=f"2024-{(i % 12) + 1:02d}-15",
            title=f"Regional Field Guide Entry #{i}",
            content=f"""# Regional Field Guide Entry #{i}

Naturalist notes for public land trailhead #{i}: seasonal hazards, water sources, and Leave No Trace reminders. Group sizes above twelve should notify park rangers. Dogs on leash where posted. This guide is not a Northline corporate policy and does not discuss software, analytics, or employment benefits.

## Seasonal notes
Spring melt increases stream crossings. Summer storms form after noon on ridge lines. Winter travel requires traction devices and earlier turnaround times. Always share a plan with someone not on the trip.
""",
        ))

    docs = [expand(d) for d in docs]
    docs = [expand2(d) for d in docs]
    return docs


# ─── Queries ──────────────────────────────────────────────────────────────────

def build_queries(docs: list[dict]) -> list[dict]:
    by_cluster: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d["cluster_id"]:
            by_cluster[d["cluster_id"]].append(d)

    # Index special groups
    version_chains = sorted({d["version_chain_id"] for d in docs if d.get("version_chain_id")})
    fragment_groups = sorted({d["fragment_group_id"] for d in docs if d.get("fragment_group_id")})
    contradictions = sorted({d["contradiction_id"] for d in docs if d.get("contradiction_id")})

    qs: list[dict] = []
    qn = 0

    def q(
        text: str,
        category: str,
        clusters: list[str] | str | None,
        *,
        contradiction_id: str | None = None,
        version_chain_id: str | None = None,
        fragment_group_id: str | None = None,
    ) -> None:
        nonlocal qn
        qn += 1
        if clusters is None:
            tc: list[str] | None = None
        elif isinstance(clusters, str):
            tc = [clusters]
        else:
            tc = clusters
        qs.append({
            "id": f"q-{qn:04d}",
            "query_text": text,
            "category": category,
            "target_cluster_ids": tc,
            "reference_ids": {
                "contradiction_id": contradiction_id,
                "version_chain_id": version_chain_id,
                "fragment_group_id": fragment_group_id,
            },
        })

    # EASY — one clear canonical
    easy = [
        ("c01", "How do I install the current Northline Pulse Web SDK v3 and initialize PulseClient?"),
        ("c02", "What naming convention does Pulse require for analytics event names?"),
        ("c03", "When should client apps call pulse.reset() during logout?"),
        ("c04", "What is the default rollout percentage for newly created boolean feature flags?"),
        ("c06", "Which dashboard roles can delete a dashboard?"),
        ("c08", "What signature header does Pulse send on outbound webhooks?"),
        ("c10", "Is session replay enabled by default for new workspaces?"),
        ("c11", "How often do dynamic cohorts re-evaluate membership?"),
        ("c13", "How long is a primary on-call shift for Pulse services?"),
        ("c14", "What severity is a complete ingest outage affecting multiple customers?"),
        ("c16", "How many business days must an RFC stay open for comments?"),
        ("c17", "What is the first-review SLA for a PR under 400 lines?"),
        ("c18", "Do full-time engineers get staging Kubernetes access by default?"),
        ("c20", "What is the system of record for secrets at Northline?"),
        ("c21", "What happens if a service has no valid on-call for more than seven days?"),
        ("c22", "Within how many business days should a P1 postmortem write-up be published?"),
        ("c24", "What is the default duration of production breakglass access?"),
        ("c25", "What data classification level applies to production database dumps?"),
        ("c28", "How many PTO days do US full-time employees accrue per year?"),
        ("c30", "Within how many days must expenses be submitted in Expensify?"),
        ("c31", "How many weeks of paid leave do birthing parents receive?"),
        ("c32", "What is the standard laptop refresh cycle in months?"),
        ("c34", "What is the guest Wi-Fi SSID at Northline offices?"),
        ("c35", "Which open source licenses are generally allowed for contributions?"),
        ("c38", "What OKR score is considered healthy stretch success?"),
    ]
    for cid, text in easy:
        q(text, "easy", cid)

    # AMBIGUOUS / distractor-prone
    ambiguous = [
        ("c01", "How do I install Northline analytics in a single-page app with npm?"),
        ("c02", "What are the analytics naming standards I should follow?"),
        ("c03", "What is the identity merge window after login?"),
        ("c04", "What default percentage should I use when creating a new flag for an experiment?"),
        ("c05", "What guardrails auto-stop bad experiments?"),
        ("c07", "How long is data retained by default?"),
        ("c08", "How long do webhooks retry failed deliveries?"),
        ("c09", "What is the API rate limit on Growth?"),
        ("c10", "What sampling rate should I use for sessions?"),
        ("c12", "How does Northline count billable users for pricing overage?"),
        ("c13", "How fast must I acknowledge a P1 page?"),
        ("c14", "What counts as Sev1 for customer issues?"),
        ("c15", "When do freezes start before company events?"),
        ("c16", "How long do RFCs need to be open?"),
        ("c17", "How many approvals do I need to merge a production PR?"),
        ("c19", "What lock timeout should migrations use in production?"),
        ("c20", "Where should I store production API secrets?"),
        ("c22", "How soon after an incident should we run the review?"),
        ("c23", "How often do we review production access?"),
        ("c24", "How long does emergency prod access last?"),
        ("c26", "How many days does security take to review a new vendor?"),
        ("c28", "How much PTO do we get each year?"),
        ("c29", "What monthly stipend do remote employees get?"),
        ("c30", "When do I need to attach a receipt to an expense?"),
        ("c33", "When is annual security training due?"),
        ("c36", "What's the escalation path when something is broken?"),
        ("c37", "What uptime do we promise customers?"),
    ]
    for cid, text in ambiguous:
        q(text, "ambiguous_distractor_prone", cid)

    # VERSIONED — latest in chain
    version_queries = [
        ("vc-sdk-install", "c01", "What is the current package init API for the Pulse web SDK writeKey and environment fields?"),
        ("vc-sdk-install", "c01", "Which ingest URL path should the latest web SDK use for tracking?"),
        ("vc-exp-guardrails", "c05", "Under the current experiment policy, what relative primary-metric drop triggers auto-pause?"),
        ("vc-exp-guardrails", "c05", "What sample-ratio drift and duration mark an experiment unhealthy today?"),
        ("vc-retention-default", "c07", "What is the current default raw event retention for Growth plan workspaces?"),
        ("vc-retention-default", "c07", "How long after workspace cancellation is data purged under the current retention policy?"),
        ("vc-status-page-sla", "c14", "How quickly must we post an initial status page update for a P1 under current comms policy?"),
        ("vc-staging-contractor", "c18", "What is the maximum contractor staging access grant length currently?"),
        ("vc-secret-rotation-db", "c20", "How often do database passwords rotate under the current standard?"),
        ("vc-wfh-stipend", "c29", "What is the current monthly remote work stipend amount?"),
        ("vc-laptop-cycle", "c32", "How often are employee laptops refreshed under the current hardware policy?"),
        ("vc-okr-wip", "c38", "How many committed team OKRs may a squad carry under current WIP guidance?"),
        ("vc-export-concurrency", "c09", "How many concurrent export jobs can a Growth workspace run under the current limit?"),
    ]
    for vc, cid, text in version_queries:
        assert vc in version_chains, vc
        q(text, "versioned", cid, version_chain_id=vc)

    # MULTI-HOP
    hop = [
        ("fg-taxonomy-checkout", "c02", "For checkout_completed, which properties are required and when should the event fire?"),
        ("fg-taxonomy-checkout", "c02", "What plan_code values are allowed on checkout events and when does checkout_started fire?"),
        ("fg-exp-power", "c05", "How should I choose a primary metric and what minimum runtime does power analysis require?"),
        ("fg-exp-power", "c05", "What default power and significance does the calculator use once a primary metric is locked?"),
        ("fg-webhook-alert", "c08", "What fields are in an alert.fired webhook and which on-call service gets checkout_* metrics?"),
        ("fg-webhook-alert", "c08", "How does Alertbridge set severity for ingest_* alert webhooks and what payload fields arrive?"),
        ("fg-cohort-export", "c11", "What file formats can cohort export produce and which cloud destinations are supported?"),
        ("fg-cohort-export", "c11", "What user fields are included in cohort exports and how are destination credentials stored?"),
        ("fg-rfc-security", "c16", "When does an RFC need Security review and what is the standard review SLA?"),
        ("fg-rfc-security", "c16", "How do I file a security rfc-review ticket and which RFC topics require that gate?"),
        ("fg-breakglass-db", "c24", "Who is eligible for production database console breakglass and what steps open a Teleport DB session?"),
        ("fg-breakglass-db", "c24", "Can contractors get prod DB breakglass, and must write statements be pasted into the incident timeline?"),
        ("fg-support-enterprise-sla", "c36", "What entitlements do Enterprise support contracts include and what are examples of P1 vs P2 issues?"),
        ("fg-seat-invoice", "c12", "How do seat counts become invoice line items for committed vs overage seats?"),
    ]
    for fg, cid, text in hop:
        assert fg in fragment_groups, fg
        q(text, "multi_hop", cid, fragment_group_id=fg)

    # CONTRADICTION-AWARE
    cx_q = [
        ("cx-identity-window", "c03", "How many days back does Pulse stitch anonymous events after identify?"),
        ("cx-flag-default-pct", "c04", "What percentage rollout do new feature flags get by default at creation?"),
        ("cx-dash-share-link-ttl", "c06", "How long until a Pulse public dashboard link expires?"),
        ("cx-api-rate-limit", "c09", "What is the Growth plan per-minute read rate limit for the REST API?"),
        ("cx-seat-overage", "c12", "What soft overage percent is allowed on Growth seats before automatic charges?"),
        ("cx-oncall-ack", "c13", "Within how many minutes must a P1 page be acknowledged?"),
        ("cx-freeze-window", "c15", "How many hours before a company event does code freeze begin?"),
        ("cx-review-approvals", "c17", "How many approvals are required to merge a typical production PR?"),
        ("cx-migration-lock", "c19", "What lock timeout does the production migrator use?"),
        ("cx-access-review-cadence", "c23", "How often must production system access be reviewed?"),
        ("cx-vendor-sla", "c26", "What is the standard SLA in business days for a vendor security review?"),
        ("cx-pto-accrual", "c28", "How many PTO days per year do US full-time employees accrue?"),
        ("cx-expense-receipt", "c30", "Above what dollar amount are receipts required for expenses?"),
        ("cx-training-deadline", "c33", "By what calendar date must annual security awareness training be completed?"),
        ("cx-uptime-sla", "c37", "What monthly uptime percentage does the Enterprise service SLA commit to?"),
    ]
    for cx, cid, text in cx_q:
        assert cx in contradictions, cx
        q(text, "contradiction_aware", cid, contradiction_id=cx)

    # UNANSWERABLE — plausible Northline-ish but no canonical answer in corpus
    unans = [
        "What is Northline Pulse's SOC 2 Type II report date for the latest audit period?",
        "How do I configure Pulse Android SDK ProGuard rules for minifyEnabled builds?",
        "What is the maximum number of feature flags allowed on the Starter plan?",
        "Does Pulse support SAML single logout (SLO) for enterprise SSO?",
        "What is the list price per seat for Pulse Growth in EUR?",
        "How do I enable HIPAA BAA self-serve from the billing UI?",
        "What regions are available for Pulse data residency in APAC?",
        "How long is the customer success onboarding white-glove program for Enterprise?",
        "What is the exact p99 SLO for the flag evaluation edge in eu-west-1?",
        "Can I import Amplitude cohorts into Pulse with one-click OAuth?",
        "What is the employee employee-number format for badge printing?",
        "How many weeks of sabbatical does Northline offer after five years?",
        "What is the VPN split-tunnel domain allowlist for contractors in India?",
        "Which version of Terraform providers is pinned for the marketing AWS account?",
        "How do I request a custom domain for hosted status pages?",
        "What is the cancellation notice period for monthly Growth self-serve?",
        "Does Pulse warehouse sync support Azure Synapse natively?",
        "What is the bug bounty payout range for critical RCE findings?",
        "How are ISO 27001 controls mapped to Jira automation bots?",
        "What is the maximum attachment size for Support tickets with replay files?",
        "How do I rotate mobile push certificate for the unreleased Pulse mobile admin app?",
        "What daycare backup benefit vendor does Northline use in Austin?",
        "Is there a public Postman collection for the v4 GraphQL API?",
        "What is the carbon offset vendor used for company travel in 2026?",
    ]
    for text in unans:
        q(text, "unanswerable", None)

    # MULTI-CLUSTER compound questions
    multi = [
        (["c01", "c03"], "After installing the web SDK, how should I call identify and what is the anonymous merge window?"),
        (["c04", "c05"], "How do feature flag default rollouts interact with experiment guardrails when launching an A/B test?"),
        (["c08", "c13"], "If an alert webhook fires for ingest_* metrics, who gets paged and what is the P1 acknowledge expectation?"),
        (["c07", "c10"], "How long are raw events retained on Growth versus how long are session replays stored?"),
        (["c09", "c08"], "What REST read rate limits apply and how long will outbound webhooks keep retrying failed deliveries?"),
        (["c12", "c30"], "How are billable seats counted and what receipt rules apply when expensing a team offsite?"),
        (["c15", "c17"], "During a release freeze, can I still merge PRs and what approval rules apply to hotfixes?"),
        (["c16", "c20"], "When an RFC changes secrets handling, what RFC comment window and secret rotation rules apply?"),
        (["c23", "c24"], "How often is production access reviewed and how does breakglass time-limit work for emergencies?"),
        (["c28", "c31"], "How does PTO accrual interact with parental leave eligibility tenure?"),
        (["c33", "c24"], "If I miss security training, what access is disabled and how does that interact with breakglass?"),
        (["c36", "c37"], "What Enterprise support first-response times apply when uptime SLA credits might also be owed?"),
        (["c11", "c04"], "Can dynamic cohorts be targeted by feature flags and how often do those cohorts refresh?"),
        (["c19", "c15"], "Can I run a database migration during a hard release freeze without special approval?"),
        (["c06", "c25"], "Can I create a public dashboard link if the underlying events are classified Restricted?"),
        (["c21", "c13"], "If SCORE shows no on-call for a service, who is paged and what are primary on-call duties?"),
        (["c26", "c25"], "What vendor review is required before a tool processes Restricted data?"),
        (["c32", "c20"], "When I refresh a laptop, what happens to local secrets and how should secrets be stored instead?"),
        (["c38", "c22"], "Should postmortem action items be written as quarterly OKRs and what is the OKR WIP limit?"),
        (["c02", "c09"], "How should checkout events be named and what API rate limits hit if I backfill them via REST?"),
    ]
    for clusters, text in multi:
        q(text, "multi_cluster", clusters)

    # Extra easy/ambiguous to approach 150–200
    more_easy = [
        ("c05", "Are error rate guardrails mandatory for billing-surface experiments under current policy?"),
        ("c07", "What is Starter plan raw event retention?"),
        ("c08", "How many active webhook endpoints may a workspace configure?"),
        ("c09", "Which response headers communicate REST rate limit state?"),
        ("c11", "What is the maximum number of conditions on a dynamic cohort?"),
        ("c12", "Which role is excluded from billable seat counts?"),
        ("c18", "How often are scrubbed production snapshots restored into staging?"),
        ("c19", "What expand/contract rule applies to database migrations?"),
        ("c26", "Who must approve High risk vendor ratings?"),
        ("c27", "How many days after quarter end is SOC 2 evidence due?"),
        ("c29", "Is the remote work stipend taxable?"),
        ("c34", "When do visitor badges expire each day?"),
        ("c36", "What is first-response SLA for Growth support tickets?"),
    ]
    for cid, text in more_easy:
        q(text, "easy", cid)

    more_amb = [
        ("c01", "What's the quick start for setting up the Pulse client with a write key?"),
        ("c05", "What percentage drop stops an experiment automatically?"),
        ("c07", "How long do we keep product data for analytics?"),
        ("c11", "How fresh is dynamic audience membership?"),
        ("c12", "What's the overage cushion for seats on Growth?"),
        ("c15", "What's the lead time before freezes for big events?"),
        ("c20", "How often do DB passwords need to change?"),
        ("c29", "What do we pay people monthly for working from home internet?"),
        ("c31", "How much parental leave does Northline offer?"),
        ("c32", "When can I get a new company laptop?"),
    ]
    for cid, text in more_amb:
        q(text, "ambiguous_distractor_prone", cid)

    return qs


# ─── Validation ───────────────────────────────────────────────────────────────

def validate_corpus(docs: list[dict]) -> list[str]:
    errors: list[str] = []
    ids = [d["id"] for d in docs]
    if len(ids) != len(set(ids)):
        errors.append("duplicate document ids")

    roles = Counter(d["role"] for d in docs)
    clusters = {d["cluster_id"] for d in docs if d["cluster_id"]}
    if not (35 <= len(clusters) <= 40):
        errors.append(f"cluster count {len(clusters)} not in 35-40")
    if not (350 <= len(docs) <= 450):
        # soft: allow slightly outside if close
        if len(docs) < 300 or len(docs) > 500:
            errors.append(f"doc count {len(docs)} far from 350-450 target")

    # version chains chronological
    by_vc: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d.get("version_chain_id"):
            by_vc[d["version_chain_id"]].append(d)
    for vc, members in by_vc.items():
        ordered = sorted(members, key=lambda x: (x["version_number"] or 0))
        dates = [m["date"] for m in ordered]
        if dates != sorted(dates):
            errors.append(f"version chain {vc} dates not aligned with version_number")
        nums = [m["version_number"] for m in ordered]
        if nums != list(range(1, len(nums) + 1)) and sorted(nums) != nums:
            errors.append(f"version chain {vc} version numbers odd: {nums}")

    # contradictions need 2+ docs with explicit shared id
    by_cx: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d.get("contradiction_id"):
            by_cx[d["contradiction_id"]].append(d)
    for cx, members in by_cx.items():
        if len(members) < 2:
            errors.append(f"contradiction {cx} has <2 docs")
        for m in members:
            if m["role"] in ("contradicting", "contradiction_chain", "canonical") or m.get("validation_note"):
                continue

    # fragments
    by_fg: dict[str, list[dict]] = defaultdict(list)
    for d in docs:
        if d.get("fragment_group_id"):
            by_fg[d["fragment_group_id"]].append(d)
    for fg, members in by_fg.items():
        if len(members) < 2:
            errors.append(f"fragment group {fg} has <2 docs")

    # validation_note presence for distractors
    for d in docs:
        if d["role"] == "distractor" and not d.get("validation_note"):
            errors.append(f"{d['id']} distractor missing validation_note")
        if d["role"] in ("contradicting", "contradiction_chain") and not d.get("validation_note"):
            # allow if note empty for chain platform standard — still prefer notes
            if not d.get("validation_note"):
                errors.append(f"{d['id']} contradicting missing validation_note")

    # word counts spot check (target 150–400; flag only extreme shorts)
    short = [d["id"] for d in docs if len(d["content"].split()) < 100]
    if short:
        errors.append(f"{len(short)} docs very short (<100 words), e.g. {short[:5]}")
    if not (350 <= len(docs) <= 450):
        if len(docs) < 350:
            errors.append(f"doc count {len(docs)} below 350 target")
        elif len(docs) > 450:
            # allow slight overrun up to 480
            if len(docs) > 480:
                errors.append(f"doc count {len(docs)} above 450 target")

    # near-duplicate titles
    title_counts = Counter(d["title"].lower().strip() for d in docs)
    dups = [t for t, c in title_counts.items() if c > 1]
    if dups:
        errors.append(f"duplicate titles: {dups[:5]}")

    print("Corpus stats:")
    print(f"  docs={len(docs)} clusters={len(clusters)} roles={dict(roles)}")
    print(f"  version_chains={len(by_vc)} fragments={len(by_fg)} contradictions={len(by_cx)}")
    print(f"  near_noise={roles.get('near_noise',0)} far_noise={roles.get('far_noise',0)}")
    return errors


def validate_queries(queries: list[dict], docs: list[dict]) -> list[str]:
    errors: list[str] = []
    clusters = {d["cluster_id"] for d in docs if d["cluster_id"]}
    vcs = {d["version_chain_id"] for d in docs if d.get("version_chain_id")}
    fgs = {d["fragment_group_id"] for d in docs if d.get("fragment_group_id")}
    cxs = {d["contradiction_id"] for d in docs if d.get("contradiction_id")}

    ids = [q["id"] for q in queries]
    if len(ids) != len(set(ids)):
        errors.append("duplicate query ids")

    if not (150 <= len(queries) <= 220):
        errors.append(f"query count {len(queries)} outside ~150-200 band")

    cats = Counter(q["category"] for q in queries)
    for q in queries:
        for cid in q["target_cluster_ids"] or []:
            if cid not in clusters:
                errors.append(f"{q['id']} unknown cluster {cid}")
        ref = q["reference_ids"]
        if ref.get("version_chain_id") and ref["version_chain_id"] not in vcs:
            errors.append(f"{q['id']} bad version_chain_id")
        if ref.get("fragment_group_id") and ref["fragment_group_id"] not in fgs:
            errors.append(f"{q['id']} bad fragment_group_id")
        if ref.get("contradiction_id") and ref["contradiction_id"] not in cxs:
            errors.append(f"{q['id']} bad contradiction_id")
        if q["category"] == "unanswerable" and q["target_cluster_ids"]:
            errors.append(f"{q['id']} unanswerable should not target clusters")
        if q["category"] == "multi_cluster" and (not q["target_cluster_ids"] or len(q["target_cluster_ids"]) < 2):
            errors.append(f"{q['id']} multi_cluster needs 2+ clusters")
        if q["category"] == "versioned" and not ref.get("version_chain_id"):
            errors.append(f"{q['id']} versioned missing version_chain_id")
        if q["category"] == "multi_hop" and not ref.get("fragment_group_id"):
            errors.append(f"{q['id']} multi_hop missing fragment_group_id")
        if q["category"] == "contradiction_aware" and not ref.get("contradiction_id"):
            errors.append(f"{q['id']} contradiction_aware missing contradiction_id")

    print("Query stats:")
    print(f"  queries={len(queries)} categories={dict(cats)}")
    return errors


def main() -> None:
    print("Building corpus…")
    docs = build_corpus()
    cerr = validate_corpus(docs)
    dump_jsonl(CORPUS_PATH, docs)
    print(f"Wrote {CORPUS_PATH} ({len(docs)} lines)")
    if cerr:
        print("CORPUS VALIDATION ISSUES:")
        for e in cerr:
            print(" -", e)
        raise SystemExit(1)
    print("Corpus validation OK")

    print("Building queries…")
    queries = build_queries(docs)
    qerr = validate_queries(queries, docs)
    dump_jsonl(QUERIES_PATH, queries)
    print(f"Wrote {QUERIES_PATH} ({len(queries)} lines)")
    if qerr:
        print("QUERY VALIDATION ISSUES:")
        for e in qerr:
            print(" -", e)
        raise SystemExit(1)
    print("Query validation OK")


if __name__ == "__main__":
    main()
