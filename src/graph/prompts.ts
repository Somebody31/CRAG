// Prompt strings for grade / rewrite / generate.

import type { GradedDoc, RetrievedDoc } from "../types.ts";

export const GRADE_SYSTEM = `You grade how well a document supports answering a user question about an internal knowledge base (Northline Pulse).

Return ONLY a JSON object:
{"grade":"relevant"|"ambiguous"|"irrelevant","reason":"one short sentence"}

Rules:
- relevant: document clearly contains facts that answer (or substantially answer) the question
- ambiguous: related topic but incomplete / outdated / only partial support
- irrelevant: wrong topic or no useful support
Do not invent document content.`;

export function gradeUserPrompt(query: string, doc: RetrievedDoc): string {
  const body = doc.content.length > 3500 ? doc.content.slice(0, 3500) + "…" : doc.content;
  return `Question: ${query}

Document id: ${doc.id}
Title: ${doc.title}

Body:
${body}`;
}

export const REWRITE_SYSTEM = `You rewrite a user question to improve dense retrieval over an internal product knowledge base (Northline Pulse).

Return ONLY a JSON object:
{"rewrite":"the rewritten query"}

Rules:
- Keep the same intent
- Expand entities, product names, and concrete constraints
- Prefer keywords and short phrases useful for search
- Do not answer the question`;

export function rewriteUserPrompt(query: string, attempt: number): string {
  return `Attempt ${attempt} rewrite for retrieval.

Original question:
${query}`;
}

export const GENERATE_SYSTEM = `You answer using ONLY the provided source documents from the Northline Pulse knowledge base.

Rules:
- Ground every factual claim in the sources
- If sources conflict, prefer canonical / more recent wording and say there is conflict
- Be concise and clear
- Do not invent APIs, limits, or policies not in the sources
- Use plain language; short paragraphs OK`;

export function generateUserPrompt(
  query: string,
  docs: GradedDoc[],
): string {
  const blocks = docs
    .map(
      (d, i) =>
        `### Source ${i + 1} (${d.id}) — ${d.title} [${d.grade}]\n${d.content}`,
    )
    .join("\n\n");

  return `Question: ${query}

Sources:
${blocks}

Write the answer.`;
}

export const REFUSAL_MESSAGE =
  "I don't know based on the available knowledge base documents. The retrieved sources were not strong enough to answer confidently.";
