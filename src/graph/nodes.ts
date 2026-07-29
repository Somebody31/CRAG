// LangGraph node functions for Phase 1 CRAG.

import { decideStrength } from "../decide.ts";
import { parseJsonObject } from "../parseJson.ts";
import type { GradeLabel, GradedDoc, StageTrace } from "../types.ts";
import type { GraphDeps } from "./deps.ts";
import {
  GENERATE_SYSTEM,
  GRADE_SYSTEM,
  REFUSAL_MESSAGE,
  REWRITE_SYSTEM,
  generateUserPrompt,
  gradeUserPrompt,
  rewriteUserPrompt,
} from "./prompts.ts";
import type { CragState } from "./state.ts";

export const MAX_CORRECTION_ATTEMPTS = 2;

function asGrade(value: unknown): GradeLabel {
  if (value === "relevant" || value === "ambiguous" || value === "irrelevant") {
    return value;
  }
  return "ambiguous";
}

function pushStage(
  stages: StageTrace[],
  name: StageTrace["name"],
  ok: boolean,
  detail?: string,
): StageTrace[] {
  return stages.concat([{ name, ok, detail }]);
}

/** Retrieve top-k for currentQuery (or initial query). */
export function makeRetrieveNode(deps: GraphDeps) {
  return async (state: CragState): Promise<Partial<CragState>> => {
    const q = state.currentQuery || state.query;
    const fromCorrection = state.correctionAttempts > 0;
    try {
      const documents = await deps.retrieveSimilar(q, {
        k: 6,
        fromCorrection,
      });
      return {
        documents,
        stages: pushStage(
          state.stages,
          "retrieve",
          true,
          `${documents.length} docs`,
        ),
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        documents: [],
        status: "error",
        error: msg,
        stages: pushStage(state.stages, "retrieve", false, msg),
      };
    }
  };
}

/** Grade each retrieved doc with the LLM. */
export function makeGradeNode(deps: GraphDeps) {
  return async (state: CragState): Promise<Partial<CragState>> => {
    if (state.status === "error") return {};

    const docs = state.documents;
    if (docs.length === 0) {
      return {
        graded: [],
        strength: "weak",
        stages: pushStage(state.stages, "grade", true, "no docs"),
      };
    }

    const graded: GradedDoc[] = [];
    try {
      for (const doc of docs) {
        const raw = await deps.completeChat({
          system: GRADE_SYSTEM,
          user: gradeUserPrompt(state.query, doc),
          temperature: 0,
        });
        const parsed = parseJsonObject(raw);
        const grade = asGrade(parsed?.grade);
        const reason =
          typeof parsed?.reason === "string" ? parsed.reason : "";
        graded.push({ ...doc, grade, reason });
      }

      const strength = decideStrength(graded.map((g) => g.grade));
      return {
        graded,
        strength,
        stages: pushStage(
          state.stages,
          "grade",
          true,
          `strength=${strength}`,
        ),
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        status: "error",
        error: msg,
        stages: pushStage(state.stages, "grade", false, msg),
      };
    }
  };
}

/** Rewrite query and bump correctionAttempts (retrieve runs next). */
export function makeCorrectNode(deps: GraphDeps) {
  return async (state: CragState): Promise<Partial<CragState>> => {
    if (state.status === "error") return {};

    const attempt = state.correctionAttempts + 1;
    try {
      const raw = await deps.completeChat({
        system: REWRITE_SYSTEM,
        user: rewriteUserPrompt(state.query, attempt),
        temperature: 0.3,
      });
      const parsed = parseJsonObject(raw);
      let rewrite =
        typeof parsed?.rewrite === "string" ? parsed.rewrite.trim() : "";
      if (!rewrite) {
        // Fallback: append a light expansion hint if model failed JSON.
        rewrite = `${state.query} Northline Pulse policy details`;
      }

      return {
        currentQuery: rewrite,
        rewrites: state.rewrites.concat([rewrite]),
        correctionAttempts: attempt,
        stages: pushStage(
          state.stages,
          "correct",
          true,
          `attempt ${attempt}`,
        ),
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        status: "error",
        error: msg,
        stages: pushStage(state.stages, "correct", false, msg),
      };
    }
  };
}

/** Docs allowed into the answer context. */
export function docsForGeneration(graded: GradedDoc[]): GradedDoc[] {
  return graded.filter(
    (d) => d.grade === "relevant" || d.grade === "ambiguous",
  );
}

export function makeGenerateNode(deps: GraphDeps) {
  return async (state: CragState): Promise<Partial<CragState>> => {
    if (state.status === "error") return {};

    const usable = docsForGeneration(state.graded);
    if (usable.length === 0) {
      return {
        status: "refused",
        refusal: REFUSAL_MESSAGE,
        answer: null,
        stages: pushStage(state.stages, "refuse", true, "no usable docs"),
      };
    }

    try {
      const answer = await deps.completeChat({
        system: GENERATE_SYSTEM,
        user: generateUserPrompt(state.query, usable),
        temperature: 0.2,
      });
      return {
        status: "answered",
        answer: answer.trim(),
        refusal: null,
        stages: pushStage(state.stages, "generate", true),
      };
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return {
        status: "error",
        error: msg,
        stages: pushStage(state.stages, "generate", false, msg),
      };
    }
  };
}

export function makeRefuseNode() {
  return async (state: CragState): Promise<Partial<CragState>> => {
    return {
      status: "refused",
      answer: null,
      refusal: REFUSAL_MESSAGE,
      stages: pushStage(state.stages, "refuse", true),
    };
  };
}

/** After grade: strong → generate; weak → correct or refuse. */
export function routeAfterGrade(state: CragState): string {
  if (state.status === "error") return "__end__";
  if (state.strength === "strong") return "generate";
  if (state.correctionAttempts >= MAX_CORRECTION_ATTEMPTS) return "refuse";
  return "correct";
}
