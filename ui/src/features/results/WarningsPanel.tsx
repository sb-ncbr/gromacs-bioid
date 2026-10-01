import React, { useMemo } from "react";
import { Alert, AlertDescription, AlertTitle } from "@e-infra/design-system";
import type { components } from "../../lib/api/types";
import { CATALOG_STAGES, stageDisplay, stageForCode } from "./error-catalog";
import { buildIssueCopy } from "./utils/issue-copy";

type WarningItem = components["schemas"]["WarningItem"];
type ErrorItem = components["schemas"]["ErrorItem"];

interface NormalizedIssue {
  code: string;
  message: string;
  stepId?: string | null;
  details?: Record<string, unknown> | null;
  critical: boolean;
}

function IssueAlert({ item }: { item: NormalizedIssue }) {
  const copy = buildIssueCopy(item.code, item.message, item.details, item.critical);
  const variant =
    copy.severity === "critical"
      ? "error"
      : copy.severity === "warning"
        ? "warning"
        : "default";
  return (
    <Alert variant={variant}>
      <AlertTitle className="font-semibold">{copy.title}</AlertTitle>
      <AlertDescription className="space-y-1">
        <p>{copy.what}</p>
        {copy.action && <p>{copy.action}</p>}
        {copy.detailsLine && <p className="text-xs text-text-muted">{copy.detailsLine}</p>}
        {copy.technical && (
          <details className="text-xs">
            <summary className="cursor-pointer text-text-muted underline underline-offset-2">
              Technical detail
            </summary>
            <pre className="mt-1 whitespace-pre-wrap rounded bg-black/5 p-2 font-mono">
              {copy.technical}
            </pre>
          </details>
        )}
        <p className="font-mono text-xs text-text-muted/70">{item.code || "unknown"}</p>
      </AlertDescription>
    </Alert>
  );
}

const WarningsPanel: React.FC<{
  warnings?: WarningItem[] | null;
  criticalErrors?: ErrorItem[] | null;
}> = ({ warnings, criticalErrors }) => {
  const { attentionGroups, infoItems } = useMemo(() => {
    const warningsArr: WarningItem[] = Array.isArray(warnings) ? warnings : [];
    const errorsArr: ErrorItem[] = Array.isArray(criticalErrors) ? criticalErrors : [];

    const all: NormalizedIssue[] = [
      ...warningsArr.map((w) => ({
        code: w.code,
        message: w.message,
        stepId: w.step_id,
        details: w.details as Record<string, unknown> | undefined,
        critical: false,
      })),
      ...errorsArr.map((e) => ({
        code: e.code,
        message: e.message,
        stepId: e.step_id,
        details: e.details as Record<string, unknown> | undefined,
        critical: true,
      })),
    ];

    const isInfo = (i: NormalizedIssue) =>
      !i.critical && buildIssueCopy(i.code, i.message, i.details, i.critical).severity === "info";

    const attention = all.filter((i) => !isInfo(i));
    const info = all.filter(isInfo);

    const groups = new Map<string, NormalizedIssue[]>();
    for (const item of attention) {
      const group = stageForCode(item.code, item.stepId);
      const list = groups.get(group) ?? [];
      list.push(item);
      groups.set(group, list);
    }
    const ordered: string[] = [];
    for (const stage of CATALOG_STAGES) {
      if (groups.has(stage.group)) ordered.push(stage.group);
    }
    for (const group of groups.keys()) {
      if (!ordered.includes(group)) ordered.push(group);
    }

    return {
      attentionGroups: ordered.map((group) => ({ group, items: groups.get(group) ?? [] })),
      infoItems: info,
    };
  }, [warnings, criticalErrors]);

  if (attentionGroups.length === 0 && infoItems.length === 0) {
    return (
      <Alert>
        <AlertTitle>No warnings recorded</AlertTitle>
        <AlertDescription>This run did not report warnings or critical errors.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {attentionGroups.map((g) => (
        <section key={g.group} id={`warn-${g.group}`}>
          <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide text-text-muted">
            {stageDisplay(g.group)}
          </h3>
          <div className="space-y-3">
            {g.items.map((item, idx) => (
              <IssueAlert key={`${item.code}-${idx}`} item={item} />
            ))}
          </div>
        </section>
      ))}

      {infoItems.length > 0 && (
        <details className="rounded-lg border border-border p-3">
          <summary className="cursor-pointer text-sm font-semibold text-text-muted">
            Information ({infoItems.length})
          </summary>
          <div className="mt-3 space-y-3">
            {infoItems.map((item, idx) => (
              <IssueAlert key={`info-${item.code}-${idx}`} item={item} />
            ))}
          </div>
        </details>
      )}
    </div>
  );
};

export default WarningsPanel;
