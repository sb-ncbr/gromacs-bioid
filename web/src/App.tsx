import './App.css';
import { ThemeProvider } from '@emotion/react';
import { CssBaseline, createTheme } from '@mui/material';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './Components/Layout';
import Frontpage from './Pages/Frontpage';
import AnnotationResults from './Pages/AnnotationResults';

function App() {

  const theme = createTheme({
    palette: {
      mode: 'light',
      background: {
        default: '#ffffff', // Full white background
        paper: '#ffffff',
      },
      primary: {
        main: '#2E7D32', // Dark green accent
        contrastText: '#ffffff',
      },
      secondary: {
        main: '#1B5E20', // Even darker green (optional, for contrast)
      },
      text: {
        primary: '#1A1A1A', // Very dark gray/black for good readability
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
        styleOverrides: {
          h1: {
            fontSize: '2.75em',
            fontWeight: 'bold',
            color: '#1A1A1A',
          },
          h2: {
            fontSize: '2em',
            fontWeight: 'bold',
            color: '#2E7D32',
          },
          h3: {
            fontSize: '1.25em',
            color: '#1A1A1A',
          },
        },
      },
      MuiButton: {
        styleOverrides: {
          root: {
            borderRadius: 8,
            textTransform: 'none',
            fontWeight: 'bold',
          },
          containedPrimary: {
            backgroundColor: '#2E7D32',
            '&:hover': {
              backgroundColor: '#27652C',
            },
          },
          outlinedPrimary: {
            borderColor: '#2E7D32',
            color: '#2E7D32',
            '&:hover': {
              backgroundColor: '#E8F5E9',
            },
          },
        },
      },
      MuiTooltip: {
        styleOverrides: {
          tooltip: {
            backgroundColor: '#2E7D32',
            fontSize: '0.875em',
          },
          arrow: {
            color: '#2E7D32',
          },
        },
      },
      MuiAlert: {
        styleOverrides: {
          standardError: {
            backgroundColor: '#fbe9e7',
            color: '#c62828',
          },
        },
      },
    },
  })

  return (
      <BrowserRouter>
        <CssBaseline/>
        <ThemeProvider theme={theme}>
          <Routes>
            <Route path='/' element={<Layout />} >
              <Route path='/' element={<Frontpage />} />
              <Route path='/results/:session' element={<AnnotationResults />} />
            </Route>
          </Routes>
        </ThemeProvider>
      </BrowserRouter>

  );
}

export default App;
