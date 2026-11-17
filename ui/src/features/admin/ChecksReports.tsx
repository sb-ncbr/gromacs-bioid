/**
 * Nightly known-answers check, alarms and identification reports
 * (2026-11-17). Both load their own data (GET /admin/checks, /admin/reports).
 */
import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Input } from "@e-infra/design-system";
import { Flag, ShieldCheck } from "lucide-react";
import { ApiError, apiErrorMessage } from "../../lib/api/client";
import { adminApi, isUnauthorized, type CheckState, type IdentificationReport } from "../../lib/api/admin";
import { dateTime, relativeTime, type Tone } from "./format";
import { RunLink } from "./Runs";
import { useAdmin, useAdminAction } from "./session";
import { Empty, Section, ToneBadge } from "./ui";

const REFRESH_MS = 30_000;
const CHECK_TONE: Record<string, Tone> = { green: "ok", amber: "warn", red: "error", running: "info" };

function useAdminQuery<T>(key: string, fn: (token: string) => Promise<T>, live: boolean) {
  const { token, signOut } = useAdmin();
  return useQuery({
    queryKey: ["admin", key, token],
    queryFn: async () => {
      try {
        return await fn(token);
      } catch (err) {
        if (isUnauthorized(err)) signOut(apiErrorMessage(err, "Sign in to the admin page."));
        throw err;
      }
    },
    refetchInterval: live ? REFRESH_MS : false,
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });
}

function useRefetching<A, R>(key: string, fn: (token: string, args: A) => Promise<R>,
                             messages: { success: (res: R, args: A) => string; failure: string }) {
  const qc = useQueryClient();
  const action = useAdminAction(fn, messages);
  return {
    ...action,
    mutate: (args: A) => action.mutate(args, { onSettled: () => qc.invalidateQueries({ queryKey: ["admin", key] }) }),
  };
}

function checkLine(check: CheckState, nowMs: number): string {
  if (!check.status) return "No check has run yet.";
  if (check.status === "running") {
    const n = Object.keys(check.runs ?? {}).length;
    return `Running since ${relativeTime((check.started_at ?? 0) * 1000, nowMs)} (${n} case${n === 1 ? "" : "s"}).`;
  }
  return `Last check ${relativeTime((check.finished_at ?? 0) * 1000, nowMs)}.`;
}

export function ChecksSection({ live, nowMs }: { live: boolean; nowMs: number }) {
  const q = useAdminQuery("checks", adminApi.checks, live);
  const [runId, setRunId] = useState("");
  const [label, setLabel] = useState("");
  const add = useRefetching("checks", (t, v: { runId: string; label: string }) => adminApi.addCase(t, v.runId, v.label),
    { success: (c) => `Case added: ${c.label}`, failure: "Could not add the case" });
  const remove = useRefetching("checks", (t, id: string) => adminApi.removeCase(t, id),
    { success: () => "Case removed", failure: "Could not remove the case" });
  const accept = useRefetching("checks", (t, id: string) => adminApi.acceptCase(t, id),
    { success: () => "Observed answers are now the known answers", failure: "Could not accept" });
  const runNow = useRefetching("checks", (t: string) => adminApi.runCheck(t),
    { success: () => "Check started: one rerun per case", failure: "Could not start the check" });
  const test = useRefetching("checks", (t: string) => adminApi.testAlarm(t),
    { success: (r) => (r.sent ? `Test alarm sent to ${r.to}` : "The test alarm could not be sent: see Recent alarms"), failure: "Could not send" });

  const d = q.data;
  const check = d?.check ?? {};
  const loops = Array.isArray(d?.crash_loops) ? d.crash_loops : [];
  return (
    <Section id="checks" title="Nightly known-answers check" icon={ShieldCheck}
      actions={
        <div className="flex gap-2">
          <Button size="sm" variant="outline" disabled={runNow.isPending || !d?.cases.length || check.status === "running"}
                  onClick={() => runNow.mutate(undefined)}>Run check now</Button>
          <Button size="sm" variant="outline" disabled={test.isPending || !d?.alert_email} onClick={() => test.mutate(undefined)}>
            Send test alarm
          </Button>
        </div>
      }>
      {q.isError ? (
        <Empty>Could not load the checks: {apiErrorMessage(q.error, "error")}</Empty>
      ) : !d ? (
        <Empty>Loading…</Empty>
      ) : (
        <div className="flex flex-col gap-4 p-4 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            {check.status && <ToneBadge tone={CHECK_TONE[check.status] ?? "muted"}>{check.status}</ToneBadge>}
            <span>{checkLine(check, nowMs)}</span>
            <span className="text-(--vm-muted)">
              Every night at 01:30 (Prague). Alarms to {d.alert_email ?? "nobody (BAT3_ALERT_EMAIL unset)"}.
            </span>
          </div>
          {loops.length > 0 && (
            <div className="rounded-md border border-(--vm-attention-line) bg-(--vm-attention-bg) p-2">
              {loops.map((l) => (
                <p key={l.deployment}>
                  <b>{l.deployment}</b>: {l.pods} of {l.of} pods in {l.reason}{l.last_exit ? ` (last exit ${l.last_exit})` : ""}
                </p>
              ))}
            </div>
          )}
          {d.cases.length === 0 ? (
            <Empty>No cases yet. Add a successful run whose answers you have checked by hand.</Empty>
          ) : (
            <ul className="flex flex-col gap-2">
              {d.cases.map((c) => {
                const r = check.results?.[c.run_id];
                return (
                  <li key={c.run_id} className="rounded-md border border-(--vm-line-2) p-2">
                    <div className="flex flex-wrap items-center gap-2">
                      {r && <ToneBadge tone={CHECK_TONE[r.status] ?? "muted"}>{r.status}</ToneBadge>}
                      <span className="font-medium">{c.label}</span>
                      <RunLink run={{ run_id: c.run_id, run_name: null }} />
                      <span className="text-(--vm-muted)">{Object.keys(c.expected).length} molecules</span>
                      <span className="ml-auto flex gap-2">
                        {r && r.status !== "green" && r.check_run && (
                          <Button size="sm" variant="outline" onClick={() => accept.mutate(c.run_id)}>Accept observed</Button>
                        )}
                        <Button size="sm" variant="ghost" onClick={() => remove.mutate(c.run_id)}>Remove</Button>
                      </span>
                    </div>
                    {r && r.diffs.length > 0 && (
                      <ul className="mt-1 list-disc pl-5 text-(--vm-fg-2)">
                        {r.diffs.map((x, i) => (
                          <li key={i}>
                            {x.kind === "database" ? `${x.resolver} stopped answering` : x.kind === "run" ? x.observed
                              : `expected ${x.expected}, got ${x.observed}`}
                            {x.segment ? ` (${x.segment})` : ""}{x.repeated ? " · second night" : ""}
                          </li>
                        ))}
                      </ul>
                    )}
                    {r?.check_run && r.status !== "green" && (
                      <p className="mt-1 text-(--vm-muted)">Check run: <RunLink run={{ run_id: r.check_run, run_name: null }} /></p>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
          <form className="flex flex-wrap items-end gap-2"
                onSubmit={(e) => { e.preventDefault(); add.mutate({ runId: runId.trim(), label: label.trim() }); setRunId(""); setLabel(""); }}>
            <label className="flex flex-col gap-1 text-xs text-text-muted">Run id
              <Input value={runId} onChange={(e) => setRunId(e.target.value)} placeholder="a successful run" className="w-72" />
            </label>
            <label className="flex flex-col gap-1 text-xs text-text-muted">Label
              <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="e.g. trypsin + benzamidine" className="w-56" />
            </label>
            <Button size="sm" type="submit" disabled={!runId.trim() || add.isPending}>Add case</Button>
          </form>
          {d.alerts.length > 0 && (
            <div>
              <h3 className="font-semibold">Recent alarms</h3>
              <ul className="mt-1">
                {d.alerts.slice(0, 8).map((a, i) => (
                  <li key={i} className="text-(--vm-fg-2)">
                    {dateTime(a.at * 1000, nowMs)} · {a.subject} · {a.sent ? "mailed" : a.error ? `not mailed: ${a.error}` : "not mailed"}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </Section>
  );
}

const REPORT_TONE: Record<IdentificationReport["status"], Tone> = { open: "warn", resolved: "ok", dismissed: "muted" };

export function ReportsSection({ live, nowMs }: { live: boolean; nowMs: number }) {
  const q = useAdminQuery("reports", adminApi.reports, live);
  const [showClosed, setShowClosed] = useState(false);
  const update = useRefetching("reports", (t, v: { id: string; status: string }) => adminApi.updateReport(t, v.id, { status: v.status }),
    { success: (r) => `Report ${r.status}`, failure: "Could not update the report" });
  const all = q.data?.reports ?? [];
  const shown = showClosed ? all : all.filter((r) => r.status === "open");
  return (
    <Section id="reports" title={`Identification reports${q.data ? ` (${q.data.open} open)` : ""}`} icon={Flag}
      actions={<Button size="sm" variant="ghost" onClick={() => setShowClosed((v) => !v)}>{showClosed ? "Open only" : "Show all"}</Button>}>
      {q.isError ? (
        <Empty>Could not load the reports: {apiErrorMessage(q.error, "error")}</Empty>
      ) : shown.length === 0 ? (
        <Empty>{q.data ? "No open reports." : "Loading…"}</Empty>
      ) : (
        <ul className="flex flex-col gap-2 p-4 text-sm">
          {shown.map((r) => (
            <li key={r.id} className="rounded-md border border-(--vm-line-2) p-2">
              <div className="flex flex-wrap items-center gap-2">
                <ToneBadge tone={REPORT_TONE[r.status]}>{r.status}</ToneBadge>
                <a className="font-medium text-(--vm-accent) hover:underline" href={`/runs/${r.run_id}?segment=${encodeURIComponent(r.segment)}`}
                   target="_blank" rel="noreferrer">{r.run_name || r.run_id} · {r.segment}</a>
                <span className="text-(--vm-muted)">{relativeTime(Date.parse(r.created_at), nowMs)}</span>
                <span className="ml-auto flex gap-2">
                  {r.status !== "resolved" && <Button size="sm" variant="outline" onClick={() => update.mutate({ id: r.id, status: "resolved" })}>Resolved</Button>}
                  {r.status !== "dismissed" && <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: r.id, status: "dismissed" })}>Dismiss</Button>}
                  {r.status !== "open" && <Button size="sm" variant="ghost" onClick={() => update.mutate({ id: r.id, status: "open" })}>Reopen</Button>}
                </span>
              </div>
              <p className="mt-1 text-(--vm-fg-2)">
                BioID said: {r.answer.identifier ? `${r.answer.database} ${r.answer.identifier}${r.answer.name ? ` (${r.answer.name})` : ""}` : "not identified"}
                {r.suggestion && <> · reporter says: <b>{r.suggestion}</b></>}
              </p>
              {r.note && <p className="mt-0.5 whitespace-pre-wrap">{r.note}</p>}
            </li>
          ))}
        </ul>
      )}
    </Section>
  );
}
