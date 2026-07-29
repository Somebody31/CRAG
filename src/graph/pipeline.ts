// Phase 1 CRAG graph: retrieve → grade → (correct → retrieve → grade)* → generate | refuse

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import type { Strength } from "../decide.ts";
import type {
  GradedDoc,
  QueryResponse,
  QueryStatus,
  RetrievedDoc,
  StageTrace,
} from "../types.ts";
import { defaultDeps, type GraphDeps } from "./deps.ts";
import {
  makeCorrectNode,
  makeGenerateNode,
  makeGradeNode,
  makeRefuseNode,
  makeRetrieveNode,
  routeAfterGrade,
} from "./nodes.ts";
import { initialState, type CragState } from "./state.ts";

const GraphState = Annotation.Root({
  query: Annotation<string>(),
  currentQuery: Annotation<string>(),
  rewrites: Annotation<string[]>({ default: () => [] }),
  correctionAttempts: Annotation<number>({ default: () => 0 }),
  documents: Annotation<RetrievedDoc[]>({ default: () => [] }),
  graded: Annotation<GradedDoc[]>({ default: () => [] }),
  strength: Annotation<Strength>({ default: () => "weak" }),
  status: Annotation<QueryStatus | "running">({ default: () => "running" }),
  answer: Annotation<string | null>({ default: () => null }),
  refusal: Annotation<string | null>({ default: () => null }),
  stages: Annotation<StageTrace[]>({ default: () => [] }),
  error: Annotation<string | null>({ default: () => null }),
});

export function buildGraph(deps: GraphDeps) {
  const retrieve = makeRetrieveNode(deps);
  const grade = makeGradeNode(deps);
  const correct = makeCorrectNode(deps);
  const generate = makeGenerateNode(deps);
  const refuse = makeRefuseNode();

  return new StateGraph(GraphState)
    .addNode("retrieve", retrieve)
    .addNode("grade", grade)
    .addNode("correct", correct)
    .addNode("generate", generate)
    .addNode("refuse", refuse)
    .addEdge(START, "retrieve")
    .addEdge("retrieve", "grade")
    .addConditionalEdges("grade", routeAfterGrade, {
      generate: "generate",
      correct: "correct",
      refuse: "refuse",
      __end__: END,
    })
    .addEdge("correct", "retrieve")
    .addEdge("generate", END)
    .addEdge("refuse", END)
    .compile();
}

/** Run Phase 1 CRAG for one query. */
export async function runCrag(
  query: string,
  deps: GraphDeps = defaultDeps,
): Promise<QueryResponse> {
  const trimmed = query.trim();
  if (!trimmed) {
    return {
      status: "error",
      query: "",
      rewrites: [],
      correctionAttempts: 0,
      documents: [],
      answer: null,
      refusal: null,
      stages: [],
      error: "query is empty",
    };
  }

  const graph = buildGraph(deps);
  const seed = initialState(trimmed);
  const final = (await graph.invoke(seed)) as CragState;

  let status: QueryStatus = "error";
  if (final.status === "answered" || final.status === "refused") {
    status = final.status;
  } else if (final.status === "error") {
    status = "error";
  } else if (final.answer) {
    status = "answered";
  } else if (final.refusal) {
    status = "refused";
  }

  return {
    status,
    query: final.query,
    rewrites: final.rewrites ?? [],
    correctionAttempts: final.correctionAttempts ?? 0,
    documents: (final.graded?.length ? final.graded : final.documents).map(
      (d) => ({
        id: d.id,
        title: d.title,
        snippet: d.snippet,
        grade: "grade" in d && d.grade ? d.grade : ("ambiguous" as const),
        fromCorrection: d.fromCorrection,
      }),
    ),
    answer: final.answer,
    refusal: final.refusal,
    stages: final.stages ?? [],
    error: final.error ?? undefined,
  };
}

export { MAX_CORRECTION_ATTEMPTS } from "./nodes.ts";
