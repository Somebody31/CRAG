// Call DeepSeek V4 Flash (OpenAI-compatible HTTP). Needs DEEPSEEK_API_KEY in .env.

export type CompleteChatOptions = {
  system: string;
  user: string;
  temperature?: number;
};

/** Ask DeepSeek and return the assistant text. */
export async function completeChat(
  options: CompleteChatOptions,
): Promise<string> {
  const apiKey = process.env.DEEPSEEK_API_KEY;
  if (!apiKey) {
    throw new Error("DEEPSEEK_API_KEY is missing (set it in .env)");
  }

  const baseUrl =
    process.env.DEEPSEEK_BASE_URL?.replace(/\/$/, "") ||
    "https://api.deepseek.com";
  const model = process.env.DEEPSEEK_MODEL || "deepseek-v4-flash";

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
    throw new Error(`DeepSeek API error ${res.status}: ${body.slice(0, 500)}`);
  }

  const data = (await res.json()) as {
    choices?: { message?: { content?: string } }[];
  };

  const text = data.choices?.[0]?.message?.content;
  if (typeof text !== "string" || text.trim() === "") {
    throw new Error("DeepSeek API returned empty content");
  }
  return text;
}
