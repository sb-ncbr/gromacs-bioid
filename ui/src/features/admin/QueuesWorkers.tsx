import { useState } from "react";
import { Link } from "react-router-dom";
import { Button, Input, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@e-infra/design-system";
import { Cpu, Pause, Play, Rows3, Trash2 } from "lucide-react";
import { adminApi, isSectionError, type AdminOverview, type LaneCard, type RetryPolicy } from "../../lib/api/admin";
import { formatDuration, relativeTime, toMs } from "./format";
import { laneHealth, policyError, policySummary, poolText, runCounts } from "./lanes";
import { useAdminAction } from "./session";
import { ConfirmButton, Empty, Section, SectionErrorNote, Stat, ToneBadge } from "./ui";

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

// -- one card per queue (2026-11-18) -------------------------------------------

function Workers({ card, nowMs }: { card: LaneCard; nowMs: number }) {
  const [open, setOpen] = useState(false);
  if (card.consumers.length === 0) return null;
  return (
    <div>
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)}
              className="text-xs text-(--vm-muted) hover:text-(--vm-fg)">
        {open ? "▾" : "▸"} {card.consumers.length} worker{card.consumers.length === 1 ? "" : "s"} consuming
      </button>
      {open && (
        <ul className="mt-1 divide-y divide-(--vm-line-2)">
          {card.consumers.map((w) => (
            <li key={w.name} className="py-1.5">
              <p className="flex flex-wrap justify-between gap-2 text-xs">
                <span className="truncate font-mono" title={w.name}>{w.name.replace(/^celery@/, "")}</span>
                <span className="text-text-muted">{w.active.length} active · {w.reserved} reserved</span>
              </p>
              {w.active.map((t, i) => {
                const started = toMs(t.started);
                return (
                  <p key={t.run_id ?? i} className="flex flex-wrap gap-x-2 pl-3 text-xs">
                    {t.run_id ? (
                      <Link to={`/runs/${encodeURIComponent(t.run_id)}`} className="font-mono">{t.run_id}</Link>
                    ) : <span className="font-mono">(no id)</span>}
                    <span className="text-text-muted">
                      {started != null ? `for ${formatDuration((nowMs - started) / 1000)}` : ""}
                    </span>
                  </p>
                );
              })}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RetryPolicyEditor({ card }: { card: LaneCard }) {
  const policy = card.retry_policy!;
  const [draft, setDraft] = useState<RetryPolicy | null>(null);
  const save = useAdminAction((t, p: RetryPolicy) => adminApi.setRetryPolicy(t, card.lane!, p), {
    success: (r) => `${card.title}: ${policySummary(r.retry_policy)}`,
    failure: "Could not save the retry policy.",
  });
  if (!draft) {
    return (
      <p className="flex flex-wrap items-center gap-2 text-sm">
        <span>{policySummary(policy)}</span>
        <Button type="button" variant="outline" size="sm" onClick={() => setDraft(policy)}>Change</Button>
      </p>
    );
  }
  const error = policyError(draft);
  const num = (k: "max_attempts" | "delay_minutes") => (
    <Input type="number" className="h-8 w-20" value={String(draft[k])}
           onChange={(e) => setDraft({ ...draft, [k]: Number(e.target.value) })} aria-label={k} />
  );
  const box = (k: "enabled" | "incomplete" | "worker_lost", text: string) => (
    <label className="flex items-center gap-1.5 text-sm">
      <input type="checkbox" checked={draft[k]} onChange={(e) => setDraft({ ...draft, [k]: e.target.checked })} />
      {text}
    </label>
  );
  return (
    <div className="grid gap-2 rounded-md border border-(--vm-line) p-2">
      {box("enabled", "Retry automatically")}
      <div className="flex flex-wrap gap-3 pl-5">
        {box("incomplete", "incomplete runs (database down, busy, out of time)")}
        {box("worker_lost", "lost workers")}
      </div>
      <div className="flex flex-wrap items-center gap-2 pl-5 text-sm">
        Up to {num("max_attempts")} attempts, {num("delay_minutes")} minutes apart
      </div>
      {error && <p className="text-xs text-(--vm-error)">{error}</p>}
      <p className="text-xs text-text-muted">
        A retried run keeps its id and reads as queued until its last attempt. Lookups that worked come from the cache.
      </p>
      <div className="flex gap-2">
        <Button type="button" size="sm" disabled={!!error || save.isPending}
                onClick={() => save.mutate(draft, { onSuccess: () => setDraft(null) })}>Save</Button>
        <Button type="button" variant="outline" size="sm" onClick={() => setDraft(null)}>Cancel</Button>
      </div>
    </div>
  );
}

function TokenControls({ card, nowMs }: { card: LaneCard; nowMs: number }) {
  const [shown, setShown] = useState<{ token: string; header: string } | null>(null);
  const create = useAdminAction((t, _: void) => adminApi.newQueueToken(t, card.lane!), {
    success: () => `New ${card.title.toLowerCase()} queue token created`, failure: "Could not create a token.",
  });
  const revoke = useAdminAction((t, _: void) => adminApi.revokeQueueToken(t, card.lane!), {
    success: () => `${card.title} queue token revoked`, failure: "Could not revoke the token.",
  });
  return (
    <div className="grid gap-1.5 text-sm">
      <p className="flex flex-wrap items-center gap-2">
        {card.token ? (
          <span>Token …{card.token.hint}, created {relativeTime(card.token.created_at * 1000, nowMs)}.</span>
        ) : (
          <span className="text-(--vm-attention)">No token: nobody can submit to this queue.</span>
        )}
        <ConfirmButton
          label={card.token ? "Replace token" : "Create token"}
          ariaLabel={`New token for the ${card.title} queue`}
          title={card.token ? "Replace the token?" : "Create a token?"}
          description={<p>{card.token ? "Submitters using the current token are refused from now on. " : ""}
            The new token is shown once.</p>}
          confirmLabel={card.token ? "Replace" : "Create"}
          onConfirm={() => create.mutate(undefined, { onSuccess: (r) => setShown({ token: r.token, header: r.header }) })}
        />
        {card.token && (
          <ConfirmButton label="Revoke" ariaLabel={`Revoke the ${card.title} queue token`} title="Revoke the token?"
                         description={<p>Nobody can submit to this queue until a new token is created.</p>}
                         confirmLabel="Revoke" destructive onConfirm={() => revoke.mutate(undefined)} />
        )}
      </p>
      {shown && (
        <div className="rounded-md border border-(--vm-attention-line) bg-(--vm-attention-bg) p-2 text-xs">
          <p className="font-medium">Copy it now: it is not shown again.</p>
          <code className="mt-1 block break-all font-mono">{shown.token}</code>
          <p className="mt-1 text-text-muted">
            Submit with <code>-H "{shown.header}: …" -F queue={card.lane}</code> on POST /api/v1/runs.
          </p>
          <div className="mt-1 flex gap-2">
            <Button type="button" variant="outline" size="sm"
                    onClick={() => void navigator.clipboard?.writeText(shown.token)}>Copy</Button>
            <Button type="button" variant="outline" size="sm" onClick={() => setShown(null)}>Done</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function QueueCard({ card, nowMs }: { card: LaneCard; nowMs: number }) {
  const action = useAdminAction(
    (token, a: { name: string; action: "purge" | "pause" | "resume" }) => adminApi.queue(token, a.name, a.action),
    {
      success: (res, a) => a.action === "purge"
        ? `Purged ${res.removed ?? 0} queued run${res.removed === 1 ? "" : "s"} from ${card.title}`
        : `${card.title} ${a.action === "pause" ? "paused" : "resumed"}`,
      failure: "The queue action failed.",
    },
  );
  const health = laneHealth(card);
  const waiting = card.waiting ?? 0;
  return (
    <section aria-labelledby={`lane-${card.queue}`} className="grid min-w-0 content-start gap-2 rounded-md border border-(--vm-line) p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 id={`lane-${card.queue}`} className="flex items-center gap-2 font-semibold text-(--vm-fg)">
          {card.title}
          <ToneBadge tone={health.tone}>{health.text}</ToneBadge>
        </h3>
        <span className="font-mono text-xs text-text-muted">{card.queue}</span>
      </div>
      <p className="text-xs text-text-muted">{card.about}</p>
      <dl className="grid grid-cols-3 gap-2">
        <Stat label="Waiting" value={card.waiting ?? "—"} />
        <Stat label="Running" value={card.running} hint={card.reserved ? `${card.reserved} reserved` : undefined} />
        <Stat label="Workers" value={card.pool ? `${card.pool.ready ?? 0}/${card.pool.replicas ?? 0}` : card.consumers.length} />
      </dl>
      <p className="truncate text-xs text-text-muted" title={poolText(card.pool)}>
        {card.deployment ? <span className="font-mono">{card.deployment}</span> : null} {poolText(card.pool)}
      </p>
      {Object.keys(card.runs).length > 0 && <p className="text-xs text-text-muted">Runs: {runCounts(card.runs)}</p>}
      {card.errors.map((e) => <SectionErrorNote key={e} what="Part of this card" error={e} />)}
      {card.retry_policy && <RetryPolicyEditor card={card} />}
      {card.lane && card.lane !== "web" && <TokenControls card={card} nowMs={nowMs} />}
      <Workers card={card} nowMs={nowMs} />
      <div className="flex flex-wrap gap-1.5">
        <Button type="button" variant="outline" size="sm" disabled={action.isPending}
                onClick={() => action.mutate({ name: card.queue, action: card.paused ? "resume" : "pause" })}>
          {card.paused ? <Play className="h-4 w-4" aria-hidden /> : <Pause className="h-4 w-4" aria-hidden />}
          {card.paused ? "Resume" : "Pause"}
        </Button>
        <ConfirmButton
          label="Purge" ariaLabel={`Purge the ${card.title} queue`} icon={Trash2}
          disabled={waiting === 0 || action.isPending} title={`Purge ${card.title}?`}
          description={<p>{waiting} queued run{waiting === 1 ? "" : "s"} will be dropped and marked cancelled.</p>}
          confirmLabel={`Drop ${waiting} run${waiting === 1 ? "" : "s"}`} destructive
          onConfirm={() => action.mutate({ name: card.queue, action: "purge" })}
        />
      </div>
    </section>
  );
}

/** Queues and their workers as cards; older APIs (no `lanes`) get the two plain sections. */
export function QueuesWorkersSection({ overview, nowMs }: { overview: AdminOverview; nowMs: number }) {
  const lanes = overview.lanes;
  if (!lanes) {
    return (
      <div className="grid gap-4 lg:grid-cols-2">
        <QueuesSection queues={overview.queues} />
        <WorkersSection workers={overview.workers} nowMs={nowMs} />
      </div>
    );
  }
  return (
    <Section id="queues" title="Queues and workers" icon={Rows3}>
      {isSectionError(lanes) ? (
        <SectionErrorNote what="Queues" error={lanes.error} />
      ) : (
        <>
          <div className="grid gap-3 lg:grid-cols-2">
            {lanes.map((card) => <QueueCard key={card.queue} card={card} nowMs={nowMs} />)}
          </div>
          <p className="mt-3 text-xs text-text-muted">
            Pausing stops workers taking new runs from the queue until resumed or the workers restart.
          </p>
        </>
      )}
    </Section>
  );
}
