import { describe, expect, it } from "vitest";

import { formatMetric, healthTone } from "./format";

describe("formatMetric", () => {
  it("formats numbers and empty values", () => {
    expect(formatMetric(7.456)).toBe("7.46");
    expect(formatMetric(12, 0)).toBe("12");
    expect(formatMetric(null)).toBe("—");
  });
});

describe("healthTone", () => {
  it("maps healthy status to emerald classes", () => {
    expect(healthTone("healthy")).toContain("emerald");
  });
});
