import { describe, expect, it } from "vitest";
import { formulaMass } from "./chemistry";

describe("formulaMass", () => {
  it("adds standard atomic weights", () => {
    expect(formulaMass("C6H12O6")).toBeCloseTo(180.156, 2);
    expect(formulaMass("C42H82NO8P")).toBeCloseTo(760.09, 1); // POPC
    expect(formulaMass("NaCl")).toBeCloseTo(58.44, 2);
    expect(formulaMass("Cl-")).toBeCloseTo(35.45, 2);
  });
  it("gives up on what it cannot read", () => {
    expect(formulaMass("C6H12Xx")).toBeNull();
    expect(formulaMass("c6h6")).toBeNull();
    expect(formulaMass("")).toBeNull();
    expect(formulaMass(undefined)).toBeNull();
  });
});
