import React, { useState, useEffect } from 'react';
import {
  Grid,
  Card,
  CardContent,
  Typography,
  Skeleton,
  Box,
} from '@mui/material';
import { styled } from '@mui/material/styles';

interface Stats {
  entries_total: number;
  entries_pending: number;
  entries_processing: number;
  entries_completed: number;
  entries_failed: number;
  runs_total: number;
  runs_completed: number;
  runs_pending: number;
  runs_failed: number;
  queue_pending: number;
}

interface StatCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  color?: 'primary' | 'secondary' | 'error' | 'warning' | 'success' | 'info';
  icon?: string;
}

const StatCardWrapper = styled(Card)<{ color?: string }>(({ theme, color = 'primary' }) => {
  const paletteColor = theme.palette[color as keyof typeof theme.palette] as any;
  const borderColor = paletteColor?.main || theme.palette.primary.main;
  
  return {
    height: '100%',
    borderLeft: `4px solid ${borderColor}`,
    transition: 'transform 0.2s, box-shadow 0.2s',
    '&:hover': {
      transform: 'translateY(-4px)',
      boxShadow: theme.shadows[8],
    },
  };
});

function StatCard({ title, value, subtitle, color = 'primary', icon }: StatCardProps) {
  return (
    <StatCardWrapper color={color}>
      <CardContent>
        <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={1}>
          <Typography variant="body2" color="text.secondary" fontWeight="600">
            {title}
          </Typography>
          {icon && <Box fontSize="1.5rem">{icon}</Box>}
        </Box>
        
        <Typography variant="h4" fontWeight="bold" gutterBottom>
          {typeof value === 'number' ? value.toLocaleString() : value}
        </Typography>
        
        {subtitle && (
          <Typography variant="body2" color="text.secondary">
            {subtitle}
          </Typography>
        )}
      </CardContent>
    </StatCardWrapper>
  );
}

export default function StatsCards() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchStats = async () => {
    try {
      const response = await fetch('/stats');
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setStats(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading && !stats) {
    return (
      <Grid container spacing={3}>
        {[1, 2, 3, 4].map((i) => (
          <Grid item xs={12} sm={6} md={3} key={i}>
            <Card sx={{ height: 140 }}>
              <CardContent>
                <Skeleton variant="text" width="60%" height={24} />
                <Skeleton variant="text" width="80%" height={48} sx={{ mt: 2 }} />
                <Skeleton variant="text" width="40%" height={20} sx={{ mt: 1 }} />
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    );
  }

  if (error) {
    return (
      <Box sx={{ mb: 3 }}>
        <Typography variant="h6" color="error">Failed to load statistics</Typography>
        <Typography variant="body2" color="text.secondary">{error}</Typography>
      </Box>
    );
  }

  if (!stats) return null;

  const successRate = stats.runs_total > 0 
    ? ((stats.runs_completed / stats.runs_total) * 100).toFixed(1) 
    : '0';

  return (
    <Grid container spacing={3}>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard 
          title="Total Entries" 
          value={stats.entries_total} 
          subtitle={`${stats.entries_completed.toLocaleString()} completed`} 
          color="primary" 
          icon="📊" 
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard 
          title="Validation Runs" 
          value={stats.runs_total} 
          subtitle={`${successRate}% success rate`} 
          color={parseFloat(successRate) > 80 ? 'success' : 'warning'} 
          icon="✅" 
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard 
          title="Pending Queue" 
          value={stats.queue_pending} 
          subtitle={`${stats.entries_processing} processing`} 
          color="info" 
          icon="⏳" 
        />
      </Grid>
      <Grid item xs={12} sm={6} md={3}>
        <StatCard 
          title="Failed" 
          value={stats.entries_failed} 
          subtitle={`${stats.runs_failed} runs failed`} 
          color="error" 
          icon="❌" 
        />
      </Grid>
    </Grid>
  );
}
