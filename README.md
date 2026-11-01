# Tax Savings MVP

A web application for self-employed people and small business owners to estimate their potential annual tax savings by converting to an S-Corporation, plus basic bookkeeping features.

## ⚠️ Important Disclaimer

**This application provides estimates only and does NOT constitute tax advice.** The calculations are based on federal self-employment tax rates and general business tax principles, but tax situations vary widely based on:

- Individual circumstances and income level
- State-specific tax considerations  
- Industry-specific rules and regulations
- Recent changes in tax law
- Timing and structuring of distributions
- Reasonable salary IRS requirements

**Always consult with a qualified tax professional or CPA before making any business decisions** based on these estimates.

## Features

### 1. **S-Corp Savings Calculator**
Onboarding questionnaire that estimates annual tax savings from converting to an S-Corporation:
- Takes user inputs: annual net profit, current entity type, state, payroll provider status
- Returns estimated annual savings range with transparent assumptions
- Tax formulas clearly documented for CPA review

### 2. **Member Accounts**
Secure user registration and authentication:
- Sign up with email and password
- Password hashing with bcrypt
- Secure session cookies (24-hour expiration)
- No third-party authentication required for MVP

### 3. **Transaction Bookkeeping**
Manual CSV upload and management:
- Import bank transactions from CSV
- Auto-categorization with keyword matching
- Manual category editing
- Monthly income/expense summary
- Encrypted storage of bank account last 4 digits (never full numbers)

### 4. **Admin Dashboard**
View member information and onboarding results:
- List all members and their sign-up dates
- View each member's savings estimates
- Dashboard overview of total users and results

### 5. **Audit Log**
Every transaction category change is logged:
- Records user, entity, action, old/new values
- Timestamp for all changes
- Helps with compliance and debugging

### 6. **Data Security**
- Passwords hashed with bcrypt
- Sensitive fields encrypted at rest (Fernet symmetric encryption)
- Never stores full bank account numbers
- SQLite for development (easy setup), PostgreSQL ready for production

## Tech Stack

- **Backend:** Python with FastAPI
- **Database:** SQLite (development) / PostgreSQL (production)
- **Frontend:** Server-rendered HTML with Jinja2, minimal JavaScript
- **Encryption:** cryptography library (Fernet)
- **Password Hashing:** bcrypt via passlib
- **Testing:** pytest with 38+ unit tests
- **Containerization:** Docker & Docker Compose

## Local Setup

### Prerequisites
- Python 3.10+
- pip

### 1. Clone and Install

```bash
cd tax-savings-app
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Generate Encryption Key

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Create .env File

```bash
cp .env.example .env
```

Edit `.env` and paste your encryption key:
```
ENCRYPTION_KEY=your-generated-key-here
DATABASE_URL=sqlite:///./tax_savings.db
ENV=dev
PORT=8000
```

### 4. Run the Application

```bash
cd backend
python -m uvicorn app:app --reload
```

Visit http://localhost:8000

### 5. Run Tests

```bash
cd backend

# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_tax_calculator.py -v

# Run with coverage
python -m pytest tests/ --cov=. --cov-report=html
```

## Running with Docker

### Option 1: SQLite (Quick Start)

```bash
docker build -t tax-savings:latest .
docker run -p 8000:8000 -e ENCRYPTION_KEY="your-key-here" tax-savings:latest
```

### Option 2: Docker Compose (With PostgreSQL)

```bash
# Generate encryption key first
export ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Start services
docker-compose up

# Run migrations (if needed)
docker-compose exec app python database.py
```

## Project Structure

```
tax-savings-app/
├── backend/
│   ├── app.py                          # FastAPI application
│   ├── models.py                       # SQLAlchemy ORM models
│   ├── schemas.py                      # Pydantic request/response schemas
│   ├── database.py                     # Database setup
│   ├── auth.py                         # Password hashing, sessions
│   ├── encryption.py                   # Encryption/decryption utilities
│   ├── tax_calculator.py               # ⭐ Tax formulas (CPA-reviewable)
│   ├── transaction_categorizer.py      # Transaction categorization logic
│   ├── routes/
│   │   ├── auth.py                     # Signup, login, logout
│   │   ├── onboarding.py               # Questionnaire and results
│   │   ├── dashboard.py                # Transactions and summary
│   │   └── admin.py                    # Member list and results
│   ├── templates/                      # Jinja2 HTML templates
│   ├── static/
│   │   ├── css/style.css              # Application CSS
│   │   └── js/main.js                 # Frontend JavaScript
│   ├── tests/
│   │   ├── test_tax_calculator.py     # 20 unit tests
│   │   └── test_categorizer.py        # 18 unit tests
│   └── __init__.py
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Tax Formula Details

The tax calculations are in `backend/tax_calculator.py` with complete transparency:

### Self-Employment Tax Calculation

**Sole Proprietor/LLC:**
```
SE Tax = (Net Profit × 0.9235) × 0.153
```

**S-Corporation:**
```
SE Tax = (W-2 Salary × 0.9235) × 0.153
Savings = (Net Profit - W-2 Salary) × 0.1413
```

### Key Assumptions (Documented in Code)

1. **Federal SE Tax Rate:** 15.3% (12.4% Social Security + 2.9% Medicare)
2. **SE Tax Base:** 92.35% of net profit (accounts for SE tax deduction)
3. **Reasonable Salary:** 50-70% of net profit (conservative: 60%)
4. **Annual S-Corp Costs:**
   - State/federal filing: $300
   - Accounting complexity: $1,500
   - Payroll processing (if needed): $600
   - **Total: ~$2,400/year**
5. **Scope:** Federal SE tax only; excludes state-specific considerations
6. **Limitations:**
   - Doesn't include 20% QBI deduction
   - Doesn't factor in state taxes
   - Doesn't cover industry-specific rules
   - Subject to IRS "reasonable salary" requirements

## Testing

The application includes comprehensive unit tests:

### Tax Calculator Tests (20 tests)
- Self-employment tax calculations
- Reasonable salary estimation
- Savings calculations
- Edge cases (low profit, high profit, already S-Corp)
- Assumptions transparency

### Transaction Categorizer Tests (18 tests)
- Keyword matching for expenses and income
- Confidence scoring
- Custom category support
- Amount-based type inference

### Run Tests

```bash
cd backend
python -m pytest tests/ -v

# Generate coverage report
python -m pytest tests/ --cov --cov-report=html
```

## API Endpoints

### Authentication
- `POST /api/auth/signup` - Register new user
- `POST /api/auth/login` - Log in user
- `POST /api/auth/logout` - Log out user
- `GET /api/auth/me` - Get current user

### Onboarding
- `POST /api/onboarding/questionnaire` - Submit questionnaire and get savings estimate
- `GET /api/onboarding/results` - Get all onboarding results
- `GET /api/onboarding/results/{id}` - Get specific result

### Dashboard
- `GET /api/dashboard/categories` - Get transaction categories
- `POST /api/dashboard/transactions/upload` - Upload CSV transactions
- `GET /api/dashboard/transactions` - Get all transactions
- `PATCH /api/dashboard/transactions/{id}` - Update transaction category
- `GET /api/dashboard/summary` - Get monthly summary

### Admin
- `GET /api/admin/members` - List all members
- `GET /api/admin/members/{id}/results` - Get member's results
- `GET /api/admin/dashboard` - Admin dashboard summary

## Database Models

- **User** - Member accounts with hashed passwords
- **OnboardingResult** - S-Corp savings estimates with assumptions
- **Transaction** - Bank transactions (encrypted account numbers)
- **Category** - Customizable transaction categories per user
- **AuditLog** - Audit trail of transaction changes

## Security Considerations

✅ **Implemented:**
- Bcrypt password hashing (not stored in plain text)
- Secure session cookies with httponly flag
- SQL parameterization to prevent injection
- Fernet symmetric encryption for sensitive fields
- Never store full bank account numbers
- CSRF protection via secure cookies

⚠️ **For Production:**
- Enable HTTPS and set secure=True on cookies
- Use Redis instead of in-memory session storage
- Implement proper rate limiting
- Add email verification for signups
- Implement proper admin authentication/authorization
- Set strong `ENCRYPTION_KEY` from secure source
- Use PostgreSQL instead of SQLite
- Enable proper CORS configuration
- Add request logging and monitoring

## Future Enhancements

- Integration with accounting software (QuickBooks, Wave)
- State-specific tax considerations
- Real-time transaction syncing from bank APIs
- Export functionality (PDF, Excel reports)
- More sophisticated categorization (ML-based)
- Estimated quarterly tax payment calculator
- Tax deadline reminders
- Professional CPA consultation booking

## Contributing

Tests must pass before any changes:
```bash
python -m pytest tests/ -v
```

## License

For demonstration and educational purposes only.

## Support

This is an MVP built for learning purposes. For actual tax advice, please consult a qualified CPA or tax professional.
