# Deployment Guide: Supabase + Vercel

## Prerequisites
- GitHub account (for Vercel integration)
- Supabase account (https://supabase.com)
- Stripe account (for payments)
- Vercel account (https://vercel.com)

---

## Step 1: Set Up Supabase PostgreSQL Database

### 1.1 Create Supabase Project
1. Go to https://supabase.com
2. Click "New Project"
3. Set name: `tax-savings-marketplace`
4. Choose region closest to users
5. Set strong database password
6. Click "Create new project" (wait 2-3 minutes)

### 1.2 Get Connection String
1. In Supabase dashboard, click "Settings" → "Database"
2. Copy "Connection string" (the one with `postgresql://`)
3. It looks like: `postgresql://postgres:[PASSWORD]@[HOST]/postgres`
4. Replace `[PASSWORD]` with your actual password if prompted
5. **IMPORTANT:** Use the "Connection pooler" string for Vercel (transaction mode)

### 1.3 Enable Extensions
1. In Supabase, go to "SQL Editor"
2. Create new query with:
```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
```
3. Execute

### 1.4 Create Tables (Automatic)
The app will auto-create all tables on first deploy via `init_db()`

---

## Step 2: Prepare GitHub Repository

### 2.1 Push Code to GitHub
```bash
cd tax-savings-app
git init
git add .
git commit -m "Initial commit: Tax savings marketplace with TurboTax features"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/tax-savings-app.git
git push -u origin main
```

### 2.2 Create `.env.local` for Testing
```bash
# Copy .env.example to .env.local
cp backend/.env.example backend/.env.local

# Edit backend/.env.local with local values:
DATABASE_URL=postgresql://user:password@localhost/postgres  # For local testing
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_test_...
ENV=dev
```

**DO NOT commit `.env` files to git!**

---

## Step 3: Deploy Backend to Vercel

### 3.1 Connect GitHub to Vercel
1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Connect GitHub account
4. Select `tax-savings-app` repo
5. Choose "Other" as framework
6. Configure:
   - **Root Directory:** `backend`
   - **Build Command:** `pip install -r requirements.txt`
   - **Output Directory:** `.`
   - **Install Command:** `pip install -r requirements.txt`

### 3.2 Add Environment Variables
In Vercel project settings → "Environment Variables", add:

```
DATABASE_URL = postgresql://postgres:[PASSWORD]@[HOST]/postgres?sslmode=require
STRIPE_SECRET_KEY = sk_live_xxxxx
STRIPE_PUBLISHABLE_KEY = pk_live_xxxxx
STRIPE_WEBHOOK_SECRET = whsec_live_xxxxx
ENV = production
```

**To get Supabase connection string:**
- Supabase dashboard → Settings → Database → "Connection pooler"
- Use "Transaction" mode for serverless
- Copy the full string

### 3.3 Deploy
1. Click "Deploy"
2. Wait for build to complete
3. Backend URL will be: `https://your-project.vercel.app`
4. API endpoint: `https://your-project.vercel.app/api/...`

---

## Step 4: Deploy Frontend (Static Files)

### 4.1 Configure Static Files
Frontend files are served from `backend/templates/` and `backend/static/`

Vercel will automatically serve HTML files from the main `/` route

### 4.2 Update Frontend API URLs
In all HTML files, change API endpoints from `http://127.0.0.1:8000` to your Vercel URL:

```javascript
// OLD (local)
const API_URL = "http://127.0.0.1:8000";

// NEW (production)
const API_URL = "https://your-project.vercel.app";
```

Or use environment variables in JavaScript:
```javascript
const API_URL = window.location.origin;  // Auto-detects production vs local
```

---

## Step 5: Configure Stripe for Production

### 5.1 Webhook in Vercel
1. Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://your-project.vercel.app/api/payments/webhook`
3. Select events:
   - `payment_intent.succeeded`
   - `customer.subscription.updated`
4. Copy signing secret to Vercel env vars as `STRIPE_WEBHOOK_SECRET`

### 5.2 Test Webhook
```bash
curl -X POST https://your-project.vercel.app/api/payments/webhook \
  -H "Content-Type: application/json" \
  -H "stripe-signature: SIGNATURE" \
  -d '{"type":"payment_intent.succeeded"}'
```

---

## Step 6: Database Migration (First Deploy)

### 6.1 Initialize Database Tables
The app auto-creates tables on first startup via `init_db()` in `app.py`

### 6.2 Verify Tables Created
```bash
# Connect to Supabase with psql:
psql "postgresql://postgres:[PASSWORD]@[HOST]/postgres"

# List tables:
\dt

# Should show: users, professional_profiles, consultations, jobs, etc.
```

### 6.3 Migrate Data (If Moving from SQLite)
```bash
# Export data from local SQLite:
sqlite3 tax_savings.db ".dump" > backup.sql

# Import to Supabase:
# (Use Supabase SQL Editor or psql)
```

---

## Step 7: Domain & SSL

### 7.1 Custom Domain (Optional)
1. Vercel dashboard → Settings → Domains
2. Add your domain (e.g., `taxsavings.com`)
3. Update DNS records as shown
4. SSL certificate auto-generated

### 7.2 Update API URLs
```javascript
// Update to use custom domain
const API_URL = "https://taxsavings.com";
```

---

## Step 8: Monitoring & Logs

### 8.1 View Vercel Logs
```bash
# Install Vercel CLI
npm i -g vercel

# Login
vercel login

# View logs in real-time
vercel logs
```

### 8.2 Database Logs
Supabase dashboard → Logs → Database

### 8.3 Error Tracking
Add Sentry (optional):
```python
import sentry_sdk
sentry_sdk.init("your-sentry-dsn", traces_sample_rate=1.0)
```

---

## Cost Breakdown (Monthly)

| Service | Free/Paid | Cost |
|---------|-----------|------|
| Vercel (API + Frontend) | Free Tier | $0 |
| Supabase PostgreSQL | Free Tier (up to 500MB) | $0-10 |
| Stripe Processing | Variable | 2.9% + $0.30 |
| **Total** | | **$0-10** |

Upgrade to Vercel Pro ($20/month) when you exceed free tier limits.

---

## Troubleshooting

### Database Connection Failed
```
Error: could not connect to server
```
- Check DATABASE_URL in Vercel env vars
- Ensure Supabase connection pooler mode = "Transaction"
- Add `?sslmode=require` to connection string

### 502 Bad Gateway
- Check Vercel function logs
- Verify all environment variables set
- Check models.py for import errors

### Stripe Webhook Not Firing
- Verify endpoint URL in Stripe dashboard
- Check signing secret in env vars
- View logs: Stripe → Developers → Webhooks → Logs

### Tables Not Created
- Run: `curl https://your-domain.com/health`
- This triggers `init_db()` on first request
- Check Supabase SQL Editor for tables

---

## Security Checklist

- [ ] Never commit `.env` files to git
- [ ] Use separate Stripe keys for dev/prod
- [ ] Enable Supabase SSL connections
- [ ] Set strong database password (30+ chars)
- [ ] Enable 2FA on Vercel & Supabase accounts
- [ ] Use environment variables for all secrets
- [ ] Enable CORS restrictions in production
- [ ] Set up database backups (Supabase auto-backs up)

---

## Production Optimization

### 1. Database Connection Pooling
Already configured via Supabase "Connection pooler"

### 2. Cache Headers
Add to `app.py`:
```python
@app.get("/")
async def home():
    response = Response(...)
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response
```

### 3. Compression
Vercel automatically enables gzip compression

### 4. Database Indexes
Already created by models.py (see `index=True` in model columns)

---

## Next Steps

1. ✅ Create Supabase project
2. ✅ Push code to GitHub
3. ✅ Deploy to Vercel
4. ✅ Add environment variables
5. ✅ Test API endpoints
6. ✅ Configure Stripe webhooks
7. ✅ Set up custom domain (optional)
8. ✅ Monitor logs & metrics

**Estimated time:** 30-45 minutes

**Questions?** Check Vercel & Supabase docs or GitHub Issues
