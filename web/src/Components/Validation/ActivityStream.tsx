import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Chip,
  Button,
  TextField,
  MenuItem,
  IconButton,
  Toolbar,
  Alert,
  CircularProgress,
  Switch,
  FormControlLabel,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import PlayArrowIcon from '@mui/icons-material/PlayArrow';
import PauseIcon from '@mui/icons-material/Pause';
import DownloadIcon from '@mui/icons-material/Download';
import ClearIcon from '@mui/icons-material/Clear';
import InfoIcon from '@mui/icons-material/Info';
import WarningIcon from '@mui/icons-material/Warning';
import ErrorIcon from '@mui/icons-material/Error';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';

interface LogEvent {
  id: string;
  timestamp: string;
  level: 'info' | 'warning' | 'error' | 'success';
  message: string;
  source?: string;
  entry_id?: number;
  batch_id?: string;
}

const LogWrapper = styled(Paper)(({ theme }) => ({
  height: 'calc(100vh - 300px)',
  minHeight: 400,
  display: 'flex',
  flexDirection: 'column',
}));

const LogList = styled(List)(({ theme }) => ({
  flexGrow: 1,
  overflow: 'auto',
  padding: theme.spacing(1),
}));

const getEventIcon = (level: string) => {
  switch (level) {
    case 'error': return <ErrorIcon color="error" />;
    case 'warning': return <WarningIcon color="warning" />;
    case 'success': return <CheckCircleIcon color="success" />;
    default: return <InfoIcon color="info" />;
  }
};

const getEventColor = (level: string) => {
  switch (level) {
    case 'error': return 'error';
    case 'warning': return 'warning';
    case 'success': return 'success';
    default: return 'default';
  }
};

export default function ActivityStream() {
  const [events, setEvents] = useState<LogEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [paused, setPaused] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const [filters, setFilters] = useState({
    level: '',
    search: '',
  });
  
  const listRef = useRef<HTMLUListElement>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const connect = () => {
    try {
      const eventSource = new EventSource('/api/validation/activity-log/stream');
      
      eventSource.onopen = () => {
        setConnected(true);
        setError(null);
        console.log('SSE connection established');
      };

      eventSource.onmessage = (event) => {
        if (!paused) {
          try {
            const newEvent: LogEvent = JSON.parse(event.data);
            newEvent.id = `${Date.now()}-${Math.random()}`;
            setEvents((prev) => [...prev.slice(-499), newEvent]);
          } catch (err) {
            console.error('Failed to parse event:', err);
          }
        }
      };

      eventSource.onerror = (err) => {
        console.error('SSE error:', err);
        setConnected(false);
        eventSource.close();
        
        // Auto-reconnect after 5 seconds
        setTimeout(() => {
          if (!eventSourceRef.current || eventSourceRef.current.readyState === EventSource.CLOSED) {
            connect();
          }
        }, 5000);
      };

      eventSourceRef.current = eventSource;
    } catch (err: any) {
      setError(err.message);
    }
  };

  const disconnect = () => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
      setConnected(false);
    }
  };

  useEffect(() => {
    connect();
    return () => disconnect();
  }, []);

  // Auto-scroll to bottom
  useEffect(() => {
    if (autoScroll && listRef.current && !paused) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [events, autoScroll, paused]);

  const filteredEvents = events.filter((event) => {
    const matchesLevel = !filters.level || event.level === filters.level;
    const matchesSearch = !filters.search || 
      event.message.toLowerCase().includes(filters.search.toLowerCase()) ||
      event.source?.toLowerCase().includes(filters.search.toLowerCase());
    return matchesLevel && matchesSearch;
  });

  const handleExport = () => {
    const dataStr = JSON.stringify(filteredEvents, null, 2);
    const dataBlob = new Blob([dataStr], { type: 'application/json' });
    const url = URL.createObjectURL(dataBlob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `activity-log-${new Date().toISOString()}.json`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleClear = () => {
    setEvents([]);
  };

  return (
    <LogWrapper>
      {/* Toolbar */}
      <Toolbar variant="dense" sx={{ bgcolor: 'background.default', borderBottom: 1, borderColor: 'divider' }}>
        <Box display="flex" gap={2} alignItems="center" flexGrow={1}>
          <Chip
            label={connected ? 'Connected' : 'Disconnected'}
            color={connected ? 'success' : 'error'}
            
          />
          
          <TextField
            
            placeholder="Search logs..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            sx={{ minWidth: 250 }}
          />
          
          <TextField
            
            select
            value={filters.level}
            onChange={(e) => setFilters({ ...filters, level: e.target.value })}
            sx={{ minWidth: 120 }}
          >
            <MenuItem value="">All Levels</MenuItem>
            <MenuItem value="info">Info</MenuItem>
            <MenuItem value="warning">Warning</MenuItem>
            <MenuItem value="error">Error</MenuItem>
            <MenuItem value="success">Success</MenuItem>
          </TextField>

          <FormControlLabel
            control={
              <Switch
                checked={autoScroll}
                onChange={(e) => setAutoScroll(e.target.checked)}
                
              />
            }
            label="Auto-scroll"
            
          />

          <Box sx={{ flexGrow: 1 }} />

          <Button
            
            startIcon={paused ? <PlayArrowIcon /> : <PauseIcon />}
            onClick={() => setPaused(!paused)}
            variant={paused ? 'contained' : 'outlined'}
          >
            {paused ? 'Resume' : 'Pause'}
          </Button>

          <IconButton  onClick={handleExport} disabled={events.length === 0}>
            <DownloadIcon />
          </IconButton>

          <IconButton  onClick={handleClear} disabled={events.length === 0}>
            <ClearIcon />
          </IconButton>
        </Box>
      </Toolbar>

      {/* Connection Error */}
      {!connected && !error && (
        <Box sx={{ p: 2 }}>
          <Alert severity="warning">
            Reconnecting to activity stream...
          </Alert>
        </Box>
      )}

      {error && (
        <Box sx={{ p: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}

      {/* Log List */}
      <LogList ref={listRef}>
        {filteredEvents.length === 0 ? (
          <Box sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              {connected ? 'No events yet' : 'Connecting...'}
            </Typography>
          </Box>
        ) : (
          filteredEvents.map((event) => (
            <ListItem key={event.id} divider sx={{ py: 1 }}>
              <ListItemIcon sx={{ minWidth: 40 }}>
                {getEventIcon(event.level)}
              </ListItemIcon>
              <ListItemText
                primary={
                  <Box display="flex" alignItems="center" gap={1}>
                    <Chip
                      label={event.level.toUpperCase()}
                      
                      color={getEventColor(event.level)}
                      sx={{ fontSize: '0.7rem' }}
                    />
                    <Typography variant="body2" color="text.secondary">
                      {new Date(event.timestamp).toLocaleTimeString()}
                    </Typography>
                    {event.source && (
                      <Chip label={event.source}  variant="outlined" sx={{ fontSize: '0.7rem' }} />
                    )}
                  </Box>
                }
                secondary={
                  <Typography variant="body2" sx={{ mt: 0.5 }}>
                    {event.message}
                    {event.entry_id && (
                      <Typography component="span" variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                        (Entry #{event.entry_id})
                      </Typography>
                    )}
                  </Typography>
                }
              />
            </ListItem>
          ))
        )}
      </LogList>

      {/* Footer Stats */}
      <Box sx={{ p: 1, bgcolor: 'background.default', borderTop: 1, borderColor: 'divider' }}>
        <Typography variant="caption" color="text.secondary">
          Showing {filteredEvents.length} of {events.length} events
          {paused && ' (paused)'}
        </Typography>
      </Box>
    </LogWrapper>
  );
}
