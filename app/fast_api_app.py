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
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from google.adk.cli.fast_api import get_fast_api_app
from app.app_utils.typing import Feedback

allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else ["*"]
)

# Artifact bucket for ADK (created by Terraform, passed via env var)
logs_bucket_name = os.environ.get("LOGS_BUCKET_NAME")

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In-memory session configuration - no persistent storage
session_service_uri = None

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=True,
)
app.title = "raju-shop"
app.description = "API for interacting with the Agent raju-shop"

# Disable FastAPI documentation to prevent it from showing on root
app.docs_url = None
app.redoc_url = None
app.openapi_url = None

# Serve static files
static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

# Remove any existing root route that might have been added by get_fast_api_app
# This ensures our custom route takes precedence
routes_to_remove = []
for route in app.routes:
    if hasattr(route, 'path') and route.path == "/":
        # Check if it's a GET route (documentation routes are usually GET)
        if hasattr(route, 'methods') and 'GET' in route.methods:
            # Skip our own route if it's already there
            if not (hasattr(route, 'endpoint') and hasattr(route.endpoint, '__name__') and route.endpoint.__name__ == 'read_root'):
                routes_to_remove.append(route)

for route in routes_to_remove:
    app.routes.remove(route)

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def read_root():
    """Serve the frontend index.html file with environment variables injected."""
    static_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        
        # Inject API_BASE_URL from environment variable if available
        api_base_url = os.getenv("API_BASE_URL", "")
        if api_base_url:
            # Inject meta tag in head section
            meta_tag = f'    <meta name="api-base-url" content="{api_base_url}">\n'
            html_content = html_content.replace("</head>", meta_tag + "</head>")
        
        return HTMLResponse(content=html_content)
    return HTMLResponse(content="<html><body>Frontend not found</body></html>", status_code=404)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
