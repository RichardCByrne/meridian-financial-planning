import { describe, it, expect } from "vitest";
import { fmtMoney, fmtPct, fmtPctDisplay } from "./format";

describe("fmtMoney", () => {
  it("formats whole euros with no decimals", () => {
    // Non-breaking space / narrow spaces vary by ICU build, so assert on the
    // meaningful parts rather than the exact separator bytes.
    const out = fmtMoney(1234);
    expect(out).toContain("€");
    expect(out).toContain("1,234");
    expect(out).not.toContain(".");
  });

  it("rounds to the nearest euro", () => {
    expect(fmtMoney(1234.6)).toContain("1,235");
  });

  it("handles negatives", () => {
    expect(fmtMoney(-500)).toContain("500");
    expect(fmtMoney(-500)).toMatch(/-|\(/); // minus sign or accounting parens
  });

  it("formats zero", () => {
    expect(fmtMoney(0)).toContain("0");
  });
});

describe("fmtPct", () => {
  it("formats a fraction as a percentage", () => {
    expect(fmtPct(0.025)).toContain("2.5");
    expect(fmtPct(0.025)).toContain("%");
  });
});

describe("fmtPctDisplay", () => {
  it("strips trailing zeros", () => {
    expect(fmtPctDisplay(0.03)).toBe("3%");
    expect(fmtPctDisplay(0.025)).toBe("2.5%");
    expect(fmtPctDisplay(0.125)).toBe("12.5%");
  });

  it("removes float noise", () => {
    // 0.07 * 100 = 7.000000000000001 in IEEE754; toPrecision(6) cleans it.
    expect(fmtPctDisplay(0.07)).toBe("7%");
  });

  it("handles zero", () => {
    expect(fmtPctDisplay(0)).toBe("0%");
  });
});
