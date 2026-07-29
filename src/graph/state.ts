// CRAG graph state shape.

import type {
  GradedDoc,
  QueryStatus,
  RetrievedDoc,
  StageTrace,
} from "../types.ts";
import type { Strength } from "../decide.ts";

export type CragState = {
  /** Original user question (never rewritten). */
  query: string;
  /** Query used for the latest retrieve (starts as query). */
  currentQuery: string;
  rewrites: string[];
  correctionAttempts: number;
  documents: RetrievedDoc[];
  graded: GradedDoc[];
  strength: Strength;
  status: QueryStatus | "running";
  answer: string | null;
  refusal: string | null;
  stages: StageTrace[];
  error: string | null;
};

export function initialState(query: string): CragState {
  return {
    query,
    currentQuery: query,
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
  };
}
