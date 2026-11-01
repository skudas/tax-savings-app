#!/usr/bin/env python
"""Test if the app imports successfully."""

try:
    from app import app
    print("App imported successfully")
    routes = [r.path for r in app.routes if hasattr(r, 'path')]
    print(f"Total routes: {len(routes)}")
    for route in sorted(routes)[:20]:
        print(f"  {route}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
