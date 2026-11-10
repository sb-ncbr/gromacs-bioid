import { useState } from "react";
import { Button, Card, Input, cn } from "@e-infra/design-system";
import { Boxes, Check, FileText, Minus, Plus, RotateCw, TriangleAlert, X } from "lucide-react";
import {
  adminApi,
  isSectionError,
  type AdminOverview,
  type DeploymentError,
  type DeploymentInfo,
  type PodInfo,
} from "../../lib/api/admin";
import { isDeploymentError, relativeTime, toMs } from "./format";
import { PodLogsDialog } from "./PodLogsDialog";
import { useAdminAction } from "./session";
import { ConfirmButton, Empty, Section, SectionErrorNote, ToneBadge } from "./ui";

const API_DEPLOYMENT = "bat3-ceitec-bat3-api";
const WEB_DEPLOYMENT = "bat3-ceitec-bat3-web";

function restartWarning(name: string): string {
  if (name === API_DEPLOYMENT)
    return "This page talks to the API: it may lose its connection for a minute while the new pods start. It reconnects by itself.";
  if (name === WEB_DEPLOYMENT) return "Pages of the web application may fail to load for a moment while the new pods start.";
  if (name.includes("worker"))
    return "Workers stop taking runs and are replaced one by one; runs active on them may be interrupted.";
  return "The pods are replaced one by one.";
}

function ScaleControl({ d }: { d: DeploymentInfo & { scale: [number, number] } }) {
  const [min, max] = d.scale;
  const current = d.replicas ?? 0;
  const [draft, setDraft] = useState<number | null>(null);
  const value = draft ?? current;
  const scale = useAdminAction((token, n: number) => adminApi.scale(token, d.name, n), {
    success: (res) => `${d.name} scaled to ${res.replicas}`,
    failure: "Could not scale the deployment.",
  });
  const clamp = (n: number) => Math.min(max, Math.max(min, n));
  const changed = draft != null && draft !== current;
  return (
    <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label={`Replicas of ${d.name}`}>
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        aria-label="One replica fewer"
        disabled={value <= min}
        onClick={() => setDraft(clamp(value - 1))}
      >
        <Minus className="h-4 w-4" aria-hidden />
      </Button>
      <Input
        type="number"
        inputMode="numeric"
        min={min}
        max={max}
        value={value}
        onChange={(e) => {
          const n = Number(e.target.value);
          if (Number.isFinite(n)) setDraft(clamp(Math.round(n)));
        }}
        aria-label={`Replicas (${min}–${max})`}
        className="h-8 w-16 text-center tabular-nums"
      />
      <Button
        type="button"
        variant="outline"
        size="icon-sm"
        aria-label="One replica more"
        disabled={value >= max}
        onClick={() => setDraft(clamp(value + 1))}
      >
        <Plus className="h-4 w-4" aria-hidden />
      </Button>
      <Button
        type="button"
        size="sm"
        disabled={!changed || scale.isPending}
        onClick={() => scale.mutate(value, { onSuccess: () => setDraft(null) })}
      >
        Apply
      </Button>
      {changed && (
        <Button type="button" variant="ghost" size="sm" onClick={() => setDraft(null)}>
          Reset
        </Button>
      )}
      <span className="text-xs text-text-muted">
        {min}–{max}
      </span>
    </div>
  );
}

function PodRow({ pod, canRestart, nowMs }: { pod: PodInfo; canRestart: boolean; nowMs: number }) {
  const [logsOpen, setLogsOpen] = useState(false);
  const restart = useAdminAction((token, name: string) => adminApi.restartPod(token, name), {
    success: (_, name) => `${name} deleted; Kubernetes starts a replacement`,
    failure: "Could not restart the pod.",
  });
  const tone = pod.deleting ? "muted" : pod.ready ? "ok" : pod.phase === "Pending" ? "warn" : "error";
  return (
    <li className="py-2 first:pt-0 last:pb-0">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <p className="min-w-0 truncate font-mono text-xs text-(--vm-fg)" title={pod.name}>
          {pod.name}
        </p>
        <ToneBadge tone={tone}>
          {pod.ready ? <Check aria-hidden /> : <X aria-hidden />}
          {pod.deleting ? "terminating" : `${pod.phase ?? "?"}${pod.ready ? "" : " · not ready"}`}
        </ToneBadge>
        {pod.waiting && <ToneBadge tone="warn">{pod.waiting}</ToneBadge>}
      </div>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-text-muted">
          <span className={cn(pod.restarts > 0 && "font-medium text-(--vm-attention)")}>
            {pod.restarts} restart{pod.restarts === 1 ? "" : "s"}
          </span>
          {pod.last_exit && <> · last exit {pod.last_exit}</>}
          {" · "}started {relativeTime(toMs(pod.started), nowMs)}
          {pod.node && <> · {pod.node}</>}
        </p>
        <div className="ml-auto flex gap-1.5">
          <Button type="button" variant="outline" size="sm" onClick={() => setLogsOpen(true)} aria-label={`Logs of ${pod.name}`}>
            <FileText className="h-4 w-4" aria-hidden />
            Logs
          </Button>
          {canRestart && (
            <ConfirmButton
              label="Restart"
              ariaLabel={`Restart pod ${pod.name}`}
              icon={RotateCw}
              disabled={pod.deleting || restart.isPending}
              title={`Restart pod ${pod.name}?`}
              description={
                <p>The pod is deleted and Kubernetes starts a replacement. Work running in it is interrupted.</p>
              }
              confirmLabel="Restart pod"
              destructive
              onConfirm={() => restart.mutate(pod.name)}
            />
          )}
        </div>
      </div>
      {logsOpen && <PodLogsDialog pod={pod.name} open={logsOpen} onOpenChange={setLogsOpen} />}
    </li>
  );
}

function DeploymentCard({ d, nowMs }: { d: DeploymentInfo | DeploymentError; nowMs: number }) {
  const restart = useAdminAction((token, name: string) => adminApi.restartDeployment(token, name), {
    success: (_, name) => `Restart of ${name} started`,
    failure: "Could not restart the deployment.",
  });
  if (isDeploymentError(d)) {
    return (
      <Card className="min-w-0 justify-start gap-2 px-4 py-3">
        <h3 className="text-sm font-semibold text-(--vm-fg)">{d.label}</h3>
        <p className="font-mono text-xs text-text-muted">{d.name}</p>
        <SectionErrorNote what="Deployment" error={d.error} />
      </Card>
    );
  }
  const noActions = !d.restartable && !d.scale;
  const healthy = d.replicas != null && d.ready >= d.replicas;
  return (
    <Card className="min-w-0 justify-start gap-0 py-0">
      <div className="space-y-2 border-b border-(--vm-line-2) px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold text-(--vm-fg)">{d.label}</h3>
            <p className="truncate font-mono text-xs text-text-muted" title={`${d.name} · ${d.image}`}>
              {d.name} · {d.image}
            </p>
          </div>
          <ToneBadge tone={d.replicas === 0 ? "muted" : healthy ? "ok" : "warn"} title="ready / desired replicas">
            {d.ready}/{d.replicas ?? "?"} ready
            {d.updated !== d.replicas && d.replicas ? ` · ${d.updated} updated` : ""}
          </ToneBadge>
        </div>
        {noActions ? (
          <p className="flex items-center gap-1.5 text-xs text-(--vm-attention)">
            <TriangleAlert className="h-3.5 w-3.5 shrink-0" aria-hidden />
            No actions from this page (logs only).
          </p>
        ) : (
          <div className="flex flex-wrap items-center justify-between gap-2">
            {d.scale ? <ScaleControl d={d as DeploymentInfo & { scale: [number, number] }} /> : <span />}
            {d.restartable && (
              <ConfirmButton
                label="Restart"
                ariaLabel={`Restart deployment ${d.name}`}
                icon={RotateCw}
                disabled={restart.isPending}
                title={`Restart ${d.label}?`}
                description={
                  <>
                    <p>A rolling restart of {d.name}.</p>
                    <p>{restartWarning(d.name)}</p>
                  </>
                }
                confirmLabel="Restart"
                destructive
                onConfirm={() => restart.mutate(d.name)}
              />
            )}
          </div>
        )}
      </div>
      <div className="px-4 py-3">
        {d.pods.length === 0 ? (
          <Empty>No pods.</Empty>
        ) : (
          <ul className="divide-y divide-(--vm-line-2)" aria-label={`Pods of ${d.name}`}>
            {d.pods.map((p) => (
              <PodRow key={p.name} pod={p} canRestart={!p.name.startsWith("bat3-redis-")} nowMs={nowMs} />
            ))}
          </ul>
        )}
      </div>
    </Card>
  );
}

export function DeploymentsSection({ deployments, nowMs }: { deployments: AdminOverview["deployments"]; nowMs: number }) {
  return (
    <section aria-labelledby="deployments-title" className="min-w-0">
      <h2 id="deployments-title" className="mb-3 flex items-center gap-2 text-base font-semibold text-(--vm-fg)">
        <Boxes className="h-4 w-4 text-(--vm-muted)" aria-hidden />
        Deployments & pods
      </h2>
      {isSectionError(deployments) ? (
        <Section id="deployments-error" title="Kubernetes">
          <SectionErrorNote what="Deployments" error={deployments.error} />
        </Section>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {deployments.map((d) => (
            <DeploymentCard key={d.name} d={d} nowMs={nowMs} />
          ))}
        </div>
      )}
    </section>
  );
}
