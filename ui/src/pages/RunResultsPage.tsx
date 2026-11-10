/**
 * /runs/:id — the redesigned run-results page (bioid_ui_handoff SPEC §2–3),
 * replaced in place. Layout: run header → error banner → status strip →
 * molecule list | stage → technical details fold → citation/retention.
 * Selection lives in the `?segment=` URL param so links/deep-selects work
 * and polling never resets it.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Alert, AlertDescription, AlertTitle, Skeleton } from "@e-infra/design-system";
import { toast } from "sonner";
import { api, apiErrorMessage, endpoints, retryUnless404 } from "../lib/api/client";
import { ownerHeaders, rememberOwnerToken } from "../lib/ownerTokens";
import { parseRunQuery } from "../lib/nav";
import {
  useRunStatus,
  useRunSummary,
  useRunMolecules,
  useRunQueue,
  useRunVerification,
  useRunIdentifiers,
  useRunLoading,
  useRunFiles,
  useRunRender,
  useCapabilities,
  typicalDuration,
  pipelineStatus,
  isLive,
  isPending,
  stageActive,
  payloadRefetchInterval,
  type SignaturesResponse,
  type VerificationResponse,
} from "../features/results/hooks";
import { adapt, elapsed, type ApiBundle, type ViewModel } from "../features/results/viewmodel";
import { MoleculeList, defaultSelection } from "../features/results/list";
import { Stage } from "../features/results/stage";
import { SystemStage, SYSTEM_SELECTION } from "../features/results/stage/SystemStage";
import { StageCanvas } from "../features/results/viewer";
import { StatusStrip } from "../features/results/status";
import { RunHeader } from "../features/results/header/RunHeader";
import { ErrorBanner } from "../features/results/header/ErrorBanner";
import { bugReport, pageName, pageTitle } from "../features/results/header/headerModel";
import { TechnicalFold, type TechnicalFoldHandle } from "../features/results/TechnicalFold";

/** Placeholder until the paper is out (SPEC §3.7). */
const CITATION = "MD BioID (manuscript in preparation)";

/** Whole-run verification: the endpoint aggregates every segment with a
 *  per-hit `segment` attribution (v3.143, D-17) → group back into the
 *  per-segment views the adapter expects. */
function groupVerification(data: VerificationResponse | undefined): ApiBundle["verification"] {
  if (!data?.hits) return null;
  const bySeg = new Map<string, NonNullable<VerificationResponse["hits"]>[number][]>();
  for (const h of data.hits) {
    const key = (h as { segment?: string | null }).segment ?? "";
    if (!bySeg.has(key)) bySeg.set(key, []);
    bySeg.get(key)!.push(h);
  }
  return [...bySeg.entries()].map(([segment, hits]) => ({ segment, hits }));
}

export default function RunResultsPage() {
  const { runId = "" } = useParams<{ runId: string }>();
  const [searchParams, setSearchParams] = useSearchParams();
  const queryClient = useQueryClient();
  const { segment } = parseRunQuery(searchParams.toString());

  const patchQuery = useCallback(
    (patch: Partial<{ segment: string | null }>) => {
      setSearchParams(
        (prev) => {
          const next = new URLSearchParams(prev);
          if (patch.segment !== undefined) {
            if (patch.segment == null) next.delete("segment");
            else next.set("segment", patch.segment);
          }
          return next;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  /* ---------- Data hooks (adaptive polling: 10–15 s while live, §2) --- */
  const statusQ = useRunStatus(runId);
  const pStatus = pipelineStatus(statusQ.data);
  const live = isLive(pStatus);
  const pending = isPending(pStatus);
  const summaryQ = useRunSummary(runId, live);

  // The elapsed time is derived from "now"; the view model only recomputes
  // when data changes, so without a tick it froze between polls ("0 s
  // elapsed" 40 s into a run). Only the elapsed value ticks, not the model.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!live) return;
    const t = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, [live]);

  // Payload queries poll while live and stop at the terminal status; their
  // last poll predates the final writes (verification, exports, render).
  // Fetch everything once more when the run ends while the page is open.
  const wasLive = useRef(false);
  useEffect(() => {
    if (live) wasLive.current = true;
    else if (wasLive.current && pStatus) {
      wasLive.current = false;
      void queryClient.invalidateQueries({
        predicate: (q) => Array.isArray(q.queryKey) && q.queryKey.includes(runId) && q.queryKey[0] !== "runStatus",
      });
    }
  }, [live, pStatus, runId, queryClient]);

  const queueQ = useRunQueue(runId, pending);
  const moleculesQ = useRunMolecules(runId, live);
  const filesQ = useRunFiles(runId, live);
  const loadingQ = useRunLoading(runId, live);
  const renderQ = useRunRender(runId, live);
  const capsQ = useCapabilities();
  const csvAvailable = capsQ.data?.additions?.includes("results_csv") ?? false;
  const typical = typicalDuration(capsQ.data);

  // Whole-run signatures + verification drive the view model.
  const signaturesAllQ = useQuery({
    queryKey: ["runSignaturesAll", runId],
    queryFn: () => api.get<SignaturesResponse>(endpoints.runSignatures(runId!)),
    enabled: !!runId,
    retry: retryUnless404,
    refetchInterval: () => payloadRefetchInterval(live),
  });
  const verificationAllQ = useQuery({
    queryKey: ["runVerificationAll", runId],
    queryFn: () => api.get<VerificationResponse>(endpoints.runVerification(runId!)),
    enabled: !!runId && !pending,
    retry: retryUnless404,
    refetchInterval: () => payloadRefetchInterval(live),
  });

  /* ---------- View model (single derivation for the whole page) ------- */
  const vm: ViewModel | null = useMemo(() => {
    if (!statusQ.data && !summaryQ.data && !moleculesQ.data) return null;
    const bundle: ApiBundle = {
      runId,
      summary: summaryQ.data ?? null,
      status: statusQ.data ?? null,
      molecules: (moleculesQ.data ?? null) as ApiBundle["molecules"],
      signatures: signaturesAllQ.data ?? null,
      verification: groupVerification(verificationAllQ.data),
      queue: queueQ.data ?? null,
      files: filesQ.data ?? null,
    };
    return adapt(bundle, { csvAvailable, typical });
  }, [runId, statusQ.data, summaryQ.data, moleculesQ.data, signaturesAllQ.data, verificationAllQ.data, queueQ.data, filesQ.data, csvAvailable, typical]);

  const molecules = vm?.molecules ?? [];
  // "Whole system" is its own selection; per-segment views (technical
  // fold, verification/identifier queries) keep the first molecule.
  const systemView = segment === SYSTEM_SELECTION && molecules.length > 0;
  const selectedId = molecules.find((m) => m.id === segment)?.id ?? defaultSelection(molecules);
  const selected = systemView ? null : molecules.find((m) => m.id === selectedId) ?? null;
  const onSelect = useCallback((id: string) => patchQuery({ segment: id }), [patchQuery]);

  // Per-segment developer views inside the technical fold.
  const verificationQ = useRunVerification(runId, selectedId ?? "", stageActive(statusQ.data, "verify_results"), live);
  const identifiersQ = useRunIdentifiers(runId, selectedId ?? "", stageActive(statusQ.data, "identify_molecules"), live);

  // Browser tab title per run state (SPEC §2).
  useEffect(() => {
    if (!vm) return;
    const name = pageName(vm.run);
    document.title = pageTitle(name, vm.run.status, vm.run.cancelled);
    return () => {
      document.title = "MD BioID";
    };
  }, [vm]);

  /* ---------- Header actions ------------------------------------------ */
  const copy = useCallback((text: string, ok: string) => {
    void navigator.clipboard?.writeText(text).then(
      () => toast.success(ok),
      () => toast.error("Copy failed"),
    );
  }, []);
  const copyLink = useCallback(() => copy(window.location.href, "Link copied"), [copy]);

  const onCancel = useCallback(() => {
    void api
      .postJson(endpoints.runCancel(runId), {}, ownerHeaders(runId))
      .then(() => {
        toast.success("Run cancelled");
        void queryClient.invalidateQueries({ queryKey: ["runStatus", runId] });
      })
      .catch((err) => toast.error(apiErrorMessage(err, "Could not cancel the run")));
  }, [runId, queryClient]);

  const onRerun = useCallback(() => {
    void api
      .postJson<{ run_id: string; owner_token?: string | null }>(endpoints.runRerun(runId), {})
      .then((res) => {
        rememberOwnerToken(res.run_id, res.owner_token);
        toast.success("Run queued");
        if (res?.run_id) window.location.assign(`/runs/${res.run_id}`);
      })
      .catch((err) => toast.error(apiErrorMessage(err, "Could not rerun")));
  }, [runId]);

  const onCite = useCallback(() => {
    copy(`Using these results? Please cite: ${CITATION}\n${window.location.href}`, "Citation copied");
  }, [copy]);

  const onReport = useCallback(() => {
    if (!vm?.error) {
      copy(`MD BioID problem report\nRun: ${runId}\n\nDescribe the problem here:`, "Details copied");
      return;
    }
    copy(bugReport(vm.run, vm.error), "Details copied");
  }, [vm, runId, copy]);

  const onDownload = useCallback(
    (key: "csv" | "json") => {
      const url = key === "csv" ? endpoints.runResultsCsv(runId) : endpoints.runFileUrl(runId, "results.json");
      window.open(url, "_blank", "noopener");
    },
    [runId],
  );

  const onOpenTechnical = useCallback(() => foldRef.current?.open(), []);
  const foldRef = useRef<TechnicalFoldHandle>(null);

  /* ---------- Early states -------------------------------------------- */
  if (statusQ.isPending) {
    return (
      <div className="mx-auto max-w-[1400px] space-y-4 p-4 sm:p-6" aria-busy>
        <Skeleton className="h-9 w-72" />
        <Skeleton className="h-14 w-full rounded-lg" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(340px,380px)_1fr]">
          <Skeleton className="h-[520px] w-full rounded-lg" />
          <Skeleton className="h-[520px] w-full rounded-lg" />
        </div>
      </div>
    );
  }

  // A failed refetch keeps the data TanStack already has (isError is set
  // with data present); only a run that never loaded is "not found". Live
  // 2026-11-09: a finishing 3PTB run flipped to "Run not found" for good.
  if ((statusQ.isError && !statusQ.data) || !vm) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <Alert variant="error">
          <AlertTitle>
            <h1>Run not found</h1>
          </AlertTitle>
          <AlertDescription>
            <p>
              Could not load results for run <code className="font-mono text-sm">{runId.slice(0, 8)}</code>. The run
              may have been deleted or the ID is incorrect.
            </p>
          </AlertDescription>
        </Alert>
        <Link to="/" className="mt-4 inline-block font-medium text-(--vm-accent) underline-offset-2 hover:underline">
          Go to the BioID start page
        </Link>
      </div>
    );
  }

  const segments = molecules.map((m) => m.id);

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6 sm:px-6">
      <RunHeader
        run={vm.run}
        runStatus={vm.run.status}
        downloads={vm.downloads}
        onCopyLink={copyLink}
        onCancel={onCancel}
        canCancel={ownerHeaders(runId) !== undefined}
        onRerun={onRerun}
        onCite={onCite}
        onDownload={onDownload}
        onReport={onReport}
      />

      {vm.run.status === "failed" && vm.error && <ErrorBanner run={vm.run} error={vm.error} />}

      <StatusStrip
        runStatus={vm.run.status}
        progress={vm.progress}
        elapsedS={live ? elapsed(vm.run.status, vm.run.started_at, vm.run.finished_at, now) : vm.run.elapsed_s}
        notes={vm.notes}
        hiddenNoteCount={vm.hidden_note_count}
        molecules={molecules}
        onSelect={onSelect}
        onCopyLink={copyLink}
        onOpenTechnical={onOpenTechnical}
      />

      {/* List | stage */}
      <div className="mt-4 grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(340px,380px)_1fr]">
        <MoleculeList
          molecules={molecules}
          runStatus={vm.run.status}
          selectedId={systemView ? SYSTEM_SELECTION : selectedId}
          onSelect={onSelect}
          groupBy={vm.run.status === "finished" ? "identification" : "kind"}
          onGroupByChange={() => {}}
          filter={null}
          onFilterChange={() => {}}
          storageKey={runId}
        />
        {selected ? (
          <Stage
            molecule={selected}
            molecules={molecules}
            notes={vm.notes}
            runStatus={vm.run.status}
            onSelect={onSelect}
            canvas={
              <StageCanvas
                runId={runId}
                runStatus={vm.run.status}
                molecules={molecules}
                selectedId={selectedId}
                onSelect={onSelect}
                renderPaths={renderQ.data ?? null}
                fallbackSegment={selectedId ?? undefined}
              />
            }
          />
        ) : systemView ? (
          <SystemStage
            molecules={molecules}
            runStatus={vm.run.status}
            canvas={
              <StageCanvas
                runId={runId}
                runStatus={vm.run.status}
                molecules={molecules}
                selectedId={null}
                onSelect={onSelect}
                renderPaths={renderQ.data ?? null}
                fallbackSegment="SYSTEM"
                defaultMode="confidence"
              />
            }
          />
        ) : (
          <section className="rounded-lg border border-(--vm-line) bg-(--vm-surface) p-6 text-sm text-(--vm-muted)">
            Molecules appear once your files are read.
          </section>
        )}
      </div>

      <TechnicalFold
        ref={foldRef}
        entries={vm.technical}
        runId={runId}
        segment={selectedId ?? ""}
        segments={segments}
        onSegmentChange={onSelect}
        status={statusQ.data ?? null}
        summary={summaryQ.data ?? null}
        loading={loadingQ.data ?? null}
        files={filesQ.data?.files ?? []}
        signatures={signaturesAllQ.data ?? null}
        identifiers={identifiersQ.data ?? null}
        verification={verificationQ.data ?? null}
      />

      {/* Citation + retention (SPEC §3.7) */}
      <footer className="mt-4 space-y-1 text-sm text-(--vm-muted)">
        <p>
          Using these results? Please cite: {CITATION}. The Cite button at the top copies it with a link to this run.
        </p>
        {vm.run.retention_days != null && (
          <p>Anyone with this link can see these results. They are kept for {vm.run.retention_days} days.</p>
        )}
      </footer>
    </div>
  );
}
