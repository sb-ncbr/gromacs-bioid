import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Paper,
  Grid,
  Card,
  CardContent,
  Button,
  CircularProgress,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Alert,
  Divider,
  Chip,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';

interface FailureAnalysisData {
  status: string;
  summary: {
    total_failed_runs: number;
    total_failed_queue: number;
    analyzed_runs: number;
    analyzed_queue: number;
  };
  categories: Record<string, number>;
  top_errors: Array<{
    error: string;
    count: number;
  }>;
  recommendations: string[];
}

export default function ValidationFailureAnalysis() {
  const [data, setData] = useState<FailureAnalysisData | null>(null);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const runAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch('/validation/stats/failure-analysis');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const result = await response.json();
      setData(result);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const startAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    try {
      // Trigger a fresh analysis
      await runAnalysis();
    } finally {
      setAnalyzing(false);
    }
  };

  useEffect(() => {
    runAnalysis();
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

  return (
    <Box>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Box>
          <Typography variant="h5" fontWeight="600" gutterBottom>
            Failure Analysis
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Analysis of validation failures
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', gap: 2 }}>
          <Button
            variant="outlined"
            startIcon={<PlayArrowIcon />}
            onClick={startAnalysis}
            disabled={analyzing || loading}
            size="small"
          >
            {analyzing ? 'Analyzing...' : 'Analyze Failures'}
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={runAnalysis}
            disabled={loading}
            size="small"
          >
            Refresh
          </Button>
        </Box>
      </Box>

      <Grid container spacing={3} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Failed Runs
              </Typography>
              <Typography variant="h4" fontWeight="bold" color="error.main">
                {data.summary.total_failed_runs.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Failed Queue
              </Typography>
              <Typography variant="h4" fontWeight="bold" color="error.main">
                {data.summary.total_failed_queue.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Analyzed Runs
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {data.summary.analyzed_runs.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={6} md={3}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary" gutterBottom>
                Analyzed Queue
              </Typography>
              <Typography variant="h4" fontWeight="bold">
                {data.summary.analyzed_queue.toLocaleString()}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      <Grid container spacing={3}>
        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="600" gutterBottom>
              Error Categories
            </Typography>
            <Divider sx={{ mb: 2 }} />
            {Object.entries(data.categories)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 10)
              .map(([category, count]) => (
                <Box key={category} sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', py: 1 }}>
                  <Typography variant="body2">{category}</Typography>
                  <Chip label={count.toLocaleString()} size="small" />
                </Box>
              ))}
          </Paper>
        </Grid>

        <Grid item xs={12} md={6}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="600" gutterBottom>
              Recommendations
            </Typography>
            <Divider sx={{ mb: 2 }} />
            {data.recommendations.length > 0 ? (
              data.recommendations.map((rec, i) => (
                <Box key={i} sx={{ display: 'flex', gap: 2, mb: 2 }}>
                  <Typography variant="body2" color="primary.main" fontWeight="600">
                    {i + 1}.
                  </Typography>
                  <Typography variant="body2">{rec}</Typography>
                </Box>
              ))
            ) : (
              <Typography variant="body2" color="text.secondary">
                No recommendations available
              </Typography>
            )}
          </Paper>
        </Grid>

        <Grid item xs={12}>
          <Paper sx={{ p: 3 }}>
            <Typography variant="h6" fontWeight="600" gutterBottom>
              Top Errors
            </Typography>
            <Divider sx={{ mb: 2 }} />
            {data.top_errors && data.top_errors.length > 0 ? (
              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell><strong>Error</strong></TableCell>
                      <TableCell align="right"><strong>Count</strong></TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {data.top_errors.map((err, i) => (
                      <TableRow key={i} hover>
                        <TableCell>
                          <Typography variant="body2">{err.error}</Typography>
                        </TableCell>
                        <TableCell align="right">
                          <Chip label={err.count.toLocaleString()} size="small" />
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            ) : (
              <Typography variant="body2" color="text.secondary">
                No detailed error data available
              </Typography>
            )}
          </Paper>
        </Grid>
      </Grid>
    </Box>
  );
}
