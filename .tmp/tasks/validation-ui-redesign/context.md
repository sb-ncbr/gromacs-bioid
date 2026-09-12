# Validation UI Redesign - Context Bundle

## Project Overview
BAT3 Validation Dashboard - Complete UI overhaul for validation monitoring and management.

## Current Issues
- Progress bar: dead/not updating
- Batch info: not showing
- Queue items: weird/not working well
- Failure analysis: broken, button does nothing
- Activity log: dead
- Recent entries: dead and unwanted
- Workers: don't list

## API Endpoints Available
- GET /api/stats/dashboard - Dashboard statistics
- GET /api/validation/queue/list - Queue items with filtering
- GET /api/validation/queue/status - Queue processor status
- GET /api/validation/queue/workers - Worker list
- POST /api/validation/queue/workers/scale - Scale workers
- GET /api/validation/stats/failure-analysis - Failure analysis data
- GET /api/validation/activity-log/stream - SSE activity stream
- POST /api/validation/queue/start-processor - Start queue processor
- POST /api/validation/entries/retry-failed - Retry failed entries

## Tech Stack
- Frontend: React + TypeScript + Material-UI (MUI)
- Backend: Python FastAPI (validation/api/main.py)
- Existing components: web/src/Components/, web/src/Pages/
- Theme: Green accent (#2E7D32), light mode

## File Structure
- Frontend: /home/tomsko/work/bat3/web/src/
- Backend: /home/tomsko/work/bat3/validation/api/

## Requirements
1. Modern, clean Material-UI design
2. Real-time updates (polling/SSE)
3. Responsive layout
4. Filterable/sortable tables
5. Interactive charts for analytics
6. Bulk actions support

## New Routes to Add
- /validation (main dashboard)
- /validation/queue
- /validation/workers
- /validation/batches
- /validation/failure-analysis
- /validation/activity-log
