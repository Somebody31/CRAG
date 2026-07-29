// Pull a JSON object out of messy LLM text (markdown, leading prose).

export type JsonObject = {
  [key: string]: unknown;
};

/** First {...} in the text, or null if parse fails. */
export function parseJsonObject(text: string): JsonObject | null {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) return null;

  try {
    const value = JSON.parse(text.slice(start, end + 1)) as unknown;
    if (value === null) return null;
    if (typeof value !== "object") return null;
    if (Array.isArray(value)) return null;
    return value as JsonObject;
  } catch {
    return null;
  }
}
