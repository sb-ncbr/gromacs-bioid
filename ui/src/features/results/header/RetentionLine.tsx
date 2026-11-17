/**
 * When the run will be deleted, with "keep longer" for its owner
 * (2026-11-17). Hidden until the run has finished.
 */
import { Button, cn } from "@e-infra/design-system";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";
import { api, apiErrorMessage, endpoints } from "../../../lib/api/client";
import { ownerHeaders } from "../../../lib/ownerTokens";
import { formatDate, retentionView, type RetentionInfo } from "./retentionModel";

export function RetentionLine({ runId, retention }: { runId: string; retention: RetentionInfo | null | undefined }) {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const view = retentionView(retention);
  if (!view) return null;
  const owner = ownerHeaders(runId);

  const keep = (days: number) => {
    setBusy(true);
    void api
      .postJson<RetentionInfo>(endpoints.runRetention(runId), { days }, owner)
      .then((r) => {
        toast.success(r.expires_at ? `Kept until ${formatDate(r.expires_at)}` : "Kept");
        void queryClient.invalidateQueries({ queryKey: ["runStatus", runId] });
      })
      .catch((err) => toast.error(apiErrorMessage(err, "Could not keep the run longer")))
      .finally(() => setBusy(false));
  };

  return (
    <div className={cn("mb-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm",
                       view.soon ? "text-(--vm-attention)" : "text-(--vm-muted)")}>
      <span className={view.soon ? "font-medium" : undefined}>{view.text}</span>
      {owner && view.choices.length > 0 && (
        <span className="flex flex-wrap items-center gap-1.5">
          <span>Keep for</span>
          {view.choices.map((d) => (
            <Button key={d} variant="outline" size="sm" disabled={busy} onClick={() => keep(d)}>
              {d === 365 ? "1 year" : `${d} days`}
            </Button>
          ))}
          <span>from today</span>
        </span>
      )}
    </div>
  );
}
