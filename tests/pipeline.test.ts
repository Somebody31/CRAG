import { describe, expect, test } from "bun:test";
import {
  docsForAnswer,
  MAX_CORRECTION_ATTEMPTS,
  routeAfterGrade,
  runCrag,
  type CragState,
} from "../src/pipeline.ts";
import type { GradedDoc } from "../src/types.ts";

function baseState(overrides: Partial<CragState>): CragState {
  return {
    query: "test",
    currentQuery: "test",
    rewrites: [],
    correctionAttempts: 0,
    documents: [],
    graded: [],
    strength: "weak",
    status: "running",
    answer: null,
    refusal: null,
    stages: [],
    error: null,
    ...overrides,
  };
}

describe("routeAfterGrade", () => {
  test("error ends the graph", () => {
    expect(routeAfterGrade(baseState({ status: "error" }))).toBe("end");
  });

  test("strong goes to generate", () => {
    expect(routeAfterGrade(baseState({ strength: "strong" }))).toBe(
      "generate",
    );
  });

  test("weak with budget left goes to correct", () => {
    expect(
      routeAfterGrade(
        baseState({ strength: "weak", correctionAttempts: 0 }),
      ),
    ).toBe("correct");
  });

  test("weak after max attempts goes to refuse", () => {
    expect(
      routeAfterGrade(
        baseState({
          strength: "weak",
          correctionAttempts: MAX_CORRECTION_ATTEMPTS,
        }),
      ),
    ).toBe("refuse");
  });
});

describe("docsForAnswer", () => {
  test("keeps relevant and ambiguous, drops irrelevant", () => {
    const docs: GradedDoc[] = [
      {
        id: "a",
        title: "A",
        content: "a",
        snippet: "a",
        score: null,
        clusterId: null,
        role: null,
        fromCorrection: false,
        grade: "relevant",
        reason: "",
      },
      {
        id: "b",
        title: "B",
        content: "b",
        snippet: "b",
        score: null,
        clusterId: null,
        role: null,
        fromCorrection: false,
        grade: "irrelevant",
        reason: "",
      },
      {
        id: "c",
        title: "C",
        content: "c",
        snippet: "c",
        score: null,
        clusterId: null,
        role: null,
        fromCorrection: false,
        grade: "ambiguous",
        reason: "",
      },
    ];
    const kept = docsForAnswer(docs);
    expect(kept.map((d) => d.id)).toEqual(["a", "c"]);
  });
});

describe("runCrag", () => {
  test("empty query returns error without calling services", async () => {
    const result = await runCrag("   ");
    expect(result.status).toBe("error");
    expect(result.error).toBe("query is empty");
  });
});
