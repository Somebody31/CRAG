// Shared Phase 1 types — plain shapes only.

export type GradeLabel = "relevant" | "ambiguous" | "irrelevant";

export type DocGrade = {
  id: string;
  title: string;
  grade: GradeLabel;
  reason: string;
};

export type RetrievedDoc = {
  id: string;
  title: string;
  content: string;
  snippet: string;
  /** Cosine distance or score from LanceDB when available. */
  score: number | null;
  clusterId: string | null;
  role: string | null;
  fromCorrection: boolean;
};

export type GradedDoc = RetrievedDoc & {
  grade: GradeLabel;
  reason: string;
};

export type StageName =
  | "retrieve"
  | "grade"
  | "correct"
  | "generate"
  | "refuse";

export type StageTrace = {
  name: StageName;
  ok: boolean;
  detail?: string;
};

export type QueryStatus = "answered" | "refused" | "error";

/** API response for POST /api/query */
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

export type CorpusDoc = {
  id: string;
  cluster_id: string | null;
  role: string;
  title: string;
  content: string;
  date: string;
  validation_note: string | null;
  contradiction_id: string | null;
  version_chain_id: string | null;
  version_number: number | null;
  fragment_group_id: string | null;
};
