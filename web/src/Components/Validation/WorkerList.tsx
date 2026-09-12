import React, { useState, useEffect } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Chip,
  Button,
  CircularProgress,
  Alert,
  LinearProgress,
  IconButton,
  Tooltip,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import RefreshIcon from '@mui/icons-material/Refresh';
import RestartAltIcon from '@mui/icons-material/RestartAlt';
import HealthAndSafetyIcon from '@mui/icons-material/HealthAndSafety';

interface Worker {
  name: string;
  active_tasks: number;
  uptime: number;
  pool_size: number;
  total_tasks: number;
  registered_tasks: number;
  status: 'active' | 'idle' | 'offline';
}

interface WorkerListProps {
  onScale?: (count: number) => void;
  onRestart?: (workerName: string) => void;
  onPing?: (workerName: string) => void;
}

const WorkerCard = styled(Card)<{ status: string }>(({ theme, status }) => ({
  height: '100%',
  borderLeft: `4px solid ${
    status === 'active' ? theme.palette.success.main :
    status === 'idle' ? theme.palette.warning.main :
    theme.palette.error.main
  }`,
  transition: 'transform 0.2s, box-shadow 0.2s',
  '&:hover': {
    transform: 'translateY(-4px)',
    boxShadow: theme.shadows[8],
  },
}));

export default function WorkerList({ onScale, onRestart, onPing }: WorkerListProps) {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pinging, setPinging] = useState<Record<string, boolean>>({});

  const fetchWorkers = async () => {
    setLoading(true);
    try {
      const response = await fetch('/validation/queue/workers');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setWorkers(data.workers || []);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handlePing = async (workerName: string) => {
    setPinging({ ...pinging, [workerName]: true });
    try {
      const response = await fetch('/api/validation/queue/workers/ping', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ worker_name: workerName }),
      });
      if (!response.ok) {
        throw new Error(`Ping failed: ${response.status}`);
      }
      await fetchWorkers();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setPinging({ ...pinging, [workerName]: false });
    }
  };

  const handleRestart = async (workerName: string) => {
    if (onRestart) {
      onRestart(workerName);
    }
  };

  useEffect(() => {
    fetchWorkers();
    const interval = setInterval(fetchWorkers, 10000);
    return () => clearInterval(interval);
  }, []);

  const formatUptime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${minutes}m`;
  };

  const totalActiveTasks = workers.reduce((sum, w) => sum + w.active_tasks, 0);
  const totalTasks = workers.reduce((sum, w) => sum + w.total_tasks, 0);
  const avgPoolSize = workers.length > 0 ? Math.round(workers.reduce((sum, w) => sum + w.pool_size, 0) / workers.length) : 0;

  if (loading && workers.length === 0) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="300px">
        <CircularProgress />
      </Box>
    );
  }

  if (error) {
    return <Alert severity="error">{error}</Alert>;
  }

  return (
    <Box>
      {/* Summary Stats */}
      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <Card sx={{ bgcolor: 'background.default' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary">Total Workers</Typography>
              <Typography variant="h4" fontWeight="bold">{workers.length}</Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card sx={{ bgcolor: 'background.default' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary">Active Tasks</Typography>
              <Typography variant="h4" fontWeight="bold" color={totalActiveTasks > 0 ? 'warning.main' : 'text.secondary'}>
                {totalActiveTasks}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card sx={{ bgcolor: 'background.default' }}>
            <CardContent>
              <Typography variant="body2" color="text.secondary">Total Tasks Processed</Typography>
              <Typography variant="h4" fontWeight="bold">{totalTasks.toLocaleString()}</Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Worker Cards */}
      {workers.length === 0 ? (
        <Alert severity="info">No workers available. Scale up workers to start processing.</Alert>
      ) : (
        <Grid container spacing={3}>
          {workers.map((worker, idx) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={idx}>
              <WorkerCard status={worker.status}>
                <CardContent>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Typography variant="h6" noWrap sx={{ maxWidth: '70%' }}>
                      {worker.name.split('@')[1] || worker.name}
                    </Typography>
                    <Chip
                      label={worker.status}
                      size="small"
                      color={worker.status === 'active' ? 'success' : worker.status === 'idle' ? 'warning' : 'error'}
                    />
                  </Box>

                  <Box sx={{ mb: 2 }}>
                    <Typography variant="body2" color="text.secondary" gutterBottom>
                      Active Tasks: {worker.active_tasks}
                    </Typography>
                    <LinearProgress
                      variant="determinate"
                      value={(worker.active_tasks / Math.max(worker.pool_size, 1)) * 100}
                      sx={{ height: 6, borderRadius: 3 }}
                    />
                  </Box>

                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Pool Size: {worker.pool_size}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Uptime: {formatUptime(worker.uptime)}
                  </Typography>
                  <Typography variant="body2" color="text.secondary" gutterBottom>
                    Total Tasks: {worker.total_tasks.toLocaleString()}
                  </Typography>

                  <Box display="flex" gap={1} sx={{ mt: 2 }}>
                    <Tooltip title="Health Check">
                      <IconButton
                        size="small"
                        onClick={() => handlePing(worker.name)}
                        disabled={pinging[worker.name]}
                      >
                        {pinging[worker.name] ? <CircularProgress size={18} /> : <HealthAndSafetyIcon />}
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Restart Worker">
                      <IconButton
                        size="small"
                        onClick={() => handleRestart(worker.name)}
                      >
                        <RestartAltIcon />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Refresh">
                      <IconButton size="small" onClick={fetchWorkers}>
                        <RefreshIcon />
                      </IconButton>
                    </Tooltip>
                  </Box>
                </CardContent>
              </WorkerCard>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Scale Controls */}
      {onScale && (
        <Box display="flex" justifyContent="flex-end" gap={2} sx={{ mt: 3 }}>
          <Button variant="outlined" onClick={() => onScale(Math.max(0, workers.length - 1))}>
            Scale Down
          </Button>
          <Button variant="contained" onClick={() => onScale(workers.length + 1)}>
            Scale Up
          </Button>
        </Box>
      )}
    </Box>
  );
}
