import { useState, useEffect } from 'react';
import { Box, Typography, TextField, Button, Paper, CircularProgress, Alert } from '@mui/material';
import { api } from '../../services/api';
import { AppSettings } from '../../types/settings';
import { useColonizationStore } from '../../stores/colonizationStore';

export const SettingsPage = () => {
  const { updateSettings } = useColonizationStore();
  const [settings, setSettings] = useState<AppSettings>({ journal_directory: '', inara_api_key: '', inara_commander_name: '' });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const backendPort = 8000;
  const currentHost = window.location.hostname || 'localhost';
  const localUrl = `http://127.0.0.1:${backendPort}/app/`;
  const lanUrlHint =
    currentHost !== 'localhost' && currentHost !== '127.0.0.1'
      ? `http://${currentHost}:${backendPort}/app/`
      : `http://<your-PC-LAN-IP>:${backendPort}/app/`;

  useEffect(() => {
    const fetchSettings = async () => {
      try {
        setLoading(true);
        const fetchedSettings = await api.getAppSettings();
        setSettings(fetchedSettings);
      } catch (err) {
        setError('Failed to load settings.');
      } finally {
        setLoading(false);
      }
    };

    fetchSettings();
  }, []);

  const handleSave = async () => {
    try {
      setSaving(true);
      setError(null);
      setSuccess(null);
      await api.updateAppSettings(settings);
     setSuccess('Settings saved successfully!');
     updateSettings();
   } catch (err) {
     setError('Failed to save settings.');
   } finally {
      setSaving(false);
    }
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSettings({
      ...settings,
      [e.target.name]: e.target.value,
    });
  };

  if (loading) {
    return (
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 4 }}>
        <CircularProgress />
      </Box>
    );
  }

  return (
    <Paper sx={{ p: 3, mt: 4 }}>
      <Typography variant="h4" gutterBottom>
        Settings
      </Typography>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

      <Box component="form" noValidate autoComplete="off">
        <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
          Journal Directory
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Path to your Elite: Dangerous journal directory. This is usually found in 'C:\\Users\\%USERNAME%\\Saved Games\\Frontier Developments\\Elite Dangerous'.
        </Typography>
        <TextField
          fullWidth
          label="Journal Directory Path"
          name="journal_directory"
          value={settings.journal_directory}
          onChange={handleChange}
          variant="outlined"
          sx={{ mb: 3 }}
        />

        <Typography variant="h6" gutterBottom>
          Inara API Settings
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Enter your Inara.cz API key and commander name. Note: Inara integration is
          currently not actively used by the application; these values are reserved
          for future features.
        </Typography>
        <TextField
          fullWidth
          label="Inara API Key"
          name="inara_api_key"
          value={settings.inara_api_key}
          onChange={handleChange}
          variant="outlined"
          sx={{ mb: 3 }}
          type="password"
        />

        <TextField
          fullWidth
          label="Inara Commander Name"
          name="inara_commander_name"
          value={settings.inara_commander_name || ''}
          onChange={handleChange}
          variant="outlined"
          sx={{ mb: 3 }}
        />

        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, mb: 3 }}>
          <Button
            variant="contained"
            color="primary"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <CircularProgress size={24} /> : 'Save Settings'}
          </Button>
        </Box>

        <Typography variant="h6" gutterBottom>
          Accessing the UI from another device
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 1 }}>
          To open EDCA from a tablet or phone on the same network, point the browser at
          this machine's IP address on port {backendPort}. For example:
        </Typography>
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            bgcolor: 'background.default',
            px: 1.5,
            py: 0.75,
            borderRadius: 1,
            mb: 2,
          }}
        >
          {lanUrlHint}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          On this PC you can always use:
        </Typography>
        <Typography
          variant="body2"
          sx={{
            fontFamily: 'monospace',
            bgcolor: 'background.default',
            px: 1.5,
            py: 0.75,
            borderRadius: 1,
          }}
        >
          {localUrl}
        </Typography>
      </Box>
    </Paper>
  );
};