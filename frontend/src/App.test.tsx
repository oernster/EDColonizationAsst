import { render, screen } from '@testing-library/react';
import App from './App';

describe('App', () => {
  it('renders the main heading', () => {
    render(<App />);
    const headingElement = screen.getByText(/Elite: Dangerous Colonization Assistant/i);
    expect(headingElement).toBeInTheDocument();
  });
});