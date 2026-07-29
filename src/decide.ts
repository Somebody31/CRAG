// Pure decide step: list of grades → strong | weak.

import type { GradeLabel } from "./types.ts";

export type Strength = "strong" | "weak";

/**
 * Strong if (at least one relevant and no irrelevant)
 * or at least two relevant. Empty list is weak.
 */
export function decideStrength(grades: GradeLabel[]): Strength {
  if (grades.length === 0) return "weak";

  let relevant = 0;
  let irrelevant = 0;
  for (const grade of grades) {
    if (grade === "relevant") relevant += 1;
    if (grade === "irrelevant") irrelevant += 1;
  }

  if (relevant >= 1 && irrelevant === 0) return "strong";
  if (relevant >= 2) return "strong";
  return "weak";
}
