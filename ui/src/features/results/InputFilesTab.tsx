import { Card, CardContent, CardHeader, CardTitle, Skeleton } from "@e-infra/design-system";
import type { LoadingInfoResponse } from "./hooks";

export interface InputFilesTabProps {
  runId: string;
  loading: LoadingInfoResponse | null;
  inputFiles: Record<string, string> | null;
  files: string[];
}

/** Placeholder — replaced by the full input/files view in the results-tabs deliverable. */
const InputFilesTab: React.FC<InputFilesTabProps> = ({ runId, loading, inputFiles, files }) => {
  const inputCount = inputFiles ? Object.keys(inputFiles).length : 0;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Input &amp; Files</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="text-sm text-text-muted">
          {loading
            ? `Input kind: ${loading.input_kind ?? "—"} · ${inputCount} input file(s), ${files.length} run file(s).`
            : `Run ${runId.slice(0, 8)}: loading information not available yet.`}
        </p>
        <Skeleton className="h-24 w-full rounded-lg" />
      </CardContent>
    </Card>
  );
};

export default InputFilesTab;
