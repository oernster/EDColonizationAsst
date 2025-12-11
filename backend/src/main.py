"""Main FastAPI application entry point"""

from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .config import get_config
from .utils.logger import setup_logging, get_logger
from .services.journal_parser import JournalParser
from .services.file_watcher import FileWatcher
from .services.data_aggregator import DataAggregator
from .services.system_tracker import SystemTracker
from .repositories.colonization_repository import ColonizationRepository
from .api.routes import router as colonization_router, set_dependencies
from .api.settings import router as settings_router
from .api.journal import router as journal_router
from .api.websocket import websocket_endpoint, set_aggregator, notify_system_update

# Setup logging
setup_logging()
logger = get_logger(__name__)

# Application lifespan management


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.

    Responsible for:
    - constructing core services and repositories
    - wiring FastAPI route and WebSocket dependencies
    - starting and stopping the journal file watcher
    """
    logger.info("Starting Elite: Dangerous Colonization Assistant")

    config = get_config()

    # Initialize core components
    repository = ColonizationRepository()
    aggregator = DataAggregator(repository)
    system_tracker = SystemTracker()
    parser = JournalParser()
    file_watcher = FileWatcher(parser, system_tracker, repository)

    # Expose components via application state for other parts of the app
    app.state.repository = repository
    app.state.aggregator = aggregator
    app.state.system_tracker = system_tracker
    app.state.file_watcher = file_watcher

    # Set dependencies for API routes and WebSocket layer
    set_dependencies(repository, aggregator, system_tracker)
    set_aggregator(aggregator)

    # Set update callback for file watcher
    file_watcher.set_update_callback(notify_system_update)

    # Start watching journal directory
    journal_dir = Path(config.journal.directory)
    try:
        await file_watcher.start_watching(journal_dir)
        logger.info("File watcher started successfully")
    except FileNotFoundError as e:
        logger.error("Failed to start file watcher: %s", e)
        logger.warning("Application will start but journal monitoring is disabled")

    try:
        yield
    finally:
        # Shutdown
        logger.info("Shutting down Elite: Dangerous Colonization Assistant")
        file_watcher_from_state: FileWatcher | None = getattr(
            app.state, "file_watcher", None
        )
        if file_watcher_from_state is not None:
            await file_watcher_from_state.stop_watching()


# Create FastAPI application
app = FastAPI(
    title="Elite: Dangerous Colonization Assistant",
    description="Real-time tracking for Elite: Dangerous colonization efforts",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.server.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(colonization_router)
app.include_router(settings_router)
app.include_router(journal_router)

# WebSocket endpoint
app.add_api_websocket_route("/ws/colonization", websocket_endpoint)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "Elite: Dangerous Colonization Assistant",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    config = get_config()
    uvicorn.run(
        "src.main:app",
        host=config.server.host,
        port=config.server.port,
        reload=True,
        log_level=config.logging.level.lower(),
    )
