import { useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router-dom";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
  Input,
  Label,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@e-infra/design-system";
import { ChevronDown, CircleX, History, ListChecks, Trash2 } from "lucide-react";
import { adminApi, isSectionError, type AdminOverview, type AdminRun } from "../../lib/api/admin";
import {
  ACTIVE_STATUSES,
  dateTime,
  formatDuration,
  parseCustomDays,
  relativeTime,
  retentionSummary,
  statusTone,
  toMs,
} from "./format";
import { useAdmin, useAdminAction } from "./session";
import { ConfirmButton, Empty, Section, SectionErrorNote, ToneBadge } from "./ui";

export function RunLink({ run }: { run: Pick<AdminRun, "run_id" | "run_name"> }) {
  const name = (run.run_name ?? "").split(">")[0].trim();
  return (
    <Link to={`/runs/${encodeURIComponent(run.run_id)}`} className="block max-w-[22rem] min-w-0 no-underline hover:underline">
      {name ? (
        <>
          <span className="block truncate text-sm font-medium text-(--vm-fg)" title={run.run_name ?? undefined}>
            {name}
          </span>
          <span className="block truncate font-mono text-[11px] text-text-muted">{run.run_id}</span>
        </>
      ) : (
        <span className="block truncate font-mono text-xs text-(--vm-fg)">{run.run_id}</span>
      )}
    </Link>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <ToneBadge tone={statusTone(status)}>{status}</ToneBadge>;
}

function CustomDaysDialog({ run, open, onOpenChange }: { run: AdminRun; open: boolean; onOpenChange: (o: boolean) => void }) {
  const [raw, setRaw] = useState(String(run.retention.days ?? 30));
  const days = parseCustomDays(raw);
  const set = useAdminAction((token, value: string) => adminApi.setRetention(token, run.run_id, value), {
    success: (_, value) => `Retention set to ${value} days`,
    failure: "Could not change the retention.",
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (days == null) return;
    set.mutate(String(days), { onSuccess: () => onOpenChange(false) });
  };
  const inputId = `days-${run.run_id}`;
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        <form onSubmit={submit} className="space-y-4">
          <DialogHeader>
            <DialogTitle>Custom retention</DialogTitle>
            <DialogDescription>Keep the run for this many days after it finished (1–365).</DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5">
            <Label htmlFor={inputId}>Days</Label>
            <Input
              id={inputId}
              type="number"
              inputMode="numeric"
              min={1}
              max={365}
              value={raw}
              onChange={(e) => setRaw(e.target.value)}
              aria-invalid={days == null}
              autoFocus
            />
            {days == null && <p className="text-xs text-(--vm-error)">Enter a whole number from 1 to 365.</p>}
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={days == null || set.isPending}>
              Set {days ?? "…"} days
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RetentionMenu({ run }: { run: AdminRun }) {
  const [custom, setCustom] = useState(false);
  const set = useAdminAction((token, value: string) => adminApi.setRetention(token, run.run_id, value), {
    success: (_, value) => (value === "preserve" ? "Run kept indefinitely" : "Retention reset to the default"),
    failure: "Could not change the retention.",
  });
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button type="button" variant="outline" size="sm" disabled={set.isPending} aria-label={`Retention of ${run.run_id}`}>
            Retention
            <ChevronDown className="h-3.5 w-3.5" aria-hidden />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuLabel className="text-xs font-normal text-text-muted">Keep this run for</DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled={run.retention.policy === "default"} onSelect={() => set.mutate("default")}>
            The default period
          </DropdownMenuItem>
          <DropdownMenuItem disabled={run.retention.policy === "preserve"} onSelect={() => set.mutate("preserve")}>
            Keep indefinitely
          </DropdownMenuItem>
          <DropdownMenuItem onSelect={() => setCustom(true)}>Custom days…</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
      {custom && <CustomDaysDialog run={run} open={custom} onOpenChange={setCustom} />}
    </>
  );
}

function DeleteRun({ run }: { run: AdminRun }) {
  const { graceDays } = useAdmin();
  const del = useAdminAction((token, id: string) => adminApi.deleteRun(token, id), {
    success: (res) => `Moved to the trash; restorable for ${res.grace_days} days`,
    failure: "Could not delete the run.",
  });
  const active = ACTIVE_STATUSES.has(run.status);
  return (
    <ConfirmButton
      label={<span className="sr-only">Delete</span>}
      ariaLabel={active ? `Cancel ${run.run_id} before deleting it` : `Delete ${run.run_id}`}
      icon={Trash2}
      size="icon-sm"
      disabled={active || del.isPending}
      title="Delete this run?"
      description={
        <>
          <p>
            <span className="font-mono">{run.run_id}</span> moves to the trash, restorable for{" "}
            {graceDays != null ? `${graceDays} days` : "the grace period"} (see Retention below). After that it is
            purged.
          </p>
        </>
      }
      confirmLabel="Move to trash"
      destructive
      onConfirm={() => del.mutate(run.run_id)}
    />
  );
}

function CancelRun({ run }: { run: AdminRun }) {
  const cancel = useAdminAction((token, id: string) => adminApi.cancelRun(token, id), {
    success: () => "Run cancelled",
    failure: "Could not cancel the run.",
  });
  return (
    <ConfirmButton
      label="Cancel"
      ariaLabel={`Cancel run ${run.run_id}`}
      icon={CircleX}
      disabled={cancel.isPending}
      title="Cancel this run?"
      description={
        <p>
          <span className="font-mono">{run.run_id}</span> is stopped (a running task is terminated) and marked
          cancelled.
        </p>
      }
      confirmLabel="Cancel run"
      destructive
      onConfirm={() => cancel.mutate(run.run_id)}
    />
  );
}

function Created({ iso, nowMs }: { iso: string | null; nowMs: number }) {
  const ms = toMs(iso);
  return (
    <span title={iso ?? undefined} className="text-xs text-text-muted">
      {dateTime(ms, nowMs)}
      <span className="block">{relativeTime(ms, nowMs)}</span>
    </span>
  );
}

function ActiveRuns({ runs, nowMs }: { runs: AdminRun[]; nowMs: number }) {
  if (runs.length === 0) return <Empty>No runs in flight.</Empty>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Running for</TableHead>
          <TableHead>Preset</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((r) => {
          const started = toMs(r.started_at);
          return (
            <TableRow key={r.run_id}>
              <TableCell>
                <RunLink run={r} />
              </TableCell>
              <TableCell>
                <StatusBadge status={r.status} />
              </TableCell>
              <TableCell>
                <Created iso={r.created_at} nowMs={nowMs} />
              </TableCell>
              <TableCell className="text-xs tabular-nums">
                {r.status === "running" && started != null ? formatDuration((nowMs - started) / 1000) : "—"}
              </TableCell>
              <TableCell className="text-xs">{r.preset ?? "—"}</TableCell>
              <TableCell className="text-right">
                <CancelRun run={r} />
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}

function RecentFailures({ runs, nowMs }: { runs: AdminRun[]; nowMs: number }) {
  if (runs.length === 0) return <Empty>No failed runs.</Empty>;
  return (
    <ul className="divide-y divide-(--vm-line-2)">
      {runs.map((r) => (
        <li key={r.run_id} className="py-2 first:pt-0 last:pb-0">
          <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
            <RunLink run={r} />
            <span className="text-xs text-text-muted" title={r.finished_at ?? r.created_at}>
              {relativeTime(toMs(r.finished_at) ?? toMs(r.created_at), nowMs)}
            </span>
          </div>
          <p className="mt-1 text-xs break-words text-(--vm-error)">{r.error || "No error message recorded."}</p>
        </li>
      ))}
    </ul>
  );
}

function RecentRuns({ runs, nowMs }: { runs: AdminRun[]; nowMs: number }) {
  if (runs.length === 0) return <Empty>No runs yet.</Empty>;
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Run</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>Created</TableHead>
          <TableHead>Preset</TableHead>
          <TableHead>Retention</TableHead>
          <TableHead className="text-right">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {runs.map((r) => (
          <TableRow key={r.run_id}>
            <TableCell>
              <RunLink run={r} />
            </TableCell>
            <TableCell>
              <div className="flex flex-wrap gap-1">
                <StatusBadge status={r.status} />
                {r.example && <ToneBadge tone="info">example</ToneBadge>}
                {r.warning_count > 0 && (
                  <ToneBadge tone="warn" title="warnings">
                    {r.warning_count} warn
                  </ToneBadge>
                )}
              </div>
            </TableCell>
            <TableCell>
              <Created iso={r.created_at} nowMs={nowMs} />
            </TableCell>
            <TableCell className="text-xs">
              {r.preset ?? "—"}
              {r.input_kind && <span className="block text-text-muted">{r.input_kind}</span>}
            </TableCell>
            <TableCell className="text-xs">
              {r.example ? <span className="text-text-muted">example: never expires</span> : retentionSummary(r.retention, nowMs)}
            </TableCell>
            <TableCell>
              <div className="flex justify-end gap-1.5">
                {!r.example && (
                  <>
                    <RetentionMenu run={r} />
                    <DeleteRun run={r} />
                  </>
                )}
              </div>
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function SubHeading({ children }: { children: ReactNode }) {
  return <h3 className="mt-5 mb-2 text-sm font-semibold text-(--vm-fg) first:mt-0">{children}</h3>;
}

const STATUS_ORDER = ["running", "queued", "pending", "created", "success", "failed", "cancelled", "timeout", "error"];

export function RunsSection({ runs, nowMs }: { runs: AdminOverview["runs"]; nowMs: number }) {
  if (isSectionError(runs)) {
    return (
      <Section id="runs" title="Runs" icon={ListChecks}>
        <SectionErrorNote what="Runs" error={runs.error} />
      </Section>
    );
  }
  const statuses = Object.entries(runs.by_status).sort(
    ([a], [b]) => (STATUS_ORDER.indexOf(a) + 1 || 99) - (STATUS_ORDER.indexOf(b) + 1 || 99),
  );
  return (
    <Section id="runs" title="Runs" icon={ListChecks}>
      <dl className="flex flex-wrap items-end gap-x-6 gap-y-3">
        <div>
          <dt className="text-xs text-text-muted">Total</dt>
          <dd className="text-lg font-semibold tabular-nums">{runs.total}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-muted">Last 24 h</dt>
          <dd className="text-lg font-semibold tabular-nums">{runs.submitted_24h}</dd>
        </div>
        <div>
          <dt className="text-xs text-text-muted">Last 7 days</dt>
          <dd className="text-lg font-semibold tabular-nums">{runs.submitted_7d}</dd>
        </div>
        <div className="min-w-0">
          <dt className="mb-1 text-xs text-text-muted">By status</dt>
          <dd className="flex flex-wrap gap-1">
            {statuses.length === 0 && <span className="text-sm text-text-muted">—</span>}
            {statuses.map(([s, n]) => (
              <ToneBadge key={s} tone={statusTone(s)}>
                {s} <span className="tabular-nums">{n}</span>
              </ToneBadge>
            ))}
          </dd>
        </div>
      </dl>

      <SubHeading>Active ({runs.active.length})</SubHeading>
      <ActiveRuns runs={runs.active} nowMs={nowMs} />

      <SubHeading>Recent failures</SubHeading>
      <RecentFailures runs={runs.recent_failures} nowMs={nowMs} />

      <SubHeading>
        <span className="inline-flex items-center gap-1.5">
          <History className="h-4 w-4 text-(--vm-muted)" aria-hidden />
          Recent runs (latest {runs.recent.length})
        </span>
      </SubHeading>
      <RecentRuns runs={runs.recent} nowMs={nowMs} />
    </Section>
  );
}
