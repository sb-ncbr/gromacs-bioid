import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { SignaturesResponse } from "./hooks";

export interface SignaturesTabProps {
  runId: string;
  segment: string;
  onSegmentChange: (segment: string) => void;
  segments: string[];
  signatures: SignaturesResponse | null;
}

/** Placeholder — replaced by the grouped signature buttons in the results-tabs deliverable. */
const SignaturesTab: React.FC<SignaturesTabProps> = ({ segment, signatures }) => {
  const count = signatures?.signatures?.length ?? 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Signatures — segment {segment}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-text-muted">
          {count > 0 ? `${count} signature(s) available.` : "No signatures loaded yet."}
        </p>
        <Skeleton className="h-24 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
};

export default SignaturesTab;
