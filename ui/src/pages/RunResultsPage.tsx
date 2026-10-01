import { useParams, useSearchParams } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@e-infra/design-system";
import { parseRunQuery } from "../lib/nav";

export default function RunResultsPage() {
  const { runId } = useParams<{ runId: string }>();
  const [searchParams] = useSearchParams();
  const { segment, tab } = parseRunQuery(searchParams.toString());

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Card>
        <CardHeader>
          <CardTitle>Run results</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2">
          <p className="text-text-muted">
            Results experience is being rebuilt in this redesign wave.
          </p>
          <dl className="grid grid-cols-1 gap-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="font-semibold text-text-heading">Run</dt>
              <dd className="font-mono text-text-muted">{runId}</dd>
            </div>
            <div>
              <dt className="font-semibold text-text-heading">Segment</dt>
              <dd className="font-mono text-text-muted">{segment}</dd>
            </div>
            <div>
              <dt className="font-semibold text-text-heading">Tab</dt>
              <dd className="font-mono text-text-muted">{tab}</dd>
            </div>
          </dl>
        </CardContent>
      </Card>
    </div>
  );
}
