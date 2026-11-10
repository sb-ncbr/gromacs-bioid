import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  ToggleGroup,
  ToggleGroupItem,
} from "@e-infra/design-system";
import { RefreshCw } from "lucide-react";
import { apiErrorMessage } from "../../lib/api/client";
import { adminApi, isUnauthorized } from "../../lib/api/admin";
import { useAdmin } from "./session";

const TAILS = [300, 1000, 5000] as const;

export function PodLogsDialog({ pod, open, onOpenChange }: { pod: string; open: boolean; onOpenChange: (o: boolean) => void }) {
  const { token, signOut } = useAdmin();
  const [tail, setTail] = useState<number>(300);
  const pre = useRef<HTMLPreElement>(null);
  const logs = useQuery({
    queryKey: ["admin", "logs", pod, tail],
    queryFn: async () => {
      try {
        return await adminApi.podLogs(token, pod, tail);
      } catch (err) {
        if (isUnauthorized(err)) signOut(apiErrorMessage(err, "Sign in to the admin page."));
        throw err;
      }
    },
    enabled: open,
    retry: false,
    staleTime: 0,
    gcTime: 0,
  });

  // Newest lines are at the bottom.
  useEffect(() => {
    if (pre.current) pre.current.scrollTop = pre.current.scrollHeight;
  }, [logs.data]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[90vh] w-[calc(100vw-2rem)] flex-col gap-3 sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle className="pr-6 break-all">Logs: {pod}</DialogTitle>
          <DialogDescription>Last {tail} lines, with timestamps.</DialogDescription>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm text-text-muted" id={`tail-${pod}`}>
            Lines
          </span>
          <ToggleGroup
            type="single"
            variant="outline"
            size="sm"
            value={String(tail)}
            onValueChange={(v) => v && setTail(Number(v))}
            aria-labelledby={`tail-${pod}`}
          >
            {TAILS.map((t) => (
              <ToggleGroupItem key={t} value={String(t)} aria-label={`Last ${t} lines`} className="px-3">
                {t}
              </ToggleGroupItem>
            ))}
          </ToggleGroup>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="ml-auto"
            onClick={() => void logs.refetch()}
            disabled={logs.isFetching}
          >
            <RefreshCw className={logs.isFetching ? "h-4 w-4 animate-spin" : "h-4 w-4"} aria-hidden />
            Refresh
          </Button>
        </div>
        {logs.isError ? (
          <p role="alert" className="text-sm text-(--vm-error)">
            {apiErrorMessage(logs.error, "Could not load the logs.")}
          </p>
        ) : (
          <pre
            ref={pre}
            tabIndex={0}
            aria-label={`Log output of ${pod}`}
            aria-busy={logs.isFetching}
            className="min-h-48 flex-1 overflow-auto rounded-md border border-(--vm-line) bg-(--vm-surface-2) p-3 font-mono text-[12px] leading-snug whitespace-pre text-(--vm-fg)"
          >
            {logs.isPending ? "Loading…" : logs.data || "(no output)"}
          </pre>
        )}
      </DialogContent>
    </Dialog>
  );
}
