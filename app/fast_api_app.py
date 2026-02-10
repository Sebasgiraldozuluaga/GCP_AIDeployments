# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import warnings
import logging
from typing import Optional, List
from contextlib import contextmanager

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import psycopg2
from psycopg2.extras import RealDictCursor

from google.adk.cli.fast_api import get_fast_api_app
from app.app_utils.typing import Feedback

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Suppress Telemetry API warnings in local development
warnings.filterwarnings("ignore", category=UserWarning, message=".*Telemetry API.*")
warnings.filterwarnings("ignore", category=UserWarning, message=".*Failed to export span.*")
warnings.filterwarnings("ignore", message=".*LogRecord init with.*trace_id.*span_id.*")
warnings.filterwarnings("ignore", message=".*LogDeprecatedInitWarning.*")

# Constants & Configuration
ALLOW_ORIGINS = os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else ["*"]
LOGS_BUCKET_NAME = os.environ.get("LOGS_BUCKET_NAME")
ENABLE_OTEL = bool(LOGS_BUCKET_NAME) and os.getenv("ENABLE_OTEL", "false").lower() == "true"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(PROJECT_ROOT, "static")
INDEX_HTML_PATH = os.path.join(STATIC_DIR, "index.html")

ARTIFACT_SERVICE_URI = f"gs://{LOGS_BUCKET_NAME}" if LOGS_BUCKET_NAME else None

# FastAPI App Creation
app: FastAPI = get_fast_api_app(
    agents_dir=PROJECT_ROOT,
    web=True,
    artifact_service_uri=ARTIFACT_SERVICE_URI,
    allow_origins=ALLOW_ORIGINS,
    session_service_uri=None,
    otel_to_cloud=ENABLE_OTEL,
)

app.title = "raju-shop"
app.description = "API for interacting with the Agent raju-shop"
app.docs_url = app.redoc_url = app.openapi_url = None

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Cleanup default routes to prioritize custom "/"
for route in list(app.routes):
    if hasattr(route, 'path') and route.path == "/" and 'GET' in getattr(route, 'methods', []):
        if not (hasattr(route, 'endpoint') and route.endpoint.__name__ == 'read_root'):
            app.routes.remove(route)

# ============================================
# Database Utilities
# ============================================

def get_db_connection():
    """Returns a new database connection."""
    return psycopg2.connect(
        host=os.getenv("PG_HOST", "localhost"),
        port=os.getenv("PG_PORT", "5432"),
        database=os.getenv("PG_DATABASE", "postgres"),
        user=os.getenv("PG_USER", "postgres"),
        password=os.getenv("PG_PASSWORD", ""),
        cursor_factory=RealDictCursor
    )

@contextmanager
def db_session():
    """Context manager for database connections and cursors."""
    conn = get_db_connection()
    try:
        with conn.cursor() as cursor:
            yield cursor
    except Exception as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def fetch_distinct_values(table: str, column: str, search: Optional[str] = None, limit: int = 50) -> List[str]:
    """Generic helper to fetch distinct values from a table/column with optional filtering."""
    base_query = f"SELECT DISTINCT {column} FROM {table}"
    
    if search:
        query = f"{base_query} WHERE {column} ILIKE %s ORDER BY {column} LIMIT %s"
        params = (f"%{search}%", limit)
    else:
        query = f"{base_query} ORDER BY {column} LIMIT %s"
        params = (limit,)

    with db_session() as cursor:
        cursor.execute(query, params)
        results = cursor.fetchall()
        return [row[column] for row in results if row[column]]

# ============================================
# API Endpoints
# ============================================

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root():
    """Serve the frontend index.html with environment variables injected."""
    if not os.path.exists(INDEX_HTML_PATH):
        return HTMLResponse(content="<html><body>Frontend not found</body></html>", status_code=404)

    with open(INDEX_HTML_PATH, "r", encoding="utf-8") as f:
        html_content = f.read()
    
    api_base_url = os.getenv("API_BASE_URL", "")
    if api_base_url:
        meta_tag = f'    <meta name="api-base-url" content="{api_base_url}">\n'
        html_content = html_content.replace("</head>", meta_tag + "</head>")
    
    return HTMLResponse(content=html_content)

@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback."""
    return {"status": "success"}

@app.get("/api/productos")
async def get_productos(
    search: Optional[str] = Query(None, description="Search term for product name"),
    limit: int = Query(50, description="Maximum number of results")
):
    """Retrieve distinct product names."""
    try:
        productos = fetch_distinct_values("catalogo_maestro", "descripcion", search, limit)
        return {"productos": productos, "total": len(productos)}
    except Exception:
        raise HTTPException(status_code=500, detail="Error retrieving products")

@app.get("/api/proveedores")
async def get_proveedores(
    search: Optional[str] = Query(None, description="Search term for provider name"),
    limit: int = Query(50, description="Maximum number of results")
):
    """Retrieve distinct provider names."""
    try:
        proveedores = fetch_distinct_values("proveedor", "razon_social", search, limit)
        return {"proveedores": proveedores, "total": len(proveedores)}
    except Exception:
        raise HTTPException(status_code=500, detail="Error retrieving providers")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
