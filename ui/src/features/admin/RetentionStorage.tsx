import { Button, Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@e-infra/design-system";
import { Archive, Gauge, HardDrive, Undo2 } from "lucide-react";
import { adminApi, isSectionError, type AdminOverview, type RunsSection } from "../../lib/api/admin";
import { dateTime, formatBytes, isResolverCache, relativeTime, retentionSummary, toMs } from "./format";
import { RunLink } from "./Runs";
import { useAdminAction } from "./session";
import { Empty, Section, SectionErrorNote, Stat, ToneBadge } from "./ui";

function SweepCount({ value, what }: { value: string[] | number; what: string }) {
  const ids = Array.isArray(value) ? value : null;
  return (
    <span title={ids && ids.length ? ids.join(", ") : undefined}>
      {ids ? ids.length : value} {what}
    </span>
  );
}

export function RetentionSection({
  retention,
  runs,
  nowMs,
}: {
  retention: AdminOverview["retention"];
  runs: AdminOverview["runs"];
  nowMs: number;
}) {
  const restore = useAdminAction((token, id: string) => adminApi.restoreRun(token, id), {
    success: (_, id) => `${id} restored (kept indefinitely)`,
    failure: "Could not restore the run.",
  });
  // Examples are never expired (retention.protected_run_ids) though they carry a date.
  const expiring: RunsSection["expiring_soon"] | null = isSectionError(runs)
    ? null
    : runs.expiring_soon.filter((r) => !r.example);

  return (
    <Section id="retention" title="Retention" icon={Archive}>
      {isSectionError(retention) ? (
        <SectionErrorNote what="Retention" error={retention.error} />
      ) : (
        <div className="space-y-4">
          <div>
            {retention.enforce ? (
              <ToneBadge tone="warn">Enforcing: expired runs move to the trash</ToneBadge>
            ) : (
              <ToneBadge tone="info" className="whitespace-normal">
                Report only (BAT3_RETENTION_ENFORCE is off): nothing is deleted
              </ToneBadge>
            )}
          </div>
          <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat label="Default" value={`${retention.default_days} d`} />
            <Stat label="Trash grace" value={`${retention.grace_days} d`} />
            <Stat label="In trash" value={retention.expired.length} />
            <Stat label="Expiring listed" value={expiring ? expiring.length : "—"} />
          </dl>

          <div>
            <h3 className="mb-1 text-sm font-semibold text-(--vm-fg)">Last sweep</h3>
            {retention.last_sweep ? (
              <p className="text-sm text-(--vm-fg-2)">
                {dateTime(toMs(retention.last_sweep.at), nowMs)} ({relativeTime(toMs(retention.last_sweep.at), nowMs)}) ·{" "}
                {retention.last_sweep.enforce ? "enforcing" : "report only"} · {retention.last_sweep.total_runs} runs ·{" "}
                {retention.last_sweep.due} due · <SweepCount value={retention.last_sweep.moved} what="moved" /> ·{" "}
                <SweepCount value={retention.last_sweep.purged} what="purged" />
                {retention.last_sweep.aborted && (
                  <span className="block text-(--vm-error)">Aborted: {retention.last_sweep.aborted}</span>
                )}
              </p>
            ) : (
              <Empty>No sweep recorded yet.</Empty>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-sm font-semibold text-(--vm-fg)">Expiring soon</h3>
            {expiring == null ? (
              <Empty>Runs unavailable.</Empty>
            ) : expiring.length === 0 ? (
              <Empty>Nothing has an expiry date.</Empty>
            ) : (
              <ul className="divide-y divide-(--vm-line-2)">
                {expiring.map((r) => (
                  <li key={r.run_id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-0.5 py-1.5">
                    <RunLink run={r} />
                    <span className="text-xs text-text-muted">{retentionSummary(r.retention, nowMs)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-sm font-semibold text-(--vm-fg)">Trash</h3>
            {retention.expired.length === 0 ? (
              <Empty>The trash is empty.</Empty>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Run</TableHead>
                    <TableHead>Trashed</TableHead>
                    <TableHead>Purged</TableHead>
                    <TableHead className="text-right">
                      <span className="sr-only">Actions</span>
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {retention.expired.map((e) => (
                    <TableRow key={e.run_id}>
                      <TableCell className="font-mono text-xs">{e.run_id}</TableCell>
                      <TableCell className="text-xs text-text-muted">{dateTime(toMs(e.expired_at), nowMs)}</TableCell>
                      <TableCell className="text-xs">
                        {e.purge_at ? (
                          <>
                            {dateTime(toMs(e.purge_at), nowMs)}{" "}
                            <span className="text-text-muted">({relativeTime(toMs(e.purge_at), nowMs)})</span>
                          </>
                        ) : (
                          "—"
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          disabled={restore.isPending && restore.variables === e.run_id}
                          onClick={() => restore.mutate(e.run_id)}
                          aria-label={`Restore ${e.run_id}`}
                        >
                          <Undo2 className="h-4 w-4" aria-hidden />
                          Restore
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
            {retention.expired.length > 0 && (
              <p className="mt-2 text-xs text-text-muted">A restored run is kept indefinitely.</p>
            )}
          </div>
        </div>
      )}
    </Section>
  );
}

export function StorageSection({ storage }: { storage: AdminOverview["storage"] }) {
  return (
    <Section id="storage" title="Storage" icon={HardDrive}>
      {isSectionError(storage) ? (
        <SectionErrorNote what="Storage" error={storage.error} />
      ) : (
        <div className="space-y-4">
          <dl className="grid grid-cols-3 gap-3">
            <Stat label="Runs (all)" value={formatBytes(storage.runs_bytes)} />
            <Stat label="Trash" value={formatBytes(storage.trash_bytes)} />
            <Stat label="Ad hoc" value={formatBytes(storage.adhoc_bytes)} />
          </dl>
          <div>
            <h3 className="mb-1 text-sm font-semibold text-(--vm-fg)">Volumes</h3>
            {storage.pvc_error && <SectionErrorNote what="Volume sizes" error={storage.pvc_error} />}
            {storage.pvcs.length > 0 && (
              <ul className="space-y-0.5 text-sm">
                {storage.pvcs.map((p) => (
                  <li key={p.name} className="flex justify-between gap-3">
                    <span className="min-w-0 truncate font-mono text-xs">{p.name}</span>
                    <span className="tabular-nums">{p.capacity ?? "—"}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <h3 className="mb-1 text-sm font-semibold text-(--vm-fg)">Loose files in the runs folder</h3>
            {storage.loose_files.length === 0 ? (
              <Empty>None.</Empty>
            ) : (
              <ul className="divide-y divide-(--vm-line-2) text-sm">
                {storage.loose_files.map((f) => (
                  <li key={f.name} className="flex items-start justify-between gap-3 py-1">
                    <span className="min-w-0">
                      <span className="block truncate font-mono text-xs" title={f.name}>
                        {f.name}
                      </span>
                      {isResolverCache(f.name) && (
                        <span className="block text-xs text-text-muted">shared search cache (not served publicly)</span>
                      )}
                    </span>
                    <span className="shrink-0 tabular-nums text-xs">{formatBytes(f.bytes)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <p className="text-xs text-text-muted">Sizes are measured at most every 10 minutes.</p>
        </div>
      )}
    </Section>
  );
}

export function LimitsSection({ limits }: { limits: AdminOverview["limits"] }) {
  return (
    <Section id="limits" title="Submission limits" icon={Gauge}>
      {isSectionError(limits) ? (
        <SectionErrorNote what="Limits" error={limits.error} />
      ) : (
        <dl className="grid grid-cols-3 gap-3">
          <Stat label="Per address / hour" value={limits.submit_per_hour} />
          <Stat label="Queue cap" value={limits.queue_cap} />
          <Stat label="Files per run" value={limits.max_files} />
        </dl>
      )}
    </Section>
  );
}
