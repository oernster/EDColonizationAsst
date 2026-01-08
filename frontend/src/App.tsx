import { useState, useEffect, useMemo } from 'react';
import { ThemeProvider, createTheme, CssBaseline, Container, Box, Typography, Tabs, Tab, Link, Button, Chip, Tooltip } from '@mui/material';
import { SystemSelector } from './components/SystemSelector/SystemSelector';
import { SiteList } from './components/SiteList/SiteList';
import { FleetCarriersPanel } from './components/FleetCarriers/FleetCarriersPanel';
import { useColonizationStore } from './stores/colonizationStore';
import { SettingsPage } from './components/Settings/SettingsPage';
import { api } from './services/api';
import { useColonizationWebSocket } from './hooks/useColonizationWebSocket';
import { useKeepAwake } from './hooks/useKeepAwake';
import { isMobileOrTablet } from './utils/device';

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
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
  },
});

const lightTheme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#FF6B00', // Elite orange
    },
    secondary: {
      main: '#2e7d32', // Darker green
    },
    background: {
      default: '#fafafa',
      paper: '#ffffff',
    },
    success: {
      main: '#2e7d32',
    },
    warning: {
      main: '#FF9800',
    },
  },
  typography: {
    fontFamily:
      '-apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen", "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif',
  },
});

function App() {
  const {
    currentSystem,
    systemData,
    loading,
    error,
    settingsVersion,
    setSystemData,
    setError,
  } = useColonizationStore();
  const [currentTab, setCurrentTab] = useState(0);
  const [systemViewTab, setSystemViewTab] = useState(0);
  const [appVersion, setAppVersion] = useState<string | null>(null);
  const [pythonVersion, setPythonVersion] = useState<string | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [commanderName, setCommanderName] = useState<string | null>(null);
  const [themeMode, setThemeMode] = useState<'dark' | 'light'>('dark');
  const keepAwakeStorageKey = 'edcaKeepAwakeEnabled';

  const readKeepAwakeEnabled = () => {
    try {
      const raw = window.localStorage.getItem(keepAwakeStorageKey);
      if (raw === 'true') return true;
      if (raw === 'false') return false;
      // Default ON for mobile/tablet, but do not override an explicit user choice.
      return isMobileOrTablet();
    } catch {
      return isMobileOrTablet();
    }
  };

  // Initialise from localStorage synchronously to avoid a "flash" of Off in tests/UI.
  const [keepAwakeEnabled, setKeepAwakeEnabled] = useState<boolean>(() => readKeepAwakeEnabled());

  // Initialise theme mode from localStorage so we remember the user's choice.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem('edcaThemeMode');
      if (saved === 'dark' || saved === 'light') {
        setThemeMode(saved);
      }
    } catch {
      // If localStorage is unavailable, just stick with the default.
    }
  }, []);

  // Initialise keep-awake preference.
  useEffect(() => {
    // Persist the default for mobile/tablet so the behaviour is stable.
    try {
      const existing = window.localStorage.getItem(keepAwakeStorageKey);
      if (existing === null) {
        window.localStorage.setItem(keepAwakeStorageKey, String(readKeepAwakeEnabled()));
      }
    } catch {
      // Ignore.
    }

    const onLocalPreferenceChanged = () => {
      setKeepAwakeEnabled(readKeepAwakeEnabled());
    };

    // Custom event fired by Settings when toggled.
    window.addEventListener('edcaKeepAwakeChanged', onLocalPreferenceChanged);
    // Also respond to cross-tab changes.
    window.addEventListener('storage', onLocalPreferenceChanged);

    return () => {
      window.removeEventListener('edcaKeepAwakeChanged', onLocalPreferenceChanged);
      window.removeEventListener('storage', onLocalPreferenceChanged);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Establish a WebSocket connection for live colonization updates. The REST
  // calls in SystemSelector provide the initial snapshot; this hook keeps the
  // currently selected system in sync when journal events arrive.
  useColonizationWebSocket(currentSystem, setSystemData, setError);

  useEffect(() => {
    const loadMeta = async () => {
      try {
        const health = await api.healthCheck();
        setAppVersion(health.version);
        // New in 1.5.0+: surface the actual Python runtime version reported by the backend.
        // This lets us verify at a glance which embedded interpreter the packaged EXE is using.
        setPythonVersion(health.python_version ?? null);
      } catch (err) {
        setHealthError('Failed to load version information');
      }

      try {
        const settings = await api.getAppSettings();
        setCommanderName(settings.inara_commander_name);
      } catch {
        // Ignore settings load errors here; commander name is optional display
      }
    };

    loadMeta();
  }, [settingsVersion]);

  const handleTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setCurrentTab(newValue);
  };

  const handleSystemViewTabChange = (_event: React.SyntheticEvent, newValue: number) => {
    setSystemViewTab(newValue);
  };

  const setThemeModeAndPersist = (next: 'dark' | 'light') => {
    setThemeMode(next);
    try {
      window.localStorage.setItem('edcaThemeMode', next);
    } catch {
      // Ignore persistence errors; theme will still switch for this session.
    }
  };

  const theme = themeMode === 'dark' ? darkTheme : lightTheme;

  const {
    status: keepAwakeStatus,
    wakeLockPossible,
    secureContext,
    enableFromUserGesture,
  } = useKeepAwake({
    enabled: keepAwakeEnabled,
    allowFallbackVideo: keepAwakeEnabled,
  });

  // If Settings enables keep-awake, try to start immediately within the same user gesture.
  useEffect(() => {
    const onTryEnableNow = () => {
      void enableFromUserGesture();
    };
    window.addEventListener('edcaKeepAwakeTryEnableNow', onTryEnableNow);
    return () => window.removeEventListener('edcaKeepAwakeTryEnableNow', onTryEnableNow);
  }, [enableFromUserGesture]);

  const keepAwakeChip = useMemo(() => {
    const tooltip = keepAwakeStatus.message;
    const labelBase = 'Keep awake';

    // Avoid a brief "Off" state while the keep-awake hook is attempting to enable.
    if (keepAwakeEnabled && keepAwakeStatus.state === 'off') {
      return (
        <Tooltip title="Enabling keep-awake…" arrow>
          <Chip
            size="small"
            label={`${labelBase}: Starting`}
            color="default"
            variant="outlined"
          />
        </Tooltip>
      );
    }

    if (keepAwakeStatus.state === 'active') {
      return (
        <Tooltip title={tooltip} arrow>
          <Chip
            size="small"
            label={`${labelBase}: On`}
            color="success"
            variant="filled"
          />
        </Tooltip>
      );
    }

    if (keepAwakeStatus.state === 'needs-user-gesture') {
      return (
        <Tooltip title={tooltip} arrow>
          <Chip
            size="small"
            label={`${labelBase}: Tap to enable`}
            color="warning"
            variant="filled"
            onClick={() => {
              void enableFromUserGesture();
            }}
          />
        </Tooltip>
      );
    }

    if (keepAwakeEnabled && keepAwakeStatus.state === 'unsupported') {
      const extra =
        wakeLockPossible || secureContext
          ? ''
          : ' (HTTP/LAN often blocks Wake Lock; fallback requires a tap)';
      return (
        <Tooltip title={`${tooltip}${extra}`} arrow>
          <Chip
            size="small"
            label={`${labelBase}: Unsupported`}
            color="default"
            variant="outlined"
          />
        </Tooltip>
      );
    }

    if (keepAwakeEnabled && keepAwakeStatus.state === 'error') {
      return (
        <Tooltip title={tooltip} arrow>
          <Chip
            size="small"
            label={`${labelBase}: Error`}
            color="error"
            variant="filled"
          />
        </Tooltip>
      );
    }

    return (
      <Tooltip title={keepAwakeEnabled ? tooltip : 'Off'} arrow>
        <Chip
          size="small"
          label={`${labelBase}: Off`}
          color="default"
          variant="outlined"
        />
      </Tooltip>
    );
  }, [keepAwakeEnabled, keepAwakeStatus, wakeLockPossible, secureContext]);

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Container maxWidth="xl">
        <Box sx={{ py: 4 }}>
          {/* Header */}
          <Box
            sx={{
              mb: 4,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'flex-start',
              flexWrap: 'wrap',
              gap: 2,
            }}
          >
            <Box>
              <Typography
                variant="h3"
                component="h1"
                gutterBottom
                sx={{ color: 'primary.main', fontWeight: 'bold' }}
              >
                Elite: Dangerous Colonization Assistant
              </Typography>
              <Typography variant="subtitle1" color="text.secondary">
                Real-time tracking for colonization efforts
              </Typography>
            </Box>
            <Box
              sx={{
                textAlign: { xs: 'left', sm: 'right' },
              }}
            >
              <Typography variant="body2" sx={{ color: 'primary.main' }}>
                Commander:
              </Typography>
              <Typography
                variant="body1"
                fontWeight="medium"
                color="text.primary"
              >
                {commanderName || 'Unknown'}
              </Typography>
              {!commanderName && (
                <Typography variant="caption" color="text.secondary" sx={{ display: 'block', mt: 0.5 }}>
                  Set your commander name in the Settings tab.
                </Typography>
              )}
              <Box
                sx={{
                  mt: 1,
                  display: 'flex',
                  justifyContent: { xs: 'flex-start', sm: 'flex-end' },
                  gap: 1,
                  alignItems: 'center',
                  flexWrap: 'wrap',
                }}
              >
                {keepAwakeChip}
                <Button
                  variant={themeMode === 'light' ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => setThemeModeAndPersist('light')}
                  sx={{
                    minWidth: 36,
                    width: 36,
                    height: 36,
                    borderRadius: 1,
                    padding: 0,
                    lineHeight: 1,
                  }}
                >
                  ☀️
                </Button>
                <Button
                  variant={themeMode === 'dark' ? 'contained' : 'outlined'}
                  size="small"
                  onClick={() => setThemeModeAndPersist('dark')}
                  sx={{
                    minWidth: 36,
                    width: 36,
                    height: 36,
                    borderRadius: 1,
                    padding: 0,
                    lineHeight: 1,
                  }}
                >
                  🌙
                </Button>
              </Box>
            </Box>
          </Box>

          <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
            <Tabs value={currentTab} onChange={handleTabChange} aria-label="nav tabs">
              <Tab label="System View" />
              <Tab label="Settings" />
              <Tab label="About" />
              <Tab label="License" />
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
                <>
                  <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                    <Tabs
                      value={systemViewTab}
                      onChange={handleSystemViewTabChange}
                      aria-label="system view detail tabs"
                      textColor="primary"
                      indicatorColor="primary"
                    >
                      <Tab label="System Commodities" />
                      <Tab label="Stations" />
                      <Tab label="Fleet carriers" />
                    </Tabs>
                  </Box>
 
                  {systemViewTab === 0 && <SiteList viewMode="system" />}
                  {systemViewTab === 1 && <SiteList viewMode="stations" />}
                  {systemViewTab === 2 && <FleetCarriersPanel />}
                </>
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

          {currentTab === 2 && (
            <Box sx={{ pt: 4, maxWidth: 900 }}>
              <Typography variant="h5" gutterBottom>
                About
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Application Name: EDColonizationAsst
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Author: Oliver Ernster
              </Typography>
              <Typography variant="body1" sx={{ mb: 1.5 }}>
                Version: {appVersion ?? 'Loading...'}
              </Typography>
              <Typography variant="body1" sx={{ mb: 3 }}>
                Python runtime: {pythonVersion ?? 'Loading...'}
              </Typography>
              {healthError && (
                <Typography variant="body2" color="error" sx={{ mt: 1, mb: 2 }}>
                  {healthError}
                </Typography>
              )}

              <Typography variant="h6" gutterBottom>
                Third‑party components
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                This project makes use of several third‑party libraries. In particular:
              </Typography>

              <Typography variant="subtitle1" sx={{ mt: 1 }}>
                Python backend (key libraries)
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                The backend is built on top of a number of open‑source Python projects, including
                but not limited to:
              </Typography>
              <Typography variant="body2" sx={{ mb: 1, pl: 2 }}>
                • <strong>FastAPI</strong> – modern, async web framework for the API layer.<br />
                • <strong>Uvicorn</strong> – ASGI server used to host the FastAPI application.<br />
                • <strong>Pydantic</strong> – data validation and settings management.<br />
                • <strong>PySide6</strong> – Qt for Python bindings used for the Windows tray UI
                  and installer tooling.<br />
                • <strong>SQLAlchemy / SQLite</strong> and related tools – persistence layer for
                  colonization data.<br />
                • Various supporting libraries for logging, testing, and utilities as listed in
                  <code>backend/requirements.txt</code> and <code>backend/requirements-dev.txt</code>.
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                I gratefully acknowledge the maintainers and contributors of these projects and
                the broader Python ecosystem.
              </Typography>

              <Typography variant="subtitle1">
                Frontend and tooling (Node.js ecosystem)
              </Typography>
              <Typography variant="body2" sx={{ mb: 1 }}>
                The React/TypeScript frontend and build tooling rely on many projects from the
                Node.js ecosystem, including:
              </Typography>
              <Typography variant="body2" sx={{ mb: 1, pl: 2 }}>
                • <strong>React</strong> and <strong>React‑DOM</strong> – core UI framework.<br />
                • <strong>Material UI (MUI)</strong> – component library for the web UI.<br />
                • <strong>Vite</strong> – dev server and build tool.<br />
                • <strong>Zustand</strong> – state management.<br />
                • <strong>Axios</strong> – HTTP client.<br />
                • A number of testing, linting, and type‑checking tools (Vitest, ESLint,
                  TypeScript, Testing Library, etc.) as listed in
                  <code>frontend/package.json</code> and <code>frontend/package-lock.json</code>.
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                I also gratefully acknowledge the authors and maintainers of these libraries and
                the wider JavaScript/TypeScript ecosystem.
              </Typography>

              <Typography variant="body2">
                Please refer to the upstream project documentation and license notices for each
                of these dependencies for their full terms and acknowledgements.
              </Typography>
            </Box>
          )}

          {currentTab === 3 && (
            <Box sx={{ pt: 4, maxWidth: 900 }}>
              <Typography variant="h5" gutterBottom>
                License
              </Typography>
              <Typography variant="body1" sx={{ mb: 2 }}>
                Elite Dangerous Colonization Assistant (EDCA) is distributed under the
                terms of the <strong>GNU Lesser General Public License, version 3</strong> (LGPL‑3.0).
              </Typography>
              <Typography variant="body2" sx={{ mb: 2 }}>
                The full text of the license is available online at{' '}
                <Link
                  href="https://github.com/oernster/EDColonizationAsst/blob/main/LICENSE"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  LICENSE
                </Link>{' '}
                and is also included in the installed application as the file
                <code> LICENSE</code>. By using this software you agree to the terms of that license.
              </Typography>
            </Box>
          )}
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;
