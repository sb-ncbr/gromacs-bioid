import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TablePagination,
  TableRow,
  TableSortLabel,
  TextField,
  MenuItem,
  Chip,
  Button,
  Toolbar,
  Typography,
  Paper,
  Checkbox,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
} from '@mui/material';
import { styled } from '@mui/material/styles';
import RefreshIcon from '@mui/icons-material/Refresh';
import FilterListIcon from '@mui/icons-material/FilterList';

interface QueueItem {
  id: number;
  entry_id: number;
  entry_local_accession: string | null;
  batch_id: string | null;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  priority: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  last_error: string | null;
}

interface QueueTableProps {
  onBulkAction?: (action: string, selectedIds: number[]) => void;
}

const getStatusColor = (status: string) => {
  switch (status) {
    case 'completed': return 'success';
    case 'processing': return 'warning';
    case 'failed': return 'error';
    default: return 'default';
  }
};

export default function QueueTable({ onBulkAction }: QueueTableProps) {
  const [items, setItems] = useState<QueueItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [rowsPerPage, setRowsPerPage] = useState(50);
  const [selected, setSelected] = useState<number[]>([]);
  const [filters, setFilters] = useState({
    status: '',
    batch_id: '',
    search: '',
  });
  const [order, setOrder] = useState<'asc' | 'desc'>('desc');
  const [orderBy, setOrderBy] = useState('created_at');

  const fetchQueue = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        limit: '200',
        ...(filters.status && { status: filters.status }),
        ...(filters.batch_id && { batch_id: filters.batch_id }),
      });
      
      const response = await fetch(`/api/validation/queue/list?${params}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      setItems(data.items);
      setError(null);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchQueue();
  }, [filters.status, filters.batch_id]);

  const handleSelectAllClick = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      const newSelected = filteredItems.map((n) => n.id);
      setSelected(newSelected);
      return;
    }
    setSelected([]);
  };

  const handleClick = (event: React.MouseEvent<unknown>, id: number) => {
    const selectedIndex = selected.indexOf(id);
    let newSelected: number[] = [];

    if (selectedIndex === -1) {
      newSelected = newSelected.concat(selected, id);
    } else if (selectedIndex === 0) {
      newSelected = newSelected.concat(selected.slice(1));
    } else if (selectedIndex === selected.length - 1) {
      newSelected = newSelected.concat(selected.slice(0, -1));
    } else if (selectedIndex > 0) {
      newSelected = newSelected.concat(
        selected.slice(0, selectedIndex),
        selected.slice(selectedIndex + 1),
      );
    }
    setSelected(newSelected);
  };

  const handleRequestSort = (property: string) => {
    const isAsc = orderBy === property && order === 'asc';
    setOrder(isAsc ? 'desc' : 'asc');
    setOrderBy(property);
  };

  const handleChangePage = (event: unknown, newPage: number) => {
    setPage(newPage);
  };

  const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
    setRowsPerPage(parseInt(event.target.value, 10));
    setPage(0);
  };

  const filteredItems = useMemo(() => {
    return items.filter((item) => {
      const matchesSearch = !filters.search || 
        item.entry_local_accession?.toLowerCase().includes(filters.search.toLowerCase()) ||
        item.batch_id?.toLowerCase().includes(filters.search.toLowerCase());
      return matchesSearch;
    });
  }, [items, filters.search]);

  const sortedItems = useMemo(() => {
    return [...filteredItems].sort((a, b) => {
      const aValue = a[orderBy as keyof QueueItem];
      const bValue = b[orderBy as keyof QueueItem];
      
      if (aValue === null || aValue === undefined) return 1;
      if (bValue === null || bValue === undefined) return -1;
      
      const comparison = aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      return order === 'asc' ? comparison : -comparison;
    });
  }, [filteredItems, order, orderBy]);

  const paginatedItems = useMemo(() => {
    const start = page * rowsPerPage;
    return sortedItems.slice(start, start + rowsPerPage);
  }, [sortedItems, page, rowsPerPage]);

  const handleRetrySelected = () => {
    if (onBulkAction) {
      onBulkAction('retry', selected);
    }
  };

  const handleClearSelected = () => {
    if (onBulkAction) {
      onBulkAction('clear', selected);
    }
  };

  const isSelected = (id: number) => selected.indexOf(id) !== -1;

  return (
    <Box>
      {/* Toolbar */}
      <Box sx={{ mb: 2 }}>
        <Paper sx={{ p: 2 }}>
          <Box display="flex" gap={2} flexWrap="wrap" alignItems="center">
            <TextField
              size="small"
              placeholder="Search accession or batch..."
              value={filters.search}
              onChange={(e) => setFilters({ ...filters, search: e.target.value })}
              sx={{ minWidth: 250 }}
              InputProps={{ startAdornment: <FilterListIcon sx={{ mr: 1, color: 'text.secondary' }} /> }}
            />
            
            <TextField
              size="small"
              select
              value={filters.status}
              onChange={(e) => setFilters({ ...filters, status: e.target.value })}
              sx={{ minWidth: 150 }}
            >
              <MenuItem value="">All Status</MenuItem>
              <MenuItem value="pending">Pending</MenuItem>
              <MenuItem value="processing">Processing</MenuItem>
              <MenuItem value="completed">Completed</MenuItem>
              <MenuItem value="failed">Failed</MenuItem>
            </TextField>

            <Box sx={{ flexGrow: 1 }} />

            <Tooltip title="Refresh">
              <IconButton onClick={fetchQueue} disabled={loading}>
                <RefreshIcon />
              </IconButton>
            </Tooltip>

            {selected.length > 0 && (
              <Box display="flex" gap={1}>
                <Button size="small" variant="outlined" onClick={handleRetrySelected}>
                  Retry ({selected.length})
                </Button>
                <Button size="small" variant="outlined" color="error" onClick={handleClearSelected}>
                  Clear ({selected.length})
                </Button>
              </Box>
            )}
          </Box>
        </Paper>
      </Box>

      {/* Table */}
      {error ? (
        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
      ) : (
        <TableContainer component={Paper}>
          <Table sx={{ minWidth: 650 }}>
            <TableHead>
              <TableRow>
                <TableCell padding="checkbox">
                  <Checkbox
                    color="primary"
                    indeterminate={selected.length > 0 && selected.length < filteredItems.length}
                    checked={filteredItems.length > 0 && selected.length === filteredItems.length}
                    onChange={handleSelectAllClick}
                  />
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'entry_local_accession'}
                    direction={orderBy === 'entry_local_accession' ? order : 'asc'}
                    onClick={() => handleRequestSort('entry_local_accession')}
                  >
                    Accession
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'batch_id'}
                    direction={orderBy === 'batch_id' ? order : 'asc'}
                    onClick={() => handleRequestSort('batch_id')}
                  >
                    Batch
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'status'}
                    direction={orderBy === 'status' ? order : 'asc'}
                    onClick={() => handleRequestSort('status')}
                  >
                    Status
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'priority'}
                    direction={orderBy === 'priority' ? order : 'asc'}
                    onClick={() => handleRequestSort('priority')}
                  >
                    Priority
                  </TableSortLabel>
                </TableCell>
                <TableCell>
                  <TableSortLabel
                    active={orderBy === 'created_at'}
                    direction={orderBy === 'created_at' ? order : 'asc'}
                    onClick={() => handleRequestSort('created_at')}
                  >
                    Created
                  </TableSortLabel>
                </TableCell>
                <TableCell>Error</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {loading ? (
                <TableRow>
                  <TableCell colSpan={7} align="center" sx={{ py: 8 }}>
                    <CircularProgress />
                  </TableCell>
                </TableRow>
              ) : paginatedItems.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} align="center">
                    No queue items found
                  </TableCell>
                </TableRow>
              ) : (
                paginatedItems.map((item) => {
                  const isItemSelected = isSelected(item.id);
                  return (
                    <TableRow
                      hover
                      role="checkbox"
                      aria-checked={isItemSelected}
                      tabIndex={-1}
                      key={item.id}
                      selected={isItemSelected}
                    >
                      <TableCell padding="checkbox">
                        <Checkbox
                          color="primary"
                          checked={isItemSelected}
                          onClick={(event) => handleClick(event, item.id)}
                        />
                      </TableCell>
                      <TableCell>{item.entry_local_accession || `Entry #${item.entry_id}`}</TableCell>
                      <TableCell>
                        {item.batch_id ? (
                          <Chip label={item.batch_id} size="small" variant="outlined" />
                        ) : (
                          '—'
                        )}
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={item.status}
                          size="small"
                          color={getStatusColor(item.status)}
                        />
                      </TableCell>
                      <TableCell>{item.priority}</TableCell>
                      <TableCell>
                        {new Date(item.created_at).toLocaleString()}
                      </TableCell>
                      <TableCell sx={{ maxWidth: 200 }}>
                        <Typography variant="body2" color="text.secondary" noWrap>
                          {item.last_error || '—'}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
          <TablePagination
            rowsPerPageOptions={[25, 50, 100]}
            component="div"
            count={filteredItems.length}
            rowsPerPage={rowsPerPage}
            page={page}
            onPageChange={handleChangePage}
            onRowsPerPageChange={handleChangeRowsPerPage}
          />
        </TableContainer>
      )}
    </Box>
  );
}
