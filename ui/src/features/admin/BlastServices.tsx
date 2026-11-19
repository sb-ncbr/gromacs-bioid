/**
 * BLAST services with a copy of one database on node-local NVMe (2026-11-19):
 * what each serves, what it is downloading, and whether workers use it.
 * Workers search a database on its service only while it is ready with the
 * release the NFS symlink points to; otherwise on NFS.
 */
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@e-infra/design-system";
import { HardDrive } from "lucide-react";
import { isSectionError, type AdminOverview, type BlastService } from "../../lib/api/admin";
import { Empty, Section, SectionErrorNote, ToneBadge } from "./ui";

function gb(bytes?: number): string {
  return bytes == null ? "–" : `${(bytes / 1e9).toFixed(0)} GB`;
}

function StateBadge({ s }: { s: BlastService }) {
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
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Section>
  );
}
