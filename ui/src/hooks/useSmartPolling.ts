import { useState, useEffect, useRef, useCallback } from "react";

// ==================== Types ====================

export interface TaskInfo {
    task_id: string;
    name: string;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    summary?: Record<string, any>;
    artifacts?: string[];
}

export interface PipelineStatus {
    run_id: string;
    pipeline_name: string;
    status: string;
    started_at?: string | null;
    finished_at?: string | null;
    input_kind?: string | null;
    input_files?: Record<string, string>;
    metadata?: Record<string, any>;
}

export interface WarningItem {
    code: string;
    message: string;
    step_id?: string | null;
    details?: Record<string, any>;
    recorded_at?: string | null;
}

export interface ErrorItem {
    code: string;
    message: string;
    step_id?: string | null;
    details?: Record<string, any>;
    critical?: boolean;
    exception_type?: string | null;
    recorded_at?: string | null;
}

export interface EventItem {
    kind: string;
    timestamp: string;
    level?: string | null;
    message?: string | null;
    task_id?: string | null;
}

export interface RunStatusResponse {
    run_id: string;
    pipeline: PipelineStatus;
    tasks: TaskInfo[];
    warnings: WarningItem[];
    critical_errors: ErrorItem[];
    events: EventItem[];
    updated_at?: string | null;
}

export interface LoadingAttemptInfo {
    strategy: string;
    success: boolean;
    error?: string | null;
}

export interface LoadingInfoResponse {
    run_id: string;
    input_kind?: string | null;
    selected_strategy?: string | null;
    topology_files: string[];
    attempts: LoadingAttemptInfo[];
    final_strategy?: string | null;
    success: boolean;
    warnings: string[];
}

export interface MoleculeSummaryResponse {
    run_id: string;
    segments: string[];
    unique_molecules?: Record<string, any>;
    type_counts?: Record<string, number>;
    total_fragment_count?: number;
    segment_meta?: Record<string, any>;
}

export interface SignatureItem {
    segment: string;
    generator: string;
    signature?: string | null;
}

export interface SignaturesResponse {
    run_id: string;
    signatures: SignatureItem[];
}

export interface IdentifierHit {
    identifier: string;
    ident_type: string;
    hit_type: string;
    resolver_name: string;
    segment: string | null;
    score: number | null;
    database_url: string | null;
    evalue: number | null;
    bit_score: number | null;
    identity_percent: number | null;
    coverage_percent: number | null;
}

export interface ResolverErrorItem {
    resolver_name: string;
    generator: string | null;
    message: string;
}

export interface IdentifiersData {
    run_id: string;
    segment: string;
    hits: IdentifierHit[];
    attempted_resolvers: string[];
    failed_resolvers: ResolverErrorItem[];
}

export interface VerifiedHitItem {
    identifier: string;
    ident_type: string;
    database: string;
    resolver_score?: number | null;
    similarity_score?: number | null;
    annotation_quality_score?: number | null;
    final_confidence: number;
    is_verified: boolean;
    rejection_reason?: string | null;
    database_url?: string | null;
}

export interface VerificationResponse {
    run_id: string;
    segment: string;
    hits: VerifiedHitItem[];
}


export interface RenderPathsResponse {
    run_id: string;
    system_mmcif?: string | null;
    segments: Record<string, string>;
}

// ==================== Hook ====================

// Map of task_id/step_id to detail endpoint
const STEP_TO_DETAIL_ENDPOINT: Record<string, keyof DetailEndpoints> = {
    load_simulation: "loading",
    analyze_universe: "molecules",
    generate_signatures: "signatures",
    identify_molecules: "identifiers",
    verify_results: "verification",
    export_results: "render",
};

interface DetailEndpoints {
    loading: LoadingInfoResponse | null;
    molecules: MoleculeSummaryResponse | null;
    signatures: SignaturesResponse | null;
    identifiers: IdentifiersData | null;
    verification: VerificationResponse | null;
    render: RenderPathsResponse | null;
}

const TERMINAL_STATUSES = ["success", "failed", "cancelled"];

export function useSmartPolling(runId: string | undefined) {
    // Status state
    const [statusData, setStatusData] = useState<RunStatusResponse | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [isPolling, setIsPolling] = useState(false);

    // Detail endpoints state
    const [loadingInfo, setLoadingInfo] = useState<LoadingInfoResponse | null>(null);
    const [molecules, setMolecules] = useState<MoleculeSummaryResponse | null>(null);
    const [signatures, setSignatures] = useState<SignaturesResponse | null>(null);
    const [identifiers, setIdentifiers] = useState<IdentifiersData | null>(null);
    const [verification, setVerification] = useState<VerificationResponse | null>(null);
    const [renderPaths, setRenderPaths] = useState<RenderPathsResponse | null>(null);

    // Cancel state
    const [cancelLoading, setCancelLoading] = useState(false);

    // Track which details have been fetched
    const fetchedDetailsRef = useRef<Set<string>>(new Set());

    // Track last updated_at for since parameter
    const lastUpdatedAtRef = useRef<string | null>(null);

    // Ref to track latest status for polling decisions
    const latestStatusRef = useRef<RunStatusResponse | null>(null);

    // Fetch detail endpoints
    const fetchDetail = useCallback(async (endpoint: string) => {
        if (!runId) return null;
        try {
            const res = await fetch(`/runs/${runId}/${endpoint}`);
            if (res.ok) {
                return await res.json();
            }
        } catch (err) {
            console.error(`Failed to fetch ${endpoint}:`, err);
        }
        return null;
    }, [runId]);

    // Fetch identifiers specifically (it's segment-based, fetch without segment param for now)
    const fetchIdentifiersData = useCallback(async () => {
        if (!runId) return null;
        try {
            const res = await fetch(`/runs/${runId}/identifiers`);
            if (res.ok) {
                return await res.json();
            }
        } catch (err) {
            console.error(`Failed to fetch identifiers:`, err);
        }
        return null;
    }, [runId]);

    // Check if a task has completed and its detail hasn't been fetched
    const checkAndFetchDetails = useCallback(async (tasks: TaskInfo[]) => {
        for (const task of tasks) {
            const stepKey = STEP_TO_DETAIL_ENDPOINT[task.task_id];
            if (!stepKey) continue;

            // Skip if already fetched
            if (fetchedDetailsRef.current.has(task.task_id)) continue;

            // Only fetch when task is successful
            if (task.status === "success") {
                fetchedDetailsRef.current.add(task.task_id);

                // Fetch the appropriate detail endpoint
                switch (stepKey) {
                    case "loading": {
                        const data = await fetchDetail("loading");
                        if (data) setLoadingInfo(data);
                        break;
                    }
                    case "molecules": {
                        const data = await fetchDetail("molecules");
                        if (data) setMolecules(data);
                        break;
                    }
                    case "signatures": {
                        const data = await fetchDetail("signatures");
                        if (data) setSignatures(data);
                        break;
                    }
                    case "identifiers": {
                        const data = await fetchIdentifiersData();
                        if (data) setIdentifiers(data);
                        break;
                    }
                    case "verification": {
                        const data = await fetchDetail("verification");
                        if (data) setVerification(data);
                        break;
                    }
                    case "render": {
                        const data = await fetchDetail("render");
                        if (data) setRenderPaths(data);
                        break;
                    }
                }
            }
        }
    }, [fetchDetail, fetchIdentifiersData]);

    // Fetch status
    const fetchStatus = useCallback(async () => {
        if (!runId) return;

        try {
            // Build URL with since parameter if we have a last updated time
            let url = `/runs/${runId}/status`;
            if (lastUpdatedAtRef.current) {
                url += `?since=${encodeURIComponent(lastUpdatedAtRef.current)}`;
            }

            const response = await fetch(url);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data: RunStatusResponse = await response.json();

            // Merge tasks by task_id
            setStatusData((prev) => {
                if (!prev) return data;

                // Create a map of existing tasks by task_id
                const taskMap = new Map(prev.tasks.map((t) => [t.task_id, t]));

                // Update or add new tasks
                for (const task of data.tasks) {
                    taskMap.set(task.task_id, task);
                }

                // Merge warnings by index (append new ones)
                const mergedWarnings = [...prev.warnings];
                for (const warning of data.warnings || []) {
                    // Check if warning already exists (by code+message)
                    const exists = mergedWarnings.some(
                        (w) => w.code === warning.code && w.message === warning.message
                    );
                    if (!exists) {
                        mergedWarnings.push(warning);
                    }
                }

                // Merge errors by index (append new ones)
                const mergedErrors = [...prev.critical_errors];
                for (const err of data.critical_errors || []) {
                    const exists = mergedErrors.some(
                        (e) => e.code === err.code && e.message === err.message
                    );
                    if (!exists) {
                        mergedErrors.push(err);
                    }
                }

                // Merge events (append new ones)
                const mergedEvents = [...prev.events];
                for (const event of data.events || []) {
                    const exists = mergedEvents.some(
                        (e) => e.kind === event.kind && e.timestamp === event.timestamp
                    );
                    if (!exists) {
                        mergedEvents.push(event);
                    }
                }

                return {
                    ...data,
                    tasks: Array.from(taskMap.values()),
                    warnings: mergedWarnings,
                    critical_errors: mergedErrors,
                    events: mergedEvents,
                };
            });

            latestStatusRef.current = data;

            // Update last updated_at for next poll
            if (data.updated_at) {
                lastUpdatedAtRef.current = data.updated_at;
            }

            // Check and fetch details for completed steps
            await checkAndFetchDetails(data.tasks);

            // Stop polling if terminal status
            if (TERMINAL_STATUSES.includes(data.pipeline.status)) {
                setIsPolling(false);
            }
        } catch (err) {
            setError(err instanceof Error ? err.message : "Failed to fetch status");
            setIsPolling(false);
        } finally {
            setIsLoading(false);
        }
    }, [runId, checkAndFetchDetails]);

    // Cancel run
    const cancelRun = useCallback(async () => {
        if (!runId) return;

        setCancelLoading(true);
        try {
            const response = await fetch(`/runs/${runId}/cancel`, {
                method: "POST",
            });
            if (!response.ok) {
                throw new Error(`Failed to cancel run: HTTP ${response.status}`);
            }

            // Refresh status after cancellation
            await fetchStatus();
        } catch (err) {
            console.error("Failed to cancel run:", err);
            setError(err instanceof Error ? err.message : "Failed to cancel run");
        } finally {
            setCancelLoading(false);
        }
    }, [runId, fetchStatus]);

    // Initialize polling
    useEffect(() => {
        if (!runId) return;

        let interval: ReturnType<typeof setInterval> | null = null;
        setIsPolling(true);

        // Initial fetch
        fetchStatus();

        // Set up polling interval (2 seconds as specified)
        interval = setInterval(() => {
            // Only poll if still active
            const currentStatus = latestStatusRef.current?.pipeline.status;
            if (currentStatus && TERMINAL_STATUSES.includes(currentStatus)) {
                if (interval) {
                    clearInterval(interval);
                    interval = null;
                }
                setIsPolling(false);
                return;
            }
            fetchStatus();
        }, 2000);

        return () => {
            if (interval) {
                clearInterval(interval);
            }
        };
    }, [runId, fetchStatus]);

    return {
        status: statusData,
        loadingInfo,
        molecules,
        signatures,
        identifiers,
        verification,
        renderPaths,
        isLoading,
        error,
        isPolling,
        cancelRun,
        cancelLoading,
    };
}
