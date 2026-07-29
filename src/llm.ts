// Call MiMo V2.5 (OpenAI-compatible HTTP).

export type CompleteChatOptions = {
  system: string;
  user: string;
  temperature?: number;
};

/** Ask MiMo and return the assistant text. Needs MIMO_API_KEY in .env. */
export async function completeChat(
  options: CompleteChatOptions,
): Promise<string> {
  const apiKey = process.env.MIMO_API_KEY;
  if (!apiKey) {
    throw new Error("MIMO_API_KEY is missing (set it in .env)");
  }

  const baseUrl =
    process.env.MIMO_BASE_URL?.replace(/\/$/, "") ||
    "https://api.xiaomimimo.com/v1";
  const model = process.env.MIMO_MODEL || "mimo-v2.5-pro";

  const res = await fetch(`${baseUrl}/chat/completions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${apiKey}`,
    },
    body: JSON.stringify({
      model: model,
      messages: [
        { role: "system", content: options.system.trim() },
        { role: "user", content: options.user },
      ],
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
