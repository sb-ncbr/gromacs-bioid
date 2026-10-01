import React from "react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Skeleton,
  TooltipProvider,
} from "@e-infra/design-system";
import { Check, Download, FileText, X } from "lucide-react";
import { endpoints } from "../../lib/api/client";
import type { LoadingInfoResponse } from "./hooks";

interface InputFilesTabProps {
  runId: string;
  loading: LoadingInfoResponse | null;
  inputFiles: Record<string, string> | null;
  files: string[];
}

function fileUrl(runId: string, file: string): string {
  return endpoints.runFileUrl(runId, file);
}

function LogLinks({ runId }: { runId: string }) {
  const types: { type: string; label: string }[] = [
    { type: "normal", label: "Normal log" },
    { type: "debug", label: "Debug log" },
  ];
  return (
    <div className="flex flex-wrap gap-3">
      {types.map(({ type, label }) => (
        <a
          key={type}
          href={`${endpoints.runLogs(runId)}?type=${type}`}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-sm text-[#2E7D32] hover:underline"
        >
          <FileText size={14} aria-hidden />
          {label}
        </a>
      ))}
    </div>
  );
}

const InputFilesTab: React.FC<InputFilesTabProps> = ({ runId, loading, inputFiles, files }) => {
  const fileSet = new Set(files);
  const inputEntries = inputFiles ? Object.entries(inputFiles) : [];
  const hasConfig = files.includes("config.ini");

  return (
    <div className="space-y-4">
      {/* Loading strategy card + attempts */}
      <Card>
        <CardHeader>
          <CardTitle>Loading strategy</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <>
              <div className="flex flex-wrap items-center gap-2 text-sm">
                <span className="font-medium text-text-heading">
                  Strategy: {loading.final_strategy ?? loading.selected_strategy ?? "—"}
                </span>
                {loading.input_kind && (
                  <Badge variant="outline">{loading.input_kind}</Badge>
                )}
                {loading.success ? (
                  <Badge variant="secondary">Loaded successfully</Badge>
                ) : (
                  <Badge className="border-transparent bg-red-100 text-red-800">Load failed</Badge>
                )}
              </div>
              {loading.topology_files && loading.topology_files.length > 0 && (
                <p className="text-xs text-text-muted">
                  Topology files: {loading.topology_files.join(", ")}
                </p>
              )}
              {Array.isArray(loading.attempts) && loading.attempts.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Attempts
                  </h4>
                  <ul className="space-y-1">
                    {loading.attempts.map((a, i) => (
                      <li key={i} className="flex items-center gap-2 text-sm">
                        {a.success ? (
                          <Check size={15} className="shrink-0 text-green-600" aria-label="Succeeded" />
                        ) : (
                          <X size={15} className="shrink-0 text-red-600" aria-label="Failed" />
                        )}
                        <span className="font-mono text-xs">{a.strategy}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {Array.isArray(loading.warnings) && loading.warnings.length > 0 && (
                <Alert variant="warning">
                  <AlertTitle>Loading warnings</AlertTitle>
                  <AlertDescription>
                    <ul className="list-disc pl-4">
                      {loading.warnings.map((w, i) => (
                        <li key={i}>{w}</li>
                      ))}
                    </ul>
                  </AlertDescription>
                </Alert>
              )}
            </>
          ) : (
            <Skeleton className="h-16 w-full" />
          )}
        </CardContent>
      </Card>

      {/* INPUT files — highlighted section */}
      <Card className="border-[#2E7D32]/40 bg-[#2E7D32]/5">
        <CardHeader>
          <CardTitle className="text-[#1b5e20]">Input files</CardTitle>
        </CardHeader>
        <CardContent>
          {inputEntries.length === 0 ? (
            <p className="text-sm text-text-muted">No input files recorded.</p>
          ) : (
            <ul className="space-y-1">
              {inputEntries.map(([key, value]) => (
                <li key={key} className="flex flex-wrap items-baseline gap-2 text-sm">
                  <span className="w-32 shrink-0 text-text-muted">{key}</span>
                  {fileSet.has(value) ? (
                    <a
                      href={fileUrl(runId, value)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all font-mono text-xs text-[#2E7D32] hover:underline"
                    >
                      {value}
                    </a>
                  ) : (
                    <span className="break-all font-mono text-xs">{value}</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Key outputs */}
      <Card>
        <CardHeader>
          <CardTitle>Key outputs</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-3">
            <Button
              size="sm"
              variant="outline"
              disabled={!fileSet.has("results.json")}
              onClick={() => {
                window.location.href = fileUrl(runId, "results.json");
              }}
              className="gap-1"
            >
              <Download size={14} aria-hidden />
              results.json
            </Button>
            {hasConfig && (
              <a
                href={fileUrl(runId, "config.ini")}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 text-sm text-[#2E7D32] hover:underline"
              >
                <FileText size={14} aria-hidden />
                config.ini
              </a>
            )}
            <LogLinks runId={runId} />
          </div>
        </CardContent>
      </Card>

      {/* Full file list */}
      <TooltipProvider delayDuration={200}>
        <Accordion type="single" collapsible>
          <AccordionItem value="files">
            <AccordionTrigger>
              All files ({files.length})
            </AccordionTrigger>
            <AccordionContent>
              <ul className="space-y-1">
                {files.length === 0 && (
                  <li className="text-sm text-text-muted">No files listed.</li>
                )}
                {files.map((f) => (
                  <li key={f} className="text-sm">
                    <a
                      href={fileUrl(runId, f)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all font-mono text-xs text-[#2E7D32] hover:underline"
                    >
                      {f}
                    </a>
                  </li>
                ))}
              </ul>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </TooltipProvider>
    </div>
  );
};

export default InputFilesTab;
