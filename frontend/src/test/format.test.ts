import { describe, expect, it } from "vitest";
import { ago, pct, title } from "../utils/format";
import { qs } from "../services/api";

describe("format utils", () => {
  it("formats probabilities and handles null", () => { expect(pct(0.1234)).toBe("12.3%"); expect(pct(null)).toBe("—"); expect(pct(0.5, 0)).toBe("50%"); });
  it("humanises snake_case", () => { expect(title("equipment_failure")).toBe("Equipment failure"); expect(title(undefined)).toBe("—"); });
  it("computes relative time", () => { expect(ago(new Date(Date.now() - 5 * 60000).toISOString())).toBe("5m ago"); });
  it("builds query strings skipping empty values", () => { expect(qs({ a: 1, b: "", c: undefined, d: "x y" })).toBe("?a=1&d=x+y"); expect(qs({})).toBe(""); });
});
