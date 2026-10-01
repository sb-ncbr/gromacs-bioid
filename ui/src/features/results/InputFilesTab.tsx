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
import { Download, FileText, X } from "lucide-react";
import { endpoints } from "../../lib/api/client";
import type { LoadingInfoResponse } from "./hooks";
import { deriveInputFiles } from "./utils/input-files";

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
  const hasConfig = files.includes("config.ini");

  // Input file paths: prefer status.pipeline.input_files keys, else derive from files list
  const inputPaths: string[] = inputFiles
    ? Object.keys(inputFiles)
    : deriveInputFiles(files);

  // Attempts: only show those with a non-empty error message
  const failedAttempts = loading?.attempts?.filter((a) => a.error && a.error.trim() !== "") ?? [];

  return (
    <div className="space-y-4">
      {/* Uploaded input — prominent zone at top */}
      <Card className="border-[#2E7D32]/40 bg-[#2E7D32]/5">
        <CardHeader>
          <CardTitle className="text-[#1b5e20]">Uploaded input</CardTitle>
        </CardHeader>
        <CardContent>
          {inputPaths.length === 0 ? (
            <p className="text-sm text-text-muted">No input files recorded.</p>
          ) : (
            <ul className="space-y-1.5">
              {inputPaths.map((path) => (
                <li key={path} className="flex items-center gap-2 text-sm">
                  <a
                    href={fileUrl(runId, path)}
                    download
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1 font-mono text-xs text-[#2E7D32] transition-colors hover:bg-[#2E7D32]/10"
                  >
                    <Download size={13} aria-hidden className="shrink-0" />
                    {path}
                  </a>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>

      {/* Loading strategy card + attempts */}
      <Card>
        <CardHeader>
          <CardTitle>Loading strategy</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <>
              {loading.success ? (
                <p className="text-base font-semibold text-green-700">
                  Loaded successfully with {loading.final_strategy ?? loading.selected_strategy ?? "unknown strategy"}
                </p>
              ) : (
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <span className="font-medium text-text-heading">
                    Strategy: {loading.final_strategy ?? loading.selected_strategy ?? "—"}
                  </span>
                  <Badge className="border-transparent bg-red-100 text-red-800">Load failed</Badge>
                </div>
              )}
              {loading.input_kind && (
                <Badge variant="outline">{loading.input_kind}</Badge>
              )}
              {loading.topology_files && loading.topology_files.length > 0 && (
                <p className="text-xs text-text-muted">
                  Topology files: {loading.topology_files.join(", ")}
                </p>
              )}
              {failedAttempts.length > 0 && (
                <div>
                  <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-text-muted">
                    Attempts
                  </h4>
                  <ul className="space-y-1">
                    {failedAttempts.map((a, i) => (
                      <li key={i} className="flex items-start gap-2 text-sm text-text-muted">
                        <X size={15} className="mt-0.5 shrink-0 text-red-600" aria-label="Failed" />
                        <span>
                          Tried <span className="font-mono text-xs">{a.strategy}</span>: {a.error}
                        </span>
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
                  <li key={f} className="flex items-center gap-2 text-sm">
                    <a
                      href={fileUrl(runId, f)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="break-all font-mono text-xs text-[#2E7D32] hover:underline"
                    >
                      {f}
                    </a>
                    <a
                      href={fileUrl(runId, f)}
                      download
                      aria-label={`Download ${f}`}
                      className="shrink-0 rounded p-1 text-text-muted transition-colors hover:bg-[#2E7D32]/10 hover:text-[#2E7D32]"
                    >
                      <Download size={14} aria-hidden />
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
