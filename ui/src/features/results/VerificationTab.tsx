import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { VerificationResponse } from "./hooks";

export interface VerificationTabProps {
  runId: string;
  segment: string;
  verification: VerificationResponse | null;
  onJumpToIdentifiers: () => void;
}

/** Placeholder — replaced by the full hits table in the results-tabs deliverable. */
const VerificationTab: React.FC<VerificationTabProps> = ({ segment, verification }) => {
  const hits = verification?.hits?.length ?? 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Verification — segment {segment}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-text-muted">{hits} verified hit(s) available.</p>
        <Skeleton className="h-24 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
};

export default VerificationTab;
