/**
 * /admin — one-page operations dashboard (src_new/api/admin.py). Not linked
 * from the header. Signed out, only the sign-in card renders; signed in, the
 * overview refetches every 5 s while "Live" is on and every action refetches
 * it at once. A section the server could not build shows its error alone.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Button, Card, Label, Skeleton, Switch } from "@e-infra/design-system";
import { LogOut, RefreshCw, TriangleAlert } from "lucide-react";
import { ApiError, apiErrorMessage } from "../lib/api/client";
import { adminApi, isSectionError, isUnauthorized, loadSession, saveSession, type AdminSession } from "../lib/api/admin";
import { relativeTime } from "../features/admin/format";
import { LoginCard } from "../features/admin/LoginCard";
import { TopStrip } from "../features/admin/TopStrip";
import { QueuesSection, WorkersSection } from "../features/admin/QueuesWorkers";
import { DeploymentsSection } from "../features/admin/Deployments";
import { RunsSection } from "../features/admin/Runs";
import { LimitsSection, RetentionSection, StorageSection } from "../features/admin/RetentionStorage";
import { AdminProvider, OVERVIEW_KEY } from "../features/admin/session";

const REFRESH_MS = 5_000;

function useNow(intervalMs: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

function Dashboard({ session, signOut }: { session: AdminSession; signOut: (message?: string) => void }) {
  const [live, setLive] = useState(true);
  const now = useNow(1_000);
  const overview = useQuery({
    queryKey: [...OVERVIEW_KEY, session.token],
    queryFn: async () => {
      try {
        return await adminApi.overview(session.token);
      } catch (err) {
        if (isUnauthorized(err)) signOut(apiErrorMessage(err, "Sign in to the admin page."));
        throw err;
      }
    },
    refetchInterval: live ? REFRESH_MS : false,
    staleTime: 0,
    // 4xx are answers; a 5xx or a dropped connection (API restarting) gets one retry.
    retry: (count, err) => !(err instanceof ApiError && err.status < 500) && count < 1,
  });
  const data = overview.data;
  const ctx = useMemo(
    () => ({
      token: session.token,
      signOut,
      graceDays: data && !isSectionError(data.retention) ? data.retention.grace_days : null,
    }),
    [session.token, signOut, data],
  );

  const controls = (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
      <div className="flex items-center gap-2">
        <Switch id="admin-live" checked={live} onCheckedChange={setLive} />
        <Label htmlFor="admin-live">Live</Label>
      </div>
      <span className="text-sm text-text-muted" aria-live="off">
        {overview.dataUpdatedAt ? `updated ${relativeTime(overview.dataUpdatedAt, now)}` : "loading…"}
      </span>
      <Button
        type="button"
        variant="outline"
        size="sm"
        onClick={() => void overview.refetch()}
        disabled={overview.isFetching}
        aria-label="Refresh now"
      >
        <RefreshCw className={overview.isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden />
        Refresh
      </Button>
      <Button type="button" variant="ghost" size="sm" onClick={() => signOut()}>
        <LogOut className="h-4 w-4" aria-hidden />
        Sign out
      </Button>
    </div>
  );

  return (
    <AdminProvider value={ctx}>
      <div className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-(--vm-fg)">Admin</h1>
            <p className="text-sm text-text-muted">Queues, workers, deployments, runs and retention of this BioID instance.</p>
          </div>
          {controls}
        </div>

        {overview.isError && (
          <div
            role="alert"
            className="flex items-start gap-2 rounded-md border border-(--vm-error-line) bg-(--vm-error-bg) px-3 py-2 text-sm text-(--vm-error)"
          >
            <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            <p>
              {apiErrorMessage(
                overview.error,
                overview.error instanceof ApiError ? "The overview failed to load." : "Could not reach the API.",
              )}
              {data && ` Showing data from ${relativeTime(overview.dataUpdatedAt, now)}.`}
            </p>
          </div>
        )}

        {!data ? (
          overview.isPending ? (
            <div className="space-y-4" aria-busy="true" aria-label="Loading the overview">
              <Skeleton className="h-20 w-full" />
              <div className="grid gap-4 lg:grid-cols-2">
                <Skeleton className="h-48" />
                <Skeleton className="h-48" />
              </div>
              <Skeleton className="h-72 w-full" />
            </div>
          ) : (
            <Card className="items-start gap-3 px-6">
              <Button type="button" onClick={() => void overview.refetch()}>
                Try again
              </Button>
            </Card>
          )
        ) : (
          <>
            <TopStrip overview={data} nowMs={now} />
            <div className="grid gap-4 lg:grid-cols-2">
              <QueuesSection queues={data.queues} />
              <WorkersSection workers={data.workers} nowMs={now} />
            </div>
            <DeploymentsSection deployments={data.deployments} nowMs={now} />
            <RunsSection runs={data.runs} nowMs={now} />
            <div className="grid items-start gap-4 lg:grid-cols-2">
              <RetentionSection retention={data.retention} runs={data.runs} nowMs={now} />
              <div className="grid gap-4">
                <StorageSection storage={data.storage} />
                <LimitsSection limits={data.limits} />
              </div>
            </div>
          </>
        )}
      </div>
    </AdminProvider>
  );
}

export default function AdminPage() {
  const qc = useQueryClient();
  const [session, setSession] = useState<AdminSession | null>(() => loadSession());
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    const previous = document.title;
    document.title = "Admin · MD BioID";
    return () => {
      document.title = previous;
    };
  }, []);

  const signOut = useCallback(
    (msg?: string) => {
      saveSession(null);
      setSession(null);
      setMessage(msg ?? null);
      qc.removeQueries({ queryKey: ["admin"] });
    },
    [qc],
  );

  if (!session) {
    return (
      <LoginCard
        message={message}
        onSignedIn={(s) => {
          saveSession(s);
          setMessage(null);
          setSession(s);
        }}
      />
    );
  }
  return <Dashboard session={session} signOut={signOut} />;
}
