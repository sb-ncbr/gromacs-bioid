// BAT3 Validation Dashboard - App JavaScript

const API_BASE = '';  // Use relative URLs (goes through nginx proxy)

// State
let pollInterval = null;
let isLoading = false;
let currentTab = 'validation';

// DOM Elements
const elements = {
    // Stats
    statTotal: document.getElementById('statTotal'),
    statCompleted: document.getElementById('statCompleted'),
    statPending: document.getElementById('statPending'),
    statFailed: document.getElementById('statFailed'),

    // Controls
    startBatchBtn: document.getElementById('startBatchBtn'),
    stopBtn: document.getElementById('stopBtn'),
    concurrency: document.getElementById('concurrency'),
    refreshBtn: document.getElementById('refreshBtn'),

    // Progress
    progressBar: document.getElementById('progressBar'),
    progressText: document.getElementById('progressText'),
    batchInfo: document.getElementById('batchInfo'),

    // Tables
    entriesBody: document.getElementById('entriesBody'),
    runsBody: document.getElementById('runsBody'),

    // Tabs
    tabs: document.querySelectorAll('.tab'),
    tabContents: document.querySelectorAll('.tab-content'),

    // Indexing elements
    indexTotal: document.getElementById('indexTotal'),
    indexCompleteness: document.getElementById('indexCompleteness'),
    indexLastTimestamp: document.getElementById('indexLastTimestamp'),
    startIndexingBtn: document.getElementById('startIndexingBtn'),
    fetchMissingBtn: document.getElementById('fetchMissingBtn'),
    indexConcurrency: document.getElementById('indexConcurrency'),
    indexProgressBar: document.getElementById('indexProgressBar'),
    indexProgressText: document.getElementById('indexProgressText'),
    indexingJobsBody: document.getElementById('indexingJobsBody'),

    // Ground Truth elements
    gtWithCount: document.getElementById('gtWithCount'),
    gtWithoutCount: document.getElementById('gtWithoutCount'),
    gtCoveragePercent: document.getElementById('gtCoveragePercent'),
    gtUniProtCount: document.getElementById('gtUniProtCount'),
    gtPdbCount: document.getElementById('gtPdbCount'),
    gtInchiCount: document.getElementById('gtInchiCount'),
    fetchAllMissingGtBtn: document.getElementById('fetchAllMissingGtBtn'),
    missingGtBody: document.getElementById('missingGtBody'),

    // Database elements
    dbStatsBody: document.getElementById('dbStatsBody'),

    // Import elements
    sqliteSourcePath: document.getElementById('sqliteSourcePath'),
    sqliteTables: document.getElementById('sqliteTables'),
    conflictStrategy: document.getElementById('conflictStrategy'),
    startImportBtn: document.getElementById('startImportBtn'),
    importProgressBar: document.getElementById('importProgressBar'),
    importProgressText: document.getElementById('importProgressText'),
    importStatusInfo: document.getElementById('importStatusInfo'),
    importJobsBody: document.getElementById('importJobsBody'),

    // Failed entries elements
    failedEntriesBody: document.getElementById('failedEntriesBody'),
    retryAllFailedBtn: document.getElementById('retryAllFailedBtn')
};

// Utility Functions
function setLoading(loading) {
    isLoading = loading;
    elements.startBatchBtn.disabled = loading;
    elements.refreshBtn.disabled = loading;
}

function formatTime(dateStr) {
    if (!dateStr) return '-';
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours} hr ago`;
    return date.toLocaleDateString();
}

function getStatusClass(status) {
    const statusMap = {
        'completed': 'status-completed',
        'pending': 'status-pending',
        'failed': 'status-failed',
        'running': 'status-running'
    };
    return statusMap[status] || '';
}

// API Functions
async function fetchStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        if (!response.ok) throw new Error('Failed to fetch stats');
        return await response.json();
    } catch (error) {
        console.error('Error fetching stats:', error);
        return null;
    }
}

async function fetchEntries() {
    try {
        const response = await fetch(`${API_BASE}/entries?limit=20`);
        if (!response.ok) throw new Error('Failed to fetch entries');
        return await response.json();
    } catch (error) {
        console.error('Error fetching entries:', error);
        return null;
    }
}

async function fetchRuns() {
    try {
        const response = await fetch(`${API_BASE}/runs?limit=10`);
        if (!response.ok) throw new Error('Failed to fetch runs');
        return await response.json();
    } catch (error) {
        console.error('Error fetching runs:', error);
        return null;
    }
}

async function fetchActiveRun() {
    try {
        const response = await fetch(`${API_BASE}/runs/active`);
        if (!response.ok) return null;
        return await response.json();
    } catch (error) {
        return null;
    }
}

async function startBatch(concurrency) {
    try {
        const response = await fetch(`${API_BASE}/runs/batch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ concurrency: parseInt(concurrency) })
        });
        if (!response.ok) throw new Error('Failed to start batch');
        return await response.json();
    } catch (error) {
        console.error('Error starting batch:', error);
        alert('Failed to start batch: ' + error.message);
        return null;
    }
}

async function _stopRun(runId) {
    try {
        const response = await fetch(`${API_BASE}/runs/${runId}/stop`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to stop run');
        return await response.json();
    } catch (error) {
        console.error('Error stopping run:', error);
        alert('Failed to stop run: ' + error.message);
        return null;
    }
}

async function _validateEntry(entryId) {
    try {
        const response = await fetch(`${API_BASE}/entries/${entryId}/validate`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to validate entry');
        return await response.json();
    } catch (error) {
        console.error('Error validating entry:', error);
        alert('Failed to validate entry: ' + error.message);
        return null;
    }
}

async function _retryEntry(entryId) {
    try {
        const response = await fetch(`${API_BASE}/entries/${entryId}/retry`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to retry entry');
        return await response.json();
    } catch (error) {
        console.error('Error retrying entry:', error);
        alert('Failed to retry entry: ' + error.message);
        return null;
    }
}

async function _retryRun(runId) {
    try {
        const response = await fetch(`${API_BASE}/runs/${runId}/retry`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to retry run');
        return await response.json();
    } catch (error) {
        console.error('Error retrying run:', error);
        alert('Failed to retry run: ' + error.message);
        return null;
    }
}

async function fetchFailedEntries() {
    try {
        const response = await fetch(`${API_BASE}/entries/failed?limit=100`);
        if (!response.ok) throw new Error('Failed to fetch failed entries');
        return await response.json();
    } catch (error) {
        console.error('Error fetching failed entries:', error);
        return null;
    }
}

async function _retryAllFailed() {
    try {
        const failedEntries = await fetchFailedEntries();
        if (!failedEntries || failedEntries.length === 0) {
            alert('No failed entries to retry');
            return null;
        }
        
        let successCount = 0;
        let failCount = 0;
        
        for (const entry of failedEntries) {
            try {
                const response = await fetch(`${API_BASE}/entries/${entry.entry_id}/retry`, {
                    method: 'POST'
                });
                if (response.ok) {
                    successCount++;
                } else {
                    failCount++;
                }
            } catch (error) {
                console.error(`Failed to retry entry ${entry.entry_id}:`, error);
                failCount++;
            }
        }
        
        alert(`Retry complete: ${successCount} succeeded, ${failCount} failed`);
        return { successCount, failCount };
    } catch (error) {
        console.error('Error retrying all failed entries:', error);
        alert('Failed to retry all failed entries: ' + error.message);
        return null;
    }
}

async function _retryIndexingJob(jobId) {
    try {
        const response = await fetch(`${API_BASE}/index/jobs/${jobId}/retry`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to retry indexing job');
        return await response.json();
    } catch (error) {
        console.error('Error retrying indexing job:', error);
        alert('Failed to retry indexing job: ' + error.message);
        return null;
    }
}

async function _deleteIndexJob(jobId) {
    if (!confirm(`Delete indexing job ${jobId}?`)) return;
    
    const response = await fetch(`${API_BASE}/index/jobs/${jobId}`, {
        method: 'DELETE'
    });
    
    if (response.ok) {
        alert('Job deleted successfully');
        refreshTab('indexing');
    } else {
        const error = await response.json().then(r => r.detail || r.message).catch(() => response.text());
        alert(`Failed to delete: ${error}`);
    }
}

// Indexing API Functions
async function fetchIndexingStats() {
    try {
        const response = await fetch(`${API_BASE}/index/stats`);
        if (!response.ok) throw new Error('Failed to fetch indexing stats');
        const text = await response.text();
        console.log('/index/stats response:', text.substring(0, 500));
        const stats = JSON.parse(text);
        console.log('Indexing stats:', stats);
        return stats;
    } catch (error) {
        console.error('Error fetching indexing stats:', error);
        return null;
    }
}

async function startIndexing(limit) {
    try {
        const response = await fetch(`${API_BASE}/index/mddbr?limit=${parseInt(limit) || 1000}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error('Failed to start indexing');
        return await response.json();
    } catch (error) {
        console.error('Error starting indexing:', error);
        alert('Failed to start indexing: ' + error.message);
        return null;
    }
}

async function fetchMissingMetadata(limit) {
    try {
        const response = await fetch(`${API_BASE}/index/fetch-missing?limit=${parseInt(limit) || 1000}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        if (!response.ok) throw new Error('Failed to fetch missing metadata');
        return await response.json();
    } catch (error) {
        console.error('Error fetching missing metadata:', error);
        alert('Failed to fetch missing metadata: ' + error.message);
        return null;
    }
}

async function fetchIndexingJobs() {
    try {
        const response = await fetch(`${API_BASE}/index/jobs?limit=10`);
        if (!response.ok) throw new Error('Failed to fetch indexing jobs');
        const text = await response.text();
        console.log('/index/jobs response:', text.substring(0, 500));
        return JSON.parse(text);
    } catch (error) {
        console.error('Error fetching indexing jobs:', error);
        return null;
    }
}

// Ground Truth API Functions
async function fetchGroundTruthStats() {
    try {
        const response = await fetch(`${API_BASE}/ground-truth/stats`);
        if (!response.ok) throw new Error('Failed to fetch ground truth stats');
        return await response.json();
    } catch (error) {
        console.error('Error fetching ground truth stats:', error);
        return null;
    }
}

async function fetchMissingGroundTruth() {
    try {
        const response = await fetch(`${API_BASE}/ground-truth/missing?limit=50`);
        if (!response.ok) throw new Error('Failed to fetch missing ground truth');
        return await response.json();
    } catch (error) {
        console.error('Error fetching missing ground truth:', error);
        return null;
    }
}

async function fetchGroundTruth(entryIds) {
    try {
        const response = await fetch(`${API_BASE}/ground-truth/fetch`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ entry_ids: entryIds })
        });
        if (!response.ok) throw new Error('Failed to fetch ground truth');
        return await response.json();
    } catch (error) {
        console.error('Error fetching ground truth:', error);
        alert('Failed to fetch ground truth: ' + error.message);
        return null;
    }
}

async function fetchAllMissingGroundTruth() {
    try {
        const response = await fetch(`${API_BASE}/ground-truth/fetch-all`, {
            method: 'POST'
        });
        if (!response.ok) throw new Error('Failed to fetch all missing ground truth');
        return await response.json();
    } catch (error) {
        console.error('Error fetching all missing ground truth:', error);
        alert('Failed to fetch all missing ground truth: ' + error.message);
        return null;
    }
}

async function fetchGroundTruthJobs() {
    try {
        const response = await fetch(`${API_BASE}/index/jobs?limit=10`);
        if (!response.ok) throw new Error("Failed to fetch ground truth jobs");
        const allJobs = await response.json();
        return allJobs.filter(job =>
            job.job_type === "ground_truth_fetch" || job.job_type === "ground_truth_fetch_all"
        );
    } catch (error) {
        console.error("Error fetching ground truth jobs:", error);
        return null;
    }
}

let gtPollingInterval = null;

function pollGroundTruthJob(jobId, onComplete) {
    const poll = async () => {
        try {
            const response = await fetch(`${API_BASE}/index/jobs?limit=1`);
            if (!response.ok) return;
            const jobs = await response.json();
            const job = jobs.find(j => j.job_id === jobId);

            if (!job) {
                clearInterval(gtPollingInterval);
                return;
            }

            const progressEl = document.getElementById("gtJobProgress");
            if (progressEl && job.total_items > 0) {
                const percent = Math.round((job.processed_items / job.total_items) * 100);
                progressEl.textContent = `${job.status}: ${job.processed_items}/${job.total_items} (${percent}%)`;
            }

            if (job.status === "completed" || job.status === "failed") {
                clearInterval(gtPollingInterval);
                onComplete(job);
            }
        } catch (error) {
            console.error("Error polling ground truth job:", error);
        }
    };

    gtPollingInterval = setInterval(poll, 2000);
    poll();
}

// Database API Functions
async function fetchDatabaseStats() {
    try {
        const response = await fetch(`${API_BASE}/database/stats`);
        if (!response.ok) throw new Error('Failed to fetch database stats');
        return await response.json();
    } catch (error) {
        console.error('Error fetching database stats:', error);
        return null;
    }
}

// Import API Functions
async function startSqliteImport(sourcePath, tables, conflictStrategy) {
    try {
        const requestBody = {
            source_path: sourcePath,
            conflict_strategy: conflictStrategy
        };
        
        // Only include tables if not 'all'
        if (tables && tables !== 'all') {
            requestBody.tables = [tables];
        }
        
        const response = await fetch(`${API_BASE}/import/sqlite`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(requestBody)
        });
        if (!response.ok) throw new Error('Failed to start import');
        return await response.json();
    } catch (error) {
        console.error('Error starting import:', error);
        alert('Failed to start import: ' + error.message);
        return null;
    }
}

async function fetchImportStatus(jobId) {
    try {
        const response = await fetch(`${API_BASE}/import/status/${jobId}`);
        if (!response.ok) throw new Error('Failed to fetch import status');
        return await response.json();
    } catch (error) {
        console.error('Error fetching import status:', error);
        return null;
    }
}

async function fetchImportJobs() {
    try {
        const response = await fetch(`${API_BASE}/import/jobs?limit=10`);
        if (!response.ok) throw new Error('Failed to fetch import jobs');
        return await response.json();
    } catch (error) {
        console.error('Error fetching import jobs:', error);
        return null;
    }
}

// UI Update Functions
function updateStats(stats) {
    if (!stats) return;

    elements.statTotal.textContent = stats.total ?? '-';
    elements.statCompleted.textContent = stats.completed ?? '-';
    elements.statPending.textContent = stats.pending ?? '-';
    elements.statFailed.textContent = stats.failed ?? '-';
}

function updateProgress(activeRun, stats) {
    if (!activeRun) {
        elements.progressBar.style.width = '0%';
        elements.progressText.textContent = '0%';
        elements.batchInfo.textContent = 'No active batch';
        elements.stopBtn.disabled = true;
        return;
    }

    elements.stopBtn.disabled = false;

    const total = stats?.pending || 0;
    const completed = activeRun.entries_processed || 0;
    const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;

    elements.progressBar.style.width = `${percentage}%`;
    elements.progressText.textContent = `${percentage}% (${completed}/${total})`;

    const batchNum = activeRun.batch_number || '?';
    const concurrency = activeRun.concurrency || '?';
    const started = formatTime(activeRun.started_at);

    elements.batchInfo.textContent = `Current batch: #${batchNum} - ${concurrency} entries - Started ${started}`;
}

function renderEntries(entries) {
    if (!entries || entries.length === 0) {
        elements.entriesBody.innerHTML = `
            <tr>
                <td colspan="5" class="loading">No entries found</td>
            </tr>
        `;
        return;
    }

    elements.entriesBody.innerHTML = entries.map(entry => `
        <tr>
            <td>${entry.id || '-'}</td>
            <td>${entry.local_accession || entry.accession || '-'}</td>
            <td>
                <span class="status-badge ${getStatusClass(entry.status)}">
                    ${entry.status || 'unknown'}
                </span>
            </td>
            <td>${entry.run_id || '-'}</td>
            <td class="actions">
                ${entry.status === 'completed' ? `
                    <button class="btn btn-secondary btn-small" onclick="viewResults(${entry.id})">View</button>
                    <button class="btn btn-secondary btn-small" onclick="retryEntry(${entry.id})">Retry</button>
                ` : ''}
                ${entry.status === 'pending' ? `
                    <button class="btn btn-primary btn-small" onclick="validateEntry(${entry.id})">Validate</button>
                ` : ''}
                ${entry.status === 'failed' ? `
                    <button class="btn btn-primary btn-small" onclick="retryEntry(${entry.id})">Retry</button>
                ` : ''}
            </td>
        </tr>
    `).join('');
}

function renderFailedEntries(entries) {
    if (!elements.failedEntriesBody) return;
    
    if (!entries || entries.length === 0) {
        elements.failedEntriesBody.innerHTML = `
            <tr>
                <td colspan="6" class="loading">No failed entries</td>
            </tr>
        `;
        return;
    }

    elements.failedEntriesBody.innerHTML = entries.map(entry => `
        <tr>
            <td>${entry.entry_id || '-'}</td>
            <td>${entry.local_accession || '-'}</td>
            <td>${entry.project_name || '-'}</td>
            <td>${entry.error_message ? entry.error_message.substring(0, 50) + '...' : '-'}</td>
            <td>${formatTime(entry.failed_at)}</td>
            <td class="actions">
                <button class="btn btn-primary btn-small" onclick="retryEntry(${entry.entry_id})">Retry</button>
            </td>
        </tr>
    `).join('');
}

function renderRuns(runs) {
    if (!runs || runs.length === 0) {
        elements.runsBody.innerHTML = `
            <tr>
                <td colspan="5" class="loading">No runs found</td>
            </tr>
        `;
        return;
    }

    elements.runsBody.innerHTML = runs.map(run => `
        <tr>
            <td>${run.id || '-'}</td>
            <td>
                <span class="status-badge ${getStatusClass(run.status)}">
                    ${run.status || 'unknown'}
                </span>
            </td>
            <td>${run.entries_processed || 0} / ${run.entries_total || '-'}</td>
            <td>${formatTime(run.started_at)}</td>
            <td class="actions">
                ${run.status === 'running' ? `
                    <button class="btn btn-danger btn-small" onclick="stopRun('${run.id}')">Stop</button>
                ` : ''}
                <button class="btn btn-secondary btn-small" onclick="viewRunDetails('${run.id}')">Details</button>
            </td>
        </tr>
    `).join('');
}

// Indexing UI Update Functions
function updateIndexingStats(stats) {
    if (!stats) return;

    elements.indexTotal.textContent = stats.total_entries ?? '-';
    elements.indexCompleteness.textContent = stats.completeness_percentage != null ? `${stats.completeness_percentage}%` : '-';
    elements.indexLastTimestamp.textContent = stats.last_indexed_at ? formatTime(stats.last_indexed_at) : '-';
}

function updateIndexingProgress(job) {
    if (!job || job.status !== 'running') {
        elements.indexProgressBar.style.width = '0%';
        elements.indexProgressText.textContent = '0%';
        return;
    }

    const total = job.total_items || 0;
    const processed = job.processed_items || 0;
    const percentage = total > 0 ? Math.round((processed / total) * 100) : 0;

    elements.indexProgressBar.style.width = `${percentage}%`;
    elements.indexProgressText.textContent = `${percentage}% (${processed}/${total})`;
}

function renderIndexingJobs(jobs) {
    if (!jobs || jobs.length === 0) {
        elements.indexingJobsBody.innerHTML = `
            <tr>
                <td colspan="6" class="loading">No indexing jobs found</td>
            </tr>
        `;
        return;
    }

    elements.indexingJobsBody.innerHTML = jobs.map(job => `
        <tr>
            <td>${job.job_id || '-'}</td>
            <td>${job.job_type || '-'}</td>
            <td>
                <span class="status-badge ${getStatusClass(job.status)}">
                    ${job.status || 'unknown'}
                </span>
            </td>
            <td>${job.processed_items || 0} / ${job.total_items || '-'}</td>
            <td>${formatTime(job.created_at)}</td>
            <td class="actions">
                ${job.status === 'failed' ? `
                    <button class="btn btn-primary btn-small" onclick="retryIndexingJob('${job.job_id}')">Retry</button>
                ` : ''}
                <button class="btn btn-danger btn-small" onclick="deleteIndexJob(${job.id})">Delete</button>
            </td>
        </tr>
    `).join('');
}

// Ground Truth UI Update Functions
function updateGroundTruthStats(stats) {
    if (!stats) return;

    elements.gtWithCount.textContent = stats.entries_with_ground_truth ?? '-';
    elements.gtWithoutCount.textContent = stats.entries_without_ground_truth ?? '-';
function updateGroundTruthStats(stats) {
    if (!stats) return;

    elements.gtWithCount.textContent = stats.entries_with_ground_truth ?? '-';
    elements.gtWithoutCount.textContent = stats.entries_without_ground_truth ?? '-';
    elements.gtCoveragePercent.textContent = stats.coverage_percent != null ? `${Math.round(stats.coverage_percent)}%` : '-';
    
    // Enhanced breakdown from dashboard
    if (stats.breakdown_by_type) {
        document.getElementById('gtUniProtCount').textContent = stats.breakdown_by_type.uniprot ?? '-';
        document.getElementById('gtPdbCount').textContent = stats.breakdown_by_type.pdb ?? '-';
        document.getElementById('gtInchiCount').textContent = stats.breakdown_by_type.inchi ?? '-';
        document.getElementById('gtPubchemCount').textContent = stats.breakdown_by_type.pubchem ?? '-';
    }
}
    
    // Calculate coverage percentage if total_entries > 0
    const coveragePercent = stats.total_entries > 0 
        ? Math.round((stats.entries_with_ground_truth / stats.total_entries) * 100) 
        : 0;
    elements.gtCoveragePercent.textContent = `${coveragePercent}%`;

    if (stats.breakdown_by_type) {
        elements.gtUniProtCount.textContent = stats.breakdown_by_type.uniprot ?? '-';
        elements.gtPdbCount.textContent = stats.breakdown_by_type.pdb ?? '-';
        elements.gtInchiCount.textContent = stats.breakdown_by_type.inchi ?? '-';
    }
}

function renderMissingGroundTruth(entries) {
    if (!entries || entries.length === 0) {
        elements.missingGtBody.innerHTML = `
            <tr>
                <td colspan="4" class="loading">No entries missing ground truth</td>
            </tr>
        `;
        return;
    }

    elements.missingGtBody.innerHTML = entries.map(entry => `
        <tr>
            <td>${entry.id || '-'}</td>
            <td>${entry.local_accession || '-'}</td>
            <td>${entry.project_name || '-'}</td>
            <td class="actions">
                <button class="btn btn-primary btn-small" onclick="fetchSingleGroundTruth('${entry.id}')">Fetch Ground Truth</button>
            </td>
        </tr>
    `).join('');
}

// Database UI Update Functions
function renderDatabaseStats(stats) {
    if (!stats || !stats.table_counts) {
        elements.dbStatsBody.innerHTML = `
            <tr>
                <td colspan="4" class="loading">No database stats available</td>
            </tr>
        `;
        return;
    }

    elements.dbStatsBody.innerHTML = Object.entries(stats.table_counts).map(([tableName, rowCount]) => `
        <tr>
            <td>${tableName}</td>
            <td>${rowCount ?? '-'}</td>
            <td>-</td>
            <td>-</td>
        </tr>
    `).join('');
}

// Import UI Update Functions
function updateImportProgress(status) {
    if (!status) {
        elements.importProgressBar.style.width = '0%';
        elements.importProgressText.textContent = '0%';
        elements.importStatusInfo.textContent = 'No active import job';
        return;
    }

    const percentage = status.progress_percentage || 0;
    elements.importProgressBar.style.width = `${percentage}%`;
    elements.importProgressText.textContent = `${percentage}% (${status.processed_items}/${status.total_items})`;

    const statusText = status.status || 'unknown';
    const jobId = status.job_id || '?';
    const sourcePath = status.source_path || 'unknown';
    
    elements.importStatusInfo.textContent = `Job: ${jobId} - Status: ${statusText} - Source: ${sourcePath}`;
}

function renderImportJobs(jobs) {
    if (!elements.importJobsBody) return;
    
    if (!jobs || jobs.length === 0) {
        elements.importJobsBody.innerHTML = `
            <tr>
                <td colspan="5" class="loading">No import jobs found</td>
            </tr>
        `;
        return;
    }

    elements.importJobsBody.innerHTML = jobs.map(job => `
        <tr>
            <td>${job.job_id || '-'}</td>
            <td>
                <span class="status-badge ${getStatusClass(job.status)}">
                    ${job.status || 'unknown'}
                </span>
            </td>
            <td>${job.total_items || '-'}</td>
            <td>${job.processed_items || 0} / ${job.total_items || '-'}</td>
            <td>${formatTime(job.created_at)}</td>
        </tr>
    `).join('');
}

// Action Handlers
async function handleStartBatch() {
    const concurrency = elements.concurrency.value;
    setLoading(true);

    const result = await startBatch(concurrency);
    if (result) {
        console.log('Batch started:', result);
        refreshAll();
    }

    setLoading(false);
}

async function handleStop() {
    const activeRun = await fetchActiveRun();
    if (activeRun && activeRun.id) {
        setLoading(true);
        await stopRun(activeRun.id);
        refreshAll();
        setLoading(false);
    }
}

// Exposed functions for onclick handlers
window.validateEntry = async (entryId) => {
    setLoading(true);
    await _validateEntry(entryId);
    refreshAll();
    setLoading(false);
};

window.retryEntry = async (entryId) => {
    setLoading(true);
    await _retryEntry(entryId);
    refreshAll();
    setLoading(false);
};

window.retryRun = async (runId) => {
    setLoading(true);
    await _retryRun(runId);
    refreshAll();
    setLoading(false);
};

window.retryAllFailed = async () => {
    setLoading(true);
    await _retryAllFailed();
    refreshAll();
    setLoading(false);
};

window.retryIndexingJob = async (jobId) => {
    setLoading(true);
    await _retryIndexingJob(jobId);
    refreshTab('indexing');
    setLoading(false);
};

window.deleteIndexJob = async (jobId) => {
    setLoading(true);
    await _deleteIndexJob(jobId);
    refreshTab('indexing');
    setLoading(false);
};

window.stopRun = async (runId) => {
    setLoading(true);
    await _stopRun(runId);
    refreshAll();
    setLoading(false);
};

window.viewResults = (entryId) => {
    alert(`View results for entry ${entryId} - TODO: Implement results view`);
};

window.viewRunDetails = (runId) => {
    alert(`View details for run ${runId} - TODO: Implement run details view`);
};

window.fetchSingleGroundTruth = async (entryId) => {
    setLoading(true);
    await fetchGroundTruth([entryId]);
    refreshTab('ground-truth');
    setLoading(false);
};

// Tab Switching Function
function switchTab(tabName) {
    currentTab = tabName;

    // Update tab buttons
    elements.tabs.forEach(tab => {
        if (tab.dataset.tab === tabName) {
            tab.classList.add('active');
        } else {
            tab.classList.remove('active');
        }
    });

    // Update tab content visibility
    elements.tabContents.forEach(content => {
        if (content.id === `tab-${tabName}`) {
            content.classList.add('active');
        } else {
            content.classList.remove('active');
        }
    });

    // Refresh data for the selected tab
    refreshTab(tabName);
}

// Tab-specific Refresh Function
async function refreshTab(tabName) {
    switch (tabName) {
        case 'indexing':
            const [indexStats, indexJobs] = await Promise.all([
                fetchIndexingStats(),
                fetchIndexingJobs()
            ]);
            updateIndexingStats(indexStats);
            renderIndexingJobs(indexJobs);
            // Update progress bar for running jobs
            const runningJob = indexJobs?.find(j => j.status === 'running');
            if (runningJob) {
                updateIndexingProgress(runningJob);
            }
            break;

        case "ground-truth":
            const [gtStats, missingGt, gtJobs] = await Promise.all([
                fetchGroundTruthStats(),
                fetchMissingGroundTruth(),
                fetchGroundTruthJobs()
            ]);
            updateGroundTruthStats(gtStats);
            renderMissingGroundTruth(missingGt);

            const runningGtJob = gtJobs?.find(j => j.status === "running");
            if (runningGtJob) {
                const progressEl = document.getElementById("gtJobProgress");
                if (progressEl && runningGtJob.total_items > 0) {
                    const percent = Math.round((runningGtJob.processed_items / runningGtJob.total_items) * 100);
                    progressEl.textContent = `${runningGtJob.status}: ${runningGtJob.processed_items}/${runningGtJob.total_items} (${percent}%)`;
                    progressEl.style.display = "block";
                }
            }
            break;


        case 'database':
            const [dbStats, importJobs] = await Promise.all([
                fetchDatabaseStats(),
                fetchImportJobs()
            ]);
            renderDatabaseStats(dbStats);
            renderImportJobs(importJobs);
            break;

        case 'validation':
            const failedEntries = await fetchFailedEntries();
            renderFailedEntries(failedEntries);
            refreshAll();
            break;
    }
}

// New Action Handlers
async function handleStartIndexing() {
    const limit = null; // No limit - fetch all
    setLoading(true);

    const result = await startIndexing(limit || 999999);
    if (result) {
        console.log('Indexing started:', result);
        refreshTab('indexing');
    }

    setLoading(false);
}

async function handleFetchMissing() {
    const limit = null; // No limit - fetch all
    setLoading(true);

    const result = await fetchMissingMetadata(limit || 999999);
    if (result) {
        console.log('Fetch missing started:', result);
        refreshTab('indexing');
    }

    setLoading(false);
}

async function handleRetryAllFailed() {
    setLoading(true);

    const result = await retryAllFailed();
    if (result) {
        console.log('Retry all failed completed:', result);
        refreshTab('validation');
    }

    setLoading(false);
}


async function handleFetchAllMissingGt() {
    setLoading(true);

    const result = await fetchAllMissingGroundTruth();
    if (result) {
        console.log("Fetch all ground truth started:", result);

        const progressEl = document.getElementById("gtJobProgress");
        if (progressEl) {
            progressEl.textContent = "Starting job...";
            progressEl.style.display = "block";
        }

        pollGroundTruthJob(result.job_id, (job) => {
            console.log("Ground truth job completed:", job);
            if (progressEl) {
                progressEl.style.display = "none";
            }
            refreshTab("ground-truth");
        });
    }

    setLoading(false);
}

async function handleStartImport() {
    const sourcePath = elements.sqliteSourcePath.value;
    const tables = elements.sqliteTables.value;
    const conflictStrategy = elements.conflictStrategy.value;
    
    setLoading(true);

    const result = await startSqliteImport(sourcePath, tables, conflictStrategy);
    if (result) {
        console.log('Import started:', result);
        refreshTab('database');
    }

    setLoading(false);
}

// Main Refresh Function
async function refreshAll() {
    if (isLoading) return;

    const [stats, entries, runs, activeRun] = await Promise.all([
        fetchStats(),
        fetchEntries(),
        fetchRuns(),
        fetchActiveRun()
    ]);

    updateStats(stats);
    updateProgress(activeRun, stats);
    renderEntries(entries);
    renderRuns(runs);

    // Also refresh indexing tab if it's currently visible
    if (currentTab === 'indexing') {
        const [indexStats, indexJobs] = await Promise.all([
            fetchIndexingStats(),
            fetchIndexingJobs()
        ]);
        updateIndexingStats(indexStats);
        renderIndexingJobs(indexJobs);
        const runningJob = indexJobs?.find(j => j.status === 'running');
        if (runningJob) {
            updateIndexingProgress(runningJob);
        }
    }
}

// Initialize
function init() {
    // Validation tab event listeners
    elements.startBatchBtn.addEventListener('click', handleStartBatch);
    elements.stopBtn.addEventListener('click', handleStop);
    elements.refreshBtn.addEventListener('click', refreshAll);
    if (elements.retryAllFailedBtn) {
        elements.retryAllFailedBtn.addEventListener('click', handleRetryAllFailed);
    }

    // Indexing tab event listeners
    elements.startIndexingBtn.addEventListener('click', handleStartIndexing);
    elements.fetchMissingBtn.addEventListener('click', handleFetchMissing);

    // Ground Truth tab event listeners
    elements.fetchAllMissingGtBtn.addEventListener('click', handleFetchAllMissingGt);

    // Import tab event listeners
    if (elements.startImportBtn) {
        elements.startImportBtn.addEventListener('click', handleStartImport);
    }

    // Tab switching event listeners
    elements.tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            switchTab(tab.dataset.tab);
        });
    });

    // Initial load
    refreshAll();

    // Poll every 10 seconds
    pollInterval = setInterval(refreshAll, 10000);

    console.log('BAT3 Validation Dashboard initialized');
}

// Start the app
document.addEventListener('DOMContentLoaded', init);
