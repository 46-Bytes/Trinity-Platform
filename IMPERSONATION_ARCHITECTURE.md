# Impersonation Feature - Complete End-to-End Architecture

This document explains the complete end-to-end flow of the impersonation feature, detailing what each file does and when it's used.

## 📋 Table of Contents
1. [Overview](#overview)
2. [Database Layer](#database-layer)
3. [Backend API Layer](#backend-api-layer)
4. [Authentication & Authorization Layer](#authentication--authorization-layer)
5. [Frontend Layer](#frontend-layer)
6. [Complete Flow Diagrams](#complete-flow-diagrams)

---

## Overview

The impersonation feature allows a **SUPER_ADMIN** user to temporarily act as another user, with full access to the system as that impersonated user. The system maintains audit logs and tracks active impersonation sessions.

### Key Components:
- **Database Model**: Tracks impersonation sessions
- **Backend Endpoints**: Start/stop impersonation, check status
- **JWT Token Handling**: Special tokens with impersonation claims
- **Frontend Context**: Manages impersonation state
- **UI Components**: Banner to show impersonation status

---

## Database Layer

### File: `backend/app/models/impersonation.py`

**Purpose**: Defines the database model for tracking impersonation sessions.

**What it does**:
- Creates `ImpersonationSession` table with:
  - `id`: Unique session identifier (UUID)
  - `original_user_id`: The superadmin who started impersonation
  - `impersonated_user_id`: The user being impersonated
  - `status`: 'active' or 'ended'
  - `created_at`: When impersonation started
  - `ended_at`: When impersonation ended (nullable)
- Establishes foreign key relationships to `User` table
- Creates indexes for efficient queries

**When it's used**:
- When creating a new impersonation session
- When checking if a session is still active
- When ending an impersonation session
- For audit logging and reporting

**Key Code Structure**:
```python
class ImpersonationSession(Base):
    __tablename__ = "impersonation_sessions"
    id = Column(UUID, primary_key=True)
    original_user_id = Column(UUID, ForeignKey("users.id"))
    impersonated_user_id = Column(UUID, ForeignKey("users.id"))
    status = Column(String(20), default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
```

---

### File: `backend/app/models/__init__.py`

**Purpose**: Exports the `ImpersonationSession` model so it's available throughout the application.

**What it does**:
- Imports `ImpersonationSession` from `impersonation.py`
- Adds it to `__all__` list for proper module exports
- Ensures Alembic can discover the model for migrations

**When it's used**:
- During application startup (model registration)
- When Alembic generates migrations
- When importing models in other files

---

### File: `backend/alembic/versions/XXXXX_add_impersonation_sessions.py`

**Purpose**: Database migration to create the `impersonation_sessions` table.

**What it does**:
- `upgrade()`: Creates the table with all columns, foreign keys, and indexes
- `downgrade()`: Drops the table if migration needs to be rolled back

**When it's used**:
- When running `alembic upgrade head` to apply the migration
- When rolling back with `alembic downgrade -1`

---

## Backend API Layer

### File: `backend/app/api/users.py`

**Purpose**: Contains the endpoint to **start** impersonation.

**Endpoint**: `POST /api/users/{user_id}/impersonate`

**What it does**:
1. **Authorization Check**: Verifies current user is `SUPER_ADMIN`
2. **Validation**:
   - Target user exists and is active
   - Target user is not a superadmin
   - Target user is not the same as current user
3. **Session Creation**: Creates an `ImpersonationSession` record with status 'active'
4. **Token Generation**: Creates a new JWT token with special claims:
   ```json
   {
     "sub": "<impersonated_user_id>",
     "original_user_id": "<superadmin_id>",
     "is_impersonation": true,
     "impersonation_session_id": "<session_id>",
     "email": "<impersonated_user_email>",
     "role": "<impersonated_user_role>",
     "exp": <expiry_timestamp>
   }
   ```
5. **Audit Logging**: Logs the impersonation start event
6. **Response**: Returns the new token, impersonated user data, and original user data

**When it's used**:
- When a superadmin clicks "Impersonate" button in the frontend
- Frontend calls this endpoint with the target user's ID

**Key Code Flow**:
```python
@router.post("/{user_id}/impersonate")
async def impersonate_user(user_id: UUID, ...):
    # 1. Check role
    if current_user.role != UserRole.SUPER_ADMIN:
        raise HTTPException(403, "Only super_admin can impersonate")
    
    # 2. Validate target user
    target_user = db.query(User).filter(User.id == user_id).first()
    # ... validation checks ...
    
    # 3. Create session
    session = ImpersonationSession(
        original_user_id=current_user.id,
        impersonated_user_id=target_user.id,
        status='active'
    )
    db.add(session)
    db.commit()
    
    # 4. Generate token
    token = jwt.encode({
        "sub": str(target_user.id),
        "is_impersonation": True,
        # ... other claims
    }, SECRET_KEY)
    
    # 5. Log event
    AuditService.log_impersonation_start(...)
    
    # 6. Return response
    return {"access_token": token, "user": ..., "original_user": ...}
```

---

### File: `backend/app/api/auth.py`

**Purpose**: Contains endpoints to **stop** impersonation and **check** impersonation status.

#### Endpoint 1: `POST /api/auth/stop-impersonation`

**What it does**:
1. **Token Decoding**: Extracts `is_impersonation`, `original_user_id`, `impersonation_session_id` from current token
2. **Validation**: Verifies the session exists and is active
3. **Session Update**: Marks the session as 'ended' and sets `ended_at` timestamp
4. **Token Generation**: Creates a new normal JWT token for the original superadmin:
   ```json
   {
     "sub": "<original_user_id>",
     "email": "<original_user_email>",
     "role": "super_admin",
     "exp": <expiry_timestamp>
   }
   ```
5. **Audit Logging**: Logs the impersonation end event
6. **Response**: Returns the new token and original user data

**When it's used**:
- When user clicks "Stop Impersonation" button in the frontend banner
- Frontend calls this endpoint to end the session

#### Endpoint 2: `GET /api/auth/impersonation-status`

**What it does**:
1. **Token Decoding**: Checks if current token has `is_impersonation` flag
2. **Session Validation**: Verifies session is still active
3. **Response**: Returns impersonation status and user details:
   ```json
   {
     "is_impersonating": true,
     "impersonated_user": {...},
     "original_user": {...},
     "impersonation_session_id": "..."
   }
   ```

**When it's used**:
- On frontend app load to check if user is already impersonating
- Called by `AuthContext.loadCurrentUser()` to restore impersonation state

#### Endpoint 3: `GET /api/auth/user` (Modified)

**What it does**:
- **Enhanced** to handle impersonation tokens
- If token has `is_impersonation: true`, returns the impersonated user
- Otherwise, returns the normal authenticated user

**When it's used**:
- On every page load to get current user info
- Used by frontend to determine what to display

---

## Authentication & Authorization Layer

### File: `backend/app/utils/auth.py`

**Purpose**: Core authentication dependency that extracts user from JWT tokens.

**Function**: `get_current_user(request, db)`

**What it does**:
1. **Token Extraction**: Gets token from `Authorization: Bearer <token>` header
2. **Token Decoding**: 
   - Tries to decode with `SECRET_KEY` (for email/password and impersonation tokens)
   - Falls back to unverified decode (for Auth0 tokens)
3. **Impersonation Detection**: Checks for `is_impersonation` flag in token payload
4. **Session Validation**: If impersonating, verifies the session is still active:
   ```python
   if is_impersonation:
       session = db.query(ImpersonationSession).filter(
           ImpersonationSession.id == session_id,
           ImpersonationSession.status == 'active'
       ).first()
       if not session:
           raise HTTPException(401, "Impersonation session has ended")
   ```
5. **User Retrieval**: 
   - If impersonating: Returns the **impersonated user** (from `sub` claim)
   - If not: Returns the **normal authenticated user**
6. **State Storage**: Stores `original_user_id` in `request.state` for audit logging

**When it's used**:
- **Every API request** that requires authentication
- Used as a FastAPI dependency: `current_user: User = Depends(get_current_user)`
- Ensures all endpoints automatically work with impersonation

**Key Code Flow**:
```python
def get_current_user(request: Request, db: Session) -> User:
    token = extract_token_from_header(request)
    payload = decode_token(token)
    
    is_impersonation = payload.get('is_impersonation', False)
    
    if is_impersonation:
        # Validate session
        session = verify_session_active(payload['impersonation_session_id'])
        # Return impersonated user
        user_id = payload['sub']  # This is impersonated user ID
        return db.query(User).filter(User.id == user_id).first()
    else:
        # Normal authentication
        return get_normal_user(payload, db)
```

---

### File: `backend/app/services/role_check.py`

**Purpose**: Alternative authentication function used by some endpoints.

**Function**: `get_current_user_from_token(request, db)`

**What it does**:
- **Same logic as `get_current_user`** but used by endpoints that need token-based auth
- Also handles impersonation tokens
- Used by endpoints like chat, files, etc.

**When it's used**:
- By endpoints that explicitly use `Depends(get_current_user_from_token)`
- Ensures consistency across all authentication methods

---

### File: `backend/app/services/audit_service.py`

**Purpose**: Logs impersonation events for security and compliance.

**Functions**:
- `log_impersonation_start()`: Logs when impersonation begins
- `log_impersonation_end()`: Logs when impersonation ends
- `log_impersonation_action()`: Logs specific actions during impersonation

**What it does**:
- Writes structured log entries with:
  - Session ID
  - Original user ID
  - Impersonated user ID
  - Timestamp
  - Action details

**When it's used**:
- Called by `POST /api/users/{user_id}/impersonate` on start
- Called by `POST /api/auth/stop-impersonation` on end
- Can be called for important actions during impersonation

---

## Frontend Layer

### File: `frontend/src/context/AuthContext.tsx`

**Purpose**: Manages authentication state and impersonation state in React.

**State Variables**:
- `isImpersonating`: Boolean flag indicating if currently impersonating
- `originalUser`: The superadmin user who started impersonation
- `user`: The current user (impersonated user if impersonating)

**Functions**:

#### `startImpersonation(userId: string)`
**What it does**:
1. Calls `POST /api/users/{userId}/impersonate`
2. Stores the new impersonation token in `localStorage`
3. Updates state: `isImpersonating = true`, `user = impersonatedUser`, `originalUser = superadmin`
4. Redirects to `/dashboard` (impersonated user's dashboard)

**When it's used**:
- When superadmin clicks "Impersonate" button in UsersPage

#### `stopImpersonation()`
**What it does**:
1. Calls `POST /api/auth/stop-impersonation`
2. Stores the new normal token in `localStorage`
3. Updates state: `isImpersonating = false`, `user = originalUser`, `originalUser = null`
4. Redirects:
   - If original user was superadmin → `/dashboard/users`
   - Otherwise → `/dashboard`

**When it's used**:
- When user clicks "Stop Impersonation" button in ImpersonationBanner

#### `loadCurrentUser()`
**What it does**:
1. First calls `GET /api/auth/impersonation-status` to check if already impersonating
2. If impersonating, restores state from the response
3. Otherwise, calls `GET /api/auth/user` for normal user
4. Updates state accordingly

**When it's used**:
- On app initialization (useEffect)
- When page refreshes
- When token is restored from localStorage

**Key Code Structure**:
```typescript
interface AuthContextType {
  user: User | null;
  isAuthenticated: boolean;
  isImpersonating: boolean;
  originalUser: User | null;
  startImpersonation: (userId: string) => Promise<void>;
  stopImpersonation: () => Promise<void>;
  // ... other methods
}
```

---

### File: `frontend/src/components/ImpersonationBanner.tsx`

**Purpose**: UI component that displays impersonation status.

**What it does**:
- Renders a yellow banner at the top of the page when `isImpersonating === true`
- Shows:
  - Impersonated user's name and email
  - Original superadmin's name and email
  - "Stop Impersonation" button
- Calls `stopImpersonation()` when button is clicked

**When it's used**:
- Included in `DashboardLayout.tsx` so it appears on all dashboard pages
- Only visible when `isImpersonating === true`

**Key Code Structure**:
```typescript
export function ImpersonationBanner() {
  const { isImpersonating, user, originalUser, stopImpersonation } = useAuth();
  
  if (!isImpersonating) return null;
  
  return (
    <div className="bg-yellow-50 border-b">
      <p>You are impersonating {user.name}</p>
      <p>Original account: {originalUser.name}</p>
      <Button onClick={stopImpersonation}>Stop Impersonation</Button>
    </div>
  );
}
```

---

### File: `frontend/src/components/layout/DashboardLayout.tsx`

**Purpose**: Main layout component for dashboard pages.

**What it does**:
- Renders the `ImpersonationBanner` component
- Ensures banner appears on all dashboard pages

**When it's used**:
- Wraps all dashboard routes in the app
- Provides consistent layout with sidebar, topbar, and impersonation banner

---

### File: `frontend/src/pages/dashboard/users/UsersPage.tsx`

**Purpose**: Page where superadmin can view and manage users.

**What it does**:
- Displays list of all users
- Shows "Impersonate" button in dropdown menu for each user (only for superadmin)
- Calls `startImpersonation(userId)` when button is clicked

**When it's used**:
- Superadmin navigates to `/dashboard/users`
- Clicks "Impersonate" on a user
- Automatically redirects to impersonated user's dashboard

**Key Code Structure**:
```typescript
{user?.role === 'super_admin' && !isImpersonating && u.role !== 'super_admin' && (
  <DropdownMenuItem onClick={() => startImpersonation(u.id)}>
    <UserCog className="w-4 h-4 mr-2" />
    Impersonate
  </DropdownMenuItem>
)}
```

---

## Complete Flow Diagrams

### Flow 1: Starting Impersonation

```
┌─────────────────┐
│  Superadmin     │
│  on UsersPage   │
│  clicks         │
│  "Impersonate"  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  UsersPage.tsx                       │
│  startImpersonation(userId)         │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  AuthContext.tsx                     │
│  POST /api/users/{userId}/impersonate│
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  backend/app/api/users.py            │
│  @router.post("/{user_id}/impersonate")│
│  1. Verify SUPER_ADMIN role          │
│  2. Validate target user             │
│  3. Create ImpersonationSession      │
│  4. Generate impersonation JWT        │
│  5. Log audit event                   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Response: {                        │
│    access_token: "<impersonation_jwt>",│
│    user: {...impersonated_user...}, │
│    original_user: {...superadmin...}│
│  }                                  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  AuthContext.tsx                    │
│  1. Store token in localStorage     │
│  2. Update state:                   │
│     - isImpersonating = true        │
│     - user = impersonatedUser       │
│     - originalUser = superadmin     │
│  3. Redirect to /dashboard          │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Dashboard (impersonated user view) │
│  - Sidebar shows impersonated role   │
│  - Dashboard shows impersonated data │
│  - Banner shows impersonation status │
└─────────────────────────────────────┘
```

---

### Flow 2: Making API Requests While Impersonating

```
┌─────────────────────────────────────┐
│  Frontend Component                  │
│  Makes API request                   │
│  Authorization: Bearer <token>      │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  backend/app/utils/auth.py          │
│  get_current_user(request, db)      │
│  1. Extract token from header       │
│  2. Decode token                     │
│  3. Check is_impersonation flag      │
│  4. If true:                         │
│     - Verify session is active       │
│     - Extract impersonated_user_id   │
│     - Return impersonated user       │
│  5. If false:                        │
│     - Return normal user             │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  API Endpoint                        │
│  Receives impersonated user          │
│  Returns data for that user         │
└─────────────────────────────────────┘
```

---

### Flow 3: Stopping Impersonation

```
┌─────────────────────────────────────┐
│  User clicks "Stop Impersonation"   │
│  in ImpersonationBanner             │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  ImpersonationBanner.tsx            │
│  stopImpersonation()                │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  AuthContext.tsx                    │
│  POST /api/auth/stop-impersonation  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  backend/app/api/auth.py            │
│  @router.post("/stop-impersonation")│
│  1. Decode current token            │
│  2. Extract original_user_id         │
│  3. Mark session as 'ended'          │
│  4. Generate normal JWT for superadmin│
│  5. Log audit event                 │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  Response: {                        │
│    access_token: "<normal_jwt>",     │
│    user: {...superadmin...}         │
│  }                                  │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  AuthContext.tsx                    │
│  1. Store new token                 │
│  2. Update state:                   │
│     - isImpersonating = false       │
│     - user = originalUser           │
│     - originalUser = null           │
│  3. Redirect to /dashboard/users   │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  UsersPage (superadmin view)        │
│  Back to normal superadmin view     │
└─────────────────────────────────────┘
```

---

### Flow 4: Page Refresh / App Reload

```
┌─────────────────────────────────────┐
│  User refreshes page                 │
│  or app reloads                      │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  AuthContext.tsx                    │
│  useEffect → loadCurrentUser()      │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│  First: GET /api/auth/impersonation-│
│         status                       │
│  Checks if token has is_impersonation│
└────────┬────────────────────────────┘
         │
         ├─── If impersonating ────────┐
         │                              │
         ▼                              ▼
┌─────────────────────────┐  ┌─────────────────────────┐
│ Restore impersonation   │  │ Normal user load         │
│ state from response     │  │ GET /api/auth/user       │
│ - isImpersonating=true  │  │                         │
│ - user=impersonatedUser │  │                         │
│ - originalUser=superadmin│ │                         │
└─────────────────────────┘  └─────────────────────────┘
         │                              │
         └──────────────┬───────────────┘
                        │
                        ▼
         ┌─────────────────────────────┐
         │  App renders with correct     │
         │  user context                │
         └─────────────────────────────┘
```

---

## Security Considerations

1. **Role-Based Access**: Only `SUPER_ADMIN` can start impersonation
2. **Session Validation**: Every request validates the session is still active
3. **Token Expiry**: Impersonation tokens have expiry times
4. **Audit Logging**: All impersonation events are logged
5. **No Self-Impersonation**: Superadmin cannot impersonate themselves
6. **No Superadmin Impersonation**: Cannot impersonate another superadmin
7. **Session Tracking**: Database tracks all active sessions

---

## Key Files Summary

| File | Purpose | When Used |
|------|---------|-----------|
| `models/impersonation.py` | Database model | Session creation, validation |
| `api/users.py` | Start impersonation endpoint | Superadmin clicks "Impersonate" |
| `api/auth.py` | Stop/status endpoints | Stop impersonation, check status |
| `utils/auth.py` | Token validation | Every authenticated API request |
| `services/role_check.py` | Alternative auth function | Some endpoints |
| `services/audit_service.py` | Logging | Start/stop events |
| `context/AuthContext.tsx` | Frontend state management | All frontend interactions |
| `components/ImpersonationBanner.tsx` | UI indicator | Always visible when impersonating |
| `pages/users/UsersPage.tsx` | Impersonation trigger | Superadmin user management |

---

## Testing Checklist

- [ ] Superadmin can impersonate a regular user
- [ ] Superadmin cannot impersonate another superadmin
- [ ] Superadmin cannot impersonate themselves
- [ ] Impersonated user sees their own dashboard
- [ ] Impersonated user sees their own sidebar
- [ ] Impersonation banner is visible
- [ ] All API calls work with impersonation token
- [ ] Session validation works (ended sessions are rejected)
- [ ] Stop impersonation returns to UsersPage
- [ ] Page refresh maintains impersonation state
- [ ] Audit logs are created correctly

---

This architecture ensures that impersonation is secure, traceable, and provides a seamless experience for superadmins to troubleshoot and support users.

