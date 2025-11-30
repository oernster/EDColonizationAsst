# Elite: Dangerous Colonization Assistant - Backend

Python FastAPI backend for the Elite: Dangerous Colonization Assistant.

## Setup

1. **Create virtual environment:**
   ```bash
   python -m venv venv
   ```

2. **Activate virtual environment:**
   ```bash
   # Windows
   venv\Scripts\activate
   
   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Configure:**
   - Edit `config.yaml` to match your Elite: Dangerous installation
   - Default journal path: `C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous`

## Running

### Development Server
```bash
uvicorn src.main:app --reload
```

The API will be available at:
- API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- WebSocket: ws://localhost:8000/ws/colonization

### Production Server
```bash
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

## Testing

### Run all tests
```bash
pytest
```

### Run with coverage
```bash
pytest --cov=src --cov-report=html
```

### Run specific test file
```bash
pytest tests/unit/test_models.py -v
```

## Code Quality

### Format code
```bash
black src/ tests/
isort src/ tests/
```

### Type checking
```bash
mypy src/
```

### Linting
```bash
pylint src/
```

## Project Structure

```
backend/
├── src/
│   ├── models/          # Data models (Pydantic)
│   ├── services/        # Business logic
│   ├── repositories/    # Data access
│   ├── api/            # API endpoints
│   ├── utils/          # Utilities
│   ├── config.py       # Configuration
│   └── main.py         # Application entry point
├── tests/
│   ├── unit/           # Unit tests
│   └── conftest.py     # Test fixtures
├── requirements.txt    # Production dependencies
└── requirements-dev.txt # Development dependencies
```

## API Endpoints

### REST API
- `GET /api/health` - Health check
- `GET /api/systems` - List all systems with construction
- `GET /api/systems/search?q={query}` - Search systems
- `GET /api/systems/current` - Get current player system
- `GET /api/systems/{system_name}` - Get system colonization data
- `GET /api/systems/{system_name}/commodities` - Get aggregated commodities
- `GET /api/sites/{market_id}` - Get specific construction site
- `GET /api/stats` - Get overall statistics

### WebSocket
- `WS /ws/colonization` - Real-time updates

#### WebSocket Messages

**Subscribe to system:**
```json
{
  "type": "subscribe",
  "system_name": "Lupus Dark Region BQ-Y d66"
}
```

**Unsubscribe from system:**
```json
{
  "type": "unsubscribe",
  "system_name": "Lupus Dark Region BQ-Y d66"
}
```

**Update notification (server -> client):**
```json
{
  "type": "update",
  "system_name": "Lupus Dark Region BQ-Y d66",
  "data": {
    "construction_sites": [...],
    "total_sites": 2,
    "completed_sites": 1,
    "in_progress_sites": 1,
    "completion_percentage": 50.0
  },
  "timestamp": "2025-11-29T01:00:00Z"
}
```

## Architecture

The backend follows SOLID principles and clean architecture:

- **Models**: Pydantic models for data validation
- **Services**: Business logic (parser, watcher, aggregator)
- **Repositories**: Data access layer (in-memory storage)
- **API**: REST endpoints and WebSocket handlers

### Key Components

1. **Journal Parser**: Parses Elite: Dangerous journal files
2. **File Watcher**: Monitors journal directory for changes
3. **System Tracker**: Tracks player's current system
4. **Data Aggregator**: Aggregates colonization data
5. **Repository**: Thread-safe in-memory data storage
6. **WebSocket Manager**: Manages real-time connections

## Configuration

Edit `config.yaml`:

```yaml
journal:
  directory: "C:\\Users\\%USERNAME%\\Saved Games\\Frontier Developments\\Elite Dangerous"
  watch_interval: 1.0

server:
  host: "0.0.0.0"
  port: 8000
  cors_origins:
    - "http://localhost:5173"

websocket:
  ping_interval: 30
  reconnect_attempts: 5

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

## Troubleshooting

### Journal files not found
- Verify the path in `config.yaml`
- Ensure Elite: Dangerous has been run at least once
- Check that the directory exists and is accessible

### Import errors
- Ensure virtual environment is activated
- Run `pip install -r requirements-dev.txt`

### Tests failing
- Check Python version (3.10+ required)
- Ensure all dependencies are installed
- Run `pytest -v` for detailed output

## License

MIT License - see LICENSE file for details