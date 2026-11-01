"""
Tax Savings MVP Application

FastAPI backend for S-Corp savings estimation and bookkeeping.
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from database import init_db, SessionLocal
from routes import auth, onboarding, dashboard, admin, professionals, consultations, messages, payments, jobs, tax_forms

# Initialize database
init_db()

# Seed the IRS deduction rule catalog (idempotent).
with SessionLocal() as _db:
    tax_forms.seed_deduction_rules(_db)

# Create FastAPI app
app = FastAPI(title="Tax Savings MVP - Marketplace")

# Get the directory where this script is located
BASE_DIR = Path(__file__).parent

# Mount static files
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(onboarding.router, prefix="/api/onboarding", tags=["onboarding"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(professionals.router, prefix="/api/professionals", tags=["professionals"])
app.include_router(consultations.router, prefix="/api/consultations", tags=["consultations"])
app.include_router(messages.router, prefix="/api/messages", tags=["messages"])
app.include_router(payments.router, prefix="/api/payments", tags=["payments"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(tax_forms.router, prefix="/api/tax", tags=["tax"])


@app.get("/", response_class=HTMLResponse)
async def home():
    """Home page."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Tax Savings MVP</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; background: #f9fafb; }
            header { background: white; border-bottom: 1px solid #e5e7eb; padding: 1rem 0; position: sticky; top: 0; }
            .navbar { max-width: 1200px; margin: 0 auto; padding: 0 20px; display: flex; justify-content: space-between; align-items: center; }
            .logo { font-size: 1.5rem; font-weight: bold; color: #2563eb; text-decoration: none; }
            nav { display: flex; gap: 2rem; list-style: none; }
            nav a { color: #374151; text-decoration: none; transition: color 0.3s; }
            nav a:hover { color: #2563eb; }
            main { max-width: 1200px; margin: 0 auto; padding: 60px 20px; }
            .hero { text-align: center; margin-bottom: 60px; }
            .hero h1 { font-size: 2.5rem; margin-bottom: 1rem; color: #111827; }
            .hero p { font-size: 1.125rem; color: #6b7280; margin-bottom: 2rem; }
            .buttons { display: flex; gap: 1rem; justify-content: center; flex-wrap: wrap; }
            .btn { padding: 0.75rem 1.5rem; border: none; border-radius: 0.375rem; font-size: 1rem; cursor: pointer; text-decoration: none; display: inline-block; transition: all 0.3s; }
            .btn-primary { background-color: #2563eb; color: white; }
            .btn-primary:hover { background-color: #1d4ed8; transform: translateY(-2px); }
            .features { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 2rem; margin: 60px 0; }
            .feature { padding: 1.5rem; background: white; border-radius: 0.375rem; border: 1px solid #e5e7eb; }
            .feature h3 { margin-bottom: 0.5rem; color: #2563eb; }
            .feature p { color: #6b7280; }
            footer { background: #f3f4f6; padding: 2rem 0; margin-top: 60px; text-align: center; color: #6b7280; font-size: 0.875rem; }
        </style>
    </head>
    <body>
        <header>
            <div class="navbar">
                <a href="/" class="logo">💰 Tax Savings</a>
                <nav>
                    <a href="/auth/signup.html">Sign Up</a>
                    <a href="/auth/login.html">Log In</a>
                    <a href="/docs">API Docs</a>
                </nav>
            </div>
        </header>
        <main>
            <div class="hero">
                <h1>Save Money on Taxes with an S-Corporation</h1>
                <p>Estimate your potential annual tax savings and manage your business finances.</p>
                <div class="buttons">
                    <a href="/onboarding/questionnaire.html" class="btn btn-primary">Get Started</a>
                    <a href="/docs" class="btn" style="background-color: #10b981; color: white;">API Documentation</a>
                </div>
            </div>
            <div class="features">
                <div class="feature">
                    <h3>📊 S-Corp Savings Calculator</h3>
                    <p>Get an instant estimate of your potential tax savings by converting to an S-Corporation.</p>
                </div>
                <div class="feature">
                    <h3>📈 Track Transactions</h3>
                    <p>Upload bank transactions, categorize expenses, and see your monthly income and expense summary.</p>
                </div>
                <div class="feature">
                    <h3>🔒 Secure & Private</h3>
                    <p>Your financial data is encrypted at rest. We never store full bank account numbers.</p>
                </div>
            </div>
        </main>
        <footer>
            <p><strong>⚠️ Disclaimer:</strong> This tool provides estimates only and does not constitute tax advice. Consult with a qualified tax professional.</p>
            <p>&copy; 2024 Tax Savings MVP. For demonstration purposes only.</p>
        </footer>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# Serve HTML pages
@app.get("/auth/signup.html", response_class=HTMLResponse)
async def signup_page():
    try:
        with open(BASE_DIR / "templates" / "auth" / "signup.html") as f:
            return f.read()
    except:
        return "<h1>Sign Up Page</h1>"

@app.get("/auth/login.html", response_class=HTMLResponse)
async def login_page():
    try:
        with open(BASE_DIR / "templates" / "auth" / "login.html") as f:
            return f.read()
    except:
        return "<h1>Log In Page</h1>"

@app.get("/onboarding/questionnaire.html", response_class=HTMLResponse)
async def onboarding_page():
    try:
        with open(BASE_DIR / "templates" / "onboarding" / "questionnaire.html") as f:
            return f.read()
    except Exception as e:
        return f"<h1>S-Corp Calculator</h1><p>Error: {e}</p>"

@app.get("/dashboard/index.html", response_class=HTMLResponse)
async def dashboard_page():
    try:
        with open(BASE_DIR / "templates" / "dashboard" / "index.html") as f:
            return f.read()
    except:
        return "<h1>Dashboard</h1>"


def read_page(relative_path: str) -> str:
    """Read a static HTML template, raising a 404 when it is missing."""
    path = BASE_DIR / relative_path
    if not path.exists():
        raise HTTPException(status_code=404, detail="Page not found")
    return path.read_text(encoding="utf-8")


@app.get("/marketplace/browse.html", response_class=HTMLResponse)
async def marketplace_browse_page():
    return read_page("templates/marketplace/browse.html")


@app.get("/marketplace/profile.html", response_class=HTMLResponse)
async def marketplace_profile_page():
    return read_page("templates/marketplace/profile.html")


@app.get("/marketplace/book.html", response_class=HTMLResponse)
async def marketplace_book_page():
    return read_page("templates/marketplace/book.html")


@app.get("/dashboard/client.html", response_class=HTMLResponse)
async def client_dashboard_page():
    return read_page("templates/dashboard/client.html")


@app.get("/dashboard/professional.html", response_class=HTMLResponse)
async def professional_dashboard_page():
    return read_page("templates/dashboard/professional.html")


@app.get("/jobs/browse.html", response_class=HTMLResponse)
async def jobs_browse_page():
    return read_page("templates/jobs/browse.html")


@app.get("/jobs/detail.html", response_class=HTMLResponse)
async def jobs_detail_page():
    return read_page("templates/jobs/detail.html")


@app.get("/jobs/post.html", response_class=HTMLResponse)
async def jobs_post_page():
    return read_page("templates/jobs/post.html")


@app.get("/jobs/my-listings.html", response_class=HTMLResponse)
async def jobs_my_listings_page():
    return read_page("templates/jobs/my-listings.html")


@app.get("/messages.html", response_class=HTMLResponse)
async def messages_page():
    return read_page("templates/messages.html")


@app.get("/messages")
async def messages_redirect():
    return RedirectResponse(url="/messages.html")


@app.get("/jobs/browse.html", response_class=HTMLResponse)
async def jobs_browse_page():
    return read_page("templates/jobs/browse.html")


@app.get("/jobs/detail.html", response_class=HTMLResponse)
async def jobs_detail_page():
    return read_page("templates/jobs/detail.html")


@app.get("/jobs/post.html", response_class=HTMLResponse)
async def jobs_post_page():
    return read_page("templates/jobs/post.html")


@app.get("/jobs/my-listings.html", response_class=HTMLResponse)
async def jobs_my_listings_page():
    return read_page("templates/jobs/my-listings.html")


@app.get("/jobs/browse")
async def jobs_browse_redirect():
    return RedirectResponse(url="/jobs/browse.html")


@app.get("/jobs/detail")
async def jobs_detail_redirect():
    return RedirectResponse(url="/jobs/detail.html")


@app.get("/jobs/post")
async def jobs_post_redirect():
    return RedirectResponse(url="/jobs/post.html")


@app.get("/jobs/my-listings")
async def jobs_my_listings_redirect():
    return RedirectResponse(url="/jobs/my-listings.html")


# Tax filing & optimization pages
@app.get("/tax/dashboard.html", response_class=HTMLResponse)
async def tax_dashboard_page():
    return read_page("templates/tax/dashboard.html")


@app.get("/tax/deduction-questionnaire.html", response_class=HTMLResponse)
async def tax_questionnaire_page():
    return read_page("templates/tax/deduction-questionnaire.html")


@app.get("/tax/forms-viewer.html", response_class=HTMLResponse)
async def tax_forms_viewer_page():
    return read_page("templates/tax/forms-viewer.html")


@app.get("/tax/entity-comparison.html", response_class=HTMLResponse)
async def tax_entity_comparison_page():
    return read_page("templates/tax/entity-comparison.html")


@app.get("/tax/estimated-taxes.html", response_class=HTMLResponse)
async def tax_estimated_taxes_page():
    return read_page("templates/tax/estimated-taxes.html")


@app.get("/tax/audit-docs.html", response_class=HTMLResponse)
async def tax_audit_docs_page():
    return read_page("templates/tax/audit-docs.html")


@app.get("/tax")
async def tax_redirect():
    return RedirectResponse(url="/tax/dashboard.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", 8000)),
        reload=os.getenv("ENV", "dev") == "dev"
    )
