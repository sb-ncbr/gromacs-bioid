import { useState } from "react";
import { Link } from "react-router-dom";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
  Skeleton,
} from "@e-infra/design-system";
import {
  Clock,
  ExternalLink,
  Inbox,
  RefreshCw,
  Trash2,
} from "lucide-react";
import {
  formatCreated,
  queueChipText,
  runTitle,
  statusStyle,
} from "./status";
import { api, endpoints } from "../../lib/api/client";

interface RunItem {
  run_id: string;
  status: string;
  created_at: string;
  input_kind?: string | null;
  run_name?: string | null;
  creator_ip?: string | null;
}
interface RunListResponse {
  runs?: RunItem[];
}
interface QueueState {
  state?: string;
  position?: number | null;
  ahead?: number | null;
}

/** "in queue" chip — fetched lazily, only for pending runs. */
function QueueChip({ runId, status }: { runId: string; status: string }) {
  const pending = status === "pending" || status === "queued";
  const q = useQuery({
    queryKey: ["runQueue", runId],
    queryFn: () => api.get<QueueState>(endpoints.runQueue(runId)),
    enabled: pending,
    retry: 0,
    refetchInterval: 15_000,
  });
  if (!pending) return null;
  const text = queueChipText(q.data);
  return (
    <Badge variant="outline" className="flex items-center gap-1 text-gray-500">
      <Clock className="h-3 w-3" />
      {text}
    </Badge>
  );
}

function RunRow({ run }: { run: RunItem }) {
  const qc = useQueryClient();
  const [pending, setPending] = useState<"rerun" | "delete" | null>(null);
  const st = statusStyle(run.status);
  const title = runTitle(run);

  const rerun = useMutation({
    mutationFn: () => api.postJson(endpoints.runRerun(run.run_id), {}),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["myRuns"] }),
  });
  const del = useMutation({
    mutationFn: () => api.delete(endpoints.run(run.run_id)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["myRuns"] }),
  });
  const busy = rerun.isPending || del.isPending;

  return (
    <li className="flex flex-col gap-3 rounded-lg border border-base-200 bg-surface-raised/40 px-4 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/runs/${encodeURIComponent(run.run_id)}`}
            className="truncate text-base font-medium text-text no-underline hover:text-primary"
            title={title}
          >
            {title}
          </Link>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-text-muted">
            <span>{formatCreated(run.created_at)}</span>
            <span aria-hidden>·</span>
            <span>{run.run_id.slice(0, 8)}…</span>
          </div>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-2">
          <Badge variant={st.variant} className={st.className}>
            {st.label}
          </Badge>
          <QueueChip runId={run.run_id} status={run.status} />
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          asChild
          type="button"
          variant="outline"
          size="sm"
        >
          <Link to={`/runs/${encodeURIComponent(run.run_id)}`}>
            <ExternalLink className="mr-1 h-3.5 w-3.5" />
            View
          </Link>
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() => setPending("rerun")}
        >
          <RefreshCw className="mr-1 h-3.5 w-3.5" />
          Rerun
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={busy}
          onClick={() => setPending("delete")}
        >
          <Trash2 className="mr-1 h-3.5 w-3.5" />
          Delete
        </Button>
      </div>

      {/* Rerun confirm */}
      <AlertDialog
        open={pending === "rerun"}
        onOpenChange={(o) => {
          if (!o) setPending(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Rerun this annotation?</AlertDialogTitle>
            <AlertDialogDescription>
              Re-queue this annotation with the same files and settings? A new
              run is created; the original is left untouched.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                setPending(null);
                rerun.mutate();
              }}
            >
              Rerun
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete confirm */}
      <AlertDialog
        open={pending === "delete"}
        onOpenChange={(o) => {
          if (!o) setPending(null);
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this annotation?</AlertDialogTitle>
            <AlertDialogDescription>
              This permanently removes the run and all of its results. This
              cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              className="text-error-600"
              onClick={() => {
                setPending(null);
                del.mutate();
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}

/** IP-bound recent annotations (GET /runs?mine=1). No re-run-all. */
export default function Recents() {
  const q = useQuery({
    queryKey: ["myRuns", { mine: 1 }],
    queryFn: () => api.get<RunListResponse>(endpoints.runs, { mine: 1 }),
    retry: 0,
    refetchInterval: 20_000,
  });

  const runs = q.data?.runs ?? [];

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle>Your annotations</CardTitle>
        <CardDescription>
          Recent runs from this browser.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex-1">
        {q.isPending ? (
          <div className="flex flex-col gap-3">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-16 w-full rounded-lg" />
            ))}
          </div>
        ) : runs.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-base-300 px-4 py-10 text-center">
            <Inbox className="h-8 w-8 text-text-muted" />
            <p className="text-sm text-text-muted">
              No annotations from this browser yet.
            </p>
          </div>
        ) : (
          <ul className="flex flex-col gap-3">
            {runs.map((run) => (
              <RunRow key={run.run_id} run={run} />
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
