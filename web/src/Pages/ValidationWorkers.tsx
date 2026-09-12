import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Chip,
  CircularProgress,
  Alert,
  Button,
  Card,
  CardContent,
  LinearProgress,
  IconButton,
  Tooltip,
  TextField,
  InputAdornment,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import ScaleIcon from '@mui/icons-material/Scale';
import TrendingUpIcon from '@mui/icons-material/TrendingUp';
import StorageIcon from '@mui/icons-material/Storage';
import SpeedIcon from '@mui/icons-material/Speed';

interface WorkerStatus {
  kubernetes: {
    deployment: string;
    desired_replicas: number;
    ready_replicas: number;
    available_replicas: number;
  };
  celery: {
    active_workers: number;
    pool_capacity: number;
    active_tasks: number;
    utilization_percent: number;
  };
  queue: {
    queued: number;
    processing: number;
    estimated_wait_minutes: number;
  };
  recommendation: {
    action: 'scale_up' | 'scale_down' | 'stable';
    suggested_replicas: number;
    reason: string;
  };
}

interface WorkerMetrics {
  period_hours: number;
  metrics: Array<{
    timestamp: string;
    tasks_completed: number;
    avg_duration_seconds: number;
  }>;
  summary: {
    total_tasks: number;
    failed_tasks: number;
    error_rate_percent: number;
    avg_tasks_per_hour: number;
  };
}

export default function ValidationWorkers() {
  const [status, setStatus] = useState<WorkerStatus | null>(null);
  const [metrics, setMetrics] = useState<WorkerMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [scaling, setScaling] = useState(false);
  const [targetReplicas, setTargetReplicas] = useState<number>(10);

  const fetchStatus = async () => {
    try {
      const response = await fetch('/validation/workers/status');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      setStatus(result);
      setTargetReplicas(result.kubernetes.desired_replicas);
    } catch (err: any) {
      setError(err.message);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await fetch('/validation/workers/metrics?hours=24');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      setMetrics(result);
    } catch (err: any) {
      console.error('Failed to fetch metrics:', err);
    }
  };

  const handleScale = async () => {
    if (!status) return;
    setScaling(true);
    setError(null);
    try {
      const response = await fetch('/validation/workers/scale', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          replicas: targetReplicas,
          reason: 'Manual scaling via UI'
        }),
      });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Scaling failed');
      await fetchStatus();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setScaling(false);
    }
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchStatus(), fetchMetrics()]);
      setLoading(false);
    };
    loadData();
    const interval = setInterval(fetchStatus, 30000); // Refresh every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading && !status) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: 400 }}>
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return (
      <Alert severity="error" sx={{ mb: 3 }}>
        {error}
      </Alert>
    );
  }

  if (!status) return null;

  const getUtilizationColor = (percent: number) => {
    if (percent > 80) return 'error.main';
    if (percent > 50) return 'warning.main';
    return 'success.main';
  };

  const getRecommendationColor = (action: string) => {
    if (action === 'scale_up') return 'error.main';
    if (action === 'scale_down') return 'info.main';
    return 'success.main';
  };

  return (
    <Box>
      <Box sx={{ mb: 3, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Box>
          <Typography variant="h5" fontWeight="600" gutterBottom>
            Worker Management
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Monitor and scale validation worker pool
          </Typography>
        </Box>
        <Tooltip title="Refresh">
          <IconButton onClick={fetchStatus} disabled={loading}>
            <RefreshIcon />
          </IconButton>
        </Tooltip>
      </Box>

      {/* Deployment Status */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" fontWeight="600" gutterBottom>
          Deployment Status
        </Typography>
        <Grid container spacing={3} sx={{ mt: 1 }}>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: 'background.default' }}>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <StorageIcon color="action" />
                  <Typography variant="body2" color="text.secondary">Replicas</Typography>
                </Box>
                <Typography variant="h4" fontWeight="bold">
                  {status.kubernetes.ready_replicas} / {status.kubernetes.desired_replicas}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  Ready / Desired
                </Typography>
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: 'background.default' }}>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <SpeedIcon color="action" />
                  <Typography variant="body2" color="text.secondary">Utilization</Typography>
                </Box>
                <Typography variant="h4" fontWeight="bold" color={getUtilizationColor(status.celery.utilization_percent)}>
                  {status.celery.utilization_percent.toFixed(1)}%
                </Typography>
                <LinearProgress
                  variant="determinate"
                  value={status.celery.utilization_percent}
                  sx={{ mt: 1, height: 6, borderRadius: 3 }}
                  color={status.celery.utilization_percent > 80 ? 'error' : status.celery.utilization_percent > 50 ? 'warning' : 'success'}
                />
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} sm={4}>
            <Card sx={{ bgcolor: 'background.default' }}>
              <CardContent>
                <Box display="flex" alignItems="center" gap={1} mb={1}>
                  <TrendingUpIcon color="action" />
                  <Typography variant="body2" color="text.secondary">Recommendation</Typography>
                </Box>
                <Chip
                  label={status.recommendation.action.replace('_', ' ').toUpperCase()}
                  color={status.recommendation.action === 'scale_up' ? 'error' : status.recommendation.action === 'scale_down' ? 'info' : 'success'}
                  size="small"
                />
                <Typography variant="caption" color="text.secondary" display="block" sx={{ mt: 1 }}>
                  {status.recommendation.reason}
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Paper>

      {/* Capacity & Queue */}
      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="600" gutterBottom>
              Worker Capacity
            </Typography>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">Total Workers</Typography>
                <Typography variant="h5" fontWeight="bold">{status.celery.active_workers}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">Pool Capacity</Typography>
                <Typography variant="h5" fontWeight="bold">{status.celery.pool_capacity}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">Active Tasks</Typography>
                <Typography variant="h5" fontWeight="bold" color="warning.main">{status.celery.active_tasks}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">Idle Workers</Typography>
                <Typography variant="h5" fontWeight="bold">{status.celery.active_workers}</Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="600" gutterBottom>
              Queue Status
            </Typography>
            <Grid container spacing={2} sx={{ mt: 1 }}>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">Queued</Typography>
                <Typography variant="h5" fontWeight="bold" color="info.main">{status.queue.queued.toLocaleString()}</Typography>
              </Grid>
              <Grid item xs={6}>
                <Typography variant="body2" color="text.secondary">Processing</Typography>
                <Typography variant="h5" fontWeight="bold" color="warning.main">{status.queue.processing.toLocaleString()}</Typography>
              </Grid>
              <Grid item xs={12}>
                <Typography variant="body2" color="text.secondary">Estimated Wait</Typography>
                <Typography variant="h5" fontWeight="bold">
                  {status.queue.estimated_wait_minutes >= 60
                    ? `${(status.queue.estimated_wait_minutes / 60).toFixed(1)} hours`
                    : `${Math.round(status.queue.estimated_wait_minutes)} minutes`
                  }
                </Typography>
              </Grid>
            </Grid>
          </Paper>
        </Grid>
      </Grid>

      {/* Scaling Controls */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" fontWeight="600" gutterBottom>
          Scale Workers
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Adjust the number of worker replicas (0-50). Changes take 1-2 minutes to apply.
        </Typography>
        <Box display="flex" gap={2} alignItems="flex-end">
          <TextField
            type="number"
            label="Target Replicas"
            value={targetReplicas}
            onChange={(e) => setTargetReplicas(Math.max(0, Math.min(50, parseInt(e.target.value) || 0)))}
            InputProps={{
              inputProps: { min: 0, max: 50 },
              startAdornment: <InputAdornment position="start"><ScaleIcon /></InputAdornment>,
            }}
            size="small"
            sx={{ width: 200 }}
          />
          <Button
            variant="contained"
            onClick={handleScale}
            disabled={scaling || targetReplicas === status.kubernetes.desired_replicas}
          >
            {scaling ? <CircularProgress size={24} /> : 'Apply Scaling'}
          </Button>
          {status.recommendation.action !== 'stable' && (
            <Button
              variant="outlined"
              onClick={() => setTargetReplicas(status.recommendation.suggested_replicas)}
              disabled={scaling}
            >
              Use Recommendation ({status.recommendation.suggested_replicas})
            </Button>
          )}
        </Box>
      </Paper>

      {/* Metrics Summary */}
      {metrics && (
        <Paper sx={{ p: 3 }}>
          <Typography variant="h6" fontWeight="600" gutterBottom>
            24h Performance Metrics
          </Typography>
          <Grid container spacing={3} sx={{ mt: 1 }}>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Tasks Completed</Typography>
              <Typography variant="h5" fontWeight="bold">{metrics.summary.total_tasks}</Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Failed Tasks</Typography>
              <Typography variant="h5" fontWeight="bold" color="error.main">{metrics.summary.failed_tasks}</Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Error Rate</Typography>
              <Typography variant="h5" fontWeight="bold" color={metrics.summary.error_rate_percent > 10 ? 'error.main' : 'success.main'}>
                {metrics.summary.error_rate_percent.toFixed(2)}%
              </Typography>
            </Grid>
            <Grid item xs={12} sm={3}>
              <Typography variant="body2" color="text.secondary">Avg Tasks/Hour</Typography>
              <Typography variant="h5" fontWeight="bold">{metrics.summary.avg_tasks_per_hour}</Typography>
            </Grid>
          </Grid>
        </Paper>
      )}
    </Box>
  );
}
