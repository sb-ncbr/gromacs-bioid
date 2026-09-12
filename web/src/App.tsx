import './App.css';
import { ThemeProvider } from '@emotion/react';
import { CssBaseline, createTheme } from '@mui/material';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './Components/Layout';
import AnnotationResults from './Pages/AnnotationResults';
import FailureAnalysis from './Pages/FailureAnalysis';

// Validation Dashboard pages
import ValidationDashboard from './Pages/ValidationDashboard';
import ValidationQueue from './Pages/ValidationQueue';
import ValidationWorkers from './Pages/ValidationWorkers';
import ValidationBatches from './Pages/ValidationBatches';
import ValidationFailureAnalysis from './Pages/ValidationFailureAnalysis';
import ValidationActivityLog from './Pages/ValidationActivityLog';

function App() {
  const theme = createTheme({
    palette: {
      mode: 'light',
      background: {
        default: '#ffffff',
        paper: '#ffffff',
      },
      primary: {
        main: '#2E7D32',
        contrastText: '#ffffff',
      },
      secondary: {
        main: '#1B5E20',
      },
      text: {
        primary: '#1A1A1A',
      },
    },
    components: {
      MuiTypography: {
        defaultProps: {
          variantMapping: {
            h1: 'h1',
            h2: 'h2',
            h3: 'h3',
            h4: 'h1',
            h5: 'h1',
            h6: 'h1',
            subtitle1: 'h3',
            subtitle2: 'h3',
            body1: 'span',
            body2: 'span',
          },
        },
      },
    },
  });

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <BrowserRouter>
        <Routes>
          <Route path='/' element={<Layout />} >
            {/* Redirect root to validation dashboard */}
            <Route index element={<Navigate to="/validation" replace />} />
            
            {/* Old routes - kept for backwards compatibility */}
            <Route path='results/:session' element={<AnnotationResults />} />
            <Route path='failure-analysis' element={<FailureAnalysis />} />
            
            {/* Validation Dashboard Routes - main app */}
            <Route path='validation' element={<ValidationDashboard />} >
              <Route index element={<ValidationDashboard />} />
              <Route path='queue' element={<ValidationDashboard />} />
              <Route path='workers' element={<ValidationDashboard />} />
              <Route path='batches' element={<ValidationDashboard />} />
              <Route path='failure-analysis' element={<ValidationDashboard />} />
              <Route path='activity-log' element={<ValidationDashboard />} />
            </Route>
          </Route>
        </Routes>
      </BrowserRouter>
    </ThemeProvider>
  );
}

export default App;
