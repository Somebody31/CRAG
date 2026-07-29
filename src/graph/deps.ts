// Injectable ports for the graph (real impls by default; mocks in tests).

import { completeChat, type CompleteChatFn } from "../llm.ts";
import { retrieveSimilar, type RetrieveSimilarFn } from "../retrieve.ts";

export type GraphDeps = {
  completeChat: CompleteChatFn;
  retrieveSimilar: RetrieveSimilarFn;
};

export const defaultDeps: GraphDeps = {
  completeChat,
  retrieveSimilar,
};
