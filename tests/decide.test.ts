import { describe, expect, test } from "bun:test";
import { decideStrength } from "../src/decide.ts";

describe("decideStrength", () => {
  test("empty is weak", () => {
    expect(decideStrength([])).toBe("weak");
  });

  test("one relevant and no irrelevant is strong", () => {
    expect(decideStrength(["relevant", "ambiguous"])).toBe("strong");
  });

  test("one relevant plus irrelevant is weak unless two relevant", () => {
    expect(decideStrength(["relevant", "irrelevant"])).toBe("weak");
    expect(decideStrength(["relevant", "relevant", "irrelevant"])).toBe(
      "strong",
    );
  });

  test("all ambiguous is weak", () => {
    expect(decideStrength(["ambiguous", "ambiguous"])).toBe("weak");
  });

  test("all irrelevant is weak", () => {
    expect(decideStrength(["irrelevant"])).toBe("weak");
  });
});
