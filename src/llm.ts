// MiMo V2.5 chat via OpenAI-compatible HTTP. Graph code calls completeChat only.

export type ChatMessage = {
  role: "system" | "user" | "assistant";
  content: string;
};

export type CompleteChatOptions = {
  system: string;
  user: string;
  /** Optional temperature (default 0.2 for grading/gen). */
  temperature?: number;
};

function mimoBaseUrl(): string {
  return (
    process.env.MIMO_BASE_URL?.replace(/\/$/, "") ||
    "https://api.xiaomimimo.com/v1"
  );
}

function mimoModel(): string {
  return process.env.MIMO_MODEL || "mimo-v2.5-pro";
}

/**
 * Ask MiMo and return assistant text.
 * Throws if MIMO_API_KEY is missing or the HTTP call fails.
 */
export async function completeChat(
  options: CompleteChatOptions,
): Promise<string> {
  const apiKey = process.env.MIMO_API_KEY;
  if (!apiKey) {
    throw new Error("MIMO_API_KEY is missing (set it in .env)");
  }

  const messages: ChatMessage[] = [
    { role: "system", content: options.system.trim() },
    { role: "user", content: options.user },
  ];

  const res = await fetch(`${mimoBaseUrl()}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: mimoModel(),
      messages,
      temperature: options.temperature ?? 0.2,
    }),
  });

  if (!res.ok) {
    const body = await res.text();
    throw new Error(`MiMo API error ${res.status}: ${body.slice(0, 500)}`);
  }

  const data = (await res.json()) as {
    choices?: { message?: { content?: string } }[];
  };

  const text = data.choices?.[0]?.message?.content;
  if (typeof text !== "string" || text.trim() === "") {
    throw new Error("MiMo API returned empty content");
  }
  return text;
}

/** Injectable chat function type for tests. */
export type CompleteChatFn = typeof completeChat;
