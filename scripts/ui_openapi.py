"""Full OpenAPI schema for the UI's generated types (ui: npm run gen:api).

The public schema (/openapi.json) lists only the documented routes; the UI
also calls internal ones (/loading, /render, ...), so its types come from
every route.
"""
import json
import sys

from fastapi.routing import APIRoute

from src_new.api.main import app

for route in app.routes:
    if isinstance(route, APIRoute):
        route.include_in_schema = True
app.openapi_schema = None
json.dump(app.openapi(), open(sys.argv[1], "w"), indent=1)
