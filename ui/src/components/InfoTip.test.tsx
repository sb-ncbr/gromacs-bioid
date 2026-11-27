/** InfoTip: a named button that opens its text and documentation link. */
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { InfoTip } from "./InfoTip";

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let host: HTMLDivElement | null = null;

afterEach(() => {
  host?.remove();
  host = null;
  document.body.innerHTML = "";
});

function render(ui: React.ReactElement) {
  host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(ui));
  return root;
}

describe("InfoTip", () => {
  it("is a keyboard-reachable button named after its topic", () => {
    render(<InfoTip topic="confidence" />);
    const button = document.querySelector("button");
    expect(button?.getAttribute("type")).toBe("button");
    expect(button?.getAttribute("aria-label")).toBe("About Confidence");
  });

  it("opens with the explanation and a documentation link", () => {
    render(<InfoTip topic="confidence" />);
    const button = document.querySelector("button")!;
    act(() => button.click());
    expect(button.getAttribute("aria-expanded")).toBe("true");
    expect(document.body.textContent).toContain("How sure BioID is");
    const link = document.querySelector<HTMLAnchorElement>('a[href="/documentation/#confidence"]');
    expect(link?.target).toBe("_blank");
    expect(link?.textContent).toContain("opens in a new tab");
  });

  it("takes an entry of its own", () => {
    render(<InfoTip entry={{ title: "Guess bonds", body: "Bonds from distances." }} />);
    expect(document.querySelector("button")?.getAttribute("aria-label")).toBe("About Guess bonds");
  });
});
