# GameGlass Integration Plan

This document outlines the architectural plan for integrating the ED Colonization Assistant with GameGlass.

## 1. Backend API Design

### 1.1. New API Endpoint: `GET /api/sites`

A new endpoint will be created to provide a comprehensive list of all construction sites, separated into "in-progress" and "completed" categories.

**Request:**

*   **Method:** `GET`
*   **Path:** `/api/sites`

**Response (Success):**

*   **Status Code:** `200 OK`
*   **Body:** `SiteListResponse`

### 1.2. New Response Model: `SiteListResponse`

To support the new endpoint, we will add a new response model to `backend/src/models/api_models.py`.

```python
from .colonization import ConstructionSite

class SiteListResponse(BaseModel):
    """Response model for a list of construction sites, categorized by status."""
    in_progress_sites: List[ConstructionSite] = Field(description="List of sites currently under construction")
    completed_sites: List[ConstructionSite] = Field(description="List of completed construction sites")
```

### 1.3. Endpoint Implementation (`backend/src/api/routes.py`)

Here is the proposed implementation for the new endpoint in `backend/src/api/routes.py`.

```python
@router.get("/sites", response_model=SiteListResponse)
async def get_all_sites() -> SiteListResponse:
    """Get all construction sites, categorized by status."""
    if _repository is None:
        raise HTTPException(status_code=500, detail="Repository not initialized")
    
    all_sites = await _repository.get_all_sites()
    
    in_progress = [site for site in all_sites if not site.is_complete]
    completed = [site for site in all_sites if site.is_complete]
    
    return SiteListResponse(
        in_progress_sites=in_progress,
        completed_sites=completed
    )
```
### 1.4. New Repository Method (`backend/src/repositories/colonization_repository.py`)

To support the new endpoint, we will add a new method to the `IColonizationRepository` interface and its implementation.

**Interface:**
```python
@abstractmethod
async def get_all_sites(self) -> List[ConstructionSite]:
    """Get all construction sites from the database"""
    pass
```

**Implementation:**
```python
async def get_all_sites(self) -> List[ConstructionSite]:
    async with self._lock:
        with self._get_db_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM construction_sites ORDER BY system_name, station_name")
            rows = cursor.fetchall()
            return [self._row_to_site(row) for row in rows if row]
```

## 2. Frontend UI Design

The web application embedded in the GameGlass shard will have a simple, clean interface, optimized for readability on a small screen.

### 2.1. Layout

The UI will be divided into two main sections: "In-Progress" and "Completed".

```mermaid
graph TD
    A[ED Colonization Assistant] --&gt; B{Main View};
    B --&gt; C[In-Progress Sites];
    B --&gt; D[Completed Sites];

    subgraph C [In-Progress Sites]
        direction LR
        C1[Site 1: Station Name];
        C2[Shopping List];
        C1 --&gt; C2;
        subgraph C2 [Shopping List]
            direction TB
            C2a[Commodity 1: Remaining];
            C2b[Commodity 2: Remaining];
            C2c[...];
        end
    end

    subgraph D [Completed Sites]
        direction TB
        D1[Site A];
        D2[Site B];
        D3[...];
    end

    style C fill:#f9f,stroke:#333,stroke-width:2px;
    style D fill:#ccf,stroke:#333,stroke-width:2px;
```

### 2.2. Styling

The design will be inspired by the in-game UI of Elite Dangerous, using a dark theme with orange and blue accents to match the provided images.

*   **Background:** Dark grey / black
*   **Text:** Light grey / white
*   **Headings:** Orange
*   **Progress Bars:** Blue / Orange
*   **Borders:** Subtle, glowing lines
