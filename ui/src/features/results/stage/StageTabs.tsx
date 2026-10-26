/**
 * Stage tabs — Matches / Sequence|Chemistry / Notes (SPEC.md §3.5c).
 * One panel visible at a time; the parent Stage remembers the last tab
 * across selections when valid for the new molecule.
 */
import { useState } from "react";
import {
  Badge,
  Button,
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  cn,
} from "@e-infra/design-system";
import { ChevronDown, Copy, Download, ExternalLink } from "lucide-react";
import type { MatchEntry, Molecule, Note, RunStatus } from "../viewmodel";
import { CONFIDENCE_ICONS, CONFIDENCE_COLOR, type IconKey } from "../list";
import {
  CONFIDENCE_EXPLAINER,
  MATCHES_VISIBLE,
  NOT_IDENTIFIED_POINTS,
  chemRows,
  fasta,
  isPolymer,
  moleculeNotes,
} from "./stageModel";

export type StageTab = "matches" | "descriptor" | "notes";

export function tabsFor(m: Molecule): { key: StageTab; label: string; attention: boolean }[] {
  const identified = m.result != null && m.result.state !== "not_identified";
  const out: { key: StageTab; label: string; attention: boolean }[] = [
    { key: "matches", label: identified ? `Matches ${1 + m.matches.length}` : "What you can do", attention: false },
    { key: "descriptor", label: isPolymer(m) ? "Sequence" : "Chemistry", attention: false },
  ];
  if (m.note_ids.length > 0) {
    out.push({ key: "notes", label: `Notes ${m.note_ids.length}`, attention: true });
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* Matches                                                              */
/* ------------------------------------------------------------------ */

function ConfPill({ confidence, exact }: { confidence: number | null; exact: boolean }) {
  if (exact || confidence == null) {
    const C = CONFIDENCE_ICONS.exact;
    return (
      <span className="inline-flex items-center gap-1 text-sm text-(--vm-high)">
        <C size={14} aria-hidden /> Exact
      </span>
    );
  }
  const key: IconKey = confidence >= 80 ? "high" : confidence >= 50 ? "medium" : "low";
  const C = CONFIDENCE_ICONS[key];
  return (
    <span className={cn("inline-flex items-center gap-1 text-sm tabular-nums", CONFIDENCE_COLOR[key])}>
      <C size={14} aria-hidden /> {confidence.toFixed(1)}
    </span>
  );
}

function MatchRow({ entry }: { entry: MatchEntry & { exact?: boolean } }) {
  return (
    <TableRow>
      <TableCell className="whitespace-nowrap">
        {entry.url ? (
          <a href={entry.url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-(--vm-accent) hover:underline">
            {entry.db} {entry.id}
            <ExternalLink size={12} aria-hidden />
          </a>
        ) : (
          `${entry.db} ${entry.id}`
        )}
      </TableCell>
      <TableCell className="max-w-[280px] truncate">{entry.what}</TableCell>
      <TableCell className="max-w-[220px] truncate text-(--vm-muted)">{entry.evidence}</TableCell>
      <TableCell className="text-right">
        <ConfPill confidence={entry.confidence} exact={entry.exact ?? false} />
      </TableCell>
    </TableRow>
  );
}

function MatchesTab({ molecule: m }: { molecule: Molecule }) {
  const [showAll, setShowAll] = useState(false);
  const [showRejected, setShowRejected] = useState(false);
  const [showExplainer, setShowExplainer] = useState(false);

  const bestRow: (MatchEntry & { exact?: boolean }) | null = m.result?.best
    ? {
        db: m.result.best.db,
        id: m.result.best.id,
        url: m.result.best.url,
        what: m.result.name ?? `${m.result.best.db} ${m.result.best.id}`,
        evidence: m.result.evidence ?? "",
        confidence: m.result.confidence,
        exact: m.result.state === "exact",
      }
    : null;
  const all = [...(bestRow ? [bestRow] : []), ...m.matches];
  const rows = showAll ? all : all.slice(0, MATCHES_VISIBLE);
  const rejected = m.rejected ?? [];
  const identified = m.result != null && m.result.state !== "not_identified";

  if (!identified) {
    return (
      <div className="px-5 py-4">
        <h3 className="text-sm font-semibold">What you can do</h3>
        <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-sm text-(--vm-fg-2)">
          {NOT_IDENTIFIED_POINTS.map((p) => (
            <li key={p}>{p}</li>
          ))}
        </ol>
        {rejected.length > 0 && (
          <RejectedToggle n={rejected.length} open={showRejected} onToggle={() => setShowRejected((v) => !v)} rejected={rejected} />
        )}
      </div>
    );
  }

  return (
    <div className="px-5 py-4">
      <div className="overflow-x-auto rounded-md border border-(--vm-line)">
        <Table>
          <TableHeader>
            <TableRow className="bg-(--vm-surface-2)">
              <TableHead>Entry</TableHead>
              <TableHead>What it is</TableHead>
              <TableHead>Match to your molecule</TableHead>
              <TableHead className="text-right">Confidence</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r, i) => (
              <MatchRow key={`${r.db}-${r.id}-${i}`} entry={r} />
            ))}
          </TableBody>
        </Table>
      </div>
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
        {!showAll && all.length > MATCHES_VISIBLE && (
          <button type="button" className="text-(--vm-accent) hover:underline" onClick={() => setShowAll(true)}>
            Show all {all.length} verified
          </button>
        )}
        {m.more.related > 0 && <span className="text-(--vm-muted)">Related entries ({m.more.related})</span>}
        {rejected.length > 0 && (
          <RejectedToggle n={rejected.length} open={showRejected} onToggle={() => setShowRejected((v) => !v)} rejected={rejected} inline />
        )}
        <Collapsible open={showExplainer} onOpenChange={setShowExplainer}>
          <CollapsibleTrigger className="inline-flex items-center gap-1 text-(--vm-muted) hover:text-(--vm-fg)">
            ⓘ {CONFIDENCE_EXPLAINER.summary}
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-2 w-full rounded-md bg-(--vm-surface-2) p-3 text-sm text-(--vm-fg-2)">
            <p>{CONFIDENCE_EXPLAINER.body}</p>
            <ul className="mt-2 space-y-1">
              {CONFIDENCE_EXPLAINER.legend.map((l) => (
                <li key={l.word}>
                  <span className="font-medium text-(--vm-fg)">{l.word}</span>
                  {l.range ? ` · ${l.range}` : ""} · {l.note}
                </li>
              ))}
            </ul>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  );
}

function RejectedToggle({
  n, open, onToggle, rejected, inline,
}: {
  n: number;
  open: boolean;
  onToggle: () => void;
  rejected: NonNullable<Molecule["rejected"]>;
  inline?: boolean;
}) {
  return (
    <div className={inline ? "contents" : "mt-3"}>
      <button type="button" onClick={onToggle} className="inline-flex items-center gap-1 text-(--vm-accent) hover:underline" aria-expanded={open}>
        Rejected candidates ({n})
        <ChevronDown size={14} aria-hidden className={cn("transition-transform", open && "rotate-180")} />
      </button>
      {open && (
        <ul className="mt-2 basis-full space-y-1 rounded-md bg-(--vm-surface-2) p-3 text-sm" style={inline ? { width: "100%" } : undefined}>
          {rejected.map((r, i) => (
            <li key={`${r.db}-${r.id}-${i}`} className="flex justify-between gap-4">
              <span className="text-(--vm-fg)">{r.what}</span>
              <span className="text-(--vm-muted) text-right">{r.clause}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sequence / chemistry                                                 */
/* ------------------------------------------------------------------ */

function copy(text: string, ok: string) {
  void navigator.clipboard?.writeText(text).then(() => {
    import("sonner").then(({ toast }) => toast.success(ok)).catch(() => {});
  });
}

function download(filename: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function DescriptorTab({ molecule: m }: { molecule: Molecule }) {
  if (isPolymer(m)) {
    const seq = m.descriptor.sequence;
    const payload = fasta(m);
    if (!seq) return <p className="px-5 py-4 text-sm text-(--vm-muted)">No sequence was recorded for this molecule.</p>;
    return (
      <div className="px-5 py-4">
        <p className="text-sm text-(--vm-muted)">{seq.length.toLocaleString()} residues, as read from your files</p>
        <pre className="mt-2 max-h-[9.5rem] overflow-auto rounded-md border border-(--vm-line) bg-(--vm-surface-2) p-3 font-mono text-[13px] leading-6 whitespace-pre-wrap break-all">
          {seq}
        </pre>
        <div className="mt-2 flex gap-2">
          <Button variant="outline" size="sm" onClick={() => payload && copy(payload, "FASTA copied")}>
            <Copy size={14} className="mr-1" aria-hidden /> Copy FASTA
          </Button>
          <Button variant="outline" size="sm" onClick={() => payload && download(`${m.display_name.replace(/\W+/g, "_")}.fasta`, payload)}>
            <Download size={14} className="mr-1" aria-hidden /> Download .fasta
          </Button>
        </div>
      </div>
    );
  }
  const rows = chemRows(m);
  if (rows.length === 0) return <p className="px-5 py-4 text-sm text-(--vm-muted)">No chemistry description was recorded for this molecule.</p>;
  return (
    <dl className="px-5 py-4">
      {rows.map((r) => (
        <div key={r.label} className="flex items-baseline gap-3 py-1">
          <dt className="w-32 shrink-0 text-xs uppercase tracking-wide text-(--vm-muted)">{r.label}</dt>
          <dd className="font-mono text-sm break-all text-(--vm-fg)">
            {r.value}
            {r.copiable && (
              <button type="button" aria-label={`Copy ${r.label}`} className="ml-1.5 text-(--vm-muted) hover:text-(--vm-fg)" onClick={() => copy(r.value, "Copied")}>
                ⧉
              </button>
            )}
          </dd>
        </div>
      ))}
    </dl>
  );
}

/* ------------------------------------------------------------------ */
/* Notes                                                                */
/* ------------------------------------------------------------------ */

function NotesTab({ molecule: m, notes }: { molecule: Molecule; notes: Note[] }) {
  const mine = moleculeNotes(m, notes);
  if (mine.length === 0) return <p className="px-5 py-4 text-sm text-(--vm-muted)">No notes for this molecule.</p>;
  return (
    <div className="space-y-3 px-5 py-4">
      {mine.map((n) => (
        <div
          key={n.id}
          className={cn(
            "rounded-md border p-3",
            n.severity === "attention" ? "border-(--vm-attention-line) bg-(--vm-attention-bg)" : "border-(--vm-info-line) bg-(--vm-info-bg)",
          )}
        >
          <p className={cn("text-sm font-semibold", n.severity === "attention" ? "text-(--vm-attention)" : "text-(--vm-info)")}>
            {n.severity === "attention" ? "⚠ " : "ⓘ "}
            {n.title}
          </p>
          <p className="mt-1 text-sm text-(--vm-fg-2)">{n.body}</p>
          {n.action && <p className="mt-1 text-sm font-medium text-(--vm-fg)">What to do: {n.action}</p>}
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* The tabs                                                             */
/* ------------------------------------------------------------------ */

export interface StageTabsProps {
  molecule: Molecule;
  notes: Note[];
  runStatus: RunStatus;
  tab: StageTab;
  onTab: (tab: StageTab) => void;
}

export function StageTabs({ molecule: m, notes, runStatus, tab, onTab }: StageTabsProps) {
  const tabs = tabsFor(m);
  const mine = moleculeNotes(m, notes);
  const hasAttention = mine.some((n) => n.severity === "attention");
  const pendingMatches = runStatus === "running" || runStatus === "queued";
  const failedNotChecked = runStatus === "failed" && m.status !== "searched";

  return (
    <Tabs value={tab} onValueChange={(v) => onTab(v as StageTab)}>
      <TabsList className="mx-5">
        {tabs.map((t) => (
          <TabsTrigger key={t.key} value={t.key}>
            {t.label}
            {t.key === "notes" && m.note_ids.length > 0 && hasAttention && (
              <Badge variant="secondary" className="ml-1.5 bg-(--vm-attention-bg) text-(--vm-attention)">
                {m.note_ids.length}
              </Badge>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      <TabsContent value="matches">
        {pendingMatches ? (
          <p className="px-5 py-4 text-sm text-(--vm-muted)">
            Matches appear when the whole run has finished. BioID checks every candidate after all molecules have been searched.
          </p>
        ) : failedNotChecked ? (
          <p className="px-5 py-4 text-sm text-(--vm-muted)">
            This molecule was not searched because the run stopped. Rerun to get results.
          </p>
        ) : (
          <MatchesTab molecule={m} />
        )}
      </TabsContent>
      <TabsContent value="descriptor">
        <DescriptorTab molecule={m} />
      </TabsContent>
      <TabsContent value="notes">
        <NotesTab molecule={m} notes={notes} />
      </TabsContent>
    </Tabs>
  );
}
