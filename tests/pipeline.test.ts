import { describe, expect, test } from "bun:test";
import { runCrag } from "../src/graph/pipeline.ts";
import { MAX_CORRECTION_ATTEMPTS } from "../src/graph/nodes.ts";
import type { GraphDeps } from "../src/graph/deps.ts";
import type { RetrievedDoc } from "../src/types.ts";

function doc(
  id: string,
  title: string,
  fromCorrection = false,
): RetrievedDoc {
  return {
    id,
    title,
    content: `Body of ${title}`,
    snippet: `Body of ${title}`,
    score: 0.1,
    clusterId: "c01",
    role: "canonical",
    fromCorrection,
  };
}

describe("runCrag with mocks", () => {
  test("strong first retrieval → answered, no rewrite", async () => {
    const deps: GraphDeps = {
      retrieveSimilar: async () => [doc("d1", "SDK Install"), doc("d2", "Init")],
      completeChat: async ({ system }) => {
        if (system.includes("grade")) {
          return JSON.stringify({
            grade: "relevant",
            reason: "direct answer",
          });
        }
        if (system.includes("ONLY the provided source")) {
          return "Install the SDK with npm and call PulseClient.init.";
        }
        throw new Error("unexpected LLM call: " + system.slice(0, 40));
      },
    };

    const result = await runCrag("How do I install the Pulse Web SDK?", deps);
    expect(result.status).toBe("answered");
    expect(result.correctionAttempts).toBe(0);
    expect(result.rewrites).toEqual([]);
    expect(result.answer).toContain("Install");
    expect(result.documents.length).toBe(2);
    expect(result.stages.some((s) => s.name === "generate" && s.ok)).toBe(
      true,
    );
  });

  test("weak then strong after rewrite → answered with correction", async () => {
    let retrieveCount = 0;
    const deps: GraphDeps = {
      retrieveSimilar: async (_q, opts) => {
        retrieveCount += 1;
        if (retrieveCount === 1) {
          return [doc("noise", "Cafeteria menu")];
        }
        return [
          doc("good", "SDK Install Guide", opts?.fromCorrection ?? false),
        ];
      },
      completeChat: async ({ system, user }) => {
        if (system.includes("grade")) {
          if (user.includes("Cafeteria")) {
            return JSON.stringify({
              grade: "irrelevant",
              reason: "wrong topic",
            });
          }
          return JSON.stringify({
            grade: "relevant",
            reason: "has install steps",
          });
        }
        if (system.includes("rewrite")) {
          return JSON.stringify({
            rewrite: "Pulse Web SDK install npm package init",
          });
        }
        if (system.includes("ONLY the provided source")) {
          return "Use @northline/pulse-web and init with writeKey.";
        }
        throw new Error("unexpected: " + system.slice(0, 50));
      },
    };

    const result = await runCrag("how install?", deps);
    expect(result.status).toBe("answered");
    expect(result.correctionAttempts).toBe(1);
    expect(result.rewrites.length).toBe(1);
    expect(result.answer).toContain("writeKey");
  });

  test("always weak → refused after max corrections", async () => {
    let grades = 0;
    const deps: GraphDeps = {
      retrieveSimilar: async () => [doc("x", "Unrelated HR policy")],
      completeChat: async ({ system }) => {
        if (system.includes("grade")) {
          grades += 1;
          return JSON.stringify({
            grade: "irrelevant",
            reason: "no support",
          });
        }
        if (system.includes("rewrite")) {
          return JSON.stringify({ rewrite: "expanded unrelated query" });
        }
        throw new Error("should not generate");
      },
    };

    const result = await runCrag(
      "What is the secret quantum tea protocol?",
      deps,
    );
    expect(result.status).toBe("refused");
    expect(result.correctionAttempts).toBe(MAX_CORRECTION_ATTEMPTS);
    expect(result.refusal).toMatch(/don't know/i);
    expect(result.answer).toBeNull();
    expect(grades).toBe(1 + MAX_CORRECTION_ATTEMPTS); // initial + after each correct
  });

  test("empty query → error", async () => {
    const deps: GraphDeps = {
      retrieveSimilar: async () => [],
      completeChat: async () => "",
    };
    const result = await runCrag("   ", deps);
    expect(result.status).toBe("error");
  });
});
