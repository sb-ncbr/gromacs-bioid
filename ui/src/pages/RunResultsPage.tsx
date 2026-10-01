import { useCallback, useEffect, useState } from "react";
import { useParams, useSearchParams } from "react-router-dom";
import {
  Alert,
  AlertDescription,
  AlertTitle,
  Badge,
  Skeleton,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@e-infra/design-system";
import { Clock } from "lucide-react";
import { DEFAULT_SEGMENT, DEFAULT_TAB, TABS, parseRunQuery, type TabKey } from "../lib/nav";
import TaskBar from "../features/results/TaskBar";
import MoleculeSelector, { type SegmentMeta } from "../features/results/MoleculeSelector";
import ResultsPanel from "../features/results/ResultsPanel";
import {
  useRunStatus,
  useRunSummary,
  useRunMolecules,
  useRunQueue,
  useRunVerification,
  useRunIdentifiers,
  useRunSignatures,
  useRunLoading,
  useRunFiles,
  useRunRender,
  pipelineStatus,
  isLive,
  isPending,
  stageActive,
  segmentMeta,
} from "../features/results/hooks";
import WarningsPanel from "../features/results/WarningsPanel";
import OverviewTab from "../features/results/OverviewTab";
import InputFilesTab from "../features/results/InputFilesTab";
import SignaturesTab from "../features/results/SignaturesTab";
import IdentifiersTab from "../features/results/IdentifiersTab";
import VerificationTab from "../features/results/VerificationTab";
import MolstarViewer from "../features/results/MolstarViewer";

const TAB_LABELS: Record<TabKey, string> = {
  overview: "Overview",
  input: "Input & Files",
  signatures: "Signatures",
  identifiers: "Identifiers",
  verification: "Verification",
  warnings: "Warnings",
};

export default function RunResultsPage() {
  const { runId = "" } = useParams<{ runId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const { segment, tab } = parseRunQuery(searchParams.toString());

  const [pendingAnchor, setPendingAnchor] = useState<string | null>(null);

  /* ---------- URL state helpers (replace, not push) ---------- */
  const patchQuery = useCallback(
    (patch: Partial<{ segment: string; tab: TabKey }>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (patch.segment !== undefined) {
            if (patch.segment === DEFAULT_SEGMENT) next.delete("segment");
            else next.set("segment", patch.segment);
          }
          if (patch.tab !== undefined) {
            if (patch.tab === DEFAULT_TAB) next.delete("tab");
            else next.set("tab", patch.tab);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  /* ---------- Data hooks (adaptive polling) ---------- */
  const statusQ = useRunStatus(runId);
  const summaryQ = useRunSummary(runId);
  const pipeline = statusQ.data?.pipeline ?? null;
  const pStatus = pipelineStatus(statusQ.data);
  const live = isLive(pStatus);
  const pending = isPending(pStatus);

  const queueQ = useRunQueue(runId, pending);
  const moleculesQ = useRunMolecules(runId, live);
  const verificationQ = useRunVerification(
    runId,
    segment,
    stageActive(statusQ.data, "verify_results"),
    live,
  );
  const identifiersQ = useRunIdentifiers(
    runId,
    segment,
    stageActive(statusQ.data, "identify_molecules"),
    live,
  );
  const signaturesQ = useRunSignatures(
    runId,
    segment,
    stageActive(statusQ.data, "generate_signatures"),
    live,
  );
  const loadingQ = useRunLoading(runId, live);
  const filesQ = useRunFiles(runId, live);
  const renderQ = useRunRender(runId, live);

  /* ---------- Derived values ---------- */
  const segments: string[] = moleculesQ.data?.segments ?? [];
  const rawMeta = moleculesQ.data?.segment_meta ?? null;
  const segMeta = (rawMeta ?? null) as Record<string, SegmentMeta> | null;
  const molecule =
    segment === DEFAULT_SEGMENT ? null : segmentMeta(moleculesQ.data ?? null, segment);

  /* ---------- TaskBar → Warnings tab + anchor ---------- */
  const handleGroupClick = useCallback(
    (groupId: string) => {
      setPendingAnchor(groupId);
      patchQuery({ tab: "warnings" });
    },
    [patchQuery],
  );

  useEffect(() => {
    if (tab !== "warnings" || !pendingAnchor) return;
    const t = window.setTimeout(() => {
      document
        .getElementById(`warn-${pendingAnchor}`)
        ?.scrollIntoView({ behavior: "smooth", block: "start" });
      setPendingAnchor(null);
    }, 150);
    return () => window.clearTimeout(t);
  }, [tab, pendingAnchor]);

  /* ---------- Initial loading ---------- */
  if (statusQ.isPending) {
    return (
      <div className="mx-auto max-w-6xl space-y-6 p-6">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-12 w-full" />
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="xl:col-span-7 space-y-4">
            <Skeleton className="h-48 w-full rounded-lg" />
            <Skeleton className="h-96 w-full rounded-lg" />
          </div>
          <div className="xl:col-span-5">
            <Skeleton className="h-96 w-full rounded-lg" />
          </div>
        </div>
      </div>
    );
  }

  /* ---------- Error / not-found ---------- */
  if (statusQ.isError) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Alert variant="error">
          <AlertTitle>Run not found</AlertTitle>
          <AlertDescription>
            Could not load results for run{" "}
            <code className="font-mono text-sm">{runId.slice(0, 8)}</code>. The run may have
            been deleted or the ID is incorrect.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  const displayTitle = summaryQ.data?.run_name?.trim() || runId.slice(0, 8);
  const badgeVariant = pStatus === "failed" ? "error" : pStatus === "success" ? "default" : "outline";
  const badgeClassName =
    pStatus === "success"
      ? "border-transparent bg-green-100 text-green-800"
      : pStatus === "failed"
        ? "border-transparent bg-red-100 text-red-800"
        : "";

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-4 sm:p-6">
      {/* Title */}
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold text-text-heading">{displayTitle}</h1>
        <Badge variant={badgeVariant} className={badgeClassName}>
          {pStatus ?? "loading"}
        </Badge>
        <span className="font-mono text-xs text-text-muted">{runId.slice(0, 8)}…</span>
      </header>

      {/* TaskBar */}
      <TaskBar tasks={statusQ.data?.tasks ?? []} onGroupClick={handleGroupClick} />

      {/* Queued banner */}
      {pending && (
        <Alert>
          <AlertTitle className="flex items-center gap-2">
            <Clock size={16} aria-hidden /> In the queue
          </AlertTitle>
          <AlertDescription>
            {queueQ.data?.position != null
              ? `Position ${queueQ.data.position} in queue`
              : "Waiting for a worker to pick up this job…"}
          </AlertDescription>
        </Alert>
      )}

      {/* Main grid: viewer left (7/12), results right (5/12) */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        {/* LEFT: selector + Mol* viewer */}
        <div className="space-y-4 xl:col-span-7">
          <MoleculeSelector
            segments={segments}
            segmentMeta={segMeta}
            selected={segment}
            onSelect={(s) => patchQuery({ segment: s })}
          />
          <MolstarViewer
            runId={runId}
            segment={segment}
            segments={segments}
            segmentMeta={segMeta}
            renderPaths={renderQ.data ?? null}
          />
        </div>

        {/* RIGHT: ResultsPanel (per-segment hits) */}
        <div className="xl:col-span-5">
          <ResultsPanel
            segment={segment}
            molecule={molecule}
            verification={
              verificationQ.data
                ? { hits: (verificationQ.data.hits ?? []) as never[] }
                : null
            }
            identifiers={identifiersQ.data ?? null}
            onJumpToIdentifiers={() => patchQuery({ tab: "identifiers" })}
          />
        </div>
      </div>

      {/* Tabs */}
      <Tabs value={tab} onValueChange={(v) => patchQuery({ tab: v as TabKey })}>
        <TabsList className="flex flex-wrap gap-1">
          {TABS.map((t) => (
            <TabsTrigger key={t} value={t}>
              {TAB_LABELS[t]}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="overview">
          <OverviewTab
            runId={runId}
            status={statusQ.data}
            summary={summaryQ.data ?? null}
          />
        </TabsContent>

        <TabsContent value="input">
          <InputFilesTab
            runId={runId}
            loading={loadingQ.data ?? null}
            inputFiles={pipeline?.input_files ?? null}
            files={filesQ.data?.files ?? []}
          />
        </TabsContent>

        <TabsContent value="signatures">
          <SignaturesTab
            segment={segment}
            onSegmentChange={(s) => patchQuery({ segment: s })}
            segments={segments}
            signatures={signaturesQ.data ?? null}
          />
        </TabsContent>

        <TabsContent value="identifiers">
          <IdentifiersTab
            segment={segment}
            onSegmentChange={(s) => patchQuery({ segment: s })}
            segments={segments}
            identifiers={identifiersQ.data ?? null}
          />
        </TabsContent>

        <TabsContent value="verification">
          <VerificationTab
            segment={segment}
            verification={verificationQ.data ?? null}
            onJumpToIdentifiers={() => patchQuery({ tab: "identifiers" })}
          />
        </TabsContent>

        <TabsContent value="warnings">
          <WarningsPanel
            warnings={statusQ.data?.warnings ?? []}
            criticalErrors={statusQ.data?.critical_errors ?? []}
          />
        </TabsContent>
      </Tabs>
    </div>
  );
}
