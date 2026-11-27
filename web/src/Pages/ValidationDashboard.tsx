import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Tabs,
  Tab,
  Paper,
  Container,
  CircularProgress,
  Alert,
  Typography,
} from '@mui/material';

import ValidationQueue from './ValidationQueue';
import ValidationBatches from './ValidationBatches';
import ValidationActivityLog from './ValidationActivityLog';
import StatsCards from '../Components/Validation/StatsCards';
import ProgressBar from '../Components/Validation/ProgressBar';

interface TabPanelProps {
  children?: React.ReactNode;
  index: number;
  value: number;
}

function TabPanel(props: TabPanelProps) {
  const { children, value, index } = props;
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`validation-tabpanel-${index}`}
      aria-labelledby={`validation-tab-${index}`}
      style={{ width: '100%' }}
    >
      {value === index && children}
    </div>
  );
}

// GitHub #25/#28: read-only views; the worker-pool and failure-analysis
// tabs (scale/restart, unbounded in-process analysis) are removed.
const tabLabels = [
  'Overview',
  'Queue',
  'Batches',
  'Activity Log',
];
const tabPaths = ['', '/queue', '/batches', '/activity-log'];

export default function ValidationDashboard() {
  const navigate = useNavigate();
  const [value, setValue] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const path = window.location.pathname;
    const tab = tabPaths.findIndex((p, i) => i > 0 && path.includes(p));
    setValue(tab > 0 ? tab : 0);
    setLoading(false);
  }, []);

  const handleChange = (_: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
    navigate(`/validation${tabPaths[newValue]}`, { replace: true });
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress size={60} />
      </Box>
    );
  }

  return (
    <Container maxWidth="xl" sx={{ py: 3 }}>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h4" fontWeight="600" gutterBottom>
          Validation Dashboard
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Validation campaign status (read-only)
        </Typography>
      </Box>

      <Paper sx={{ mb: 2 }}>
        <Tabs
          value={value}
          onChange={handleChange}
          variant="scrollable"
          scrollButtons="auto"
          sx={{ borderBottom: 1, borderColor: 'divider' }}
        >
          {tabLabels.map((label) => (
            <Tab
              key={label}
              label={label}
              sx={{
                textTransform: 'none',
                fontWeight: 600,
                fontSize: '0.95rem',
                minHeight: 56,
              }}
            />
          ))}
        </Tabs>
      </Paper>

      <Paper sx={{ p: 3, minHeight: 600 }}>
        <TabPanel value={value} index={0}>
          <StatsCards />
          <Box sx={{ mt: 4 }}>
            <ProgressBar />
          </Box>
        </TabPanel>
        <TabPanel value={value} index={1}>
          <ValidationQueue />
        </TabPanel>
        <TabPanel value={value} index={2}>
          <ValidationBatches />
        </TabPanel>
        <TabPanel value={value} index={3}>
          <ValidationActivityLog />
        </TabPanel>
      </Paper>
    </Container>
  );
}
