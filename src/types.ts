// Plain shared shapes for Phase 1.

export type GradeLabel = "relevant" | "ambiguous" | "irrelevant";

export type RetrievedDoc = {
  id: string;
  title: string;
  content: string;
  snippet: string;
  score: number | null;
  clusterId: string | null;
  role: string | null;
  fromCorrection: boolean;
};

export type GradedDoc = {
  id: string;
  title: string;
  content: string;
  snippet: string;
  score: number | null;
  clusterId: string | null;
  role: string | null;
  fromCorrection: boolean;
  grade: GradeLabel;
  reason: string;
};

export type StageTrace = {
  name: string;
  ok: boolean;
  detail?: string;
};

export type QueryStatus = "answered" | "refused" | "error";

export type QueryResponse = {
  status: QueryStatus;
  query: string;
  rewrites: string[];
  correctionAttempts: number;
  documents: Array<{
    id: string;
    title: string;
    snippet: string;
    grade: GradeLabel;
    fromCorrection: boolean;
  }>;
  answer: string | null;
  refusal: string | null;
  stages: StageTrace[];
  error?: string;
};
