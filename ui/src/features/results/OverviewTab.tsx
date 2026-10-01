import React from "react";
import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { RunStatusResponse, RunSummaryWithTitle, TaskInfo } from "./hooks";

interface OverviewTabProps {
  runId: string;
  status: RunStatusResponse | null;
  summary?: RunSummaryWithTitle | null;
}

function formatTime(value?: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "—" : date.toLocaleString();
}

function formatDuration(
  started: string | null | undefined,
  finished: string | null | undefined,
): string {
  if (!started) return "—";
  const startMs = new Date(started).getTime();
  if (Number.isNaN(startMs)) return "—";
  const endMs = finished ? new Date(finished).getTime() : Date.now();
  if (Number.isNaN(endMs)) return "—";
  const seconds = Math.round((endMs - startMs) / 1000);
  if (seconds < 0) return "—";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

function MetaValue({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-wide text-text-muted">{label}</dt>
      <dd className="mt-1 text-sm font-medium text-text-heading">{value}</dd>
    </div>
  );
}

const OverviewTab: React.FC<OverviewTabProps> = ({ runId, status, summary }) => {
  if (!status) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <Skeleton className="h-10 w-2/3" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  const pipeline = status.pipeline;
  const tasks: TaskInfo[] = Array.isArray(status.tasks) ? status.tasks : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Overview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        <dl className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <MetaValue label="Run" value={`${summary?.run_name?.trim() || runId.slice(0, 8)}…`} />
          <MetaValue label="Status" value={pipeline.status || "—"} />
          <MetaValue label="Input" value={pipeline.input_kind || summary?.input_kind || "—"} />
          <MetaValue label="Started" value={formatTime(pipeline.started_at)} />
          <MetaValue label="Finished" value={formatTime(pipeline.finished_at)} />
          <MetaValue
            label="Warnings / Errors"
            value={`${summary?.warning_count ?? (status.warnings?.length ?? 0)} / ${
              summary?.error_count ?? (status.critical_errors?.length ?? 0)
            }`}
          />
        </dl>

        <div>
          <h3 className="mb-2 text-sm font-semibold text-text-heading">Task durations</h3>
          {tasks.length === 0 ? (
            <p className="text-sm text-text-muted">No task details available yet.</p>
          ) : (
            <ul className="divide-y divide-gray-200 rounded-md border border-gray-200">
              {tasks.map((task) => (
                <li key={task.task_id} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
                  <span className="min-w-0 flex-1 truncate">{task.name}</span>
                  <span className="shrink-0 text-xs uppercase text-text-muted">{task.status}</span>
                  <span className="w-20 shrink-0 text-right tabular-nums text-text-muted">
                    {formatDuration(task.started_at, task.finished_at)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default OverviewTab;
