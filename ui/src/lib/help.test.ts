/**
 * Every info button links to a documentation section that exists: the
 * anchors are read from the Markdown sources (explicit `{#id}` or the
 * mkdocs/python-markdown heading slug), so a renamed heading fails here.
 */
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { CONFIG_SECTION_DOCS, DATABASE_GROUP_DOCS, HELP, docsHref } from "./help";

const DOCS = resolve(__dirname, "../../../docs/site/docs");

/** python-markdown toc slugify (mkdocs default), after markup is stripped. */
function slugify(text: string): string {
  return text
    .replace(/`/g, "")
    .normalize("NFKD")
    .replace(/[\u0080-\uffff]/g, "") // non-ASCII dropped, as python-markdown does
    .replace(/[^\w\s-]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[-\s]+/g, "-");
}

function anchors(page: string): Set<string> {
  const out = new Set<string>();
  for (const line of readFileSync(resolve(DOCS, page), "utf8").split("\n")) {
    const m = /^#{1,6}\s+(.*?)\s*$/.exec(line);
    if (!m) continue;
    const explicit = /\{#([\w-]+)\}\s*$/.exec(m[1]);
    out.add(explicit ? explicit[1] : slugify(m[1]));
  }
  return out;
}

const ALL_LINKS = [
  ...Object.entries(HELP).map(([k, h]) => [k, (h as { docs?: string }).docs] as const),
  ...Object.entries(CONFIG_SECTION_DOCS),
  ...Object.entries(DATABASE_GROUP_DOCS),
].filter((e): e is readonly [string, string] => Boolean(e[1]));

describe("info-button documentation links", () => {
  it.each(ALL_LINKS)("%s -> %s exists", (_key, docs) => {
    const [page, anchor] = docs.split("#");
    expect(anchors(page)).toContain(anchor);
  });

  it("slugifies like mkdocs", () => {
    expect(slugify("Stage 3 — verification")).toBe("stage-3-verification");
    expect(slugify("`[pdb]` — RCSB structure search")).toBe("pdb-rcsb-structure-search");
    expect(slugify("`data.verification` — the identifications")).toBe("dataverification-the-identifications");
  });

  it("builds served URLs", () => {
    expect(docsHref("index.md#confidence")).toBe("/documentation/#confidence");
    expect(docsHref("identifiers.md#hit-types")).toBe("/documentation/identifiers/#hit-types");
  });

  it("keeps every text short enough for a bubble", () => {
    for (const h of Object.values(HELP)) expect(h.body.length).toBeLessThanOrEqual(320);
  });
});
