import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { RunStatusResponse } from "./hooks";

export interface OverviewTabProps {
  runId: string;
  status: RunStatusResponse | null | undefined;
}

/** Placeholder — replaced by the full overview in the results-tabs deliverable. */
const OverviewTab: React.FC<OverviewTabProps> = ({ runId, status }) => {
  const pipeline = status?.pipeline;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Overview</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
          <div>
            <dt className="font-semibold text-text-heading">Run</dt>
            <dd className="font-mono text-text-muted">{runId.slice(0, 8)}…</dd>
          </div>
          <div>
            <dt className="font-semibold text-text-heading">Status</dt>
            <dd>{pipeline?.status ?? "—"}</dd>
          </div>
          <div>
            <dt className="font-semibold text-text-heading">Input</dt>
            <dd>{pipeline?.input_kind ?? "—"}</dd>
          </div>
        </dl>
        <Skeleton className="h-24 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
};

export default OverviewTab;
