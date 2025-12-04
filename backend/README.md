# Trinity Platform Backend

FastAPI backend with Auth0 authentication integration.

## Setup

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment:**
   - Windows: `venv\Scripts\activate`
   - Mac/Linux: `source venv/bin/activate`

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables:**
   - Copy `.env.example` to `.env`
   - Fill in your Auth0 credentials and database connection string

5. **Initialize the database:**
   ```bash
   alembic upgrade head
   ```

6. **Run the application:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

## Auth0 Configuration

### 1. Create Auth0 Application
- Go to [Auth0 Dashboard](https://manage.auth0.com/)
- Create a new "Regular Web Application"
- Note your Domain, Client ID, and Client Secret

### 2. Configure Callback URLs
Add these URLs in your Auth0 Application Settings:
- **Allowed Callback URLs:** `http://localhost:8000/api/auth/callback`
- **Allowed Logout URLs:** `http://localhost:8000, http://localhost:5173`
- **Allowed Web Origins:** `http://localhost:5173`

### 3. Enable Connections
- Go to Authentication > Database
- Enable Username-Password-Authentication or your preferred connection

## API Endpoints

### Authentication
- `GET /api/auth/login` - Redirect to Auth0 login
- `GET /api/auth/callback` - Auth0 callback handler
- `GET /api/auth/logout` - Logout user
- `GET /api/auth/user` - Get current user info

### Health Check
- `GET /health` - API health check

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application entry point
│   ├── config.py            # Configuration management
│   ├── database.py          # Database connection
│   ├── models/              # SQLAlchemy models
│   │   ├── __init__.py
│   │   └── user.py
│   ├── schemas/             # Pydantic schemas
│   │   ├── __init__.py
│   │   └── user.py
│   ├── api/                 # API routes
│   │   ├── __init__.py
│   │   └── auth.py
│   └── services/            # Business logic
│       ├── __init__.py
│       └── auth_service.py
├── alembic/                 # Database migrations
├── .env                     # Environment variables
├── .env.example             # Environment variables template
├── requirements.txt         # Python dependencies
└── README.md               # This file
```



