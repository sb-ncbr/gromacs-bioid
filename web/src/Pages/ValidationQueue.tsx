import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  CircularProgress,
  Alert,
  Divider,
  Chip,
  Button,
} from '@mui/material';
import QueueTable from '../Components/Validation/QueueTable';

interface QueueData {
  queue: {
    queued: number;
    processing: number;
    paused: number;
    completed: number;
    failed: number;
  };
  active_batches: Array<{
    batch_id: string;
    status: string;
    total_entries: number;
    completed_entries: number;
    failed_entries: number;
    started_at: string;
  }>;
}

export default function ValidationQueue() {
  const [data, setData] = useState<QueueData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchQueueStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/api/validation/queue/status');
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      setData(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleBulkAction = async (action: string, selectedIds: number[]) => {
    try {
      const response = await fetch('/api/validation/queue/bulk-action', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action, queue_item_ids: selectedIds }),
      });
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      
      const result = await response.json();
      
      if (result.success) {
        alert(`"${action.replace(/_/g, ' ').toUpperCase()}": ${result.affected || result.deleted || 0} items affected`);
      } else {
        alert(`"${action.replace(/_/g, ' ').toUpperCase()}" failed: ${result.error}`);
      }
      
      await fetchQueueStatus();
    } catch (err: any) {
      setError(err.message);
      alert(`Error: ${err.message}`);
    }
  };
  
  const handleProcessorAction = async (action: string) => {
    try {
      const response = await fetch(`/api/validation/queue/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      
      const result = await response.json();
      alert(result.success ? result.message : result.error);
      fetchQueueStatus();
    } catch (err: any) {
      alert(`Error: ${err.message}`);
    }
  };

  useEffect(() => {
    fetchQueueStatus();
    const interval = setInterval(fetchQueueStatus, 5000); // Refresh every 5 seconds
    return () => {
      clearInterval(interval);
    };
  }, []);

  if (loading && !data) {
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

  if (!data) return null;

  const total = data.queue.queued + data.queue.processing + data.queue.completed + data.queue.failed;
  const progressPercent = total > 0 ? Math.round(((data.queue.completed + data.queue.failed) / total) * 100) : 0;

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight="600" gutterBottom>
          Queue Status
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Real-time validation queue metrics
        </Typography>
      </Box>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Queued
              </Typography>
              <Typography variant="h3" fontWeight="bold" color="info.main">
                {data.queue.queued.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Processing
              </Typography>
              <Typography variant="h3" fontWeight="bold" color="warning.main">
                {data.queue.processing.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Completed
              </Typography>
              <Typography variant="h3" fontWeight="bold" color="success.main">
                {data.queue.completed.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Failed
              </Typography>
              <Typography variant="h3" fontWeight="bold" color="error.main">
                {data.queue.failed.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Total
              </Typography>
              <Typography variant="h3" fontWeight="bold">
                {total.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={2}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Progress
              </Typography>
              <Typography variant="h3" fontWeight="bold">
                {progressPercent}%
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Queue Actions */}
      <Paper sx={{ p: 2, mb: 3 }}>
        <Grid container spacing={2}>
          <Grid item>
            <Button 
              variant="contained" 
              color="primary"
              onClick={() => handleBulkAction('queue_all_pending', [])}
            >
              Queue All Pending
            </Button>
          </Grid>
          <Grid item>
            <Button 
              variant="contained" 
              color="error"
              onClick={() => handleBulkAction('queue_all_failed', [])}
            >
              Queue All Failed
            </Button>
          </Grid>
          <Grid item>
            <Button 
              variant="outlined"
              onClick={() => handleBulkAction('clear_completed', [])}
            >
              Clear Completed
            </Button>
          </Grid>
          <Grid item>
            <Button 
              variant="outlined"
              color="warning"
              onClick={() => handleBulkAction('clear_all', [])}
            >
              Clear ALL
            </Button>
          </Grid>
        </Grid>
        
        {/* Processor Control */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mt: 3, mb: 1 }}>
          <Typography variant="h6">
            Processor Control
          </Typography>
          <Chip 
            label={data?.queue?.processing > 0 ? '🟢 RUNNING' : data?.queue?.queued > 0 ? '🟡 QUEUED' : '🔴 IDLE'}
            color={data?.queue?.processing > 0 ? 'success' : data?.queue?.queued > 0 ? 'warning' : 'default'}
            size="small"
          />
        </Box>
        <Grid container spacing={2}>
          <Grid item>
            <Button 
              variant="contained" 
              color="success"
              onClick={() => handleProcessorAction('start-processing')}
            >
              ▶ Start
            </Button>
          </Grid>
          <Grid item>
            <Button 
              variant="outlined" 
              color="warning"
              onClick={() => handleProcessorAction('pause-processing')}
            >
              ⏸ Pause
            </Button>
          </Grid>
          <Grid item>
            <Button 
              variant="outlined"
              onClick={() => handleProcessorAction('resume-processing')}
            >
              ▶️ Resume
            </Button>
          </Grid>
          <Grid item>
            <Button 
              variant="outlined"
              color="error"
              onClick={() => handleProcessorAction('stop-processing')}
            >
              ⏹ Stop
            </Button>
          </Grid>
        </Grid>
      </Paper>

      {/* Queue Table */}
      <QueueTable onBulkAction={handleBulkAction} />

      <Paper sx={{ p: 3, mt: 3 }}>
        <Typography variant="h6" fontWeight="600" gutterBottom>
          Active Batches
        </Typography>
        <Divider sx={{ mb: 2 }} />
        {data.active_batches && data.active_batches.length > 0 ? (
          <Grid container spacing={2}>
            {data.active_batches.map((batch) => (
              <Grid item xs={12} md={6} key={batch.batch_id}>
                <Paper sx={{ p: 2, bgcolor: 'background.default' }}>
                  <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                    <Typography variant="subtitle2" fontWeight="600">
                      {batch.batch_id}
                    </Typography>
                    <Chip
                      label={batch.status}
                      color={batch.status === 'running' ? 'success' : 'default'}
                      size="small"
                    />
                  </Box>
                  <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
                    {batch.completed_entries.toLocaleString()} / {batch.total_entries.toLocaleString()} completed
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {batch.failed_entries.toLocaleString()} failed
                  </Typography>
                </Paper>
              </Grid>
            ))}
          </Grid>
        ) : (
          <Typography variant="body2" color="text.secondary">
            No active batches
          </Typography>
        )}
      </Paper>
    </Box>
  );
}
