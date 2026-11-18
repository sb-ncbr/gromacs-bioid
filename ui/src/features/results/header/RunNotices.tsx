/**
 * Failed lookups a rerun could fix (with "Re-run failed lookups"), a waiting
 * automatic retry, and links between a run and its reruns (2026-11-18).
 */
import { Button, cn } from "@e-infra/design-system";
import { Link } from "react-router-dom";
import { runNotices } from "./runNotices";
import type { components } from "../../../lib/api/types";

type Status = components["schemas"]["RunStatusResponse"];

function Box({ tone, children }: { tone: "info" | "attention"; children: React.ReactNode }) {
  return (
    <div role="status" className={cn(
      "mb-3 rounded-md border px-3 py-2 text-sm",
      tone === "attention"
        ? "border-(--vm-attention-line) bg-(--vm-attention-bg) text-(--vm-fg)"
        : "border-(--vm-info-line) bg-(--vm-info-bg) text-(--vm-fg)",
    )}>
      {children}
    </div>
  );
}

export function RunNotices({ status, nowMs, onRerun }: {
  status: Status | null | undefined;
  nowMs: number;
  onRerun: () => void;
}) {
  const n = runNotices(status, nowMs);
  const linkCls = "font-medium text-(--vm-accent) underline-offset-2 hover:underline";
  return (
    <>
      {n.supersededBy && (
        <Box tone="info">
          This run was re-run by its owner.{" "}
          <Link to={`/runs/${n.supersededBy}`} className={linkCls}>See the newer results</Link>
        </Box>
      )}
      {n.retry && <Box tone="info">{n.retry}</Box>}
      {n.incomplete.length > 0 && !n.supersededBy && (
        <Box tone="attention">
          <p className="font-medium">Some database lookups failed for reasons a rerun can fix:</p>
          <ul className="my-1 list-disc pl-5">
            {n.incomplete.map((line) => <li key={line}>{line}</li>)}
          </ul>
          <p className="text-(--vm-muted)">
            Matches only these databases would have found may be missing. A rerun repeats only these lookups;
            the others are answered from the cache.
          </p>
          <Button variant="outline" size="sm" className="mt-2" onClick={onRerun}>Re-run failed lookups</Button>
        </Box>
      )}
      {(n.rerunOf || n.attempts) && (
        <p className="mb-3 text-xs text-(--vm-muted)">
          {n.rerunOf && (
            <>Re-run of <Link to={`/runs/${n.rerunOf}`} className={linkCls}>{n.rerunOf.slice(0, 8)}</Link>. </>
          )}
          {n.attempts}
        </p>
      )}
    </>
  );
}
