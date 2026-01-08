import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';
import App from './App';

// Avoid network noise from components that load systems/health/settings.
import axios from 'axios';

describe('App', () => {
  beforeEach(() => {
    window.localStorage.clear();
    axios.get = () => Promise.reject(new Error('Network disabled in unit tests'));
  });

  it('renders the main heading', () => {
    render(<App />);
    const headingElement = screen.getByText(/Elite: Dangerous Colonization Assistant/i);
    expect(headingElement).toBeInTheDocument();
  });

  it('defaults keep-awake to Off on desktop when no preference is stored', () => {
    // Most test environments have a non-mobile UA; ensure it explicitly.
    Object.defineProperty(window.navigator, 'userAgent', {
      value: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
      configurable: true,
    });

    render(<App />);

    // Chip text in header.
    expect(screen.getByText(/Keep awake: Off/i)).toBeInTheDocument();
  });

  it('reads keep-awake preference from localStorage', () => {
    window.localStorage.setItem('edcaKeepAwakeEnabled', 'true');

    render(<App />);

    // When enabled, the app may show "Starting" briefly while the hook runs.
    // We just assert it does not show the plain Off state.
    expect(screen.getByText(/Keep awake:/i)).toBeInTheDocument();
    expect(screen.queryByText(/Keep awake: Off/i)).not.toBeInTheDocument();
  });
});
