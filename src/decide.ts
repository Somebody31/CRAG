// Pure decide step: grades → strong | weak. No I/O.

import type { GradeLabel } from "./types.ts";

export type Strength = "strong" | "weak";

/**
 * Phase 1 rule (AGENTS.md):
 * Strong if (relevant >= 1 && irrelevant === 0) OR relevant >= 2.
 * Weak otherwise (including empty list).
 */
export function decideStrength(grades: GradeLabel[]): Strength {
  if (grades.length === 0) return "weak";

  let relevant = 0;
  let irrelevant = 0;
  for (const g of grades) {
    if (g === "relevant") relevant += 1;
    else if (g === "irrelevant") irrelevant += 1;
  }

  if (relevant >= 1 && irrelevant === 0) return "strong";
  if (relevant >= 2) return "strong";
  return "weak";
}
