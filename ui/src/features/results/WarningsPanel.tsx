import React, { useMemo } from "react";
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@e-infra/design-system";
import type { components } from "../../lib/api/types";
import {
  CATALOG_STAGES,
  getCatalogEntry,
  interpolate,
  formatDetails,
  stageDisplay,
  stageForCode,
  titleCase,
} from "./error-catalog";

type WarningItem = components["schemas"]["WarningItem"];
type ErrorItem = components["schemas"]["ErrorItem"];

interface NormalizedIssue {
  code: string;
  message: string;
  stepId?: string | null;
  details?: Record<string, unknown>;
  critical: boolean;
}

interface GroupedIssue {
  group: string;
  items: NormalizedIssue[];
}

const WarningsPanel: React.FC<{
  warnings?: WarningItem[] | null;
  criticalErrors?: ErrorItem[] | null;
}> = ({ warnings, criticalErrors }) => {
  const grouped = useMemo<GroupedIssue[]>(() => {
    const warningsArr: WarningItem[] = Array.isArray(warnings) ? warnings : [];
    const errorsArr: ErrorItem[] = Array.isArray(criticalErrors) ? criticalErrors : [];

    const items: NormalizedIssue[] = [
      ...warningsArr.map((w) => ({
        code: w.code,
        message: w.message,
        stepId: w.step_id,
        details: w.details,
        critical: false,
      })),
      ...errorsArr.map((e) => ({
        code: e.code,
        message: e.message,
        stepId: e.step_id,
        details: e.details,
        critical: true,
      })),
    ];

    const groups = new Map<string, NormalizedIssue[]>();
    for (const item of items) {
      const group = stageForCode(item.code, item.stepId);
      const list = groups.get(group) ?? [];
      list.push(item);
      groups.set(group, list);
    }

    const ordered: string[] = [];
    for (const stage of CATALOG_STAGES) {
      if (groups.has(stage.group)) {
        ordered.push(stage.group);
      }
    }
    for (const group of groups.keys()) {
      if (!ordered.includes(group)) {
        ordered.push(group);
      }
    }

    return ordered.map((group) => ({
      group,
      items: groups.get(group) ?? [],
    }));
  }, [warnings, criticalErrors]);

  if (grouped.length === 0) {
    return (
      <Alert>
        <AlertTitle>No warnings recorded</AlertTitle>
        <AlertDescription>
          This run did not report warnings or critical errors.
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-4">
        {grouped.map((g) => (
          <div key={g.group} id={`warn-${g.group}`}>
            <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-muted">
              {stageDisplay(g.group)}
            </h3>
            <div className="space-y-3">
              {g.items.map((item, idx) => {
                const entry = getCatalogEntry(item.code);
                const known = Boolean(entry);
                const severity = item.critical
                  ? "critical"
                  : entry?.kind ?? "warning";
                const variant =
                  severity === "critical"
                    ? "error"
                    : severity === "warning"
                      ? "warning"
                      : "default";
                const title = known && entry ? entry.user_title : titleCase(item.code || "Unknown issue");
                const what = known && entry
                  ? interpolate(entry.user_what, item.details)
                  : item.message;
                const action =
                  known && entry && entry.user_action
                    ? interpolate(entry.user_action, item.details)
                    : null;
                const detailsLine =
                  known && entry
                    ? formatDetails(entry, item.details)
                    : "";
                const rawCode = item.code || "unknown";

                return (
                  <Alert key={`${item.code}-${idx}`} variant={variant}>
                    <AlertTitle className="font-semibold">
                      {title}
                    </AlertTitle>
                    <AlertDescription className="space-y-1">
                      <p>{what}</p>
                      {action && <p>{action}</p>}
                      {detailsLine && (
                        <p className="text-xs text-text-muted">{detailsLine}</p>
                      )}
                      <p className="font-mono text-xs text-text-muted">{rawCode}</p>
                      {!known && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="cursor-help text-xs underline">
                              details on hover
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            <pre className="max-w-xs whitespace-pre-wrap font-mono text-xs">
                              {item.details
                                ? JSON.stringify(item.details, null, 2)
                                : "No additional details."}
                            </pre>
                          </TooltipContent>
                        </Tooltip>
                      )}
                    </AlertDescription>
                  </Alert>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </TooltipProvider>
  );
};

export default WarningsPanel;
