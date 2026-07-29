// Call the local Qwen3 embedding HTTP server (OpenAI-style /v1/embeddings).

/** Embed texts; returns one vector per input, same order. */
export async function embedTexts(texts: string[]): Promise<number[][]> {
  if (texts.length === 0) return [];

  const baseUrl =
    process.env.EMBED_BASE_URL?.replace(/\/$/, "") || "http://127.0.0.1:8090";
  const model = process.env.EMBED_MODEL || "Qwen/Qwen3-Embedding-0.6B";

  const res = await fetch(`${baseUrl}/v1/embeddings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model: model, input: texts }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(
      `Embed server error ${res.status}: ${body.slice(0, 400)}. Is it running on ${baseUrl}?`,
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

  // Responses may arrive out of order — sort by index.
  const sorted = rows.slice().sort((a, b) => {
    const ai = a.index ?? 0;
    const bi = b.index ?? 0;
    return ai - bi;
  });

  const vectors: number[][] = [];
  for (let i = 0; i < sorted.length; i++) {
    const vec = sorted[i].embedding;
    if (!Array.isArray(vec) || vec.length === 0) {
      throw new Error(`Embed server missing embedding for index ${i}`);
    }
    vectors.push(vec);
  }
  return vectors;
}

export async function embedText(text: string): Promise<number[]> {
  const vectors = await embedTexts([text]);
  return vectors[0];
}
