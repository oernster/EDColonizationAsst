import { useState } from 'react';
import { ThemeProvider, createTheme, CssBaseline, Container, Box, Typography, Tabs, Tab } from '@mui/material';
import { SystemSelector } from './components/SystemSelector/SystemSelector';
import { SiteList } from './components/SiteList/SiteList';
import { useColonizationStore } from './stores/colonizationStore';
import { SettingsPage } from './components/Settings/SettingsPage';

const darkTheme = createTheme({
  palette: {
    mode: 'dark',
    primary: {
      main: '#FF6B00', // Elite orange
    },
    secondary: {
      main: '#4CAF50', // Green for completed
    },
    background: {
      default: '#1a1a1a',
      paper: '#2d2d2d',
    },
    success: {
      main: '#4CAF50', // Green
    },
    warning: {
      main: '#FF9800', // Orange
    },
  },
  typography: {
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
  },
});

function App() {
  const { currentSystem, systemData, loading, error } = useColonizationStore();
  const [currentTab, setCurrentTab] = useState(0);

  const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  return (
    <ThemeProvider theme={darkTheme}>
      <CssBaseline />
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          {/* Header */}
          <Box sx={{ mb: 4 }}>
            <Typography variant="h3" component="h1" gutterBottom sx={{ color: 'primary.main', fontWeight: 'bold' }}>
              Elite: Dangerous Colonization Assistant
            </Typography>
            <Typography variant="subtitle1" color="text.secondary">
              Real-time tracking for colonization efforts
            </Typography>
          </Box>
          
          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs value={currentTab} onChange={handleTabChange} aria-label="nav tabs">
              <Tab label="System View" />
              <Tab label="Settings" />
            </Tabs>
          </Box>

          {currentTab === 0 && (
            <Box sx={{ pt: 4 }}>
              {/* System Selector */}
              <Box sx={{ mb: 4 }}>
                <SystemSelector />
              </Box>

              {/* Error Display */}
              {error && (
                <Box sx={{ mb: 4, p: 2, bgcolor: 'error.dark', borderRadius: 1 }}>
                  <Typography color="error.contrastText">{error}</Typography>
                </Box>
              )}

              {/* Loading State */}
              {loading && (
                <Box sx={{ textAlign: 'center', py: 4 }}>
                  <Typography>Loading colonization data...</Typography>
                </Box>
              )}

              {/* Site List */}
              {!loading && currentSystem && systemData && (
                <SiteList />
              )}

              {/* Empty State */}
              {!loading && !currentSystem && !error && (
                <Box sx={{ textAlign: 'center', py: 8 }}>
                  <Typography variant="h6" color="text.secondary">
                    Select a system to view colonization progress
                  </Typography>
                </Box>
              )}
            </Box>
          )}

          {currentTab === 1 && (
            <Box sx={{ pt: 4 }}>
              <SettingsPage />
            </Box>
          )}
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;