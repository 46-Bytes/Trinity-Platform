# Firm Architecture & Flow Documentation

This document explains how the Firm Account feature works across both backend and frontend.

---

## 📁 **Backend Files Structure**

### **1. Models (`app/models/firm.py`)**
**Purpose**: Database schema definition for the `firms` table.

**Key Fields**:
- `id`: UUID primary key
- `firm_name`: Name of the organization
- `firm_admin_id`: UUID of the user who is the Firm Admin
- `seat_count`: Total seats purchased (minimum 5)
- `seats_used`: Number of active advisor seats currently used
- `clients`: Array of client user IDs (PostgreSQL ARRAY)
- `subscription_id`: Link to subscription record
- `billing_email`: Email for billing notifications

**Relationships**:
- `advisors`: One-to-many with `User` (users with `firm_id` pointing to this firm)
- `engagements`: One-to-many with `Engagement` (engagements belonging to this firm)
- `subscription`: One-to-one with `Subscription`

**What it does**: Defines the database structure. SQLAlchemy uses this to create/query the `firms` table.

---

### **2. Schemas (`app/schemas/firm.py`)**
**Purpose**: Pydantic models for API request/response validation.

**Key Schemas**:
- `FirmCreate`: Input for creating a firm (`firm_name`, `seat_count`, `billing_email`)
- `FirmResponse`: Output format for firm data
- `FirmAdvisorAdd`: Input for adding advisor (`email`, `name`)
- `FirmClientAdd`: Input for adding client (`email`, `name`, `given_name`, `family_name`)
- `FirmAdvisorResponse`: Output format for advisor data
- `FirmClientResponse`: Output format for client data
- `AdvisorSuspendRequest`: Input for suspending advisor (with `reassignments` dict)

**What it does**: Validates incoming API requests and formats outgoing responses. Ensures data types and required fields are correct.

---

### **3. Permissions (`app/services/firm_permissions.py`)**
**Purpose**: Permission checking functions for firm operations.

**Key Functions**:
- `can_manage_firm_users(user, firm_id)`: Can user add/remove advisors/clients?
- `can_view_firm_engagements(user, firm_id)`: Can user see all firm engagements?
- `can_assign_advisors(user, firm_id)`: Can user assign advisors to engagements?
- `can_modify_subscription(user, firm_id)`: Can user change seat count/billing?

**Rules**:
- `SUPER_ADMIN`: Can do everything
- `FIRM_ADMIN`: Can manage their own firm only
- `FIRM_ADVISOR`: Limited permissions (view own engagements)
- Others: No firm permissions

**What it does**: Centralized permission logic. Used by API endpoints to check if a user can perform an action.

---

### **4. Service Layer (`app/services/firm_service.py`)**
**Purpose**: Business logic for firm operations (the "brain" of firm management).

**Key Methods**:

#### `create_firm(firm_name, firm_admin_id, seat_count, billing_email)`
- Creates a new `Firm` record
- Sets `firm_admin_id` and updates user's `role` to `FIRM_ADMIN`
- Creates initial `Subscription` record
- Sets `seats_used = 1` (for the Firm Admin, but Firm Admin doesn't count toward billed seats)

#### `add_advisor_to_firm(firm_id, advisor_email, advisor_name, added_by_user_id)`
- Checks seat availability
- If user exists: Updates their `firm_id` and `role` to `FIRM_ADVISOR`
- If user doesn't exist: Creates new `User` with placeholder `auth0_id`
- Increments `firm.seats_used` (only counts active advisors)
- **No password handling** (Auth0 only)

#### `add_client_to_firm(firm_id, email, name, given_name, family_name, added_by)`
- If client exists: Links them to firm (sets `firm_id`, `role = CLIENT`)
- If client doesn't exist: Creates new `User` with `role = CLIENT`
- Adds client ID to `firm.clients` array
- **No password handling** (Auth0 only)

#### `remove_advisor_from_firm(firm_id, advisor_id, removed_by_user_id)`
- Reassigns primary engagements to Firm Admin
- Removes advisor from secondary advisor lists
- Sets `advisor.firm_id = None`, `role = ADVISOR`, `is_active = False`
- **Decrements `firm.seats_used`** (removing advisor frees a seat)

#### `suspend_advisor(firm_id, advisor_id, suspended_by_user_id, reassignments)`
- Sets `advisor.is_active = False`
- **Keeps `firm_id` and `role`** (advisor still in firm, just inactive)
- Reassigns primary engagements based on `reassignments` dict
- Removes from secondary lists
- **Does NOT decrement `seats_used`** (suspended advisors still count as seats)

#### `reactivate_advisor(firm_id, advisor_id, reactivated_by_user_id)`
- Sets `advisor.is_active = True`
- **Does NOT change `seats_used`** (seats already counted)

#### `get_firm_advisors(firm_id, current_user)`
- Returns all `FIRM_ADVISOR` users in the firm (excludes `FIRM_ADMIN`)

#### `get_advisor_engagements(firm_id, advisor_id, current_user)`
- Returns dict with `primary` and `secondary` engagement lists
- Used for suspension warning dialog

**What it does**: All the complex business logic. API endpoints call these methods. Handles seat counting, engagement reassignment, user lifecycle.

---

### **5. API Endpoints (`app/api/firms.py`)**
**Purpose**: HTTP endpoints that expose firm operations to the frontend.

**Key Endpoints**:

#### `POST /api/firms`
- Creates a new firm
- Only `ADVISOR` or `SUPER_ADMIN` can create
- Calls `firm_service.create_firm()`

#### `GET /api/firms`
- Lists firms (filtered by user role)
- `FIRM_ADMIN` sees only their firm
- `SUPER_ADMIN` sees all firms

#### `GET /api/firms/{firm_id}`
- Gets firm details
- Permission check via `can_view_firm_engagements()`

#### `POST /api/firms/{firm_id}/advisors`
- Adds advisor to firm
- Validates `FirmAdvisorAdd` schema
- Calls `firm_service.add_advisor_to_firm()`
- Permission check via `can_manage_firm_users()`

#### `GET /api/firms/{firm_id}/advisors`
- Lists all advisors in firm
- **Calculates `seats_used` from active advisors** (not stored value)
- Returns `FirmAdvisorListResponse` with `advisors`, `total`, `seats_used`, `seats_available`

#### `DELETE /api/firms/{firm_id}/advisors/{advisor_id}`
- Removes advisor from firm
- Calls `firm_service.remove_advisor_from_firm()`

#### `POST /api/firms/{firm_id}/advisors/{advisor_id}/suspend`
- Suspends advisor
- Accepts `AdvisorSuspendRequest` with optional `reassignments` dict
- Calls `firm_service.suspend_advisor()`

#### `POST /api/firms/{firm_id}/advisors/{advisor_id}/reactivate`
- Reactivates suspended advisor
- Calls `firm_service.reactivate_advisor()`

#### `GET /api/firms/{firm_id}/advisors/{advisor_id}/engagements`
- Gets advisor's engagements (for suspension warning)
- Returns `{ primary: [...], secondary: [...] }`

#### `POST /api/firms/{firm_id}/clients`
- Adds client to firm
- Validates `FirmClientAdd` schema
- Calls `firm_service.add_client_to_firm()`

#### `GET /api/firms/{firm_id}/stats`
- Returns firm statistics
- **Calculates `seats_used` from active advisors** (not stored value)
- Returns `advisors_count`, `active_advisors_count`, `seats_used`, `seats_available`, etc.

**What it does**: HTTP layer. Validates requests, checks permissions, calls service methods, returns JSON responses.

---

## 🎨 **Frontend Files Structure**

### **1. Redux Store (`frontend/src/store/slices/firmReducer.ts`)**
**Purpose**: Centralized state management for firm data.

**State Structure**:
```typescript
{
  firm: Firm | null,           // Current firm data
  advisors: Advisor[],         // List of advisors
  clients: Client[],            // List of clients
  stats: FirmStats | null,      // Statistics (from /stats endpoint)
  seats_used: number | null,    // From advisors API
  seats_available: number | null, // From advisors API
  isLoading: boolean,
  error: string | null
}
```

**Key Async Thunks**:

#### `fetchFirm()`
- Calls `GET /api/firms`
- Stores firm data in Redux state

#### `fetchFirmAdvisors(firmId)`
- Calls `GET /api/firms/{firmId}/advisors`
- Stores advisors list AND `seats_used`/`seats_available` from response

#### `fetchFirmStats(firmId)`
- Calls `GET /api/firms/{firmId}/stats`
- Stores statistics (used on Dashboard)

#### `addAdvisorToFirm({ firmId, advisorData })`
- Calls `POST /api/firms/{firmId}/advisors`
- Sends `{ email, name }` (no password)
- Optimistically updates state

#### `addClientToFirm({ firmId, email, name, ... })`
- Calls `POST /api/firms/{firmId}/clients`
- Sends `{ email, name, given_name, family_name }` (no password)

#### `suspendAdvisor({ firmId, advisorId, reassignments })`
- Calls `POST /api/firms/{firmId}/advisors/{advisorId}/suspend`
- Sends `{ reassignments: { "engagement_id": "new_advisor_id" } }`

#### `reactivateAdvisor({ firmId, advisorId })`
- Calls `POST /api/firms/{firmId}/advisors/{advisorId}/reactivate`

**What it does**: Manages all firm-related state. Components dispatch these thunks to fetch/update data. Redux automatically updates UI when state changes.

---

### **2. Dashboard Home (`frontend/src/pages/dashboard/DashboardHome.tsx`)**
**Purpose**: Main dashboard that shows different views based on user role.

**FirmAdminDashboard Component**:
- Fetches `firm`, `advisors`, `clients`, `stats` on mount
- Displays stat cards:
  - **Firm Advisors**: `stats.advisors_count` (total, excluding admin)
  - **Total Clients**: `clients.length`
  - **Active Engagements**: `stats.active_engagements`
  - **Monthly Usage**: Static (placeholder)
- Shows **Billing & Subscription** section with `seats_used` / `seat_count`
- Lists advisors in "Advisor Overview" section

**What it does**: Main landing page for `firm_admin`. Shows overview of firm health, advisors, clients, engagements.

---

### **3. Advisors Page (`frontend/src/pages/dashboard/AdvisorsPage.tsx`)**
**Purpose**: Manage advisors (add, remove, suspend, reactivate).

**Key Features**:
- **Add Advisor Dialog**: Form with `email`, `name`, `given_name`, `family_name` (no password)
- **Advisor List**: Shows all advisors with status (active/suspended)
- **Actions Menu** (per advisor):
  - **Suspend**: Opens dialog that:
    - Fetches advisor's engagements via `getAdvisorEngagements()`
    - If engagements exist: Shows reassignment UI (dropdowns for each primary engagement)
    - If no engagements: Shows simple warning
    - Validates all primary engagements are reassigned
    - Calls `suspendAdvisor()` with `reassignments` dict
  - **Reactivate**: Calls `reactivateAdvisor()`
  - **Remove**: Calls `removeAdvisorFromFirm()`
- **Stat Cards**:
  - **Total Advisors**: `advisors.length` (excluding admin)
  - **Active Advisors**: `advisors.filter(a => a.is_active).length`
  - **Seats Used**: `seats_used` from Redux (from advisors API)

**What it does**: Full CRUD interface for advisors. Handles suspension with engagement reassignment.

---

### **4. Clients Page (`frontend/src/pages/dashboard/ClientsPage.tsx`)**
**Purpose**: Manage clients (add, view list).

**Key Features**:
- **Add Client Dialog**: Form with `email`, `name`, `given_name`, `family_name` (no password)
- **Client List**: Shows all clients in the firm
- **Stat Cards**: Total clients count

**What it does**: Simple interface for adding/viewing clients. Clients are linked to firm but credentials managed by Auth0.

---

## 🔄 **Complete Flow Examples**

### **Flow 1: Adding an Advisor**

1. **Frontend**: User fills form in `AdvisorsPage.tsx` → clicks "Add Advisor"
2. **Redux**: Dispatches `addAdvisorToFirm({ firmId, advisorData: { email, name } })`
3. **API Call**: `POST /api/firms/{firmId}/advisors` with `{ email, name }`
4. **Backend API** (`firms.py`):
   - Validates `FirmAdvisorAdd` schema
   - Checks `can_manage_firm_users(current_user, firm_id)`
   - Calls `firm_service.add_advisor_to_firm(...)`
5. **Service** (`firm_service.py`):
   - Checks seat availability
   - Creates/updates `User` with `role = FIRM_ADVISOR`, `firm_id = firm_id`
   - Increments `firm.seats_used`
   - Commits to database
6. **Response**: Returns `FirmAdvisorResponse` (advisor data)
7. **Redux**: Updates `advisors` array in state
8. **UI**: Advisor appears in list, seats count updates

---

### **Flow 2: Suspending an Advisor with Engagements**

1. **Frontend**: User clicks "Suspend" on advisor in `AdvisorsPage.tsx`
2. **Redux**: Dispatches `getAdvisorEngagements({ firmId, advisorId })`
3. **API Call**: `GET /api/firms/{firmId}/advisors/{advisorId}/engagements`
4. **Backend**: Returns `{ primary: [...], secondary: [...] }`
5. **Frontend**: Shows dialog with:
   - Warning message
   - Dropdown for each primary engagement to reassign
   - Validation: All primary engagements must be reassigned
6. **User**: Selects new advisors for each engagement → clicks "Confirm"
7. **Redux**: Dispatches `suspendAdvisor({ firmId, advisorId, reassignments: { "eng_id": "new_advisor_id" } })`
8. **API Call**: `POST /api/firms/{firmId}/advisors/{advisorId}/suspend` with `{ reassignments: {...} }`
9. **Backend Service**:
   - Reassigns primary engagements based on `reassignments` dict
   - Removes advisor from secondary lists
   - Sets `advisor.is_active = False`
   - **Does NOT change `seats_used`**
10. **Response**: Returns updated advisor
11. **Redux**: Updates advisor in `advisors` array
12. **UI**: Advisor shows as "Suspended", seats count unchanged

---

### **Flow 3: Login & Role Assignment**

1. **User**: Clicks "Sign in" → Redirected to Auth0 Universal Login
2. **Auth0**: User enters email/password → Auth0 validates
3. **Auth0 Callback**: Redirects to `/api/auth/callback` with authorization code
4. **Backend** (`auth.py`):
   - Exchanges code for token
   - Gets user info from Auth0
   - Calls `AuthService.get_or_create_user(db, user_info)`
5. **Auth Service** (`auth_service.py`):
   - Finds user by `auth0_id` or `email`
   - **If user exists**: Updates info but **keeps existing `role` from database**
   - **If new user**: Creates with role from Auth0 metadata (or defaults to `ADVISOR`)
   - Returns `User` object
6. **Backend**: Creates session, redirects to frontend with token
7. **Frontend**: Stores token, calls `GET /api/auth/user`
8. **Backend**: Returns user data with **role from database**
9. **Frontend**: `AuthContext` stores user, `DashboardHome` shows appropriate view based on role

**Key Point**: Database role is source of truth. Auth0 login doesn't overwrite existing roles.

---

## 🔑 **Key Concepts**

### **Seat Management**
- **`seat_count`**: Total seats purchased (stored in `firm` table)
- **`seats_used`**: Calculated from active `FIRM_ADVISOR` users (NOT stored, computed on-the-fly)
- **Firm Admin does NOT count** toward `seats_used`
- **Suspended advisors still count** as seats (they're still in the firm)
- **Removed advisors free up seats** (they're no longer in the firm)

### **Role Hierarchy**
- `SUPER_ADMIN`: Can do everything
- `ADMIN`: Can view all firms
- `FIRM_ADMIN`: Can manage their own firm (add advisors/clients, suspend, view all engagements)
- `FIRM_ADVISOR`: Can view/manage their own engagements
- `CLIENT`: Can view their own engagements
- `ADVISOR`: Solo advisor (not in a firm)

### **Authentication Flow**
- **All users log in via Auth0** (no local passwords)
- **Credentials stored in Auth0**, not in our database
- **Adding advisor/client** just links them to firm (creates placeholder user if needed)
- **When they log in via Auth0**, our backend links their Auth0 account to the database user by email

---

## 📊 **Data Flow Diagram**

```
┌─────────────┐
│   Frontend  │
│  (React)    │
└──────┬──────┘
       │
       │ HTTP Requests (with Bearer token)
       │
       ▼
┌─────────────────┐
│  API Endpoints  │
│  (firms.py)     │
└──────┬──────────┘
       │
       │ Permission Checks
       │
       ▼
┌─────────────────┐
│  Service Layer  │
│ (firm_service)  │
└──────┬──────────┘
       │
       │ Business Logic
       │
       ▼
┌─────────────────┐
│  Database       │
│  (PostgreSQL)   │
└─────────────────┘
```

---

## 🎯 **Summary**

- **Backend**: Models define structure, Schemas validate data, Services contain logic, API exposes endpoints
- **Frontend**: Redux manages state, Components render UI, Thunks make API calls
- **Flow**: User action → Redux thunk → API endpoint → Permission check → Service method → Database → Response → Redux update → UI refresh
- **Key Principle**: Database role is source of truth. Auth0 handles authentication, our database handles authorization (roles/permissions).

