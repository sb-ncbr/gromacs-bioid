import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  Button,
  Toolbar,
  TextField,
  InputAdornment,
  Divider,
  CircularProgress,
  Switch,
  FormControlLabel,
  Alert,
} from '@mui/material';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import ClearIcon from '@mui/icons-material/Clear';
import InfoIcon from '@mui/icons-material/Info';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import SearchIcon from '@mui/icons-material/Search';

interface LogEvent {
  id: number;
  job_id: string;
  activity_type: string;
  message: string;
  severity: string;
  created_at: string;
}

const getEventIcon = (severity: string) => {
  switch (severity) {
    case 'error': return <ErrorIcon color="error" />;
    case 'warning': return <WarningIcon color="warning" />;
    case 'success': return <CheckCircleIcon color="success" />;
    default: return <InfoIcon color="info" />;
  }
};

export default function ValidationActivityLog() {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  
  const listRef = useRef<HTMLUListElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const loadInitialEvents = async () => {
    try {
      const response = await fetch('/api/validation/activity-log/stream');
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (Array.isArray(data)) {
        setEvents(data);
      }
    } catch (err: any) {
      console.error('Failed to load initial events:', err);
    }
  };

  const connect = () => {
    // Load initial events first
    if (events.length === 0) {
      loadInitialEvents();
    }

    // Then set up SSE for live updates (optional - for future)
    setConnected(true);
    setError(null);
  };

  const disconnect = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
    setConnected(false);
  };

  useEffect(() => {
    connect();
    return () => disconnect();
  }, []);

  useEffect(() => {
    if (autoScroll && listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [events, autoScroll]);

  const clearEvents = () => setEvents([]);

  const filteredEvents = events.filter(event => {
    if (searchTerm === '') return true;
    const search = searchTerm.toLowerCase();
    return (
      event.message?.toLowerCase().includes(search) ||
      event.job_id?.toLowerCase().includes(search) ||
      event.activity_type?.toLowerCase().includes(search)
    );
  });

  const formatTimestamp = (timestamp: string) => {
    return new Date(timestamp).toLocaleTimeString('cs-CZ', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  return (
    <Box>
      <Box sx={{ mb: 3 }}>
        <Typography variant="h5" fontWeight="600" gutterBottom>
          Activity Log
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Validation activity history
        </Typography>
      </Box>

      <Paper sx={{ mb: 2, p: 2 }}>
        <Toolbar disableGutters sx={{ gap: 2, flexWrap: 'wrap' }}>
          <Button
            variant="outlined"
            startIcon={<ClearIcon />}
            onClick={clearEvents}
            size="small"
          >
            Clear
          </Button>

          <FormControlLabel
            control={
              <Switch
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                size="small"
              />
            }
            label="Auto-scroll"
          />

          <Box sx={{ flexGrow: 1 }} />

          <TextField
            placeholder="Search events..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            size="small"
            sx={{ width: 300 }}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon fontSize="small" />
                </InputAdornment>
              ),
            }}
          />
        </Toolbar>
      </Paper>

      {error && (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {error}
        </Alert>
      )}

      <Paper sx={{ height: 'calc(100vh - 400px)', minHeight: 400, display: 'flex', flexDirection: 'column' }}>
        <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography variant="body2" fontWeight="600">
              Events
            </Typography>
            <Typography variant="body2" color="text.secondary">
              ({filteredEvents.length} events)
            </Typography>
          </Box>
        </Box>

        <List
          ref={listRef}
          sx={{ flexGrow: 1, overflow: 'auto', p: 0 }}
          disablePadding
        >
          {filteredEvents.length === 0 ? (
            <Box sx={{ p: 4, textAlign: 'center' }}>
              <CircularProgress size={24} sx={{ mb: 2 }} />
              <Typography variant="body2" color="text.secondary">
                Loading events...
              </Typography>
            </Box>
          ) : (
            filteredEvents.map((event) => (
              <React.Fragment key={event.id}>
                <ListItem alignItems="flex-start" sx={{ py: 1 }}>
                  <ListItemIcon sx={{ minWidth: 40 }}>
                    {getEventIcon(event.severity)}
                  </ListItemIcon>
                  <ListItemText
                    primary={
                      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}>
                        <Chip
                          label={event.severity.toUpperCase()}
                          size="small"
                          sx={{ height: 20 }}
                        />
                        <Typography variant="body2" color="text.secondary">
                          {formatTimestamp(event.created_at)}
                        </Typography>
                        <Chip
                          label={event.job_id}
                          size="small"
                          sx={{ height: 20, fontSize: '0.7rem' }}
                        />
                        <Typography variant="body2" fontWeight="500">
                          {event.activity_type.replace(/_/g, ' ')}
                        </Typography>
                      </Box>
                    }
                    secondary={
                      <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                        {event.message}
                      </Typography>
                    }
                  />
                </ListItem>
                <Divider />
              </React.Fragment>
            ))
          )}
        </List>
      </Paper>
    </Box>
  );
}
