import React, { useState, useEffect } from 'react';
import {
    Box,
    Button,
    Typography,
    Paper,
    Grid,
    Card,
    CardContent,
    CircularProgress,
    List,
    ListItem,
    ListItemText,
    ListItemSecondaryAction,
    Chip,
    Alert,
    AlertTitle,
} from '@mui/material';
import { styled } from '@mui/material/styles';

interface FailureAnalysisData {
    analyzed_at: string;
    database: {
        total_failed_runs: number;
        with_results_json: number;
        without_results_json: number;
        error_categories: Record<string, number>;
        recent_failures: any[];
    };
    results_files: {
        runs_analyzed: number;
        task_failures: Record<string, number>;
        failure_points: Record<string, number>;
    };
    summary: {
        total_db_failures: number;
        hung_before_completion: number;
        most_common_error_category: [string, number] | null;
    };
    recommendations: string[];
}

const StatCard = styled(Card)(({ theme, color = 'primary' }) => ({
    height: '100%',
    borderLeft: `4px solid ${(theme.palette as any)[color]?.main || theme.palette.primary.main}`,
    transition: 'transform 0.2s',
    '&:hover': {
        transform: 'translateY(-4px)',
    },
}));

export default function FailureAnalysis() {
    const [data, setData] = useState<FailureAnalysisData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const runAnalysis = async () => {
        setLoading(true);
        setError(null);
        try {
            const response = await fetch('/api/failure-analysis');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            setData(result);
        } catch (err: any) {
            setError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        runAnalysis();
    }, []);

    if (loading && !data) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress size={60} />
            </Box>
        );
    }

    return (
        <Box sx={{ p: 3, maxWidth: 1400, mx: 'auto' }}>
            <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
                <Typography variant="h3" component="h1" gutterBottom>
                    🔍 Failure Analysis
                </Typography>
                <Button
                    variant="contained"
                    size="large"
                    onClick={runAnalysis}
                    disabled={loading}
                    sx={{ minWidth: 150 }}
                >
                    {loading ? 'Analyzing...' : 'Run Analysis'}
                </Button>
            </Box>

            {error && (
                <Alert severity="error" sx={{ mb: 3 }}>
                    <AlertTitle>Error</AlertTitle>
                    {error}
                </Alert>
            )}

            {data && (
                <>
                    {/* Summary Stats */}
                    <Grid container spacing={3} mb={3}>
                        <Grid xs={12} sm={6} md={3}>
                            <StatCard color="error">
                                <CardContent>
                                    <Typography variant="h4" fontWeight="bold">
                                        {data.database.total_failed_runs.toLocaleString()}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Total Failed Runs
                                    </Typography>
                                </CardContent>
                            </StatCard>
                        </Grid>
                        <Grid xs={12} sm={6} md={3}>
                            <StatCard color="error">
                                <CardContent>
                                    <Typography variant="h4" fontWeight="bold">
                                        {data.database.without_results_json.toLocaleString()}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Hung (No Results)
                                    </Typography>
                                </CardContent>
                            </StatCard>
                        </Grid>
                        <Grid xs={12} sm={6} md={3}>
                            <StatCard color="warning">
                                <CardContent>
                                    <Typography variant="h4" fontWeight="bold">
                                        {data.database.with_results_json.toLocaleString()}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Completed w/ Errors
                                    </Typography>
                                </CardContent>
                            </StatCard>
                        </Grid>
                        <Grid xs={12} sm={6} md={3}>
                            <StatCard color="info">
                                <CardContent>
                                    <Typography variant="h6" fontWeight="bold">
                                        {data.summary.most_common_error_category?.[0] || 'N/A'}
                                    </Typography>
                                    <Typography variant="body2" color="text.secondary">
                                        Top Error Category ({data.summary.most_common_error_category?.[1] || 0})
                                    </Typography>
                                </CardContent>
                            </StatCard>
                        </Grid>
                    </Grid>

                    {/* Recommendations */}
                    {data.recommendations.length > 0 && (
                        <Paper sx={{ p: 3, mb: 3 }}>
                            <Typography variant="h5" gutterBottom>
                                💡 Recommendations
                            </Typography>
                            {data.recommendations.map((rec, idx) => (
                                <Alert
                                    key={idx}
                                    severity={rec.includes('🔴') ? 'error' : rec.includes('🟡') ? 'warning' : 'info'}
                                    sx={{ mb: 1, mt: 1 }}
                                >
                                    {rec.replace(/[🔴🟡🟢💡📥🔧⚠️]/g, '').trim()}
                                </Alert>
                            ))}
                        </Paper>
                    )}

                    {/* Error Categories */}
                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Typography variant="h5" gutterBottom>
                            ⚠️ Error Categories
                        </Typography>
                        <List>
                            {Object.entries(data.database.error_categories)
                                .sort((a, b) => b[1] - a[1])
                                .map(([category, count]) => (
                                    <ListItem key={category} divider>
                                        <ListItemText
                                            primary={category}
                                            secondary={`${count.toLocaleString()} failures`}
                                        />
                                        <ListItemSecondaryAction>
                                            <Chip
                                                label={count.toLocaleString()}
                                                color={count > 100 ? 'error' : count > 50 ? 'warning' : 'default'}
                                            />
                                        </ListItemSecondaryAction>
                                    </ListItem>
                                ))}
                        </List>
                    </Paper>

                    {/* Task Failures */}
                    <Paper sx={{ p: 3, mb: 3 }}>
                        <Typography variant="h5" gutterBottom>
                            🔴 Task Failures
                        </Typography>
                        {Object.entries(data.results_files.task_failures).length > 0 ? (
                            <List>
                                {Object.entries(data.results_files.task_failures)
                                    .sort((a, b) => b[1] - a[1])
                                    .map(([task, count]) => (
                                        <ListItem key={task} divider>
                                            <ListItemText
                                                primary={task}
                                                secondary={`${count} failures`}
                                            />
                                            <ListItemSecondaryAction>
                                                <Chip label={count} color="error" />
                                            </ListItemSecondaryAction>
                                        </ListItem>
                                    ))}
                            </List>
                        ) : (
                            <Typography color="text.secondary">
                                No task failures found in results.json files
                            </Typography>
                        )}
                    </Paper>

                    {/* Raw Data */}
                    <Paper sx={{ p: 3 }}>
                        <Typography variant="h5" gutterBottom>
                            📄 Raw Data
                        </Typography>
                        <Box
                            component="pre"
                            sx={{
                                bgcolor: 'grey.100',
                                p: 2,
                                borderRadius: 1,
                                overflow: 'auto',
                                maxHeight: 400,
                                fontSize: '0.875rem',
                            }}
                        >
                            {JSON.stringify(data, null, 2)}
                        </Box>
                    </Paper>
                </>
            )}
        </Box>
    );
}
