import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { IdentifiersResponse } from "./hooks";

export interface IdentifiersTabProps {
  runId: string;
  segment: string;
  onSegmentChange: (segment: string) => void;
  segments: string[];
  identifiers: IdentifiersResponse | null;
}

/** Placeholder — replaced by the identifier hits table in the results-tabs deliverable. */
const IdentifiersTab: React.FC<IdentifiersTabProps> = ({ segment, identifiers }) => {
  const hits = identifiers?.hits?.length ?? 0;
  const failed = identifiers?.failed_resolvers?.length ?? 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Identifiers — segment {segment}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-text-muted">
          {hits} hit(s), {failed} failed resolver(s).
        </p>
        <Skeleton className="h-24 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
};

export default IdentifiersTab;
