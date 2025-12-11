# GameGlass Integration

This document describes how a GameGlass shard (or any embedded web view) should talk to the ED Colonization Assistant backend. It focuses on:

- The HTTP **API endpoints** exposed by the assistant
- The **request / response shapes** that are relevant to GameGlass
- How to obtain a **shopping list of commodities** for construction sites


## 1. Backend Overview

The backend is a FastAPI service that exposes:

- **REST endpoints** under the `/api` prefix
- A **WebSocket endpoint** at `/ws/colonization` for real-time updates

By default the service listens on `http://localhost:<port>`, where the port is configured in the backend configuration (see the main application README / config). When developing a GameGlass shard on the same machine, the typical base URLs are:

- `http://localhost:<port>/api/...` for HTTP requests
- `ws://localhost:<port>/ws/colonization` for WebSocket connections

CORS is configured to allow browser-based clients, so calls from the shard’s embedded web view are permitted as long as they target the correct origin and port.


## 2. Key REST Endpoints for GameGlass

This section documents the endpoints that a GameGlass shard is expected to use, especially for displaying:

- Construction sites (per-system and across all systems)
- A **shopping list of required commodities**


### 2.1. List All Construction Sites

**Method:** GET  
**Path:** `/api/sites`

**Purpose**

Returns **all construction sites** known to the assistant, split into **in-progress** and **completed** categories. This is a convenient way to populate a main site list in a shard.

**Successful Response (shape)**

```json
{
  "in_progress_sites": [
    {
      "market_id": 123456,
      "station_name": "Example Depot",
      "station_type": "Outpost",
      "system_name": "LHS 1234",
      "system_address": 1234567890,
      "construction_progress": 42.5,
      "construction_complete": false,
      "construction_failed": false,
      "commodities": [
        {
          "name": "water",
          "name_localised": "Water",
          "required_amount": 1000,
          "provided_amount": 250,
          "remaining_amount": 750,
          "progress_percentage": 25.0,
          "payment": 250000,
          "status": "in_progress"
        }
      ],
      "total_commodities_needed": 750,
      "commodities_progress_percentage": 25.0,
      "last_updated": "2025-01-01T12:00:00Z",
      "last_source": "journal"
    }
  ],
  "completed_sites": [
    {
      "market_id": 987654,
      "station_name": "Finished Depot",
      "station_type": "Coriolis",
      "system_name": "LHS 5678",
      "system_address": 987654321,
      "construction_progress": 100.0,
      "construction_complete": true,
      "construction_failed": false,
      "commodities": [],
      "total_commodities_needed": 0,
      "commodities_progress_percentage": 100.0,
      "last_updated": "2025-01-02T10:00:00Z",
      "last_source": "journal"
    }
  ]
}
```

Notes:

- The `commodities` array on each site contains **per-commodity progress**.
- The fields `total_commodities_needed` and `commodities_progress_percentage` summarize the commodity situation for each site.
- You can use this endpoint to:
  - Render global lists of depots
  - Build a **global shopping list** by aggregating `commodities` across **all** sites in the shard itself


### 2.2. Systems and System Selection

These endpoints help present and filter data by star system.


#### 2.2.1. List Systems with Construction Sites

**Method:** GET  
**Path:** `/api/systems`

**Purpose**

Returns a list of system names that currently have construction sites.

**Response Example**

```json
{
  "systems": [
    "LHS 1234",
    "LHS 5678"
  ]
}
```

Typical usage: populate a system dropdown or allow manual system selection in the shard.


#### 2.2.2. Search Systems (Autocomplete)

**Method:** GET  
**Path:** `/api/systems/search`  
**Query Parameters:**

- `q` (required, string): case-insensitive search term

**Response Example**

```json
{
  "systems": [
    "LHS 1234"
  ]
}
```


#### 2.2.3. Player’s Current System

**Method:** GET  
**Path:** `/api/systems/current`

**Purpose**

Returns the current system and (if applicable) station, as tracked by the assistant’s system tracker.

**Response Example**

```json
{
  "system_name": "LHS 1234",
  "station_name": "Example Depot",
  "is_docked": true
}
```

Typical usage:

- Auto-select the current system in the shard
- Optionally show whether the player is docked and where


### 2.3. Per-System Colonization Data

These endpoints operate on a **single system** and are useful for building a per-system view in the shard.


#### 2.3.1. Get All Sites in a System

**Method:** GET  
**Path:** `/api/system`  
**Query Parameters:**

- `name` (required, string): system name, for example `LHS 1234`

**Purpose**

Returns colonization data for a single system, including its construction sites and overall progress.

**Response Example (simplified)**

```json
{
  "system_name": "LHS 1234",
  "construction_sites": [
    {
      "market_id": 123456,
      "station_name": "Example Depot",
      "station_type": "Outpost",
      "system_name": "LHS 1234",
      "system_address": 1234567890,
      "construction_progress": 42.5,
      "construction_complete": false,
      "construction_failed": false,
      "commodities": [
        {
          "name": "water",
          "name_localised": "Water",
          "required_amount": 1000,
          "provided_amount": 250,
          "remaining_amount": 750,
          "progress_percentage": 25.0,
          "payment": 250000,
          "status": "in_progress"
        }
      ],
      "total_commodities_needed": 750,
      "commodities_progress_percentage": 25.0,
      "last_updated": "2025-01-01T12:00:00Z",
      "last_source": "journal"
    }
  ],
  "total_sites": 1,
  "completed_sites": 0,
  "in_progress_sites": 1,
  "completion_percentage": 0.0
}
```


#### 2.3.2. Get a Single Site by Market ID

**Method:** GET  
**Path:** `/api/sites/{market_id}`

**Purpose**

Returns full details for a single construction site, identified by its market ID. This is useful if the shard deep-links to one specific depot.

**Response Example (simplified)**

```json
{
  "site": {
    "market_id": 123456,
    "station_name": "Example Depot",
    "system_name": "LHS 1234",
    "commodities": [
      {
        "name": "water",
        "name_localised": "Water",
        "required_amount": 1000,
        "provided_amount": 250,
        "remaining_amount": 750,
        "progress_percentage": 25.0,
        "payment": 250000,
        "status": "in_progress"
      }
    ],
    "total_commodities_needed": 750,
    "commodities_progress_percentage": 25.0
  }
}
```


### 2.4. Shopping List (Aggregated Commodities)

This is the primary endpoint for building a **per-system shopping list of commodities** in a GameGlass shard.

**Method:** GET  
**Path:** `/api/system/commodities`  
**Query Parameters:**

- `name` (required, string): system name

**Purpose**

Returns an **aggregated view of commodities** required across all construction sites in the specified system.

**Response Example**

```json
{
  "commodities": [
    {
      "commodity_name": "water",
      "commodity_name_localised": "Water",
      "total_required": 1000,
      "total_provided": 250,
      "total_remaining": 750,
      "average_payment": 250000,
      "sites_requiring": [
        "Example Depot",
        "Another Depot"
      ],
      "progress_percentage": 25.0
    }
  ]
}
```

Key fields for a shard:

- `commodity_name_localised`: display name
- `total_remaining`: how much the commander still needs to deliver
- `average_payment`: indicative payment per unit
- `sites_requiring`: which depots need this commodity
- `progress_percentage`: overall progress towards the total requirement

**Typical usage in a shard**

- For the **current system**:
  1. Call `/api/systems/current` to obtain `system_name`.
  2. Call `/api/system/commodities?name=<system_name>`.
  3. Render a list of rows with:
     - Commodity name
     - Remaining quantity
     - Payment information
     - List of depots requiring it (optional)

- For a **manually selected system**:
  1. Populate a system selector from `/api/systems`.
  2. When a system is chosen, call `/api/system/commodities?name=<selected_system>` and render as above.

If you want a **global shopping list** across **all systems**, there is no dedicated endpoint. Instead:

1. Call `/api/sites`.
2. Aggregate the `commodities` arrays from all `in_progress_sites` on the client (in the shard) to compute global totals.


### 2.5. Supporting Endpoints

These endpoints are useful for diagnostics and auxiliary UI, but are not strictly required for a basic construction-site-and-shopping-list shard.


#### 2.5.1. Health Check

**Method:** GET  
**Path:** `/api/health`

**Purpose**

Returns the health status of the assistant.

**Response Example**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "journal_directory": "C:\\\\Users\\\\Example\\\\Saved Games\\\\Frontier Developments\\\\Elite Dangerous",
  "journal_accessible": true
}
```

Typical usage:

- Verify that the backend is running before attempting other calls
- Show a small status indicator in the shard (optional)


#### 2.5.2. Journal Status

**Method:** GET  
**Path:** `/api/journal/status`

**Purpose**

Provides a minimal view of the latest journal-derived system.

**Response Example**

```json
{
  "current_system": "LHS 1234"
}
```

This can act as a fallback for inferring the current system directly from journal logs, but `/api/systems/current` is the richer endpoint if available.


#### 2.5.3. Settings

**Method:** GET  
**Path:** `/api/settings`

Returns the current application settings, including the journal directory and Inara configuration.

**Method:** POST  
**Path:** `/api/settings`

Accepts an updated settings object in JSON format. These endpoints are typically managed by the main web UI rather than a GameGlass shard, but they are listed here for completeness.


#### 2.5.4. Overall Statistics (Optional)

**Method:** GET  
**Path:** `/api/stats`

**Purpose**

Returns overall statistics about colonization data stored in the assistant. This can be used for high-level summary panels in a shard (for example totals of sites, systems, etc.). Exact contents may evolve with the backend and can be inspected via the generated OpenAPI docs (`/docs` route) or by calling the endpoint directly.


## 3. Real-Time Updates via WebSocket

For a more responsive shard you can subscribe to real-time system updates instead of (or in addition to) polling REST endpoints.

**URL:** `ws://localhost:<port>/ws/colonization`


### 3.1. Subscribing to a System

To begin receiving updates for a particular system, send a JSON message:

```json
{
  "type": "subscribe",
  "system_name": "LHS 1234"
}
```

Upon subscription, the server immediately sends a snapshot:

```json
{
  "type": "update",
  "system_name": "LHS 1234",
  "data": {
    "construction_sites": [
      {
        "market_id": 123456,
        "station_name": "Example Depot",
        "commodities": [
          {
            "name_localised": "Water",
            "required_amount": 1000,
            "provided_amount": 250,
            "remaining_amount": 750,
            "progress_percentage": 25.0,
            "payment": 250000,
            "status": "in_progress"
          }
        ],
        "total_commodities_needed": 750,
        "commodities_progress_percentage": 25.0
      }
    ],
    "total_sites": 1,
    "completed_sites": 0,
    "in_progress_sites": 1,
    "completion_percentage": 0.0
  },
  "timestamp": "2025-01-01T12:00:00Z"
}
```

Whenever new journal data is processed for that system, further `update` messages are sent with the same shape, allowing the shard to refresh its lists and shopping data without polling.


### 3.2. Unsubscribe and Keepalive

To stop receiving updates for a system:

```json
{
  "type": "unsubscribe",
  "system_name": "LHS 1234"
}
```

To keep the WebSocket connection alive, periodically send:

```json
{
  "type": "ping"
}
```

The server responds with:

```json
{
  "type": "pong",
  "timestamp": "2025-01-01T12:00:10Z"
}
```


## 4. Recommended Integration Flow for a Shard

A typical GameGlass shard that wants to show **construction sites** and a **shopping list of commodities** might:

1. **On load**
   - Call `/api/health` to confirm the backend is running.
   - Call `/api/systems/current` to determine the commander’s current system.
   - Optionally, call `/api/systems` to populate a system selector.

2. **For the selected system**
   - Call `/api/system?name=<system_name>` to display per-site cards.
   - Call `/api/system/commodities?name=<system_name>` to build the aggregated **shopping list** for that system.

3. **Optional: real-time updates**
   - Open `ws://localhost:<port>/ws/colonization`.
   - Send a `subscribe` message for the selected system.
   - Update the UI whenever an `update` message is received.

4. **When the shard is closed or the system changes**
   - Send an `unsubscribe` message for the old system, or close the WebSocket connection.

This API-focused description is intended to be sufficient for shard authors to integrate with the ED Colonization Assistant without needing to inspect the backend code.
