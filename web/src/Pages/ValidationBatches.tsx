import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TablePagination,
  Chip,
  Paper,
  LinearProgress,
  Alert,
} from '@mui/material';

interface Batch {
  batch_id: string;
  status: string;
  total_entries: number;
  completed_entries: number;
  failed_entries: number;
  started_at: string;
}

interface QueueStatus {
  queue: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
  };
  active_batches: Batch[];
}

export default function ValidationBatches() {
  const [batches, setBatches] = useState<Batch[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(10);

  const fetchBatches = async () => {
    setLoading(true);
    try {
      // Get batches from queue status endpoint
      const response = await fetch('/validation/queue/status');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data: QueueStatus = await response.json();
      setBatches(data.active_batches || []);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBatches();
    const interval = setInterval(fetchBatches, 10000);
    return () => clearInterval(interval);
  }, []);

  const getStatusChip = (status: string) => {
    const colors: Record<string, 'default' | 'success' | 'warning' | 'error'> = {
      completed: 'success',
      processing: 'warning',
      failed: 'error',
      pending: 'default',
      running: 'warning',
    };
    return (
      <Chip
        label={status}
        color={colors[status] || 'default'}
        size="small"
        sx={{ fontWeight: 600 }}
      />
    );
  };

  const calculateProgress = (batch: Batch) => {
    if (batch.total_entries === 0) return 0;
    return Math.round(((batch.completed_entries + batch.failed_entries) / batch.total_entries) * 100);
  };

  const handleCancelBatch = async (batchId: string) => {
    if (!window.confirm(`Cancel batch ${batchId}? This will cancel all associated queue items.`)) {
      return;
    }
    
    try {
      const response = await fetch(`/batch-runs/${batchId}/cancel`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const result = await response.json();
      alert(result.success ? `Batch cancelled: ${result.message}` : `Failed: ${result.error}`);
      fetchBatches();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };
  
  const formatDate = (dateStr: string) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('cs-CZ', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const handleChangePage = (_: unknown, newPage: number) => setPage(newPage);
  const handleChangeRowsPerPage = (e: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(e.target.value, 10));
    setPage(0);
  };

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight="600" gutterBottom>
          Batches
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Active validation batches
        </Typography>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ width: '100%', overflow: 'hidden' }}>
        {loading && batches.length === 0 ? (
          <LinearProgress />
        ) : (
          <>
            <TableContainer sx={{ maxHeight: 'calc(100vh - 350px)' }}>
              <Table stickyHeader size="medium">
                <TableHead>
                  <TableRow>
                    <TableCell><strong>Batch ID</strong></TableCell>
                    <TableCell><strong>Status</strong></TableCell>
                    <TableCell align="right"><strong>Total</strong></TableCell>
                    <TableCell align="right"><strong>Completed</strong></TableCell>
                    <TableCell align="right"><strong>Failed</strong></TableCell>
                    <TableCell align="right"><strong>Progress</strong></TableCell>
                    <TableCell><strong>Started</strong></TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {batches
                    .slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage)
                    .map((batch) => (
                      <TableRow
                        key={batch.batch_id}
                        hover
                        sx={{ '&:last-child td, &:last-child th': { border: 0 } }}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight="500">
                            {batch.batch_id}
                          </Typography>
                        </TableCell>
                        <TableCell>{getStatusChip(batch.status)}</TableCell>
                        <TableCell align="right">{batch.total_entries.toLocaleString()}</TableCell>
                        <TableCell align="right">{batch.completed_entries.toLocaleString()}</TableCell>
                        <TableCell align="right">{batch.failed_entries.toLocaleString()}</TableCell>
                        <TableCell align="right" sx={{ minWidth: 150 }}>
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                            <LinearProgress
                              variant="determinate"
                              value={calculateProgress(batch)}
                              sx={{ flexGrow: 1, height: 6, borderRadius: 1 }}
                            />
                            <Typography variant="body2" color="text.secondary" sx={{ minWidth: 45 }}>
                              {calculateProgress(batch)}%
                            </Typography>
                          </Box>
                        </TableCell>
                        <TableCell>
                          <Typography variant="body2" color="text.secondary">
                            {formatDate(batch.started_at)}
                          </Typography>
                        </TableCell>
                      </TableRow>
                    ))}
                  {batches.length === 0 && !loading && (
                    <TableRow>
                      <TableCell colSpan={7} align="center">
                        <Typography variant="body2" color="text.secondary" sx={{ py: 4 }}>
                          No active batches
                        </Typography>
                      </TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </TableContainer>
            <TablePagination
              rowsPerPageOptions={[10, 25, 50, 100]}
              component="div"
              count={batches.length}
              rowsPerPage={rowsPerPage}
              page={page}
              onPageChange={handleChangePage}
              onRowsPerPageChange={handleChangeRowsPerPage}
              sx={{ borderTop: 1, borderColor: 'divider' }}
            />
          </>
        )}
      </Paper>
    </Box>
  );
}
