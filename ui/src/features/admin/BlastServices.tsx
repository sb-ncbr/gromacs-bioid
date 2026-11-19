/**
 * BLAST services with a copy of one database on node-local NVMe (2026-11-19):
 * what each serves, what it is downloading, and whether workers use it.
 * Workers search a database on its service only while it is ready with the
 * release the NFS symlink points to; otherwise on NFS. The NVMe copy can be
 * turned off (the service stops and its volume is deleted: NVMe is
 * expensive) and on again (a new volume; the database is copied from NFS).
 */
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@e-infra/design-system";
import { HardDrive, Power, PowerOff } from "lucide-react";
import { adminApi, isSectionError, type AdminOverview, type BlastService } from "../../lib/api/admin";
import { useAdminAction } from "./session";
import { ConfirmButton, Empty, Section, SectionErrorNote, ToneBadge } from "./ui";

function gb(bytes?: number): string {
  return bytes == null ? "–" : `${(bytes / 1e9).toFixed(0)} GB`;
}

function NvmeControl({ s }: { s: BlastService }) {
  const toggle = useAdminAction((token, on: boolean) => adminApi.blastNvme(token, s.db, on), {
    success: (res) => `NVMe copy of ${res.db} turned ${res.on ? "on: copying from NFS" : "off"}`,
    failure: "Could not change the NVMe copy.",
  });
  const nv = s.nvme;
  if (!nv || nv.on === null) return <span className="text-xs text-(--vm-muted)">–</span>;
  if (nv.volume === "deleting") return <ToneBadge tone="muted">freeing NVMe…</ToneBadge>;
  return nv.on ? (
    <ConfirmButton
      label="Turn off"
      ariaLabel={`Turn off the NVMe copy of ${s.db}`}
      icon={PowerOff}
      disabled={toggle.isPending}
      title={`Turn off the NVMe copy of ${s.db}?`}
      description={
        <>
          <p>The {s.db} service stops and its NVMe volume ({nv.size}) is deleted. Searches of {s.db} go to NFS.</p>
          <p>Turning it on again copies the database from NFS, which takes hours for nr and nt.</p>
        </>
      }
      confirmLabel="Turn off and free NVMe"
      destructive
      onConfirm={() => toggle.mutate(false)}
    />
  ) : (
    <ConfirmButton
      label="Turn on"
      ariaLabel={`Turn on the NVMe copy of ${s.db}`}
      icon={Power}
      disabled={toggle.isPending}
      title={`Turn on the NVMe copy of ${s.db}?`}
      description={
        <p>A {nv.size} NVMe volume is created and the service copies {s.db} from NFS (hours for nr and nt);
          searches use it once the copy is complete.</p>
      }
      confirmLabel="Turn on"
      onConfirm={() => toggle.mutate(true)}
    />
  );
}

function StateBadge({ s }: { s: BlastService }) {
  if (s.nvme?.on === false) return <ToneBadge tone="muted">off (NFS)</ToneBadge>;
  if (s.used_by_workers) return <ToneBadge tone="ok">serving</ToneBadge>;
  if (s.state === "ready") return <ToneBadge tone="info" title="ready, but NFS points to another release">ready, not used</ToneBadge>;
  if (s.state === "staging") return <ToneBadge tone="muted">{s.staging?.finished ? "downloaded" : "downloading"}</ToneBadge>;
  return <ToneBadge tone="error">{s.state}</ToneBadge>;
}

function Progress({ s }: { s: BlastService }) {
  const st = s.staging;
  if (!st || st.total_bytes == null || st.finished) return <>{st?.finished ? "done" : "–"}</>;
  const files = st.files_total ? ` · ${st.files_done ?? 0}/${st.files_total} files` : "";
  return <>{gb(st.done_bytes)} / {gb(st.total_bytes)}{files}</>;
}

export function BlastServicesSection({ services }: { services: AdminOverview["blast_services"] }) {
  return (
    <Section id="blast-services" title="BLAST databases on NVMe" icon={HardDrive}>
      {!services ? (
        <Empty>Not reported by this API version.</Empty>
      ) : isSectionError(services) ? (
        <SectionErrorNote what="BLAST services" error={services.error} />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Database</TableHead>
              <TableHead>State</TableHead>
              <TableHead>Serves</TableHead>
              <TableHead>NFS points to</TableHead>
              <TableHead>Download / copy</TableHead>
              <TableHead className="text-right">Searches</TableHead>
              <TableHead className="text-right">NVMe copy</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {services.map((s) => (
              <TableRow key={s.db}>
                <TableCell className="font-medium">{s.db}</TableCell>
                <TableCell>
                  <StateBadge s={s} />
                  {s.error && <div className="mt-1 max-w-80 truncate text-xs text-(--vm-error)" title={s.error}>{s.error}</div>}
                </TableCell>
                <TableCell className="text-xs">{s.release ?? "–"}{s.prefetch && s.prefetch !== s.release ? <div className="text-(--vm-muted)">next: {s.prefetch}</div> : null}</TableCell>
                <TableCell className="text-xs">{s.nfs_release ?? "–"}</TableCell>
                <TableCell className="text-xs"><Progress s={s} /></TableCell>
                <TableCell className="text-right text-xs">
                  {s.counts ? `${s.counts.searches} done · ${s.counts.running} running · ${s.counts.waiting} waiting` : "–"}
                  {s.counts && (s.counts.timeouts > 0 || s.counts.failures > 0) ? (
                    <div className="text-(--vm-attention)">{s.counts.timeouts} timeouts · {s.counts.failures} failures</div>
                  ) : null}
                </TableCell>
                <TableCell className="text-right"><NvmeControl s={s} /></TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Section>
  );
}
