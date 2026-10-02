import React from "react";
import {
  Button,
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
import { Check, Info, X, ExternalLink } from "lucide-react";
import {
  buildDownloadBlob,
  downloadBlob,
  exportFilename,
  hitsToJson,
  hitsToTsv,
  presentHits,
  resolveHitUrl,
  truncateName,
  type VerifiedHit,
} from "./utils";
import type { VerificationResponse } from "./hooks";

interface VerificationTabProps {
  segment: string;
  verification: VerificationResponse | null;
  onJumpToIdentifiers: () => void;
}

function pct(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "\u2014";
  return `${(Math.round(v * 10) / 10).toFixed(1)}%`;
}

const VerificationTab: React.FC<VerificationTabProps> = ({
  segment,
  verification,
  onJumpToIdentifiers,
}) => {
  // Fidelity-first: presentHits preserves the server's stored order (no re-sort).
  const hits: VerifiedHit[] = presentHits(verification?.hits);

  const doExport = (fmt: "tsv" | "json") => {
    const content = fmt === "tsv" ? hitsToTsv(hits) : hitsToJson(hits);
    const mime = fmt === "tsv" ? "text/tab-separated-values" : "application/json";
    downloadBlob(buildDownloadBlob(content, mime), exportFilename(segment, fmt));
  };

  return (
    <TooltipProvider delayDuration={150}>
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-2">
            <CardTitle>Verification</CardTitle>
            <span className="text-xs text-text-muted">segment {segment}</span>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {verification === null ? (
            <Skeleton className="h-40 w-full" />
          ) : hits.length === 0 ? (
            <p className="text-sm text-text-muted">
              No verification results recorded for segment {segment}.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-24">Verified</TableHead>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Similarity</TableHead>
                    <TableHead className="w-40">Confidence</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hits.map((h, i) => {
                    const url = resolveHitUrl(h);
                    const name = h.name ?? h.identifier;
                    return (
                      <TableRow key={`${h.identifier}-${i}`}>
                        <TableCell>
                          <span className="inline-flex items-center gap-1">
                            {h.is_verified ? (
                              <span className="inline-flex items-center gap-1 text-green-700">
                                <Check size={15} aria-label="Verified" /> Verified
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-red-700">
                                <X size={15} aria-label="Rejected" /> Rejected
                                {h.rejection_reason && (
                                  <Tooltip>
                                    <TooltipTrigger asChild>
                                      <Info size={13} className="cursor-help text-gray-400" />
                                    </TooltipTrigger>
                                    <TooltipContent>Rejected: {h.rejection_reason}</TooltipContent>
                                  </Tooltip>
                                )}
                              </span>
                            )}
                          </span>
                        </TableCell>
                        <TableCell>
                          <Tooltip>
                            <TooltipTrigger asChild>
                              {url ? (
                                <a
                                  href={url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="inline-flex max-w-[16rem] items-center gap-1 align-middle text-[#2E7D32] hover:underline"
                                >
                                  <span className="truncate">{truncateName(name)}</span>
                                  <ExternalLink size={13} aria-hidden className="shrink-0" />
                                </a>
                              ) : (
                                <span className="inline-block max-w-[16rem] truncate align-middle">
                                  {truncateName(name)}
                                </span>
                              )}
                            </TooltipTrigger>
                            <TooltipContent>
                              <span className="font-mono text-xs">{h.identifier}</span>
                            </TooltipContent>
                          </Tooltip>
                        </TableCell>
                        <TableCell>
                          <span className="text-xs text-gray-500">{h.ident_type}</span>
                        </TableCell>
                        <TableCell className="tabular-nums">{pct(h.similarity_score)}</TableCell>
                        <TableCell className="tabular-nums">
                          <span className="inline-flex items-center gap-2">
                            <span className="text-xs tabular-nums">{pct(h.final_confidence)}</span>
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          )}

          {hits.length > 0 && (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={() => doExport("tsv")}>
                Export TSV
              </Button>
              <Button size="sm" variant="outline" onClick={() => doExport("json")}>
                Export JSON
              </Button>
              <Button size="sm" variant="ghost" onClick={onJumpToIdentifiers}>
                View all identifiers
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </TooltipProvider>
  );
};

export default VerificationTab;
