import { Link } from "react-router-dom";
import { Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@e-infra/design-system";
import { Cpu, Pause, Play, Rows3, Trash2 } from "lucide-react";
import { adminApi, isSectionError, type AdminOverview } from "../../lib/api/admin";
import { formatDuration, toMs } from "./format";
import { useAdminAction } from "./session";
import { ConfirmButton, Empty, Section, SectionErrorNote, ToneBadge } from "./ui";

export function QueuesSection({ queues }: { queues: AdminOverview["queues"] }) {
  const action = useAdminAction(
    (token, a: { name: string; action: "purge" | "pause" | "resume" }) => adminApi.queue(token, a.name, a.action),
    {
      success: (res, a) =>
        a.action === "purge"
          ? `Purged ${res.removed ?? 0} queued run${res.removed === 1 ? "" : "s"} from ${a.name}`
          : `${a.name} ${a.action === "pause" ? "paused" : "resumed"}`,
      failure: "The queue action failed.",
    },
  );
  const busy = (name: string) => action.isPending && action.variables?.name === name;

  return (
    <Section id="queues" title="Queues" icon={Rows3}>
      {isSectionError(queues) ? (
        <SectionErrorNote what="Queues" error={queues.error} />
      ) : (
        <>
          {queues.error && <SectionErrorNote what="Queue state" error={queues.error} />}
          {queues.queues.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Queue</TableHead>
                  <TableHead className="text-right">Waiting</TableHead>
                  <TableHead>State</TableHead>
                  <TableHead className="text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {queues.queues.map((q) => {
                  const paused = queues.paused.includes(q.name);
                  return (
                    <TableRow key={q.name}>
                      <TableCell className="font-mono text-xs">{q.name}</TableCell>
                      <TableCell className="text-right tabular-nums">{q.waiting}</TableCell>
                      <TableCell>
                        {paused ? <ToneBadge tone="warn">paused</ToneBadge> : <ToneBadge tone="ok">consuming</ToneBadge>}
                      </TableCell>
                      <TableCell>
                        <div className="flex justify-end gap-1.5">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={busy(q.name)}
                            onClick={() => action.mutate({ name: q.name, action: paused ? "resume" : "pause" })}
                            aria-label={`${paused ? "Resume" : "Pause"} queue ${q.name}`}
                          >
                            {paused ? <Play className="h-4 w-4" aria-hidden /> : <Pause className="h-4 w-4" aria-hidden />}
                            {paused ? "Resume" : "Pause"}
                          </Button>
                          <ConfirmButton
                            label="Purge"
                            ariaLabel={`Purge queue ${q.name}`}
                            icon={Trash2}
                            disabled={q.waiting === 0 || busy(q.name)}
                            title={`Purge ${q.name}?`}
                            description={
                              <p>
                                {q.waiting} queued run{q.waiting === 1 ? "" : "s"} will be dropped from the queue and
                                never start. Their run pages are not updated: they keep showing as queued.
                              </p>
                            }
                            confirmLabel={`Drop ${q.waiting} run${q.waiting === 1 ? "" : "s"}`}
                            destructive
                            onConfirm={() => action.mutate({ name: q.name, action: "purge" })}
                          />
                        </div>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
          <p className="mt-3 text-xs text-text-muted">
            Pausing stops workers taking new runs from the queue until resumed or the workers restart.
          </p>
        </>
      )}
    </Section>
  );
}

export function WorkersSection({ workers, nowMs }: { workers: AdminOverview["workers"]; nowMs: number }) {
  return (
    <Section id="workers" title="Workers (Celery)" icon={Cpu}>
      {isSectionError(workers) ? (
        <SectionErrorNote what="Workers" error={workers.error} />
      ) : (
        <>
          {workers.error && <SectionErrorNote what="Worker state" error={workers.error} />}
          {!workers.error && workers.workers.length === 0 && <Empty>No workers answered.</Empty>}
          <ul className="divide-y divide-(--vm-line-2)">
            {workers.workers.map((w) => (
              <li key={w.name} className="py-2 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
                  <p className="min-w-0 truncate font-mono text-xs text-(--vm-fg)" title={w.name}>
                    {w.name}
                  </p>
                  <p className="text-xs text-text-muted">
                    {w.active.length} active · {w.reserved} reserved
                  </p>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {w.queues.length === 0 ? (
                    <ToneBadge tone="warn">no queues</ToneBadge>
                  ) : (
                    w.queues.map((q) => (
                      <ToneBadge key={q} tone="muted" className="font-mono">
                        {q}
                      </ToneBadge>
                    ))
                  )}
                </div>
                {w.active.length > 0 && (
                  <ul className="mt-1.5 space-y-0.5 text-sm">
                    {w.active.map((t, i) => {
                      const started = toMs(t.started);
                      return (
                        <li key={t.run_id ?? i} className="flex flex-wrap items-baseline gap-x-2">
                          {t.run_id ? (
                            <Link to={`/runs/${encodeURIComponent(t.run_id)}`} className="font-mono text-xs">
                              {t.run_id}
                            </Link>
                          ) : (
                            <span className="font-mono text-xs">(no id)</span>
                          )}
                          <span className="text-xs text-text-muted">
                            {started != null ? `running for ${formatDuration((nowMs - started) / 1000)}` : "running"}
                          </span>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}
