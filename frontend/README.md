# Elite: Dangerous Colonization Assistant - Frontend

React + TypeScript frontend for the Elite: Dangerous Colonization Assistant.

## Setup

1. **Install dependencies:**
   ```bash
   npm install
   ```

2. **Configure:**
   - The frontend is configured to proxy API requests to `http://localhost:8000`
   - Ensure the backend is running before starting the frontend

## Running

### Development Server
```bash
npm run dev
```

The application will be available at: http://localhost:5173

### Production Build
```bash
npm run build
npm run preview
```

## Testing

### Run tests
```bash
npm test
```

### Run tests with UI
```bash
npm run test:ui
```

### Run tests with coverage
```bash
npm run test:coverage
```

## Code Quality

### Type checking
```bash
npm run type-check
```

### Linting
```bash
npm run lint
```

## Project Structure

```
frontend/
├── src/
│   ├── components/      # React components
│   │   ├── SystemSelector/
│   │   └── SiteList/
│   ├── stores/          # Zustand state management
│   ├── services/        # API services
│   ├── types/           # TypeScript types
│   ├── App.tsx          # Main application
│   ├── main.tsx         # Entry point
│   └── index.css        # Global styles
├── public/              # Static assets
├── index.html           # HTML template
├── package.json         # Dependencies
├── tsconfig.json        # TypeScript config
└── vite.config.ts       # Vite config
```

## Features

- **System Selector**: Search and select star systems with autocomplete
- **Real-time Updates**: WebSocket connection for live data (coming soon)
- **Construction Sites**: View all construction sites in a system
- **Commodity Tracking**: Detailed commodity requirements with progress bars
- **Color-Coded Status**: Green for completed, orange for in-progress
- **Responsive Design**: Works on desktop and mobile devices

## Technologies

- **React 18** - UI framework
- **TypeScript** - Type safety
- **Material-UI** - Component library
- **Zustand** - State management
- **Axios** - HTTP client
- **Vite** - Build tool

## Troubleshooting

### Blank page
- Ensure backend is running on port 8000
- Check browser console for errors
- Verify `npm install` completed successfully

### API connection errors
- Verify backend is accessible at http://localhost:8000
- Check CORS settings in backend
- Ensure proxy configuration in `vite.config.ts` is correct

### Build errors
- Clear node_modules: `rm -rf node_modules package-lock.json`
- Reinstall: `npm install`
- Check Node.js version (18+ required)

## License

MIT License - see LICENSE file for details