import React, { useMemo } from "react";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@e-infra/design-system";
import { cn } from "@e-infra/design-system";

/** A single pipeline task as returned by the API. */
export interface TaskInfo {
  task_id: string;
  name: string;
  status: "pending" | "running" | "success" | "failed" | "warning" | "skipped" | string;
  started_at?: string | null;
  finished_at?: string | null;
}

export interface StageGroup {
  id: string;
  display: string;
  tasks: string[];
}

/** The 5 canonical stage groups (source: errors/error-catalog.json). */
export const STAGE_GROUPS: StageGroup[] = [
  {
    id: "prepare",
    display: "Prepare structure",
    tasks: ["discover_input", "load_simulation", "repair_topology", "unwrap_periodic_boundaries", "analyze_universe"],
  },
  {
    id: "signatures",
    display: "Generate signatures",
    tasks: ["generate_signatures"],
  },
  {
    id: "identify",
    display: "Identify molecules",
    tasks: ["identify_molecules"],
  },
  {
    id: "verify",
    display: "Verify results",
    tasks: ["verify_results"],
  },
  {
    id: "export",
    display: "Export results",
    tasks: ["export_results", "render_png"],
  },
];

type Severity = "completed" | "running" | "warning" | "failed" | "pending";

const SEVERITY_RANK: Record<Severity, number> = {
  failed: 5,
  warning: 4,
  running: 3,
  pending: 2,
  completed: 1,
};

const SEVERITY_STYLES: Record<Severity, { dot: string; ring: string; label: string }> = {
  completed: { dot: "bg-green-500", ring: "ring-green-400", label: "Completed" },
  running: { dot: "bg-blue-500 animate-pulse", ring: "ring-blue-400", label: "Running" },
  warning: { dot: "bg-orange-500", ring: "ring-orange-400", label: "Warning" },
  failed: { dot: "bg-red-500", ring: "ring-red-400", label: "Failed" },
  pending: { dot: "bg-gray-400", ring: "", label: "Pending" },
};

function taskSeverity(status: string): Severity {
  switch (status) {
    case "success":
      return "completed";
    case "running":
      return "running";
    case "warning":
      return "warning";
    case "failed":
      return "failed";
    default:
      return "pending"; // pending, skipped, unknown
  }
}

function worstSeverity(tasks: TaskInfo[]): Severity {
  let worst: Severity = "pending";
  let worstRank = 0;
  for (const t of tasks) {
    const s = taskSeverity(t.status);
    if (SEVERITY_RANK[s] > worstRank) {
      worstRank = SEVERITY_RANK[s];
      worst = s;
    }
  }
  return worst;
}

function formatDuration(started: string | null | undefined, finished: string | null | undefined): string {
  if (!started) return "—";
  const s = new Date(started).getTime();
  const e = finished ? new Date(finished).getTime() : Date.now();
  const secs = Math.round((e - s) / 1000);
  if (secs < 60) return `${secs}s`;
  const m = Math.floor(secs / 60);
  const rem = secs % 60;
  return `${m}m ${rem}s`;
}

export interface TaskBarProps {
  tasks: TaskInfo[];
  onGroupClick?: (groupId: string) => void;
}

const TaskBar: React.FC<TaskBarProps> = ({ tasks, onGroupClick }) => {
  const taskMap = useMemo(() => {
    const map = new Map<string, TaskInfo>();
    for (const t of tasks) map.set(t.task_id, t);
    return map;
  }, [tasks]);

  const ungrouped = useMemo(
    () => tasks.filter((t) => !STAGE_GROUPS.some((g) => g.tasks.includes(t.task_id))),
    [tasks],
  );

  return (
    <TooltipProvider delayDuration={200}>
      <div className="flex flex-wrap items-center gap-3" role="navigation" aria-label="Pipeline stages">
        {STAGE_GROUPS.map((group, idx) => {
          const groupTasks = group.tasks
            .map((id) => taskMap.get(id))
            .filter((t): t is TaskInfo => t !== undefined);

          const severity = groupTasks.length > 0 ? worstSeverity(groupTasks) : "pending";
          const style = SEVERITY_STYLES[severity];

          return (
            <Tooltip key={group.id}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => onGroupClick?.(group.id)}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border border-gray-200 px-3 py-2",
                    "text-sm font-medium text-gray-800 transition-colors hover:bg-gray-50 cursor-pointer",
                  )}
                  aria-label={`${group.display} – ${style.label}`}
                >
                  <span className={cn("h-2.5 w-2.5 rounded-full", style.dot)} />
                  <span>
                    {idx + 1}. {group.display}
                  </span>
                </button>
              </TooltipTrigger>
              <TooltipContent side="bottom" className="max-w-xs">
                <p className="font-semibold text-xs mb-1">{group.display}</p>
                {groupTasks.length === 0 && <p className="text-xs text-gray-500">No tasks</p>}
                {groupTasks.map((t) => (
                  <div key={t.task_id} className="flex items-center gap-2 text-xs">
                    <span
                      className={cn("h-1.5 w-1.5 rounded-full", SEVERITY_STYLES[taskSeverity(t.status)].dot)}
                    />
                    <span className="flex-1">{t.name}</span>
                    <span className="text-gray-500 tabular-nums">
                      {formatDuration(t.started_at, t.finished_at)}
                    </span>
                  </div>
                ))}
              </TooltipContent>
            </Tooltip>
          );
        })}

        {/* Ungrouped rail – tasks not in any known group */}
        {ungrouped.length > 0 && (
          <div className="flex items-center gap-2 ml-2 pl-3 border-l border-gray-200">
            <span className="text-xs text-gray-500">Other:</span>
            {ungrouped.map((t) => (
              <Tooltip key={t.task_id}>
                <TooltipTrigger asChild>
                  <span
                    className={cn(
                      "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
                      "bg-gray-100 text-gray-600 cursor-default",
                    )}
                  >
                    <span className={cn("h-1.5 w-1.5 rounded-full", SEVERITY_STYLES[taskSeverity(t.status)].dot)} />
                    {t.name}
                  </span>
                </TooltipTrigger>
                <TooltipContent side="bottom">
                  <p className="text-xs">{t.name} · {formatDuration(t.started_at, t.finished_at)}</p>
                </TooltipContent>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
    </TooltipProvider>
  );
};

export default TaskBar;
