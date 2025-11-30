# Elite: Dangerous Colonization Assistant - Architecture Plan

## 1. System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Interface (React)                    │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │System Search │  │ Site Filter  │  │  Commodity Display │   │
│  │& Autocomplete│  │  & Selection │  │  with Color Coding │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ WebSocket (Real-time updates)
                              │ REST API (Initial data)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Python Backend (FastAPI)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │   Journal    │  │     File     │  │       Data         │   │
│  │    Parser    │  │   Watcher    │  │    Aggregator      │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐   │
│  │  WebSocket   │  │  REST API    │  │   Data Store       │   │
│  │   Server     │  │   Endpoints  │  │   (In-Memory)      │   │
│  └──────────────┘  └──────────────┘  └────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ File System Watch
                              │
┌─────────────────────────────────────────────────────────────────┐
│              Elite: Dangerous Journal Files                      │
│  C:\Users\%userprofile%\Saved Games\Frontier Developments\      │
│                    Elite Dangerous\                              │
│  - Journal.*.log (Line-delimited JSON)                          │
│  - Status.json (Real-time ship status)                          │
└─────────────────────────────────────────────────────────────────┘
```

## 2. Backend Architecture (Python)

### 2.1 Technology Stack
- **Framework**: FastAPI (async support, WebSocket, auto-documentation)
- **File Watching**: watchdog
- **Testing**: pytest, pytest-asyncio, pytest-cov
- **Type Checking**: mypy
- **Code Quality**: pylint, black, isort

### 2.2 Project Structure

```
backend/
├── src/
│   ├── __init__.py
│   ├── main.py                      # FastAPI application entry point
│   ├── config.py                    # Configuration management
│   ├── models/
│   │   ├── __init__.py
│   │   ├── journal_events.py        # Pydantic models for journal events
│   │   ├── colonisation.py          # Colonisation-specific models
│   │   └── api_models.py            # API request/response models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── journal_parser.py        # Parse journal files
│   │   ├── file_watcher.py          # Watch for file changes
│   │   ├── data_aggregator.py       # Aggregate colonisation data
│   │   └── system_tracker.py        # Track current system
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── colonisation_repository.py  # Data access layer
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py                # REST API endpoints
│   │   └── websocket.py             # WebSocket handlers
│   └── utils/
│       ├── __init__.py
│       ├── logger.py                # Logging configuration
│       └── validators.py            # Custom validators
├── tests/
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── unit/
│   │   ├── test_journal_parser.py
│   │   ├── test_file_watcher.py
│   │   ├── test_data_aggregator.py
│   │   └── test_system_tracker.py
│   ├── integration/
│   │   ├── test_api_endpoints.py
│   │   └── test_websocket.py
│   └── fixtures/
│       └── sample_journal_data.json
├── requirements.txt
├── requirements-dev.txt
├── pytest.ini
├── mypy.ini
└── README.md
```

### 2.3 Core Components

#### 2.3.1 Journal Parser Service
**Responsibility**: Parse Elite: Dangerous journal files and extract relevant events

```python
# Interfaces (Abstract Base Classes)
class IJournalParser(ABC):
    @abstractmethod
    def parse_file(self, file_path: Path) -> List[JournalEvent]:
        """Parse a journal file and return list of events"""
        pass
    
    @abstractmethod
    def parse_line(self, line: str) -> Optional[JournalEvent]:
        """Parse a single line from journal file"""
        pass

# Implementation
class JournalParser(IJournalParser):
    """
    Parses Elite: Dangerous journal files.
    Follows Single Responsibility Principle.
    """
    def __init__(self, event_factory: IEventFactory):
        self._event_factory = event_factory
    
    def parse_file(self, file_path: Path) -> List[JournalEvent]:
        # Implementation
        pass
    
    def parse_line(self, line: str) -> Optional[JournalEvent]:
        # Implementation
        pass
```

**Key Events to Parse**:
- `ColonizationConstructionDepot` - Construction site status
- `ColonizationContribution` - Player contributions
- `Location` - Current system/station
- `FSDJump` - System changes
- `Docked` - Station docking

#### 2.3.2 File Watcher Service
**Responsibility**: Monitor journal directory for changes and trigger parsing

```python
class IFileWatcher(ABC):
    @abstractmethod
    async def start_watching(self, directory: Path) -> None:
        """Start watching directory for changes"""
        pass
    
    @abstractmethod
    async def stop_watching(self) -> None:
        """Stop watching directory"""
        pass

class FileWatcher(IFileWatcher):
    """
    Watches Elite: Dangerous journal directory for changes.
    Uses Observer pattern to notify subscribers.
    """
    def __init__(self, 
                 parser: IJournalParser,
                 event_bus: IEventBus):
        self._parser = parser
        self._event_bus = event_bus
        self._observer = None
    
    async def start_watching(self, directory: Path) -> None:
        # Implementation using watchdog
        pass
```

#### 2.3.3 Data Aggregator Service
**Responsibility**: Aggregate colonisation data by system and construction site

```python
class IDataAggregator(ABC):
    @abstractmethod
    def aggregate_by_system(self, 
                           system_name: str) -> SystemColonisationData:
        """Aggregate all construction sites in a system"""
        pass
    
    @abstractmethod
    def aggregate_commodities(self, 
                             sites: List[ConstructionSite]) -> Dict[str, CommodityAggregate]:
        """Aggregate commodities across multiple sites"""
        pass

class DataAggregator(IDataAggregator):
    """
    Aggregates colonisation data.
    Follows Open/Closed Principle - extensible for new aggregation types.
    """
    def __init__(self, repository: IColonisationRepository):
        self._repository = repository
    
    def aggregate_by_system(self, system_name: str) -> SystemColonizationData:
        # Implementation
        pass
```

#### 2.3.4 Colonization Repository
**Responsibility**: Data access and storage (in-memory with thread-safe operations)

```python
class IColonizationRepository(ABC):
    @abstractmethod
    def add_construction_site(self, site: ConstructionSite) -> None:
        """Add or update construction site data"""
        pass
    
    @abstractmethod
    def get_sites_by_system(self, system_name: str) -> List[ConstructionSite]:
        """Get all construction sites in a system"""
        pass
    
    @abstractmethod
    def get_all_systems(self) -> List[str]:
        """Get list of all known systems with construction"""
        pass

class ColonizationRepository(IColonizationRepository):
    """
    Thread-safe in-memory storage for colonization data.
    Uses Repository pattern for data access abstraction.
    """
    def __init__(self):
        self._data: Dict[str, Dict[int, ConstructionSite]] = {}
        self._lock = asyncio.Lock()
```

### 2.4 Data Models

```python
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class CommodityStatus(str, Enum):
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    NOT_STARTED = "not_started"

class Commodity(BaseModel):
    """Represents a commodity requirement for construction"""
    name: str
    name_localised: str
    required_amount: int
    provided_amount: int
    payment: int
    
    @property
    def remaining_amount(self) -> int:
        return max(0, self.required_amount - self.provided_amount)
    
    @property
    def progress_percentage(self) -> float:
        if self.required_amount == 0:
            return 100.0
        return (self.provided_amount / self.required_amount) * 100.0
    
    @property
    def status(self) -> CommodityStatus:
        if self.provided_amount >= self.required_amount:
            return CommodityStatus.COMPLETED
        elif self.provided_amount > 0:
            return CommodityStatus.IN_PROGRESS
        return CommodityStatus.NOT_STARTED

class ConstructionSite(BaseModel):
    """Represents a construction site (depot)"""
    market_id: int
    station_name: str
    station_type: str
    system_name: str
    system_address: int
    construction_progress: float
    construction_complete: bool
    construction_failed: bool
    commodities: List[Commodity]
    last_updated: datetime
    
    @property
    def is_complete(self) -> bool:
        return self.construction_complete
    
    @property
    def total_commodities_needed(self) -> int:
        return sum(c.remaining_amount for c in self.commodities)

class SystemColonizationData(BaseModel):
    """Aggregated colonization data for a system"""
    system_name: str
    construction_sites: List[ConstructionSite]
    total_sites: int
    completed_sites: int
    in_progress_sites: int
    
    @property
    def completion_percentage(self) -> float:
        if self.total_sites == 0:
            return 0.0
        return (self.completed_sites / self.total_sites) * 100.0

class CommodityAggregate(BaseModel):
    """Aggregated commodity data across multiple sites"""
    commodity_name: str
    commodity_name_localised: str
    total_required: int
    total_provided: int
    total_remaining: int
    sites_requiring: List[str]  # List of station names
    average_payment: float
    
    @property
    def progress_percentage(self) -> float:
        if self.total_required == 0:
            return 100.0
        return (self.total_provided / self.total_required) * 100.0
```

### 2.5 API Endpoints

```python
# REST API Endpoints
GET  /api/systems                    # Get all systems with construction
GET  /api/systems/{system_name}      # Get colonisation data for system
GET  /api/systems/search?q={query}   # Search systems (autocomplete)
GET  /api/sites/{market_id}          # Get specific construction site
GET  /api/health                     # Health check

# WebSocket Endpoint
WS   /ws/colonization                # Real-time updates
```

### 2.6 WebSocket Protocol

```json
// Client -> Server (Subscribe to system)
{
  "type": "subscribe",
  "system_name": "Lupus Dark Region BQ-Y d66"
}

// Server -> Client (Update notification)
{
  "type": "update",
  "system_name": "Lupus Dark Region BQ-Y d66",
  "data": {
    "construction_sites": [...],
    "timestamp": "2025-11-29T01:00:00Z"
  }
}

// Server -> Client (Current system changed)
{
  "type": "system_changed",
  "old_system": "System A",
  "new_system": "System B",
  "timestamp": "2025-11-29T01:00:00Z"
}
```

## 3. Frontend Architecture (React)

### 3.1 Technology Stack
- **Framework**: React 18+ with TypeScript
- **State Management**: Zustand (lightweight, simple)
- **UI Library**: Material-UI (MUI) or Tailwind CSS + Headless UI
- **WebSocket**: native WebSocket API with reconnection logic
- **HTTP Client**: Axios
- **Testing**: Jest, React Testing Library
- **Build Tool**: Vite

### 3.2 Project Structure

```
frontend/
├── public/
│   └── index.html
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/
│   │   ├── SystemSelector/
│   │   │   ├── SystemSelector.tsx
│   │   │   ├── SystemSelector.test.tsx
│   │   │   └── SystemAutocomplete.tsx
│   │   ├── SiteList/
│   │   │   ├── SiteList.tsx
│   │   │   ├── SiteList.test.tsx
│   │   │   ├── SiteCard.tsx
│   │   │   └── SiteFilter.tsx
│   │   ├── CommodityDisplay/
│   │   │   ├── CommodityDisplay.tsx
│   │   │   ├── CommodityDisplay.test.tsx
│   │   │   ├── CommodityList.tsx
│   │   │   ├── CommodityItem.tsx
│   │   │   └── ProgressBar.tsx
│   │   ├── Layout/
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── MainLayout.tsx
│   │   └── common/
│   │       ├── LoadingSpinner.tsx
│   │       ├── ErrorBoundary.tsx
│   │       └── StatusBadge.tsx
│   ├── hooks/
│   │   ├── useWebSocket.ts
│   │   ├── useColonisationData.ts
│   │   └── useSystemSearch.ts
│   ├── services/
│   │   ├── api.ts
│   │   └── websocket.ts
│   ├── stores/
│   │   ├── colonisationStore.ts
│   │   └── uiStore.ts
│   ├── types/
│   │   ├── colonisation.ts
│   │   └── api.ts
│   ├── utils/
│   │   ├── formatters.ts
│   │   └── colors.ts
│   └── styles/
│       └── theme.ts
├── tests/
│   └── setup.ts
├── package.json
├── tsconfig.json
├── vite.config.ts
└── README.md
```

### 3.3 Component Hierarchy

```
App
├── MainLayout
│   ├── Header
│   │   └── SystemSelector
│   │       └── SystemAutocomplete
│   ├── Sidebar (optional - for filters/settings)
│   │   └── SiteFilter
│   └── MainContent
│       ├── SiteList
│       │   └── SiteCard (multiple)
│       │       ├── StatusBadge
│       │       ├── ProgressBar
│       │       └── CommodityDisplay
│       │           └── CommodityList
│       │               └── CommodityItem (multiple)
│       │                   ├── ProgressBar
│       │                   └── StatusIndicator
│       └── AggregatedView (optional)
│           └── CommodityAggregate
```

### 3.4 Key Components

#### 3.4.1 SystemSelector Component
```typescript
interface SystemSelectorProps {
  onSystemSelect: (systemName: string) => void;
  currentSystem?: string;
}

export const SystemSelector: React.FC<SystemSelectorProps> = ({
  onSystemSelect,
  currentSystem
}) => {
  // Auto-detect current system from backend
  // Provide autocomplete search
  // Show current system prominently
};
```

#### 3.4.2 SiteCard Component
```typescript
interface SiteCardProps {
  site: ConstructionSite;
  expanded?: boolean;
  onToggle?: () => void;
}

export const SiteCard: React.FC<SiteCardProps> = ({
  site,
  expanded,
  onToggle
}) => {
  // Display site name, type, progress
  // Show completion status with color coding
  // Expandable to show commodity details
};
```

#### 3.4.3 CommodityItem Component
```typescript
interface CommodityItemProps {
  commodity: Commodity;
  siteName: string;
}

export const CommodityItem: React.FC<CommodityItemProps> = ({
  commodity,
  siteName
}) => {
  // Color coding:
  // - GREEN text for completed (provided >= required)
  // - ORANGE text for in-progress (provided < required)
  // Show: name, required, provided, remaining, progress bar, payment
};
```

### 3.5 State Management (Zustand)

```typescript
interface ColonizationStore {
  // State
  currentSystem: string | null;
  systemData: SystemColonizationData | null;
  allSystems: string[];
  selectedSites: Set<number>;
  loading: boolean;
  error: string | null;
  
  // Actions
  setCurrentSystem: (system: string) => void;
  updateSystemData: (data: SystemColonizationData) => void;
  toggleSiteSelection: (marketId: number) => void;
  clearSelection: () => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useColonizationStore = create<ColonizationStore>((set) => ({
  // Implementation
}));
```

### 3.6 WebSocket Hook

```typescript
export const useWebSocket = (url: string) => {
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);
  const ws = useRef<WebSocket | null>(null);
  
  useEffect(() => {
    // Connect to WebSocket
    // Handle reconnection
    // Parse messages
    // Update store
  }, [url]);
  
  const sendMessage = useCallback((message: any) => {
    if (ws.current?.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(message));
    }
  }, []);
  
  return { isConnected, lastMessage, sendMessage };
};
```

## 4. UI/UX Design Specifications

### 4.1 Color Scheme

```typescript
export const theme = {
  colors: {
    // Status colors
    completed: '#4CAF50',      // Green for completed commodities
    inProgress: '#FF9800',     // Orange for needed commodities
    notStarted: '#9E9E9E',     // Gray for not started
    
    // Site status
    siteComplete: '#4CAF50',   // Green badge for complete sites
    siteInProgress: '#2196F3', // Blue for in-progress sites
    
    // UI colors
    background: '#1a1a1a',     // Dark background (Elite theme)
    surface: '#2d2d2d',        // Card background
    primary: '#FF6B00',        // Elite orange
    text: '#FFFFFF',
    textSecondary: '#B0B0B0',
  }
};
```

### 4.2 Layout Design

```
┌─────────────────────────────────────────────────────────────────┐
│  Header                                                          │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ 🔍 Search System: [Lupus Dark Region BQ-Y d66    ▼]   │    │
│  │    Current: Lupus Dark Region BQ-Y d66 (Auto-detected)│    │
│  └────────────────────────────────────────────────────────┘    │
├─────────────────────────────────────────────────────────────────┤
│  Filters: [All Sites ▼] [Show Completed ☑] [Aggregate View ☐] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🟢 Sweet City O' Mine (COMPLETE)                         │  │
│  │ Progress: ████████████████████████ 100%                  │  │
│  │ Type: Planetary Construction Depot                       │  │
│  │ ✓ All commodities delivered                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 🔵 Sword Of Repentance (IN PROGRESS)                     │  │
│  │ Progress: ████████████░░░░░░░░░░ 65%                    │  │
│  │ Type: Orbital Construction Site                          │  │
│  │                                                           │  │
│  │ Commodities Required:                                    │  │
│  │ ┌────────────────────────────────────────────────────┐  │  │
│  │ │ ✓ Ceramic Composites                               │  │  │
│  │ │   497 / 497 (100%) ████████████████████████        │  │  │
│  │ │   Payment: 724 CR                                  │  │  │
│  │ ├────────────────────────────────────────────────────┤  │  │
│  │ │ 🟠 CMM Composite                                   │  │  │
│  │ │   2519 / 3912 (64%) ████████████░░░░░░░░          │  │  │
│  │ │   Remaining: 1393                                  │  │  │
│  │ │   Payment: 6788 CR                                 │  │  │
│  │ ├────────────────────────────────────────────────────┤  │  │
│  │ │ 🟠 Steel                                           │  │  │
│  │ │   783 / 1871 (42%) ████████░░░░░░░░░░░░          │  │  │
│  │ │   Remaining: 1088                                  │  │  │
│  │ │   Payment: 1234 CR                                 │  │  │
│  │ └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 📊 Aggregated Commodities (All Sites)                    │  │
│  │ ┌────────────────────────────────────────────────────┐  │  │
│  │ │ 🟠 CMM Composite - 1393 needed                     │  │  │
│  │ │   Required by: Sword Of Repentance                 │  │  │
│  │ ├────────────────────────────────────────────────────┤  │  │
│  │ │ 🟠 Steel - 1088 needed                             │  │  │
│  │ │   Required by: Sword Of Repentance                 │  │  │
│  │ └────────────────────────────────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

## 5. Testing Strategy

### 5.1 Backend Testing

```python
# Unit Tests
- test_journal_parser.py
  - Test parsing valid journal lines
  - Test parsing invalid/malformed data
  - Test event type detection
  - Test data extraction

- test_file_watcher.py
  - Test file change detection
  - Test new file detection
  - Test event emission
  - Test error handling

- test_data_aggregator.py
  - Test system aggregation
  - Test commodity aggregation
  - Test progress calculations
  - Test site delineation

# Integration Tests
- test_api_endpoints.py
  - Test GET /api/systems
  - Test GET /api/systems/{name}
  - Test search functionality
  - Test error responses

- test_websocket.py
  - Test connection establishment
  - Test subscription mechanism
  - Test real-time updates
  - Test reconnection logic
```

### 5.2 Frontend Testing

```typescript
// Component Tests
- SystemSelector.test.tsx
  - Test autocomplete functionality
  - Test system selection
  - Test current system display

- SiteCard.test.tsx
  - Test completion status display
  - Test color coding
  - Test expand/collapse

- CommodityItem.test.tsx
  - Test progress calculation
  - Test color coding (green/orange)
  - Test data display

// Integration Tests
- Test WebSocket connection
- Test real-time updates
- Test state management
- Test error handling
```

## 6. Design Patterns Applied

### 6.1 SOLID Principles

1. **Single Responsibility Principle**
   - Each service has one clear responsibility
   - JournalParser only parses
   - FileWatcher only watches
   - DataAggregator only aggregates

2. **Open/Closed Principle**
   - Services are open for extension via interfaces
   - New event types can be added without modifying existing code
   - New aggregation strategies can be added

3. **Liskov Substitution Principle**
   - All implementations can replace their interfaces
   - Mock implementations for testing

4. **Interface Segregation Principle**
   - Small, focused interfaces
   - Clients only depend on methods they use

5. **Dependency Inversion Principle**
   - High-level modules depend on abstractions
   - Dependency injection throughout

### 6.2 Other Patterns

- **Repository Pattern**: Data access abstraction
- **Observer Pattern**: File watching and event notifications
- **Factory Pattern**: Event creation from JSON
- **Strategy Pattern**: Different aggregation strategies
- **Singleton Pattern**: Configuration and logger
- **Facade Pattern**: API layer simplifies complex operations

## 7. Deployment & Configuration

### 7.1 Configuration File

```yaml
# config.yaml
journal:
  directory: "C:\\Users\\%USERNAME%\\Saved Games\\Frontier Developments\\Elite Dangerous"
  watch_interval: 1.0  # seconds

server:
  host: "localhost"
  port: 8000
  cors_origins:
    - "http://localhost:5173"  # Vite dev server

websocket:
  ping_interval: 30  # seconds
  reconnect_attempts: 5

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

### 7.2 Environment Variables

```bash
# .env
ED_JOURNAL_PATH=C:\Users\%USERNAME%\Saved Games\Frontier Developments\Elite Dangerous
API_HOST=localhost
API_PORT=8000
WS_PORT=8000
LOG_LEVEL=INFO
```

## 8. Development Workflow

### 8.1 Backend Development

```bash
# Setup
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements-dev.txt

# Run tests
pytest tests/ -v --cov=src --cov-report=html

# Type checking
mypy src/

# Code formatting
black src/ tests/
isort src/ tests/

# Linting
pylint src/

# Run server
python -m src.main
```

### 8.2 Frontend Development

```bash
# Setup
cd frontend
npm install

# Run tests
npm test

# Type checking
npm run type-check

# Development server
npm run dev

# Build
npm run build
```

## 9. Future Enhancements

1. **Persistent Storage**: Add SQLite/PostgreSQL for historical data
2. **Trade Route Suggestions**: Suggest where to buy needed commodities
3. **Notifications**: Desktop notifications for construction completion
4. **Multi-Commander Support**: Track multiple commanders
5. **Export Functionality**: Export shopping lists
6. **Mobile App**: React Native version
7. **Community Features**: Share construction progress with squadron
8. **Analytics Dashboard**: Historical progress tracking

## 10. Performance Considerations

1. **File Watching**: Debounce file change events (1 second)
2. **WebSocket**: Throttle updates to max 1 per second per client
3. **Data Aggregation**: Cache aggregated results, invalidate on update
4. **Frontend**: Virtual scrolling for large commodity lists
5. **Memory**: Limit stored journal events to last 24 hours

## 11. Security Considerations

1. **File Access**: Validate journal file paths
2. **WebSocket**: Implement connection limits
3. **API**: Rate limiting on endpoints
4. **Input Validation**: Sanitize all user inputs
5. **CORS**: Restrict to known origins

---

This architecture provides a solid foundation for a maintainable, testable, and extensible Elite: Dangerous Colonization Assistant application.