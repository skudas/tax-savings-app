#!/usr/bin/env python
"""List all routes in the app."""

from app import app

print("All API Routes:")
for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ','.join(sorted(route.methods - {'OPTIONS', 'HEAD'}))
        print(f"  {route.path:45} [{methods}]")

print("\nTotal routes:", len(app.routes))
