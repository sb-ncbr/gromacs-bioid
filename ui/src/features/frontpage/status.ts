/**
 * Display helpers for the IP-bound "recents" list.
 * Copy tone: plain language for a biologist audience. Statuses map to a
 * coloured Badge (pending gray / running blue / success green / failed red /
 * warning amber). No raw codes, paths or exception text reach the user.
 */

export type StatusVariant = "default" | "error" | "secondary" | "outline";

export interface StatusStyle {
  variant: StatusVariant;
  className: string;
  label: string;
}

/** Map a pipeline status string to a Badge variant + Tailwind color classes. */
export function statusStyle(status: string | null | undefined): StatusStyle {
  const s = (status || "").toLowerCase();
  switch (s) {
    case "pending":
    case "queued":
      return { variant: "outline", className: "text-gray-600", label: "Queued" };
    case "running":
      return { variant: "secondary", className: "text-blue-700", label: "Running" };
    case "success":
    case "completed":
    case "done":
      return { variant: "default", className: "text-white", label: "Completed" };
    case "failed":
    case "error":
      return { variant: "error", className: "", label: "Failed" };
    case "warning":
      return { variant: "secondary", className: "text-amber-700", label: "Needs review" };
    case "cancelled":
      return { variant: "outline", className: "text-gray-500", label: "Cancelled" };
    default:
      return { variant: "outline", className: "text-text-muted", label: "Unknown" };
  }
}

/**
 * Human-readable title for a run: run_name -> input_kind -> short id.
 * Short id is the first 8 hex chars + "…".
 */
export function runTitle(run: {
  run_name?: string | null;
  input_kind?: string | null;
  run_id: string;
}): string {
  if (run.run_name && run.run_name.trim()) return run.run_name.trim();
  if (run.input_kind && run.input_kind.trim()) {
    return run.input_kind
      .replace(/[_-]+/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());
  }
  return run.run_id.slice(0, 8) + "…";
}

/** Format an ISO timestamp as a short local date+time, or "—" if invalid. */
export function formatCreated(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const date = d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
  const time = d.toLocaleTimeString(undefined, {
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${date} · ${time}`;
}

/** Compact "in queue" chip text from a queue-state payload. */
export function queueChipText(q: {
  state?: string;
  position?: number | null;
  ahead?: number | null;
} | null | undefined): string {
  if (!q || !q.state) return "in queue";
  if (q.position != null && q.position > 1) {
    return `in queue · #${q.position}`;
  }
  if (q.ahead != null && q.ahead > 0) {
    return `in queue · ${q.ahead} ahead`;
  }
  if (q.state === "running") return "starting…";
  return "in queue";
}
