// Call local Qwen3-Embedding-0.6B HTTP server (OpenAI-compatible /v1/embeddings).

function embedBaseUrl(): string {
  return (
    process.env.EMBED_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8090"
  );
}

/**
 * Embed one or more texts. Returns vectors in the same order as inputs.
 * Server must expose POST /v1/embeddings with body { model, input }.
 */
export async function embedTexts(texts: string[]): Promise<number[][]> {
  if (texts.length === 0) return [];

  const res = await fetch(`${embedBaseUrl()}/v1/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: process.env.EMBED_MODEL || "Qwen/Qwen3-Embedding-0.6B",
      input: texts,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `Embed server error ${res.status}: ${body.slice(0, 400)}. Is the embed server running on ${embedBaseUrl()}?`,
    );
  }

  const data = (await res.json()) as {
    data?: Array<{ embedding?: number[]; index?: number }>;
  };

  const rows = data.data;
  if (!Array.isArray(rows) || rows.length !== texts.length) {
    throw new Error(
      `Embed server returned ${rows?.length ?? 0} vectors for ${texts.length} texts`,
    );
  }

  // OpenAI-style responses may be unsorted; order by index.
  const sorted = [...rows].sort(
    (a, b) => (a.index ?? 0) - (b.index ?? 0),
  );

  return sorted.map((row, i) => {
    const vec = row.embedding;
    if (!Array.isArray(vec) || vec.length === 0) {
      throw new Error(`Embed server missing embedding for index ${i}`);
    }
    return vec;
  });
}

/** Single-text helper. */
export async function embedText(text: string): Promise<number[]> {
  const [vec] = await embedTexts([text]);
  return vec;
}

export type EmbedTextsFn = typeof embedTexts;
