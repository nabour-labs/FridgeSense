import { describe, expect, it } from "vitest";
import { synthTemplate } from "./helpers.js";

describe("FridgeSenseStack", () => {
  it("synthesizes", () => {
    expect(synthTemplate().toJSON()).toBeTypeOf("object");
  });
});
