import { Alert, AlertDescription, AlertTitle, Skeleton } from "@e-infra/design-system";

export interface WarningsPanelProps {
  warnings?: unknown[] | null;
  criticalErrors?: unknown[] | null;
}

/**
 * Placeholder — replaced by the real error-catalog-bound panel in the
 * warnings-panel deliverable.
 */
const WarningsPanel: React.FC<WarningsPanelProps> = ({ warnings, criticalErrors }) => {
  const w = Array.isArray(warnings) ? warnings.length : 0;
  const e = Array.isArray(criticalErrors) ? criticalErrors.length : 0;
  return (
    <div className="space-y-3">
      <Alert>
        <AlertTitle>Warnings</AlertTitle>
        <AlertDescription>
          {w} warning(s), {e} critical error(s) recorded — grouped view lands in the next wave.
        </AlertDescription>
      </Alert>
      <Skeleton className="h-24 w-full rounded-lg" />
    </div>
  );
};

export default WarningsPanel;
