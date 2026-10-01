import React, { useMemo } from "react";
import {
  Badge,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@e-infra/design-system";
import { Info } from "lucide-react";
import { cn } from "@e-infra/design-system";
import type { components } from "../../lib/api/types";
import { resolveHitUrl } from "./utils";

type IdentifierHit = components["schemas"]["IdentifierHit"];
type IdentifiersResponse = components["schemas"]["IdentifiersResponse"];
type ResolverErrorItem = components["schemas"]["ResolverErrorItem"];

interface IdentifiersTabProps {
  segment: string;
  onSegmentChange: (segment: string) => void;
  segments: string[];
  identifiers: IdentifiersResponse | null;
}

const METRIC_KEYS: { key: keyof IdentifierHit; label: string }[] = [
  { key: "score", label: "Score" },
  { key: "evalue", label: "E-value" },
  { key: "bit_score", label: "Bit Score" },
  { key: "identity_percent", label: "Identity %" },
  { key: "coverage_percent", label: "Coverage %" },
];

function formatMetric(value: number | null | undefined): string {
  if (value == null) return "—";
  if (value < 0.01 && value > 0) return value.toExponential(2);
  return value.toFixed(value < 10 ? 2 : 1);
}

const IdentifiersTab: React.FC<IdentifiersTabProps> = ({
  segment,
  onSegmentChange,
  segments,
  identifiers,
}) => {
  const options = segments.length > 0 ? segments : [segment];
  const hits: IdentifierHit[] = useMemo(
    () => identifiers?.hits ?? [],
    [identifiers],
  );
  const attemptedResolvers: string[] = useMemo(
    () => identifiers?.attempted_resolvers ?? [],
    [identifiers],
  );
  const failedResolvers: ResolverErrorItem[] = useMemo(
    () => identifiers?.failed_resolvers ?? [],
    [identifiers],
  );

  // Determine which metric columns have at least one non-null value
  const visibleMetrics = useMemo(() => {
    return METRIC_KEYS.filter((m) => hits.some((h) => h[m.key] != null));
  }, [hits]);

  // Build map of failed resolver messages for tooltips
  const failedMap = useMemo(() => {
    const map = new Map<string, string[]>();
    for (const f of failedResolvers) {
      const existing = map.get(f.resolver_name) ?? [];
      existing.push(f.message);
      map.set(f.resolver_name, existing);
    }
    return map;
  }, [failedResolvers]);

  const allResolverNames = useMemo(() => {
    const set = new Set<string>(attemptedResolvers);
    for (const f of failedResolvers) set.add(f.resolver_name);
    return Array.from(set);
  }, [attemptedResolvers, failedResolvers]);

  return (
    <TooltipProvider delayDuration={150}>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-2">
            <CardTitle>Identifiers</CardTitle>
            <Badge variant="outline">segment {segment}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Segment select */}
          <div className="flex flex-wrap gap-1.5" role="listbox" aria-label="Identifier segment">
            {options.map((s) => (
              <button
                key={s}
                type="button"
                onClick={() => onSegmentChange(s)}
                className={cn(
                  "rounded-md border px-2.5 py-1 text-xs transition-colors",
                  s === segment
                    ? "border-[#2E7D32] bg-[#2E7D32]/10 font-medium text-[#1b5e20]"
                    : "border-gray-200 bg-white text-gray-600 hover:bg-gray-50",
                )}
              >
                {s}
              </button>
            ))}
          </div>

          {/* Failed resolvers chips */}
          {allResolverNames.length > 0 && (
            <div>
              <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-text-muted">
                Resolvers
              </h4>
              <div className="flex flex-wrap gap-1.5">
                {allResolverNames.map((name) => {
                  const failures = failedMap.get(name);
                  const isFailed = failures !== undefined && failures.length > 0;
                  const chip = (
                    <span
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs",
                        isFailed
                          ? "bg-red-100 text-red-800"
                          : "bg-gray-100 text-gray-600",
                      )}
                    >
                      {name}
                      {isFailed && <Info size={11} aria-hidden />}
                    </span>
                  );
                  return isFailed ? (
                    <Tooltip key={name}>
                      <TooltipTrigger asChild>
                        <span className="cursor-help">{chip}</span>
                      </TooltipTrigger>
                      <TooltipContent>
                        <div className="space-y-1 max-w-xs">
                          <p className="font-semibold text-xs">Failure details:</p>
                          {failures!.map((msg, i) => (
                            <p key={i} className="text-xs text-gray-700">{msg}</p>
                          ))}
                        </div>
                      </TooltipContent>
                    </Tooltip>
                  ) : (
                    <span key={name}>{chip}</span>
                  );
                })}
              </div>
            </div>
          )}

          {/* Hits table */}
          {identifiers === null ? (
            <Skeleton className="h-32 w-full" />
          ) : hits.length === 0 ? (
            <p className="text-sm text-text-muted">No identifier hits found for this segment.</p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Identifier</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Hit Type</TableHead>
                    <TableHead>Resolver</TableHead>
                    {visibleMetrics.map((m) => (
                      <TableHead key={m.key as string}>{m.label}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hits.map((hit, i) => {
                    const url = resolveHitUrl(hit);
                    return (
                      <TableRow key={`${hit.identifier}-${i}`}>
                        <TableCell>
                          {url ? (
                            <a
                              href={url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#2E7D32] hover:underline"
                            >
                              {hit.identifier}
                            </a>
                          ) : (
                            <span>{hit.identifier}</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <span className="text-xs text-gray-500">{hit.ident_type}</span>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs">{hit.hit_type}</span>
                        </TableCell>
                        <TableCell>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="inline-flex items-center gap-1 cursor-help">
                                {hit.resolver_name}
                                <Info size={12} className="text-gray-400" aria-hidden />
                              </span>
                            </TooltipTrigger>
                            <TooltipContent>
                              <div className="space-y-0.5 text-xs">
                                <p><strong>Resolver:</strong> {hit.resolver_name}</p>
                                <p><strong>Hit type:</strong> {hit.hit_type}</p>
                                <p><strong>Segment:</strong> {hit.segment ?? segment}</p>
                                {hit.database_url && (
                                  <p>
                                    <a href={hit.database_url} target="_blank" rel="noopener noreferrer" className="text-[#2E7D32] underline">
                                      Database link
                                    </a>
                                  </p>
                                )}
                              </div>
                            </TooltipContent>
                          </Tooltip>
                        </TableCell>
                        {visibleMetrics.map((m) => (
                          <TableCell key={m.key as string} className="tabular-nums">
                            {formatMetric(hit[m.key] as number | null | undefined)}
                          </TableCell>
                        ))}
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};

export default IdentifiersTab;
