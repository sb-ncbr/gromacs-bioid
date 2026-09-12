import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  Button,
  Grid,
  Chip,
  Alert,
} from '@mui/material';
import { styled } from '@mui/material/styles';

interface QueueStatus {
  queued: number;
  processing: number;
  paused: number;
  completed: number;
  failed: number;
  progress_percent?: number;
}

interface ApiResponse {
  queue: QueueStatus;
  active_batches?: Array<{
    batch_id: string;
    status: string;
    total_entries: number;
    completed_entries: number;
    failed_entries: number;
    started_at: string;
  }>;
}

const ProgressWrapper = styled(Paper)(({ theme }) => ({
  padding: theme.spacing(3),
  marginBottom: theme.spacing(2),
}));

export default function ProgressBar() {
  const [status, setStatus] = useState<ApiResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/validation/queue/status');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setStatus(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !status) {
    return (
      <ProgressWrapper>
        <LinearProgress />
      </ProgressWrapper>
    );
  }

  if (error) {
    return (
      <ProgressWrapper>
        <Alert severity="error">{error}</Alert>
      </ProgressWrapper>
    );
  }

  if (!status) return null;

  const queue = status.queue;
  const total = queue.queued + queue.processing + queue.completed + queue.failed;
  const progressPercent = total > 0 ? ((queue.completed + queue.failed) / total) * 100 : 0;
  const remaining = queue.queued + queue.processing;

  return (
    <ProgressWrapper>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
        <Typography variant="h6" fontWeight="bold">
          Queue Processing Progress
        </Typography>
        <Chip
          label={`${remaining} items remaining`}
          variant="outlined"
          size="small"
        />
      </Box>

      <Box sx={{ mb: 2 }}>
        <Box display="flex" justifyContent="space-between" mb={1}>
          <Typography variant="body2" color="text.secondary">
            {remaining} items remaining
          </Typography>
          <Typography variant="body2" fontWeight="600">
            {progressPercent.toFixed(1)}% complete
          </Typography>
        </Box>
        <LinearProgress
          variant="determinate"
          value={progressPercent}
          sx={{ height: 10, borderRadius: 5 }}
        />
      </Box>

      <Grid container spacing={2} sx={{ mt: 1 }}>
        <Grid item xs={6} sm={3}>
          <Box textAlign="center">
            <Typography variant="h6" fontWeight="bold" color="text.secondary">
              {queue.queued}
            </Typography>
            <Typography variant="body2" color="text.secondary">Queued</Typography>
          </Box>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Box textAlign="center">
            <Typography variant="h6" fontWeight="bold" color="warning.main">
              {queue.processing}
            </Typography>
            <Typography variant="body2" color="text.secondary">Processing</Typography>
          </Box>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Box textAlign="center">
            <Typography variant="h6" fontWeight="bold" color="success.main">
              {queue.completed}
            </Typography>
            <Typography variant="body2" color="text.secondary">Completed</Typography>
          </Box>
        </Grid>
        <Grid item xs={6} sm={3}>
          <Box textAlign="center">
            <Typography variant="h6" fontWeight="bold" color="error.main">
              {queue.failed}
            </Typography>
            <Typography variant="body2" color="text.secondary">Failed</Typography>
          </Box>
        </Grid>
      </Grid>

      {status.active_batches && status.active_batches.length > 0 && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" fontWeight="600" gutterBottom>
            Active Batches: {status.active_batches.length}
          </Typography>
          {status.active_batches.map((batch) => (
            <Chip
              key={batch.batch_id}
              label={`${batch.batch_id} (${batch.status})`}
              size="small"
              sx={{ mr: 1, mb: 1 }}
              color={batch.status === 'running' ? 'success' : 'default'}
            />
          ))}
        </Box>
      )}
    </ProgressWrapper>
  );
}
