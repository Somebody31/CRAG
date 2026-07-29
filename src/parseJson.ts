// Pull JSON out of messy LLM text (markdown fences, leading prose).

export type JsonObject = {
  [key: string]: unknown;
};

/** First {...} object in text, or null. */
export function parseJsonObject(text: string): JsonObject | null {
  const start = text.indexOf("{");
  const end = text.lastIndexOf("}");
  if (start === -1 || end === -1 || end <= start) return null;

  try {
    const value = JSON.parse(text.slice(start, end + 1)) as unknown;
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      return null;
    }
    return value as JsonObject;
  } catch {
    return null;
  }
}

/** First [...] array in text, or null. */
export function parseJsonArray(text: string): unknown[] | null {
  const start = text.indexOf("[");
  const end = text.lastIndexOf("]");
  if (start === -1 || end === -1 || end <= start) return null;

  try {
    const value = JSON.parse(text.slice(start, end + 1)) as unknown;
    if (!Array.isArray(value)) return null;
    return value;
  } catch {
    return null;
  }
}
