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
import ValidationWorkers from './ValidationWorkers';
import ValidationBatches from './ValidationBatches';
import ValidationFailureAnalysis from './ValidationFailureAnalysis';
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

const tabLabels = [
  'Overview',
  'Queue',
  'Workers',
  'Batches',
  'Failure Analysis',
  'Activity Log',
];

export default function ValidationDashboard() {
  const navigate = useNavigate();
  const [value, setValue] = useState(0);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const path = window.location.pathname;
    if (path.includes('/queue')) setValue(1);
    else if (path.includes('/workers')) setValue(2);
    else if (path.includes('/batches')) setValue(3);
    else if (path.includes('/failure-analysis')) setValue(4);
    else if (path.includes('/activity-log')) setValue(5);
    else setValue(0);
    setLoading(false);
  }, []);

  const handleChange = (_: React.SyntheticEvent, newValue: number) => {
    setValue(newValue);
    const paths = ['', '/queue', '/workers', '/batches', '/failure-analysis', '/activity-log'];
    navigate(`/validation${paths[newValue]}`, { replace: true });
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
          Monitor and manage validation runs, queue, workers, and analytics
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
          <ValidationWorkers />
        </TabPanel>
        <TabPanel value={value} index={3}>
          <ValidationBatches />
        </TabPanel>
        <TabPanel value={value} index={4}>
          <ValidationFailureAnalysis />
        </TabPanel>
        <TabPanel value={value} index={5}>
          <ValidationActivityLog />
        </TabPanel>
      </Paper>
    </Container>
  );
}
