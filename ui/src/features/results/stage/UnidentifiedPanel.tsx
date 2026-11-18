/**
 * A molecule BioID could not identify (2026-11-17): what BioID does know,
 * the closest candidates it rejected, and two ways on: run again with the
 * Deep search preset, or tell us what it is.
 */
import { Button } from "@e-infra/design-system";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, apiErrorMessage, endpoints } from "../../../lib/api/client";
import { ownerHeaders, rememberOwnerToken } from "../../../lib/ownerTokens";
import type { Molecule } from "../viewmodel";
import { formulaMass } from "./chemistry";
import { ReportDialog } from "./ReportDialog";

const CLOSEST = 3;

export function UnidentifiedPanel({ molecule: m }: { molecule: Molecule }) {
  const { runId = "" } = useParams();
  const [busy, setBusy] = useState(false);
  const d = m.descriptor;
  const mass = formulaMass(d.formula);
  const facts: [string, string][] = [];
  if (d.formula) facts.push(["Formula", d.formula]);
  if (mass != null) facts.push(["Mass", `${mass.toFixed(2)} g/mol (average)`]);
  if (d.sequence) facts.push(["Sequence", `${d.sequence.length} residues`]);
  if (d.inchikey) facts.push(["InChIKey", d.inchikey]);
  const closest = (m.rejected ?? []).slice(0, CLOSEST);

  const rerunDeep = () => {
    setBusy(true);
    void api
      .postJson<{ run_id: string; owner_token?: string | null }>(endpoints.runRerun(runId), { preset: "deep" }, ownerHeaders(runId))
      .then((res) => {
        rememberOwnerToken(res.run_id, res.owner_token);
        toast.success("Queued with Deep search");
        window.location.assign(`/runs/${res.run_id}`);
      })
      .catch((err) => {
        toast.error(apiErrorMessage(err, "Could not start the run"));
        setBusy(false);
      });
  };

  return (
    <div className="mb-4 space-y-3">
      {(facts.length > 0 || d.smiles) && (
        <div className="rounded-md bg-(--vm-surface-2) p-3 text-sm">
          <h3 className="font-semibold">What BioID knows about it</h3>
          <dl className="mt-1 grid grid-cols-[max-content_1fr] gap-x-3 gap-y-0.5">
            {facts.map(([k, v]) => (
              <div key={k} className="contents">
                <dt className="text-(--vm-muted)">{k}</dt>
                <dd className="font-mono break-all">{v}</dd>
              </div>
            ))}
            {d.smiles && (
              <div className="contents">
                <dt className="text-(--vm-muted)">SMILES</dt>
                <dd className="font-mono break-all">
                  {d.smiles.length > 160 ? `${d.smiles.slice(0, 160)}…` : d.smiles}{" "}
                  <button type="button" className="text-(--vm-accent) hover:underline"
                          onClick={() => void navigator.clipboard?.writeText(d.smiles ?? "").then(() => toast.success("SMILES copied"))}>
                    copy
                  </button>
                </dd>
              </div>
            )}
          </dl>
        </div>
      )}
      {closest.length > 0 && (
        <div className="text-sm">
          <h3 className="font-semibold">Closest candidates (rejected)</h3>
          <ul className="mt-1 space-y-0.5">
            {closest.map((r) => (
              <li key={`${r.db}-${r.id}`}>
                <span className="font-medium">{r.db} {r.id}</span>
                {r.what && <span className="text-(--vm-fg-2)"> · {r.what}</span>}
                <span className="text-(--vm-muted)"> · {r.clause}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="outline" disabled={busy} onClick={rerunDeep}>Run again with Deep search</Button>
        <ReportDialog segment={m.id} moleculeName={m.display_name} identified={false}
                      trigger={<Button size="sm" variant="outline">Tell us what this is</Button>} />
      </div>
    </div>
  );
}
