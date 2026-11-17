/**
 * "This identification looks wrong" / "Tell us what this is" (2026-11-17):
 * POST /runs/{id}/reports with the molecule's segment, a note and what the
 * reporter thinks it is. Reviewed by the BioID team on the admin page.
 */
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Input,
  Label,
  Textarea,
} from "@e-infra/design-system";
import { useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";
import { toast } from "sonner";
import { api, apiErrorMessage, endpoints } from "../../../lib/api/client";

export function ReportDialog({ segment, moleculeName, identified, trigger }: {
  segment: string;
  moleculeName: string;
  identified: boolean;
  trigger: ReactNode;
}) {
  const { runId = "" } = useParams();
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [suggestion, setSuggestion] = useState("");
  const [busy, setBusy] = useState(false);

  const send = () => {
    setBusy(true);
    void api
      .postJson<{ message: string }>(endpoints.runReports(runId), { segment, note, suggestion })
      .then((r) => {
        toast.success(r.message || "Thank you");
        setOpen(false);
        setNote("");
        setSuggestion("");
      })
      .catch((err) => toast.error(apiErrorMessage(err, "Could not send the report")))
      .finally(() => setBusy(false));
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{identified ? "This identification looks wrong" : "Tell us what this is"}</DialogTitle>
          <DialogDescription>
            {moleculeName}. The BioID team reads every report; correct answers become test cases that BioID is
            checked against every night.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1">
            <Label htmlFor="report-suggestion">What is it? (optional)</Label>
            <Input id="report-suggestion" maxLength={200} value={suggestion}
                   placeholder="e.g. POPC, UniProt P00766, PubChem 2244"
                   onChange={(e) => setSuggestion(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="report-note">{identified ? "What looks wrong? (optional)" : "Anything else? (optional)"}</Label>
            <Textarea id="report-note" maxLength={2000} rows={4} value={note}
                      onChange={(e) => setNote(e.target.value)} />
          </div>
          <p className="text-xs text-(--vm-muted)">The report includes this run's link and BioID's current answer.</p>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>Cancel</Button>
          <Button onClick={send} disabled={busy}>Send</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
