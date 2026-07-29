// Phase 1 CRAG pipeline — start here to see the whole run.
//
//   retrieve → grade → (correct → retrieve → grade)* → generate | refuse
//
// Correction = rewrite the query and re-search LanceDB (no web).
// After 2 weak grades, we refuse instead of guessing.

import { Annotation, END, START, StateGraph } from "@langchain/langgraph";
import { decideStrength, type Strength } from "./decide.ts";
import { completeChat } from "./llm.ts";
import { parseJsonObject } from "./parseJson.ts";
import { retrieveSimilar } from "./retrieve.ts";
import type {
  GradeLabel,
  GradedDoc,
  QueryResponse,
  QueryStatus,
  RetrievedDoc,
  StageTrace,
} from "./types.ts";

export const MAX_CORRECTION_ATTEMPTS = 2;

const REFUSAL_MESSAGE =
  "I don't know based on the available knowledge base documents. The retrieved sources were not strong enough to answer confidently.";

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

export type CragState = {
  query: string;
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

function emptyState(query: string): CragState {
  return {
    query: query,
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

function addStage(
  stages: StageTrace[],
  name: string,
  ok: boolean,
  detail?: string,
): StageTrace[] {
  const next = stages.slice();
  next.push({ name: name, ok: ok, detail: detail });
  return next;
}

function readGrade(value: unknown): GradeLabel {
  if (value === "relevant" || value === "ambiguous" || value === "irrelevant") {
    return value;
  }
  // Safe default when the model returns bad JSON.
  return "ambiguous";
}

/** Keep relevant + ambiguous for the answer; drop irrelevant. */
export function docsForAnswer(graded: GradedDoc[]): GradedDoc[] {
  const out: GradedDoc[] = [];
  for (const doc of graded) {
    if (doc.grade === "relevant" || doc.grade === "ambiguous") {
      out.push(doc);
    }
  }
  return out;
}

/** Where to go after grading. Exported for unit tests. */
export function routeAfterGrade(state: CragState): string {
  if (state.status === "error") return "end";
  if (state.strength === "strong") return "generate";
  if (state.correctionAttempts >= MAX_CORRECTION_ATTEMPTS) return "refuse";
  return "correct";
}

// ---------------------------------------------------------------------------
// Nodes (plain async functions)
// ---------------------------------------------------------------------------

async function retrieveNode(state: CragState): Promise<Partial<CragState>> {
  const queryText = state.currentQuery || state.query;
  const fromCorrection = state.correctionAttempts > 0;

  try {
    const documents = await retrieveSimilar(queryText, {
      k: 6,
      fromCorrection: fromCorrection,
    });
    return {
      documents: documents,
      stages: addStage(
        state.stages,
        "retrieve",
        true,
        documents.length + " docs",
      ),
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      documents: [],
      status: "error",
      error: msg,
      stages: addStage(state.stages, "retrieve", false, msg),
    };
  }
}

async function gradeNode(state: CragState): Promise<Partial<CragState>> {
  if (state.status === "error") return {};

  if (state.documents.length === 0) {
    return {
      graded: [],
      strength: "weak",
      stages: addStage(state.stages, "grade", true, "no docs"),
    };
  }

  try {
    const graded: GradedDoc[] = [];

    for (const doc of state.documents) {
      let body = doc.content;
      if (body.length > 3500) {
        body = body.slice(0, 3500) + "…";
      }

      const raw = await completeChat({
        system: `You grade how well a document supports answering a user question about an internal knowledge base (Northline Pulse).

Return ONLY a JSON object:
{"grade":"relevant"|"ambiguous"|"irrelevant","reason":"one short sentence"}

Rules:
- relevant: document clearly contains facts that answer the question
- ambiguous: related topic but incomplete or only partial support
- irrelevant: wrong topic or no useful support
Do not invent document content.`,
        user:
          "Question: " +
          state.query +
          "\n\nDocument id: " +
          doc.id +
          "\nTitle: " +
          doc.title +
          "\n\nBody:\n" +
          body,
        temperature: 0,
      });

      const parsed = parseJsonObject(raw);
      const grade = readGrade(parsed?.grade);
      let reason = "";
      if (typeof parsed?.reason === "string") {
        reason = parsed.reason;
      }

      graded.push({
        id: doc.id,
        title: doc.title,
        content: doc.content,
        snippet: doc.snippet,
        score: doc.score,
        clusterId: doc.clusterId,
        role: doc.role,
        fromCorrection: doc.fromCorrection,
        grade: grade,
        reason: reason,
      });
    }

    const labels: GradeLabel[] = [];
    for (const g of graded) {
      labels.push(g.grade);
    }
    const strength = decideStrength(labels);

    return {
      graded: graded,
      strength: strength,
      stages: addStage(state.stages, "grade", true, "strength=" + strength),
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      status: "error",
      error: msg,
      stages: addStage(state.stages, "grade", false, msg),
    };
  }
}

async function correctNode(state: CragState): Promise<Partial<CragState>> {
  if (state.status === "error") return {};

  const attempt = state.correctionAttempts + 1;

  try {
    const raw = await completeChat({
      system: `You rewrite a user question to improve dense retrieval over an internal product knowledge base (Northline Pulse).

Return ONLY a JSON object:
{"rewrite":"the rewritten query"}

Rules:
- Keep the same intent
- Expand entities, product names, and concrete constraints
- Prefer keywords useful for search
- Do not answer the question`,
      user:
        "Attempt " +
        attempt +
        " rewrite for retrieval.\n\nOriginal question:\n" +
        state.query,
      temperature: 0.3,
    });

    const parsed = parseJsonObject(raw);
    let rewrite = "";
    if (typeof parsed?.rewrite === "string") {
      rewrite = parsed.rewrite.trim();
    }
    // If JSON failed, still try a simple expanded query.
    if (!rewrite) {
      rewrite = state.query + " Northline Pulse policy details";
    }

    const rewrites = state.rewrites.slice();
    rewrites.push(rewrite);

    return {
      currentQuery: rewrite,
      rewrites: rewrites,
      correctionAttempts: attempt,
      stages: addStage(state.stages, "correct", true, "attempt " + attempt),
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      status: "error",
      error: msg,
      stages: addStage(state.stages, "correct", false, msg),
    };
  }
}

async function generateNode(state: CragState): Promise<Partial<CragState>> {
  if (state.status === "error") return {};

  const usable = docsForAnswer(state.graded);
  if (usable.length === 0) {
    return {
      status: "refused",
      refusal: REFUSAL_MESSAGE,
      answer: null,
      stages: addStage(state.stages, "refuse", true, "no usable docs"),
    };
  }

  try {
    let blocks = "";
    for (let i = 0; i < usable.length; i++) {
      const d = usable[i];
      blocks +=
        "### Source " +
        (i + 1) +
        " (" +
        d.id +
        ") — " +
        d.title +
        " [" +
        d.grade +
        "]\n" +
        d.content +
        "\n\n";
    }

    const answer = await completeChat({
      system: `You answer using ONLY the provided source documents from the Northline Pulse knowledge base.

Rules:
- Ground every factual claim in the sources
- If sources conflict, prefer canonical / more recent wording and say there is conflict
- Be concise and clear
- Do not invent APIs, limits, or policies not in the sources`,
      user: "Question: " + state.query + "\n\nSources:\n" + blocks + "Write the answer.",
      temperature: 0.2,
    });

    return {
      status: "answered",
      answer: answer.trim(),
      refusal: null,
      stages: addStage(state.stages, "generate", true),
    };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return {
      status: "error",
      error: msg,
      stages: addStage(state.stages, "generate", false, msg),
    };
  }
}

async function refuseNode(state: CragState): Promise<Partial<CragState>> {
  return {
    status: "refused",
    answer: null,
    refusal: REFUSAL_MESSAGE,
    stages: addStage(state.stages, "refuse", true),
  };
}

// ---------------------------------------------------------------------------
// Graph + public entry
// ---------------------------------------------------------------------------

function buildGraph() {
  return new StateGraph(GraphState)
    .addNode("retrieve", retrieveNode)
    .addNode("grade", gradeNode)
    .addNode("correct", correctNode)
    .addNode("generate", generateNode)
    .addNode("refuse", refuseNode)
    .addEdge(START, "retrieve")
    .addEdge("retrieve", "grade")
    .addConditionalEdges("grade", routeAfterGrade, {
      generate: "generate",
      correct: "correct",
      refuse: "refuse",
      end: END,
    })
    .addEdge("correct", "retrieve")
    .addEdge("generate", END)
    .addEdge("refuse", END)
    .compile();
}

/** Run Phase 1 CRAG for one query. */
export async function runCrag(query: string): Promise<QueryResponse> {
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

  const graph = buildGraph();
  const final = (await graph.invoke(emptyState(trimmed))) as CragState;

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

  const sourceDocs = final.graded.length > 0 ? final.graded : [];
  const documents: QueryResponse["documents"] = [];
  for (const d of sourceDocs) {
    documents.push({
      id: d.id,
      title: d.title,
      snippet: d.snippet,
      grade: d.grade,
      fromCorrection: d.fromCorrection,
    });
  }

  return {
    status: status,
    query: final.query,
    rewrites: final.rewrites,
    correctionAttempts: final.correctionAttempts,
    documents: documents,
    answer: final.answer,
    refusal: final.refusal,
    stages: final.stages,
    error: final.error ?? undefined,
  };
}
