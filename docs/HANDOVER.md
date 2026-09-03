# Trinity Platform — Engineering Handover

> **Status:** Draft for review · **Prepared:** 1 September 2026
> **Repository:** `https://github.com/46-Bytes/Trinity-Platform` · **Branch documented:** `staging` @ `a13404f` (55 commits ahead of `main`)
> **Audience:** The engineer or team taking ownership of Trinity. Assumes working knowledge of Python, FastAPI, React and PostgreSQL; assumes no prior knowledge of this codebase or its domain.

---

## 1. Document Control

### 1.1 Purpose

This document is the complete engineering reference for the Trinity Platform. It is written so that a team with no prior exposure can stand the system up, understand every subsystem, make a safe change, ship it, and operate it — without needing the original authors.

It covers what the system *is*, not what it was intended to be. Where the code and the intent disagree, the code is documented and the gap is flagged.

### 1.2 How to read it

| If you are… | Start at |
|---|---|
| Standing the system up for the first time | *Environments, Configuration & Deployment* → its local setup runbook |
| Trying to understand the shape of the system | *System Architecture* → *Data Model & Database* |
| About to make your first change | *Engineering Standards, Workflow & Testing* → its definition-of-done checklist |
| On call, something is broken | *Operations, Diagnostics & Troubleshooting* → the troubleshooting table |
| Working out how to deploy it | *Unmerged Work on Other Branches* — a complete, unmerged deployment already exists |
| Scoping the next phase of work | the technical-debt register in *Operations* → *Unmerged Work* → *Handover Checklist & Open Questions* |
| Taking over as the responsible owner | §2.4 below, then *Handover Checklist & Open Questions* |

### 1.3 Conventions used in this document

- File references are repo-relative, e.g. `backend/app/main.py:46`.
- **Gotcha** callouts mark behaviour that is surprising, fragile, or has already caused an incident.
- **TO CONFIRM** marks a statement that could not be verified from the codebase and needs a human answer before this document is final. Every one of these is collected in *Handover Checklist & Open Questions*.
- No secret values appear anywhere in this document. Environment variable *names* and their purpose are documented; their values are not.

---

## 2. Executive Summary

### 2.1 What Trinity is

Trinity is a multi-tenant SaaS platform for **business advisory firms**. An advisory firm subscribes for a number of seats, its advisors run structured engagements with their SMB clients, and Trinity uses Claude to turn the raw material of those engagements — questionnaire responses, uploaded financials, position descriptions, meeting notes — into finished advisory deliverables: scored diagnostic reports, strategy workbooks, strategic business plans, HR matrices, position descriptions, task plans and client presentations.

The product's core loop is:

```
  Firm subscribes (seats)
        │
        ▼
  Advisor creates an Engagement for a Client
        │
        ▼
  Client/advisor completes a Diagnostic  ──►  AI pipeline scores it,
  (Sale Ready or Value Builder)               writes a report, generates tasks
        │
        ▼
  Diagnostic output seeds the AI Tools
  (BBA report, Strategy Workbook, Strategic
   Business Plan, Roles Matrix, PD & Scorecards)
        │
        ▼
  Value Builder Programme tracks the client through
  13 modules of deliverables until re-diagnostic
```

Everything downstream of the diagnostic is optional and advisor-driven; the diagnostic is the spine.

### 2.2 The system in one paragraph

A React 18 single-page application (Vite, TypeScript, Redux Toolkit, shadcn/ui) talks over HTTP to a FastAPI monolith (Python, SQLAlchemy 2.x, Alembic) backed by a single PostgreSQL database. Identity is Auth0, with a parallel local email-and-password path. All AI work goes to the Anthropic Claude API through one service class, driven by Markdown prompt files kept on disk. Long-running AI jobs run in-process as FastAPI background tasks and are observed by the frontend through polling. Generated documents are produced server-side as PDF, DOCX, XLSX and PPTX and written to the local filesystem. Transactional email goes out through Resend.

### 2.3 Scale and shape of the codebase

| Metric | Count |
|---|---|
| Backend | ~38,900 lines of Python — 21 routers, 42 services, 21 model modules, 18 schema modules |
| Database tables | 25 |
| Alembic revisions | 80 |
| AI prompt assets | 62 Markdown prompts + 2 scoring maps, across 7 tool families |
| Frontend | ~47,100 lines of TS/TSX — 40 pages, 79 feature components, 49 shadcn/ui primitives, 17 Redux slices |
| Automated tests | 11 backend test modules, concentrated on the Value Builder programme. No frontend tests. |

### 2.4 The six things to know before touching anything

Each of these has already cost someone time, and none of them is obvious from reading the code.

1. **Local development runs against a shared hosted database.** There is no per-developer database. A destructive local command or a stray migration affects everyone. → *Environments, Configuration & Deployment*
2. **`alembic upgrade head` cannot build the schema from empty.** An early revision alters a table before it is created, so a fresh environment needs a schema dump, not a replay. → *Data Model & Database*
3. **Eight tables in the database have no code that touches them.** Two features — the Sale Ready programme and the self-service tier — had their migrations merged while their application code stayed on unmerged branches. The schema is live; nothing can read or write it. → *Unmerged Work on Other Branches*
4. **Long AI jobs run inside the API process, and nothing recovers them.** A deploy or restart kills a running diagnostic and strands the row in `processing` permanently — the cleanup routine that would reset it is bound to a worker lifecycle event this deployment never fires. → *System Architecture*, then *Operations, Diagnostics & Troubleshooting*
5. **Migrations collide across branches.** When two branches produce sibling revisions, merge them — never stamp past one. → *Operations, Diagnostics & Troubleshooting*
6. **There is no source of truth for configuration.** Secrets are correctly kept out of git — `backend/.env` and the Google service-account key are gitignored and were never committed, verified against full history — but the only copy of a working configuration therefore lives on developer machines. There is no `.env.example` and no secret store. Capturing and rotating that configuration is the highest-priority handover task. → *Handover Checklist & Open Questions*

---

## 3. Glossary

| Term | Meaning in Trinity |
|---|---|
| **Firm** | A subscribing advisory business. The tenant boundary. Owns advisors, clients and engagements. |
| **Advisor** | A consultant who runs engagements. Either an independent `advisor` or a firm-scoped `firm_advisor`. |
| **Client** | The SMB being advised. A user account with the `client` role, attached to engagements. |
| **Engagement** | A unit of advisory work between advisors and one or more clients. The container for diagnostics, tasks, notes, files, chat and tool outputs. |
| **Diagnostic** | A scored structured assessment of a client business. Two variants ship: **Sale Ready** and **Value Builder**. |
| **Sale Ready** | The diagnostic variant that assesses readiness for sale or exit. |
| **Value Builder** | The diagnostic variant that assesses value drivers — and also the name of the 13-module improvement programme that follows it. |
| **BBA** | Benchmark Business Advisory — the originating advisory methodology, and the name of the report-generation tool built on it. Its API routes are still prefixed `/api/poc` from its proof-of-concept origin. |
| **SBP** | Strategic Business Plan — the 14-section plan generator. |
| **Module** | One of the 13 stages (M0, V1–V11, M12) of the Value Builder programme. |
| **Deliverable** | A concrete artefact expected within a programme module. Can be completed, or scoped out of the engagement. |
| **RAG status** | Red/Amber/Green rating derived from diagnostic module scores. |
| **Impersonation** | A super admin assuming another user's identity, through an audited, session-tracked token. |
| **Seat** | One advisor's place on a firm's subscription. |

---

## Contents

1. [Document Control](#1-document-control)
2. [Executive Summary](#2-executive-summary)
3. [Glossary](#3-glossary)
4. [Technology Stack & Dependencies](#4-technology-stack--dependencies)
5. [System Architecture](#5-system-architecture)
6. [Environments, Configuration & Deployment](#6-environments-configuration--deployment)
7. [Data Model & Database](#7-data-model--database)
8. [Authentication, Authorization & Impersonation](#8-authentication-authorization--impersonation)
9. [Core Domain Modules](#9-core-domain-modules)
10. [Diagnostic Engine](#10-diagnostic-engine)
11. [AI Layer — Claude Integration & Prompt System](#11-ai-layer--claude-integration--prompt-system)
12. [AI Tools — BBA, Strategy Workbook & Strategic Business Plan](#12-ai-tools--bba-strategy-workbook--strategic-business-plan)
13. [AI Tools — Roles Matrix, PD & Scorecard](#13-ai-tools--roles-matrix-pd--scorecard)
14. [Value Builder Programme — Program Guide & Deliverables](#14-value-builder-programme--program-guide--deliverables)
15. [Frontend Architecture](#15-frontend-architecture)
16. [Engineering Standards, Workflow & Testing](#16-engineering-standards-workflow--testing)
17. [Operations, Diagnostics & Troubleshooting](#17-operations-diagnostics--troubleshooting)
18. [Unmerged Work on Other Branches](#18-unmerged-work-on-other-branches)
19. [Handover Checklist & Open Questions](#19-handover-checklist--open-questions)

---

## 4. Technology Stack & Dependencies

Trinity is a two-manifest project: a Python/FastAPI backend pinned in `backend/requirements.txt`, and a Vite/React frontend declared in `frontend/package.json`. Everything below was read from the manifests on branch `staging` and cross-checked against the import sites.

There is no `Dockerfile`, no `runtime.txt`, no `.python-version`, no `pyproject.toml`, no `Procfile`, and no CI workflow — `.github/` holds only `pull_request_template.md`, with no `workflows/` directory. `docker-compose.yml` at the repo root is unused and is not part of any run path: it declares a single service, nothing in the repo consumes it, `backend/README.md` never mentions it, and there is no Dockerfile for either side. Its contents are deliberately not reproduced here; treat it as debt.

### Layered stack — backend

Line numbers in the Version column are `backend/requirements.txt`.

| Layer | Technology | Version (as pinned) | What it is used for in Trinity |
|---|---|---|---|
| Web framework | `fastapi[standard]` | `==0.123.7` (`:2`) | The whole HTTP surface. App constructed at `backend/app/main.py:46-52` with `docs_url="/api/docs"`, `redoc_url="/api/redoc"`; 21 routers imported at `backend/app/main.py:12-28`, registered at `:86-107`. |
| ASGI server | `uvicorn[standard]` | `==0.38.0` (`:3`) | The only server invoked. `backend/app/main.py:163-170` runs `uvicorn.run("app.main:app", host="0.0.0.0", port=settings.PORT, reload=settings.DEBUG)`; `backend/README.md:37` documents `uvicorn app.main:app --reload --port 8000`. |
| Multipart parsing | `python-multipart` | `==0.0.20` (`:4`) | FastAPI's requirement for `UploadFile` / `File(...)` form uploads — e.g. `backend/app/api/diagnostics.py:190` and `:1065`. |
| ORM | `sqlalchemy` | `==2.0.44` (`:13`) | Engine and session factory in `backend/app/database.py`; models under `backend/app/models/`. 2.x library, 1.x idiom — see below. |
| Postgres driver | `psycopg2-binary` | `==2.9.11` (`:14`) | Sole DB driver. `backend/app/database.py:21-30` passes psycopg2-specific `connect_args` (`connect_timeout`, `keepalives*`) and, for non-local hosts, defaults `sslmode` to `require`. |
| Migrations | `alembic` | `==1.17.2` (`:15`) | `backend/alembic/` + `backend/alembic.ini`. `backend/alembic/env.py:24` overrides the ini placeholder from `settings.DATABASE_URL`; `target_metadata = Base.metadata` at `:31`. |
| Validation | `pydantic` | `==2.12.5` (`:24`) | Schemas under `backend/app/schemas/`; `field_validator` (v2 API) at `backend/app/config.py:82` and `:89`. |
| Settings loader | `pydantic-settings` | `==2.12.0` (`:25`) | `Settings(BaseSettings)` at `backend/app/config.py:9`; `env_file = ".env"`, `case_sensitive = True` (`:96-98`); instantiated eagerly at `:102`. |
| Env file loading | `python-dotenv` | `==1.2.1` (`:18`) | Backs `pydantic-settings`' `env_file` support. No direct import under `backend/app/`. |
| OAuth client | `authlib` | `==1.6.5` (`:7`) | Auth0 Authorization Code flow. `from authlib.integrations.starlette_client import OAuth` at `backend/app/services/auth_service.py:6`, used by `AuthService.create_oauth_client()` (`:19-20`). |
| JWT verification | `python-jose[cryptography]` | `==3.5.0` (`:8`) | Verification of Auth0 tokens. `from jose import jwt, JWTError` at `backend/app/utils/auth.py:9` and `backend/app/api/auth.py:13`; `from jose import jwt` at `backend/app/api/users.py:39`. Algorithm comes from `AUTH0_ALGORITHMS` (default `"RS256"`, `backend/app/config.py:26`). |
| Session cookies | `itsdangerous` | `==2.2.0` (`:10`) | Required by Starlette's `SessionMiddleware`, added at `backend/app/main.py:56-63` (cookie `trinity_session`, `max_age=3600*24*7`, `same_site="lax"`, `https_only=settings.APP_ENV != "development"`). |
| Password hashing | `passlib[bcrypt]` | `==1.7.4` (`:32`) | Imported at `backend/app/utils/password.py:9`; `CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")` at `:12`. |
| Password hashing (backend algo) | `bcrypt` | `==5.0.0` (`:31`) | Installed as the passlib extra, but the code uses **pbkdf2_sha256, not bcrypt** — `backend/app/utils/password.py:4-7`: pbkdf2 was chosen "to avoid bcrypt's 72-byte password length limitation". |
| HTTP client (server-side) | `requests` | `==2.32.5` (`:9`) | Auth0 Management API calls (`backend/app/services/auth0_management.py:5`) and JWKS fetch (`backend/app/utils/auth.py:5`, aliased `http_requests`). |
| LLM (live) | `anthropic` | `>=0.52.0` (`:38`) — **unpinned floor** | The live AI provider. `from anthropic import AsyncAnthropic` at `backend/app/services/claude_service.py:13`; one class-level client built at startup (`ClaudeService.initialize_client()`, called from `startup_event` at `backend/app/main.py:125`; definition at `claude_service.py:29-45`). |
| LLM (rollback only) | `openai` | `==2.9.0` (`:35`) | Retained, not running. See *AI provider: Claude live, OpenAI parked* below. |
| Malformed-JSON recovery | `json-repair` | `==0.30.3` (`:41`) | Lazily imported inside `ClaudeService._repair_json` at `backend/app/services/claude_service.py:471` (`from json_repair import repair_json`); logs `"[Claude] JSON repaired via json_repair library"` at `:475`. Called from the response path at `:584`. |
| PDF rendering | `xhtml2pdf` | `==0.2.17` (`:44`) | `from xhtml2pdf import pisa` at `backend/app/services/report_service.py:10` — the diagnostic PDF report. |
| Markdown → HTML | `markdown` | `==3.10` (`:45`) | `import markdown` at `backend/app/services/report_service.py:6`; converts AI-authored Markdown into the HTML that `pisa` rasterises. |
| Word generation | `python-docx` | `==1.2.0` (`:49`) | Five `.docx` producers plus one lazy import — see the deliverable table. |
| HTML → Word bridge | `beautifulsoup4` | `==4.14.3` (`:50`) | Single site: `backend/app/services/sbp_report_export.py:16`, used at `:197` (`BeautifulSoup(html_content, "html.parser")`). |
| Excel generation | `openpyxl` | `==3.1.5` (`:53`) | Four `.xlsx` producers, two of which `load_workbook()` a shipped template. |
| PowerPoint generation | `python-pptx` | `==1.0.2` (`:56`) | Two `.pptx` producers plus one lazy import. |
| Transactional email | `resend` | *(no version specifier)* (`:64`) | `import resend` at `backend/app/services/email_service.py:5`; the only outbound mail transport. |
| Tests | `pytest` | `==8.3.4` (`backend/requirements-dev.txt`) | `backend/requirements-dev.txt` layers `-r requirements.txt` plus pytest. Suite in `backend/tests/` — see *Engineering Standards, Workflow & Testing*. |
| Process manager, CORS shim, date utils, task-queue packages | `gunicorn`, `fastapi-cors`, `python-dateutil`, `celery[redis]`, `redis`, `flower` | see below | Pinned, not part of any run path. See *Dependencies that are pinned but not used*. |

### Dependencies that are pinned but not used

Five manifest entries buy nothing at runtime. Removing them is not uniformly safe, so they are listed with the exact condition attached.

| Package | Pin | Status |
|---|---|---|
| `gunicorn` | `==24.1.1` (`:47`) | **Never invoked.** Outside `backend/venv/`, the string `gunicorn` occurs in exactly one place in the repo: `backend/requirements.txt:47`. No start script, compose service, docs line or `.vscode/launch.json` entry uses it; uvicorn is the only server that runs. Safe to drop. |
| `fastapi-cors` | `==0.0.6` (`:21`) | **Unused.** CORS is Starlette's built-in `CORSMiddleware` (`backend/app/main.py:5`, added at `:67-83`) with an explicit origin allowlist, because `allow_credentials=True` forbids `"*"`. Nothing in the repo imports `fastapi_cors`. Safe to drop. |
| `python-dateutil` | `==2.9.0.post0` (`:28`) | **No import found** under `backend/app/`, `backend/tests/` or `backend/scripts/`. Alembic's `timezone` option would need it, but that option is commented out (`backend/alembic.ini:21`). Safe to drop, subject to a transitive check. |
| `celery[redis]`, `redis`, `flower` | `==5.4.0`, `==5.2.1`, `==2.0.1` (`:59-61`) | **Cannot simply be removed.** `backend/app/tasks/diagnostic_tasks.py:14-18` imports `celery` at module scope (`states`, `SoftTimeLimitExceeded`, `worker_ready`, and `app.celery_app.celery_app`), and `backend/app/api/diagnostics.py:500` imports `_run_pipeline` from that same module to serve a diagnostic submit — so the `celery` package must be installed for the API to start and serve, even though no broker, worker or scheduler is ever run. Dropping these pins requires moving `_run_pipeline` out of `backend/app/tasks/diagnostic_tasks.py` first. `flower` is pinned and imported by nothing. `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` (`backend/app/config.py:58-59`) are read only by `backend/app/celery_app.py`. |

**Gotcha (the inverse case):** `httpx` is imported directly at `backend/app/services/claude_service.py:12`, `backend/app/services/openai_service.py:22` and `backend/app/api/auth.py:97`, but it appears nowhere in `backend/requirements.txt`. It is satisfied only transitively, via `anthropic`/`openai`. If the Anthropic SDK drops or renames that dependency, three import sites break with no manifest change to explain it. Pin `httpx` explicitly.

### Layered stack — frontend

| Layer | Technology | Version (as declared) | What it is used for in Trinity |
|---|---|---|---|
| UI framework | `react` / `react-dom` | `^18.3.1` | `createRoot` at `frontend/src/main.tsx:61`; provider tree `Provider → QueryClientProvider → AuthProvider → TooltipProvider → BrowserRouter` at `frontend/src/App.tsx:120-132`. |
| Build tool | `vite` | `^5.4.19` | `frontend/vite.config.ts`; dev server `host: "::"`, `port: 8080`, `allowedHosts: ["*"]`. |
| React transform | `@vitejs/plugin-react-swc` | `^3.11.0` | SWC (not Babel) for JSX/Fast Refresh — imported `frontend/vite.config.ts:2`, applied at `:29`. |
| Language | `typescript` | `^5.8.3` | Three-file project-reference setup: `frontend/tsconfig.json` (solution + `@/*` path alias), `tsconfig.app.json` (`include: ["src"]`), `tsconfig.node.json` (`include: ["vite.config.ts"]`). |
| Client + server state | `@reduxjs/toolkit` + `react-redux` | `^2.11.1` / `^9.2.0` | The actual server-state layer. `configureStore` at `frontend/src/store/index.ts:22-51` with 17 reducers (map at `:24-40`); all 17 files in `frontend/src/store/slices/` use `createAsyncThunk`. |
| Server cache | `@tanstack/react-query` | `^5.83.0` | **Provider only.** See *Overlapping responsibilities*. |
| Routing | `react-router-dom` | `^6.30.1` | `BrowserRouter`/`Routes`/`Route`/`Navigate` at `frontend/src/App.tsx:5`; imported in 32 files. |
| Forms | `react-hook-form` | `^7.61.1` | 6 files: `components/engagement/form.tsx`, `.../tasks/NoteForm.tsx`, `.../tasks/TaskForm.tsx`, `components/firms/CreateFirmDialog.tsx`, `components/subscriptions/CreateSubscriptionDialog.tsx`, `components/ui/form.tsx`. |
| Schema validation | `zod` | `^3.25.76` | 3 files: `components/engagement/form.tsx`, `.../tasks/NoteForm.tsx`, `.../tasks/TaskForm.tsx`. |
| Form/schema glue | `@hookform/resolvers` | `^3.10.0` | `zodResolver` in exactly those three files (`form.tsx:2`, `NoteForm.tsx:2`, `TaskForm.tsx:3`). |
| Headless primitives | `@radix-ui/react-*` | 27 packages, `^1.x`–`^2.x` | Behaviour/accessibility layer under `frontend/src/components/ui/*.tsx`. All 27 have at least one import site; the most-reused are `react-slot` (4 files), `react-dialog` (3), `react-label` and `react-toggle` (2 each). |
| Component layer | shadcn/ui | *(not an npm dep)* | Vendored source. Config in `frontend/components.json`: `style: "default"`, `rsc: false`, `tsx: true`, `baseColor: "slate"`, `cssVariables: true`, `prefix: ""`, aliases `components`→`@/components`, `utils`→`@/lib/utils`, `ui`→`@/components/ui`, `lib`→`@/lib`, `hooks`→`@/hooks`. |
| Styling | `tailwindcss` | `^3.4.17` | `frontend/tailwind.config.ts` — `darkMode: ["class"]`, `prefix: ""`, HSL CSS-variable colour tokens, `trinity`/`trinity-md`/`trinity-lg`/`trinity-xl`/`glow` box shadows (`:82-88`), fonts DM Sans (`sans`) and Plus Jakarta Sans (`heading`) at `:16-19`. |
| Tailwind plugins | `tailwindcss-animate`, `@tailwindcss/typography` | `^1.0.7`, `^0.5.16` | `plugins: [require("tailwindcss-animate")]` at `frontend/tailwind.config.ts:115`. **`@tailwindcss/typography` is installed but absent from that array** — `prose` classes do nothing. |
| CSS pipeline | `postcss` + `autoprefixer` | `^8.5.6`, `^10.4.21` | `frontend/postcss.config.js` — those two plugins, nothing else. |
| Class merging | `clsx` + `tailwind-merge` | `^2.1.1`, `^2.6.0` | Both used only by the `cn()` helper in `frontend/src/lib/utils.ts`. |
| Variant API | `class-variance-authority` | `^0.7.1` | 10 files, all shadcn primitives: `ui/alert.tsx`, `badge`, `button`, `label`, `navigation-menu`, `sheet`, `sidebar`, `toast`, `toggle-group`, `toggle`. |
| Icons | `lucide-react` | `^0.462.0` | Most-used frontend dependency: **117 files**. |
| Charts | `recharts` | `^2.15.4` | Two files: `frontend/src/components/ui/chart.tsx` (shadcn wrapper) and `frontend/src/pages/dashboard/components/SuperAdminDashboard.tsx`. |
| Toasts | `sonner` | `^1.7.4` | 45 files import from `sonner`; mounted as `<Sonner />` at `frontend/src/App.tsx:125`. A second, separate Radix toaster is mounted alongside it at `:124`. |
| Theme switching | `next-themes` | `^0.3.0` | One file: `frontend/src/components/ui/sonner.tsx`, to pick the toast theme. |
| Command palette | `cmdk` | `^1.1.1` | `frontend/src/components/ui/command.tsx`. |
| Carousel | `embla-carousel-react` | `^8.6.0` | `frontend/src/components/ui/carousel.tsx`. |
| Drawer | `vaul` | `^0.9.9` | `frontend/src/components/ui/drawer.tsx`. |
| Date picker | `react-day-picker` | `^8.10.1` | `frontend/src/components/ui/calendar.tsx`. |
| Date utilities | `date-fns` | `^3.6.0` | **Zero imports in `frontend/src`.** Present only as `react-day-picker` v8's peer requirement. |
| OTP input | `input-otp` | `^1.4.2` | `frontend/src/components/ui/input-otp.tsx`. |
| Resizable panes | `react-resizable-panels` | `^2.1.9` | `frontend/src/components/ui/resizable.tsx`. |
| Lint | `eslint` + `typescript-eslint` | `^9.32.0`, `^8.38.0` | Flat config `frontend/eslint.config.js`: `js.configs.recommended` + `tseslint.configs.recommended`, plugins `react-hooks` and `react-refresh`, `ignores: ["dist"]`. |
| Dev tagging | `lovable-tagger` | `^1.1.11` | `componentTagger()` at `frontend/vite.config.ts:29`, applied only when `mode === "development"`. Evidence the scaffold came from Lovable (see also `"name": "vite_react_shadcn_ts"` at `frontend/package.json:2`). |

### Backend runtime

**Python version.** Nothing in version control declares one. The only in-repo evidence is the gitignored virtualenv: `backend/venv/pyvenv.cfg` reports `version = 3.12.4` with `home = C:\Users\...\Python312`. The stray pip log at `backend/=0.52.0:12` corroborates CPython 3.12 on Windows (`jiter-0.13.0-cp312-cp312-win_amd64.whl`).

**Gotcha:** the production Python version is asserted nowhere in version control. Anyone provisioning a new environment has to infer 3.12 from a venv that is (correctly) gitignored. Declare it in a `.python-version` or `runtime.txt` on day one.

**FastAPI / Uvicorn.** `fastapi[standard]` pulls in `fastapi-cli` (0.0.16) and `fastapi-cloud-cli` (0.6.0), both present in the venv, but the documented entry point is plain uvicorn.

Startup and shutdown work is confined to two lifecycle hooks, both using the deprecated `@app.on_event` decorator rather than a lifespan context manager:

- `startup_event` — `backend/app/main.py:118-132`. Calls `ClaudeService.initialize_client()` at `:125`. The OpenAI equivalent is commented out at `:128-130`.
- `shutdown_event` — `backend/app/main.py:155-160`. Logging only.

Generated files are served off disk: `app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")` at `backend/app/main.py:115`, where `files_dir` is `backend/files` and is `mkdir(exist_ok=True)`'d at `:113`. That mount is unauthenticated — see *Operations, Diagnostics & Troubleshooting*.

#### SQLAlchemy: 2.x installed, 1.x idiom

The pin is `sqlalchemy==2.0.44`, but the codebase is written in legacy 1.x style:

```python
# backend/app/database.py:9, :95
from sqlalchemy.ext.declarative import declarative_base   # deprecated location in 2.0
Base = declarative_base()
```

- Models use `Column(...)` with `relationship(...)`. There is not a single `Mapped[...]` annotation or `mapped_column()` anywhere under `backend/app/`.
- Query style is overwhelmingly legacy `Session.query()`: **392 occurrences of `db.query(`** across `backend/app/`, against **3** `select()` call sites in 2 files (`backend/app/api/engagements.py:268`, `backend/app/services/program_deliverable_service.py:199` and `:233`).

**Gotcha:** do not describe this as "SQLAlchemy 2.x style". It is the 1.x API running on the 2.0 runtime via the legacy shim. `sqlalchemy.ext.declarative.declarative_base` emits a deprecation warning under 2.0 (the supported import is `sqlalchemy.orm.declarative_base`), so a SQLAlchemy 2.1 bump is a breaking change, not a patch.

Engine configuration is tuned for a remote managed Postgres (`backend/app/database.py:33-42`): `pool_pre_ping=True`, `pool_size=10`, `max_overflow=10`, `pool_recycle=1800`, `pool_timeout=30`, `echo=False`. A `do_connect` event listener at `:60-88` retries new DBAPI connections up to 3 times with exponential backoff (`_CONNECT_BACKOFF = 0.5`) on a fixed list of transient DNS/network error strings (`:46-54`), because `pool_pre_ping` only revalidates *pooled* connections.

#### Alembic

`backend/alembic.ini:56` still carries the template placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`. This is not the real connection string — `backend/alembic/env.py:24` overrides it at runtime from `settings.DATABASE_URL`, so the ini value is inert. Other ini settings: `script_location = alembic` (`:5`), `prepend_sys_path = .` (`:13`), `version_path_separator = os` (`:50`), `[logger_root]` and `[logger_sqlalchemy]` at `WARN`, `[logger_alembic]` at `INFO` (`:80-93`).

`env.py` carries two autogenerate filters worth knowing about before running `alembic revision --autogenerate`: `include_object` (`:53-59`) suppresses eight redundant `*_id_key` unique constraints listed in `EXEMPT_UNIQUE_CONSTRAINTS` (`:41-50`), and `strip_comment_directives` (`:81-96`) drops comment-only diffs so `alembic check` reports structural drift only. The migration workflow itself belongs to *Data Model & Database*.

**Gotcha:** `backend/README.md:73-75` states that `alembic upgrade head` cannot build a database from empty in this repo — an early revision runs `ALTER TABLE advisor_client` before that table is created. Only upgrades of an already-populated database work.

#### Pydantic v2

Strictly v2 API: `field_validator` with `@classmethod` (`backend/app/config.py:82-94`) and `pydantic_settings.BaseSettings` (`:5`, `:9`). Two validators enforce provider-specific ranges: `OPENAI_TEMPERATURE` must be `0.0–2.0` (`:82-87`), `ANTHROPIC_TEMPERATURE` must be `0.0–1.0` (`:89-94`).

Because `settings = Settings()` runs at module import (`backend/app/config.py:102`), every field declared without a default is a hard startup requirement. There are ten:

| Required setting | Declared at |
|---|---|
| `DATABASE_URL` | `backend/app/config.py:19` |
| `AUTH0_DOMAIN` | `:22` |
| `AUTH0_CLIENT_ID` | `:23` |
| `AUTH0_CLIENT_SECRET` | `:24` |
| `AUTH0_AUDIENCE` | `:25` |
| `AUTH0_MANAGEMENT_API_AUDIENCE` | `:30` |
| `AUTH0_MANAGEMENT_CLIENT_ID` | `:31` |
| `AUTH0_MANAGEMENT_CLIENT_SECRET` | `:32` |
| `SECRET_KEY` | `:38` |
| `ANTHROPIC_API_KEY` | `:47` |

Missing any one means the process cannot import, let alone serve. `backend/tests/conftest.py:26-41` hand-mirrors these and stubs them when no `.env` is present so tests import cleanly (`backend/README.md:49-51`); a new required field must be added there by hand. Full env-var semantics belong to *Environments, Configuration & Deployment*.

`backend/app/config.py` also carries three Google Drive settings that no dependency in `requirements.txt` supports — `GOOGLE_DRIVE_ENABLED` (default `False`), `GOOGLE_DRIVE_CREDENTIALS_FILE`, `GOOGLE_DRIVE_FOLDER_ID` (`:78-80`). No Google client library is pinned (no `google-api-python-client`, `google-auth`, `gspread`, `oauth2client`) and no file under `backend/app/` reads any of the three. Declared, referenced nowhere; the handover implications are in *Environments, Configuration & Deployment*.

### AI provider: Claude live, OpenAI parked

Both SDKs are installed; only one is wired.

| | Anthropic | OpenAI |
|---|---|---|
| Manifest | `anthropic>=0.52.0` (`backend/requirements.txt:38`) | `openai==2.9.0` (`backend/requirements.txt:35`) |
| Service module | `backend/app/services/claude_service.py` | `backend/app/services/openai_service.py` |
| Client class | `AsyncAnthropic` (`claude_service.py:13`, `:23`, `:34`) | `AsyncOpenAI` (`openai_service.py:19`, `:31`, `:42`) |
| Startup init | **Active** — `backend/app/main.py:125` | **Commented out** — `backend/app/main.py:128-130` |
| Import in `main.py` | `from .services.claude_service import ClaudeService` (`:31`) | `# from .services.openai_service import OpenAIService  # Preserved for rollback` (`:30`) |
| API key setting | `ANTHROPIC_API_KEY: str` — required (`config.py:47`) | `OPENAI_API_KEY: Optional[str] = None` — optional (`config.py:41`) |
| Model default | `ANTHROPIC_MODEL = "claude-opus-4-6"` (`config.py:48`) | `OPENAI_MODEL = "gpt-4o"` (`config.py:42`) |
| Timeout default | `ANTHROPIC_TIMEOUT = 1800.0` (`config.py:53`); client falls back to `600.0` if unset (`claude_service.py:33`) | `OPENAI_TIMEOUT = None` (`config.py:44`) |

`backend/app/services/openai_service.py:1-12` is explicit about its status and spells out the rollback recipe:

```
PRESERVED FOR ROLLBACK -- OpenAI GPT integration via Responses API.

This service has been replaced by claude_service.py (Anthropic Claude).
All downstream services now import from claude_service instead.

To re-enable OpenAI:
1. Set LLM_PROVIDER=openai in .env and uncomment OPENAI_API_KEY
2. In main.py: switch ClaudeService.initialize_client() -> OpenAIService.initialize_client()
3. In each service file: swap 'from app.services.claude_service import ...'
   back to 'from app.services.openai_service import ...'
```

`backend/app/services/claude_service.py:2-3` mirrors it: "Mirrors OpenAIService interface exactly for drop-in replacement." The rollback is therefore a manual, per-file edit. `LLM_PROVIDER` (`backend/app/config.py:55`, default `"claude"`) exists as a setting but no code branches on it at runtime — step 1 of the docstring's own recipe is a no-op on its own. Client construction and prompt mechanics are owned by *AI Layer — Claude Integration & Prompt System*.

**Gotcha:** the swap left cosmetic wreckage. Variables are still named `openai_service` while holding a `ClaudeService`: `openai_service = ClaudeService()` at `backend/app/api/upload_poc.py:239`, `:1544`, `:1698`, `:1815`, and `self.openai_service = ClaudeService()` at `backend/app/services/bba_conversation_engine.py:54`. Grepping for `openai` produces false positives; grep for `AsyncOpenAI` instead.

`anthropic` is the only entry in `requirements.txt` with a version floor and no ceiling; `resend` has no specifier at all. See *Version policy* below.

### Document generation — which library produces which deliverable

| Library | Module | Deliverable produced |
|---|---|---|
| `markdown` + `xhtml2pdf` | `backend/app/services/report_service.py` | **Diagnostic PDF report.** Markdown from the AI is converted to HTML (`:6`), styled, then rendered by `pisa` (`:10`). |
| `python-docx` | `backend/app/services/bba_report_export.py` | **BBA Word report** — module docstring: "Generates Word documents from BBA report data using python-docx". Uses `docx.oxml` XML injection at `:231`, `:338`, `:584`, `:781`, `:930` for cell shading. |
| `python-docx` + `beautifulsoup4` | `backend/app/services/sbp_report_export.py` | **Strategic Business Plan `.docx`** — "Generates professional .docx files from the assembled plan". BeautifulSoup parses HTML fragments into docx content at `:197`. |
| `python-docx` | `backend/app/services/pd_export.py` | **Position Description `.docx`** — docstring: "following the seven-section structure of the sample position descriptions". |
| `python-docx` | `backend/app/services/document_template_service.py` | **Templated documents** — "Generates documents from Word templates stored in the database" (import at `:14`). |
| `python-docx` | `backend/app/services/sbp_conversation_engine.py:102` | Lazy import for reading `.docx` inside the SBP conversation flow. |
| `openpyxl` (build from scratch) | `backend/app/services/bba_task_list_export.py` | **Phase 2 Excel Task List (Engagement Planner)** — columns `Rec #, Recommendation, Owner, Task, Advisor Hrs, Advisor, Status, Notes, Timing`; Status dropdown via `DataValidation` (`:23`); `CellIsRule` conditional formatting (`:24`); optional monthly-BBA-hours summary sheet; footer "Prepared by Benchmark Business Advisory – Confidential." |
| `openpyxl` (build from scratch) | `backend/app/services/scorecard_export.py` | **Half-Yearly Role Scorecard `.xlsx`** — single sheet: Role Purpose, Responsibilities & Outcomes, Behaviour & Leadership Expectations, Transition Milestones, Half-Yearly Summary, with per-section rating dropdowns applied by section and column letter. |
| `openpyxl` (`load_workbook` on a template) | `backend/app/services/roles_matrix_export.py` | **Roles & Responsibilities Matrix `.xlsx`** — written into a copy of the HR Planning Tool workbook "so the output keeps the exact 'Job Roles' layout, headings and formatting". |
| `openpyxl` (`load_workbook` on a template) | `backend/app/services/strategy_workbook_exporter.py` | **Strategy Workbook `.xlsx`** — loads the Strategy Workbook Template and maps extracted data to cells, "preserving all formatting, dropdowns, and data validation". |
| `python-pptx` | `backend/app/services/bba_pptx_export.py` | **Phase 3 BBA presentation `.pptx`** — branded deck generated from `bba.presentation_slides`, navy/white BBA branding matching the Word report. |
| `python-pptx` | `backend/app/services/sbp_pptx_export.py` | **Strategic Business Plan `.pptx`** — "Generates .pptx files from generated slide content". |
| `python-pptx` | `backend/app/services/sbp_conversation_engine.py:115` | Lazy import inside the SBP conversation flow. |

**Gotcha:** `xhtml2pdf` is the most defensively-coded dependency in the backend. `report_service.py` names it on 16 separate lines, all workarounds: `<colgroup>` injection so it "distributes width predictably" (`:500`), forced fixed table layout because "explicit fixed layout + colgroup prevents the xhtml2pdf negative-availWidth crash" (`:626`), and two manual hard-wrapping helpers — `_wrap_cell_text` (`:1820`) and `_pre_wrap_advisor_table_cells` (`:1908`) — because "xhtml2pdf does not reliably honour word-wrap, overflow, or soft hyphens". Changing report HTML risks a hard PDF-generation crash, not a layout wobble.

Import style is inconsistent across the exporters, which changes *when* a missing dependency surfaces. These wrap their imports in `try:` and raise a friendly "install it" message at call time: `bba_report_export.py` (`:12-16`), `document_template_service.py` (`:14`), `bba_task_list_export.py` (`:21-24`), `strategy_workbook_exporter.py` (`:19-22`), `bba_pptx_export.py` (`:16-20`). These import at module top level and fail at import time instead: `pd_export.py` (`:13-15`), `sbp_report_export.py` (`:10-16`), `sbp_pptx_export.py` (`:10-13`), `scorecard_export.py` (`:18-21`), `roles_matrix_export.py` (`:15-17`).

### Email

`resend` is the only email transport: `backend/app/services/email_service.py:5` imports it, and `resend.api_key` is assigned per-send rather than once at import. The two templates, their triggers and their failure behaviour belong to *Core Domain Modules*.

The stack-level point is what is *not* installed. `backend/app/config.py:71-75` retains five SMTP settings — `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` — under the comment "Email (Gmail SMTP — legacy, unused)". No SMTP library is pinned and nothing under `backend/app/` reads them. There is also a stray `FROM_EMAIL: Optional[str] = None` (`:68`), distinct from `RESEND_FROM_EMAIL` (`:66`).

### Frontend

**Build.** `frontend/vite.config.ts:8-9` reads `VITE_API_BASE_URL` through `loadEnv` and uses it as the dev-proxy target for both `/api` (`:17-21`) and `/files` (`:22-26`), falling back to `http://localhost:8000`. The dev server binds `host: "::"` on port **8080** (`:13-14`) — which is why `settings.FRONTEND_URL` defaults to `http://localhost:8080` (`backend/app/config.py:35`) and why 8080 is in the backend CORS allowlist (`backend/app/main.py:73`, `:77`). The `@` alias resolves to `./src` (`vite.config.ts:32`) and is mirrored in `frontend/tsconfig.json`, `frontend/tsconfig.app.json` and `frontend/components.json`. The proxy entries are near-dead in practice — every module but one bypasses them with an absolute origin; see *Frontend Architecture*.

**Gotcha:** `allowedHosts: ["*"]` (`frontend/vite.config.ts:15`) disables Vite's DNS-rebinding host check on the dev server.

**TypeScript strictness is effectively off.** `frontend/tsconfig.app.json` sets `strict: false`, `noImplicitAny: false`, `noUnusedLocals: false`, `noUnusedParameters: false`, `noFallthroughCasesInSwitch: false`; the root `frontend/tsconfig.json` additionally sets `strictNullChecks: false` and `allowJs: true`. Only `frontend/tsconfig.node.json` — which covers `vite.config.ts` alone — has `strict: true`. ESLint compounds it: `"@typescript-eslint/no-unused-vars": "off"` at `frontend/eslint.config.js:23`.

**No typecheck in the build.** `frontend/package.json` scripts are exactly `dev` (`vite`), `build` (`vite build`), `build:dev` (`vite build --mode development`), `lint` (`eslint .`), `preview` (`vite preview`). `vite build` with the SWC plugin strips types without checking them, and there is no `tsc --noEmit` step anywhere. Type errors ship, and unreferenced modules are never compiled at all — which is the only reason a broken, unrouted Help page does not fail the build (*Frontend Architecture*).

**Entry point.** `frontend/index.html` is minimal (root div + `/src/main.tsx`) but carries a hardcoded `<link rel="canonical" href="https://trinity.app" />` plus SEO/OG tags and `<meta name="twitter:site" content="@TrinityPlatform" />`. `frontend/src/main.tsx:29-48` monkey-patches `window.fetch` globally: it decodes the `auth_token` JWT with native `atob`, and if `exp` has passed it clears the token, dispatches an `auth:token-expired` event, and returns a synthetic 401 without hitting the network. A capture-phase `document` click listener at `:53-59` is a second layer for UI-only interactions. Know this before debugging any network behaviour.

#### Overlapping responsibilities

| Overlap | What's actually used |
|---|---|
| **Redux Toolkit vs TanStack Query** (server state) | **Redux Toolkit wins outright.** `@tanstack/react-query` appears in exactly one file — `frontend/src/App.tsx:4` (import), `:45` (`new QueryClient()`), `:121`/`:131` (provider). There is not a single `useQuery`, `useMutation` or `useQueryClient` call anywhere in `frontend/src`, and no `createApi` (RTK Query is unused too). All server state flows through `createAsyncThunk`, present in all 17 files in `frontend/src/store/slices/` and registered at `frontend/src/store/index.ts:24-40`. The provider is inert scaffolding from the Lovable starter. |
| **Two toast systems** | `sonner` (45 files) is the working one. A second Radix-based `<Toaster />` from `@/components/ui/toaster` is mounted next to `<Sonner />` at `frontend/src/App.tsx:124-125`. Two independent toast stacks can render simultaneously. |
| **`clsx` vs `tailwind-merge`** | Not a conflict — both used together inside the single `cn()` helper in `frontend/src/lib/utils.ts`. |
| **Radix vs shadcn/ui** | Not a conflict — shadcn/ui is vendored source wrapping the Radix primitives; only Radix is an npm dependency. |
| **`fetch` vs an HTTP client** | No `axios` in `frontend/package.json` or `frontend/src`. Everything uses native `fetch` (e.g. `frontend/src/lib/clientFetcher.ts:4` reads `import.meta.env.VITE_API_BASE_URL`), which is what makes the `main.tsx` monkey-patch effective globally. |

**Naming trap:** the Redux slice files are named `*Reducer.ts`, not `*Slice.ts`, but they contain `createSlice` calls and are imported into `frontend/src/store/index.ts` under names like `engagementReducer`. Searching for `store/slices/*Slice.ts` finds nothing.

#### Package managers

Both lockfiles are committed and tracked:

```
frontend/bun.lockb          201,126 bytes   mtime 2025-12-09   (Bun)
frontend/package-lock.json  251,871 bytes   mtime 2025-12-17   (npm, lockfileVersion 3)
frontend/package.json         2,865 bytes   mtime 2025-12-10
```

`bun.lockb` predates the last `package.json` edit while `package-lock.json` postdates it, so the two are not in sync and `bun.lockb` is stale relative to the current manifest. Whichever tool a developer reaches for produces a different `node_modules`. There is no `packageManager` field in `frontend/package.json`, and no `.npmrc` or `bunfig.toml` to arbitrate. Pick one, delete the other, record the choice.

### Version policy

**Backend: exact pins, two holes.** Every line in `backend/requirements.txt` uses `==` except two: `anthropic>=0.52.0` (`:38`, floor only) and `resend` (`:64`, no specifier at all). The `==` pins reproduce a fixed direct-dependency set; the two loose entries drift, so any rebuild picks up whatever Anthropic and Resend published that day. Since the Anthropic SDK is the backbone of every AI feature, a breaking change in `AsyncAnthropic` or the Messages API surface would land on the next deploy with no code change and no lockfile diff to explain it. There is no `pip freeze` lockfile, no hashes and no `constraints.txt`, so even the `==` pins do not lock transitive dependencies — which is how `httpx` ends up imported by three modules while absent from the manifest. `backend/requirements-dev.txt` layers `-r requirements.txt` plus `pytest==8.3.4`, so dev and prod share one source of truth for runtime deps.

**Frontend: caret ranges.** Every entry in `frontend/package.json` uses `^`, permitting any semver-minor/patch upgrade. Reproducibility rests entirely on the lockfile — and there are two, disagreeing. `npm ci` against `package-lock.json` is currently the only deterministic install path in the repo; `npm install` or `bun install` resolve fresh versions within the ranges.

**Net position:** the backend is nearly reproducible but has a live drift hole at its most critical dependency; the frontend is reproducible only if everyone agrees to use `npm ci`, which nothing in the repo enforces.

### The stray file `backend/=0.52.0`

Read in full: 3,535 bytes of captured pip stdout — not source, not config.

```
Collecting anthropic
  Downloading anthropic-0.86.0-py3-none-any.whl.metadata (3.0 kB)
...
Successfully installed annotated-types-0.7.0 anthropic-0.86.0 anyio-4.12.1 ...
```

The cause is a shell-quoting accident. Someone ran the equivalent of:

```
pip install anthropic >=0.52.0
```

In PowerShell and cmd, `>` is the output-redirection operator, so the shell consumed `>=0.52.0` as a redirect target and created a file literally named `=0.52.0` in `backend/`, into which pip's log was written. pip therefore saw only `anthropic` with no specifier and resolved the newest release, `0.86.0`. The log's own text shows the resolution happened against the global CPython 3.12 install (`...\Programs\Python\Python312\lib\site-packages`), not the project venv. The correct invocation quotes the specifier: `pip install "anthropic>=0.52.0"`.

The file is committed — `git ls-files backend/=0.52.0` returns it. Nothing imports or reads it. It is safe to delete; the real fix is to pin `anthropic` properly in `requirements.txt`. Other stray tracked artefacts under `backend/` are inventoried in *Operations, Diagnostics & Troubleshooting*.

### Version-of-record quick reference

Where the manifest is loose, the gitignored `backend/venv/Lib/site-packages` shows what was actually resolved on the dev machine:

| Package | Manifest says | venv holds |
|---|---|---|
| `anthropic` | `>=0.52.0` | `0.86.0` |
| `resend` | *(unspecified)* | `2.30.1` |
| `openai` | `==2.9.0` | `2.9.0` |
| `fastapi` | `==0.123.7` | `0.123.7` |
| `fastapi-cli` | *(via `fastapi[standard]`)* | `0.0.16` |
| `fastapi-cloud-cli` | *(via `fastapi[standard]`)* | `0.6.0` |
| `fastapi-cors` | `==0.0.6` | `0.0.6` (installed, unused) |

These are dev-machine observations, not a production manifest — evidence of intent, not a deployment guarantee.

---

## 5. System Architecture

Trinity Platform is two deployables: a FastAPI + SQLAlchemy backend against a single PostgreSQL database, and a Vite-built React 18 SPA served as static assets that calls the backend over HTTP. There is no third process. Read the next subsection before anything else in this document — several later sections assume it.

### How background work executes

There is no worker tier, no broker and no scheduler. Everything runs inside the API process.

**One endpoint defers work.** `POST /api/diagnostics/{diagnostic_id}/submit` is the only route in the codebase that calls `background_tasks.add_task` — `backend/app/api/diagnostics.py:499-501`, dispatching `_run_pipeline` (`backend/app/tasks/diagnostic_tasks.py:73`). It flips the diagnostic to `processing`, commits, and returns the row immediately; the AI pipeline then runs on the same event loop after the response has been sent. `backend/app/api/upload_poc.py:30` imports `BackgroundTasks` but never uses it.

**Every other AI surface blocks the HTTP request for the whole model call.** Roles Matrix extraction and generation, PD and Scorecard generation, Strategy Workbook steps, Strategic Business Plan turns, BBA conversation turns and diagnostic report regeneration all `await` the Anthropic call inside the handler and return only when the model has finished. With `ANTHROPIC_TIMEOUT` defaulting to `1800.0` (`backend/app/config.py:53`), a single request can legitimately hold a connection open for thirty minutes. This is why the submit handler sets `Connection: keep-alive` and `Keep-Alive: timeout=1800, max=100` on its own response (`backend/app/api/diagnostics.py:469-470`), and why any proxy or load balancer in front of the API needs a read timeout to match.

**Consequences of running in-process:**

- Deferred work shares the API process's memory, event loop, database pool and Anthropic client. A background pipeline and a foreground request compete for the same twenty pooled connections.
- A restart, a deploy, a crash or an autoscale event strands in-flight work. The process dies mid-pipeline and the diagnostic row stays at `processing`.
- **There is no automatic recovery.** Nothing at FastAPI startup sweeps stale rows, and the shutdown hook (`backend/app/main.py:155-160`) only logs — it does not drain in-flight tasks. A stranded diagnostic must be reset by hand, via `POST /api/diagnostics/{id}/cancel` or SQL.
- Concurrency is bounded only by the event loop. Nothing limits how many pipelines run at once.

The operational view — how to spot a stuck run, what to check, what to reset — belongs to *Operations, Diagnostics & Troubleshooting*. What each pipeline step computes belongs to *Diagnostic Engine*.

**Gotcha:** `_run_pipeline` lives in a module that imports Celery at module scope (`backend/app/tasks/diagnostic_tasks.py:14-18`), and `backend/app/api/diagnostics.py:500` imports `_run_pipeline`, so **the `celery` package must be installed for the API to serve a diagnostic submit** even though no worker exists. Removing the `celery`/`redis` pins requires moving `_run_pipeline` out of that module first. See *Handover Checklist & Open Questions*.

**Gotcha:** the same module carries two error paths that can never fire. `except SoftTimeLimitExceeded` (`:217-231`) needs a worker to raise it, so **no timeout flips a stuck diagnostic to `failed`** — a hung Claude call holds `processing` until `ANTHROPIC_TIMEOUT` expires and the generic `except Exception` (`:248-263`) catches it. `cleanup_stale_tasks` (`:34-50`), which resets `processing` rows to `draft`, is bound to a worker-startup signal the API process never emits.

### Component diagram

```
                    +--------------------------------------------+
                    |  Browser - React 18 SPA                    |
                    |  main.tsx : patched window.fetch (JWT exp) |
                    |  App.tsx  : Redux > RQ > Auth > Router     |
                    |  localStorage["auth_token"]                |
                    +---------------------+----------------------+
                                          |
                    56 files each declare their own
                    const API_BASE_URL = import.meta.env
                        .VITE_API_BASE_URL || <fallback>
                    header: Authorization: Bearer <jwt>
                                          |
            +-----------------------------+-----------------------------+
            |                                                           |
   AuthContext.tsx:18 only, fallback ''         all 55 others, fallback
   (relative -> hits the dev proxy)             'http://localhost:8000'
            |                                                           |
  +---------v-------------------+                                       |
  | Vite dev server :8080       |                                       |
  | vite.config.ts proxy:       |                                       |
  |   /api   -> apiTarget       |                                       |
  |   /files -> apiTarget       |                                       |
  | `npm run build` emits plain |                                       |
  | static assets - no proxy    |                                       |
  +---------+-------------------+                                       |
            +-----------------------------+-----------------------------+
                                          |
                    +---------------------v----------------------+
                    |  FastAPI app  (backend/app/main.py:46)     |
                    |  :8000  docs /api/docs  redoc /api/redoc   |
                    |                                            |
                    |  [outer] CORSMiddleware                    |
                    |  [inner] SessionMiddleware "trinity_session|
                    |    |                                       |
                    |    +-- api/      routers + auth deps       |
                    |    +-- services/ business logic            |
                    |    +-- models/   SQLAlchemy ORM            |
                    |    +-- schemas/  Pydantic in/out           |
                    |    +-- tasks/    _run_pipeline             |
                    |    +-- utils/file_loader.py (lru_cache)    |
                    |   (../tool_service/  via sys.path hack)    |
                    |                                            |
                    |  StaticFiles mount: /files -> backend/files|
                    |  BackgroundTasks: in-process, same event   |
                    |  loop, one caller only                     |
                    +--+--------+---------+---------+---------+--+
                       |        |         |         |         |
      Depends(get_db)  |        |         |         |         |
   database.py:98      |        |         |         |         |
                       |        |         |         |         |
            +----------v--+  +--v-------+ +-v------+ +v--------------------+
            | SQLAlchemy  |  | Auth0    | | Claude | | Resend HTTPS        |
            | Engine      |  | HTTPS    | | HTTPS  | | (email_service.py)  |
            | pool_size 10|  | OIDC +   | | Msgs + | +---------------------+
            | overflow 10 |  | JWKS +   | | Files  |
            | pre_ping    |  | Mgmt API | | API    | +---------------------+
            +------+------+  +----------+ +--------+ | Local filesystem    |
                   |                                 | TWO disjoint roots: |
            +------v-----------------+               | backend/files/**    |
            | PostgreSQL (Render dev)|               |   SERVED at /files  |
            | TLS required off-box   |               | backend/uploads/**  |
            +------------------------+               |   served by nothing |
                                                     +---------------------+
```

Every outbound arrow is traceable: Auth0 OIDC client registration in `backend/app/services/auth_service.py:20` (Authlib `OAuth().register`), JWKS fetch in `backend/app/utils/auth.py:24`, Auth0 Management API in `backend/app/services/auth0_management.py`, Anthropic `AsyncAnthropic` client in `backend/app/services/claude_service.py:29`, Resend (`import resend`) in `backend/app/services/email_service.py`, filesystem in `backend/app/services/file_service.py:50` and `backend/app/utils/file_loader.py:13`.

**The frontend-to-backend arrow is not uniform.** `VITE_API_BASE_URL` is not read once and shared; it is re-read in 56 separate source files, each with a hand-copied `const API_BASE_URL`. Fifty-five of them fall back to the absolute `'http://localhost:8000'` (`frontend/src/pages/Login.tsx:7`, `frontend/src/lib/clientFetcher.ts:4`, `frontend/src/store/slices/tasksReducer.ts:67`, and so on). One does not: `frontend/src/context/AuthContext.tsx:18` falls back to `''`. With the variable unset — the default dev setup — **auth calls go same-origin through the Vite proxy while every other call goes direct to `localhost:8000` and relies on the CORS allow-list.** The two halves of the app talk to different origins. The `/api` and `/files` proxy entries at `frontend/vite.config.ts:16-27` are therefore exercised only by `AuthContext`'s calls; every other module bypasses the proxy.

**Gotcha:** when `VITE_API_BASE_URL` *is* set, `frontend/vite.config.ts:9` reuses that same variable as the proxy `target`. One variable is simultaneously the browser-facing base URL and the server-side proxy target; the two can only agree by coincidence.

### Configuration

All settings come from one Pydantic-Settings class, `backend/app/config.py:9`, instantiated once as the module-level `settings` (`backend/app/config.py:102`). `env_file = ".env"`, `case_sensitive = True` (`:96-98`). A field with no default is **required at import time** — the process will not start without it, and ten fields are in that state. The full variable-by-variable table, defaults and deployment values are owned by *Environments, Configuration & Deployment*.

Three architectural facts about that class matter here:

- **`SECRET_KEY` does two unrelated jobs** — Starlette session-cookie signing (`backend/app/main.py:58`) and HS256 application JWT signing/verification (`backend/app/utils/auth.py:112`). Rotating it invalidates every live session *and* every issued email/password token at once.
- **`DATABASE_URL` drives more than the DSN.** Its host determines whether TLS is forced (`backend/app/database.py:16`, `:28-30`).
- **Several declared blocks have no reader.** `OPENAI_*`, `SMTP_*`, `CELERY_*`/Redis and `GOOGLE_DRIVE_*` (`backend/app/config.py:77-80`) are all declared and referenced by no live code path. They are listed in *Handover Checklist & Open Questions*; do not read them as features.

### Backend layering contract

The backend is `backend/app/` — `api/`, `services/`, `models/`, `schemas/`, `utils/`, `tasks/` — plus one package outside it, `backend/tool_service/`, described below. Four of those packages carry a rule.

| Layer | Directory | Owns | Must not |
| --- | --- | --- | --- |
| API | `backend/app/api/` | HTTP verbs/paths, status codes, `Depends(get_db)`, `Depends(get_current_user)`, permission checks, `HTTPException` | Contain multi-step domain logic; be imported by services |
| Schemas | `backend/app/schemas/` | Pydantic request bodies and `response_model` shapes; `ConfigDict(from_attributes=True)` for ORM projection | Touch the DB session |
| Services | `backend/app/services/` | Business logic. Uniform shape: `class XService: def __init__(self, db: Session)` plus a module-level `get_x_service(db)` factory | Raise HTTP-shaped errors as their primary contract (several do anyway) |
| Models | `backend/app/models/` | SQLAlchemy declarative classes bound to `Base` from `backend/app/database.py:95`; column `comment=` strings carry the allowed status/priority values | Import services or api |

The service layer does **not** create its own session. It receives the request-scoped `Session` the router got from `Depends(get_db)` and stores it on `self.db` — `backend/app/services/file_service.py:42`, `backend/app/services/strategy_workbook_service.py:26`, `backend/app/services/chat_service.py:59`, `backend/app/services/diagnostic_service.py:104`, and eleven more with the identical `def __init__(self, db: Session)` signature. Each pairs with a factory (`get_file_service`, `get_diagnostic_service`, …) that is a one-line constructor call. The one exception is `_run_pipeline`, which builds its own `SessionLocal()` because the request session is closed by the time it runs (`backend/app/tasks/diagnostic_tasks.py:87`).

`backend/app/schemas/__init__.py` re-exports schemas for only five domains (user, engagement, diagnostic, task, note); every other router imports its schemas straight from the module — `from ..schemas.firm import ...`. There is no single schema registry.

**A request through all four layers** — `POST /api/files/upload`:

1. `backend/app/api/files.py:27` declares the route and the two dependencies.
2. FastAPI resolves `get_db` (`backend/app/database.py:98`) and `get_current_user` (`backend/app/utils/auth.py:187`).
3. The router does HTTP-only work: caps the batch at `MAX_UPLOAD_FILES = 20` (`backend/app/api/files.py:24`, enforced at `:53`) and parses `diagnostic_id` out of the multipart form.
4. It builds the service with the *same* session: `file_service = get_file_service(db)` (`backend/app/api/files.py:59`).
5. `FileService.upload_files` (`backend/app/services/file_service.py:173`) loops over each file into `upload_file` (`:75`), which validates the extension against `ALLOWED_EXTENSIONS` (`:28-37`) and the 10 MB `MAX_FILE_SIZE` (`:40`), writes bytes to `backend/files/uploads/diagnostic/<id>/<uuid>.<ext>` (`:105`) or `backend/files/uploads/users/<user_id>/…` (`:108`), constructs the `Media` model, `flush()`es to get the PK (`:141`), ships the file to Anthropic via `claude_service.upload_file` (`:148`), stamps `llm_file_id` / `llm_provider` / `llm_uploaded_at` plus the legacy `openai_*` mirrors (`:156-162`), then `commit()`s (`:168`).
6. The router serialises with `media.to_dict()` and returns 201.

**Gotcha:** `files.py` illustrates the layering rule and also where it leaks — after the service has already committed, the router itself queries `Diagnostic`, mutates `diagnostic.media`, and calls `db.commit()` again at `backend/app/api/files.py:90`. Two commits on the same session in one request.

**Gotcha:** a failed Anthropic upload is swallowed (`backend/app/services/file_service.py:164-166`) and the `Media` row is committed anyway with `llm_file_id` null. Downstream AI steps see a file record with no provider handle.

### Middleware order

`backend/app/main.py:56` adds `SessionMiddleware`, then `backend/app/main.py:67` adds `CORSMiddleware`. Starlette's `add_middleware` does `self.user_middleware.insert(0, ...)` (`backend/venv/Lib/site-packages/starlette/applications.py:126`), so **the last middleware added ends up outermost**. The runtime stack is:

```
request -> CORSMiddleware -> SessionMiddleware -> router -> endpoint
```

**Gotcha:** the comment at `backend/app/main.py:55` — "IMPORTANT: SessionMiddleware must be added BEFORE CORS to ensure cookies work" — describes source order and reads as if it described execution order. It does not. CORS is outermost at runtime.

Consequences, in order of how often they bite:

- CORS being outermost means the browser preflight `OPTIONS` is answered before any session-cookie work happens, and `Access-Control-Allow-*` headers are attached to *every* response coming back out, including the `Set-Cookie` response from the session layer and errors raised deeper in the stack. Reversing the two `add_middleware` calls would put CORS inside the session layer, and any response short-circuited above it would reach the browser without CORS headers — surfacing as an opaque network failure rather than a readable status.
- `allow_credentials=True` (`backend/app/main.py:80`) forbids `"*"`, which is why the origin list is enumerated: `settings.FRONTEND_URL` plus eight fixed entries — `http://localhost:` and `http://127.0.0.1:` on ports `5173`, `3000`, `8080`, `8000` (`backend/app/main.py:69-79`). `allow_methods` and `allow_headers` are both `["*"]`.
- `SessionMiddleware` must exist at all because Authlib stores the OAuth `state` in `request.session` during `authorize_redirect` (`backend/app/api/auth.py:62`) and reads it back in `authorize_access_token` in the callback (`backend/app/api/auth.py:89`). `get_current_user` also falls back to `request.session.get('user')` when there is no bearer token (`backend/app/utils/auth.py:218`), and `GET /api/auth/check` reads it directly (`backend/app/api/auth.py:258`).
- Cookie settings: name `trinity_session`, `max_age = 3600 * 24 * 7` (7 days), `same_site="lax"`, `https_only` on for every environment except `APP_ENV == "development"` (`backend/app/main.py:59-62`).

### Router mount table

Prefixes are declared in two different places. The effective path is always under `/api`, but where the `/api` comes from is not consistent. Twenty-one routers, in `include_router` order (`backend/app/main.py:86-107`).

| Router module | Prefix declared in router | Added at `include_router` | Effective mount | Tag |
| --- | --- | --- | --- | --- |
| `backend/app/api/auth.py:28` | `/api/auth` | — | `/api/auth` | `authentication` |
| `backend/app/api/diagnostics.py:44` | `/diagnostics` | `prefix="/api"` | `/api/diagnostics` | `diagnostics` |
| `backend/app/api/files.py:22` | `/files` | `prefix="/api"` | `/api/files` | `files` |
| `backend/app/api/upload_poc.py:97` | `/api/poc` | — | `/api/poc` | `bba` |
| `backend/app/api/engagements.py:48` | `/api/engagements` | — | `/api/engagements` | `engagements` |
| `backend/app/api/note.py:23` | `/api/notes` | — | `/api/notes` | `notes` |
| `backend/app/api/tasks.py:29` | `/api/tasks` | — | `/api/tasks` | `tasks` |
| `backend/app/api/settings.py:13` | `/api/settings` | — | `/api/settings` | `settings` |
| `backend/app/api/chat.py:25` | `/api/chat` | — | `/api/chat` | `chat` |
| `backend/app/api/users.py:41` | `/api/users` | — | `/api/users` | `users` |
| `backend/app/api/adv_client.py:20` | `/api/advisor-client` | — | `/api/advisor-client` | `advisor-client` |
| `backend/app/api/firms.py:52` | `/api/firms` | — | `/api/firms` | `firms` |
| `backend/app/api/subscriptions.py:24` | `/api/subscriptions` | — | `/api/subscriptions` | `subscriptions` |
| `backend/app/api/dashboard.py:24` | `/api/dashboard` | — | `/api/dashboard` | `dashboard` |
| `backend/app/api/strategy_workbook.py:38` | `/strategy-workbook` | `prefix="/api"` | `/api/strategy-workbook` | `strategy-workbook` |
| `backend/app/api/strategic_business_plan.py:46` | `/strategic-business-plan` | `prefix="/api"` | `/api/strategic-business-plan` | `strategic-business-plan` |
| `backend/app/api/program_guide.py:27` | `/program-guide` | `prefix="/api"` | `/api/program-guide` | `program-guide` |
| `backend/app/api/program_deliverable.py:38` | `/deliverables` | `prefix="/api"` | `/api/deliverables` | `deliverables` |
| `backend/app/api/ai_field_privacy.py:21` | `/api/ai-field-privacy` | — | `/api/ai-field-privacy` | `ai-field-privacy` |
| `backend/app/api/roles_matrix.py:40` | `/api/roles-matrix` | — | `/api/roles-matrix` | `roles-matrix` |
| `backend/app/api/pd_scorecard.py:44` | `/api/pd-scorecard` | — | `/api/pd-scorecard` | `pd-scorecard` |

Six routers (`diagnostics`, `files`, `strategy_workbook`, `strategic_business_plan`, `program_guide`, `program_deliverable`) declare a bare prefix and get `/api` bolted on at `backend/app/main.py:88-104`; the other fifteen hard-code `/api/...` in the `APIRouter(...)` call and are mounted with no prefix. Three lines in `main.py` carry a trailing comment reading "already has /api prefix" (`:90`, `:106`, `:107`) — the inconsistency tracked by hand.

**Gotcha:** reading a route path from a router file alone is not enough. `@router.get("/{diagnostic_id}")` in `diagnostics.py` is `GET /api/diagnostics/{id}` at runtime, not `GET /diagnostics/{id}`. The docstring at `backend/app/api/diagnostics.py:449` tells the frontend to poll `GET /diagnostics/{diagnostic_id}` — that path does not exist.

A second, unrelated import inconsistency: `backend/app/api/__init__.py` re-exports only six routers (`auth_router`, `engagements_router`, `notes_router`, `tasks_router`, `settings_router`, `adv_client_router`); the remaining fifteen are imported straight from their modules in `main.py:12-28`.

Two unprefixed endpoints live directly on the app:

| Method | Path | Source | Returns |
| --- | --- | --- | --- |
| `GET` | `/` | `backend/app/main.py:136` | `{"message": "Trinity Platform API", "version": "1.0.0", "status": "running"}` |
| `GET` | `/health` | `backend/app/main.py:146` | `{"status": "healthy", "environment": settings.APP_ENV}` |

Neither has an auth dependency. `/health` performs no database check — it returns 200 while Postgres is unreachable.

OpenAPI is served at the FastAPI defaults except for the doc UIs: `docs_url="/api/docs"`, `redoc_url="/api/redoc"` (`backend/app/main.py:50-51`). `openapi_url` is not overridden, so the schema is at `/openapi.json`, outside `/api`.

### The package outside `app/`: `backend/tool_service/`

`backend/tool_service/tool_selector.py` (84 lines) is the only Python package under `backend/` that is not inside `app/`. It is reached through a `sys.path` mutation performed inside a request handler, from exactly one call site:

```python
backend_path = Path(__file__).parent.parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from tool_service.tool_selector import create_tool_for_engagement
```
`backend/app/api/engagements.py:195-202`

`create_tool_for_engagement(db, engagement_id, tool_type, created_by_user_id)` (`backend/tool_service/tool_selector.py:13`) verifies the engagement exists, then dispatches on `tool_type`:

| `tool_type` | Behaviour |
| --- | --- |
| `diagnostic`, `value_builder`, `sale_ready` | `get_diagnostic_service(db).create_diagnostic(...)` (`:43-48`) |
| `kpi_builder` | `_create_kpi_builder` (`:56`) — returns a placeholder dict, writes nothing; the model does not exist |
| anything else | returns `None` silently (`:53`) |

Nothing else in the repo references the package and no test covers it. Folding it into `backend/app/services/` would remove the path hack.

**Gotcha:** the call site wraps it in `try/except Exception` and only `print`s a warning on failure (`backend/app/api/engagements.py:211-213`), so engagement creation succeeds with no tool attached and no error surfaced to the client.

### Static mounts and the two storage roots

```python
base_dir  = Path(__file__).resolve().parents[1]   # backend/
files_dir = base_dir / "files"
files_dir.mkdir(exist_ok=True)
app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")
```
`backend/app/main.py:111-115`

There are **two disjoint filesystem roots** and only one of them is served over HTTP.

| Root | Written by | Reachable at `/files/...`? |
| --- | --- | --- |
| `backend/files/` — `prompts/`, `templates/`, `program_guide/`, `uploads/{diagnostic,users,sbp,strategy-workbook}`, `exports/sbp` | diagnostic and profile uploads (`backend/app/services/file_service.py:105`, `:108`), SBP (`backend/app/api/strategic_business_plan.py:49`), Strategy Workbook (`backend/app/api/strategy_workbook.py:387-390`), SBP exporters (`backend/app/services/sbp_report_export.py:22`, `backend/app/services/sbp_pptx_export.py:19`), plus the repo checkout | **Yes** — `app.mount("/files", …)`, no auth dependency |
| `settings.UPLOAD_DIR` → `backend/uploads/{bba,roles-matrix,pd-scorecard}` | BBA POC (`backend/app/api/upload_poc.py:100-101`), Roles Matrix (`backend/app/api/roles_matrix.py:54-59`), PD Scorecard (`backend/app/api/pd_scorecard.py:78-83`) | **No** — no mount covers it |

`UPLOAD_DIR` is resolved the same way in all three: if the setting is relative it is anchored at `backend/`, then a per-tool subdirectory is appended. Files under it leave the system only through authenticated routes — for the BBA POC, `GET /api/poc/{project_id}/files/{filename:path}` (`backend/app/api/upload_poc.py:387`) with `Depends(get_current_user)`.

Everything under `backend/files/`, by contrast, is anonymously readable over HTTP:

| Path under `backend/files/` | Written by | Exposed at |
| --- | --- | --- |
| `prompts/*.md` (system, category, scoring, advice, admin-mode prompts) | repo checkout | `/files/prompts/...` |
| `prompts/bba/`, `sale-ready/`, `value-builder/`, `roles-matrix/`, `pd-scorecard/`, `strategic-business-plan/`, `strategy-workbook/` | repo checkout | `/files/prompts/<dir>/...` |
| `uploads/diagnostic/<diagnostic_id>/<uuid>.<ext>` | `backend/app/services/file_service.py:105` | `/files/uploads/diagnostic/...` |
| `uploads/users/<user_id>/...` | `backend/app/services/file_service.py:108` | `/files/uploads/users/...` |
| `uploads/sbp/` | `backend/app/api/strategic_business_plan.py:49` | `/files/uploads/sbp/...` |
| `uploads/strategy-workbook/<workbook_id>/Strategy_Workshop_Workbook.xlsx` | `backend/app/api/strategy_workbook.py:387-390` | `/files/uploads/strategy-workbook/...` |
| `exports/sbp/` (.docx and .pptx) | `backend/app/services/sbp_report_export.py:22`, `backend/app/services/sbp_pptx_export.py:19` | `/files/exports/sbp/...` |
| `templates/`, `program_guide/`, `scoring_map.json`, `task_library.json`, `diagnostic-surveyjs.json` | repo checkout | `/files/...` |
| `Benchmark_BBA_Diagnostic_Report_Full_Workflow (1).txt` | repo checkout (stray artefact) | `/files/...` |

**Security implication:** client-uploaded financial documents, generated SBP reports and PowerPoints, and the full proprietary prompt library are served to anyone with the URL. Filenames under `uploads/diagnostic/` are UUIDs, so that is security-by-obscurity, not access control — and the URL is *known* for anything the app hands out: profile pictures are stored on the user row as `/files/<rel_path>` (`backend/app/api/settings.py:131`) and are public by construction. Prompt files, the JSON scoring maps, the sample SBP exports and the stray `.txt` at the root of `backend/files/` all have guessable names.

### Startup and shutdown

```python
@app.on_event("startup")
async def startup_event():
    ClaudeService.initialize_client()
```
`backend/app/main.py:118-132`

`ClaudeService.initialize_client()` (`backend/app/services/claude_service.py:29`) builds the single class-level `AsyncAnthropic` client with an explicit `httpx.Timeout(connect=10.0, read=ANTHROPIC_TIMEOUT or 600.0, write=10.0, pool=10.0)` and `max_retries=1`. Because `ANTHROPIC_TIMEOUT` defaults to `1800.0` (`backend/app/config.py:53`), the effective read timeout out of the box is 30 minutes, not 10. It is idempotent (`if cls._client is None`, `:32`). Every call site reaches it through the `client` property (`:48`), which raises `RuntimeError` rather than lazily constructing one if startup never ran — so a unit test or script that imports a service without booting the app fails loudly instead of silently opening a second client. The client's internals are owned by *AI Layer — Claude Integration & Prompt System*.

The shutdown hook (`backend/app/main.py:155-160`) only logs. Nothing drains in-flight `BackgroundTasks`, closes the SQLAlchemy pool, or closes the Anthropic client.

`from . import models  # noqa: F401` at `backend/app/main.py:32` imports `backend/app/models/__init__.py`, which pulls 25 model classes from 20 modules so they attach themselves to `Base.metadata`. The inline comment says this is "for Alembic".

**Gotcha:** that comment is misleading. `backend/alembic/env.py:15-18` does its own `from app.database import Base` / `from app import models` and sets `target_metadata = Base.metadata` (`:31`) — Alembic never loads `main.py`. What the `main.py` import actually buys you is runtime correctness: without it, string-based relationships such as `relationship("Engagement", back_populates="tasks")` (`backend/app/models/task.py:67`) would fail to resolve for any model class no router happened to import. Do not delete it on the grounds that "Alembic has its own import".

### `get_db` and the session lifecycle

`backend/app/database.py`:

| Setting | Value | Line | Why |
| --- | --- | --- | --- |
| `pool_pre_ping` | `True` | `:35` | Revalidate a pooled connection before handing it out |
| `pool_size` | `10` | `:36` | Keep connections warm so DNS is re-resolved rarely |
| `max_overflow` | `10` | `:37` | Hard ceiling of 20 concurrent connections per process |
| `pool_recycle` | `1800` | `:38` | Recycle before the hosted Postgres idle cutoff |
| `pool_timeout` | `30` | `:39` | Wait for a free connection, then raise |
| `echo` | `False` | `:41` | SQL logging off; also silenced via `logging.getLogger('sqlalchemy.engine')` at `backend/app/main.py:41-43` |
| `connect_args` | `connect_timeout=10`, `keepalives=1`, `keepalives_idle=30`, `keepalives_interval=10`, `keepalives_count=5` | `:21-27` | TCP keepalives stop NAT/firewall from silently dropping idle sockets |
| `sslmode` | `require` when the host is not local | `:28-30` | Host classified local by `make_url(DATABASE_URL).host in (None, "localhost", "127.0.0.1", "::1")` (`:16`); an explicit `sslmode` in the DSN query wins |

A `do_connect` event listener (`backend/app/database.py:60-88`) retries brand-new DBAPI connections up to `_CONNECT_RETRIES = 3` times with `_CONNECT_BACKOFF = 0.5`s exponential backoff, but only when the lower-cased error text contains one of seven markers (`could not translate host name`, `name or service not known`, `temporary failure in name resolution`, `connection refused`, `connection timed out`, `server closed the connection unexpectedly`, `connection reset by peer`). Anything else — bad password, missing database — raises on the first attempt (`:75-76`). This exists because `pool_pre_ping` revalidates *pooled* connections only and does nothing when the pool has to dial fresh.

```python
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```
`backend/app/database.py:92-111`

FastAPI resolves `Depends(get_db)` once per request and caches it, so the router, `get_current_user`, and any service built with `get_x_service(db)` all share **one** `Session` and therefore one transaction. `autoflush=False` means nothing is written until an explicit `flush()` or `commit()`.

**Who commits:** whoever wants to. There is no commit-on-success wrapper. `get_db` has no `except` branch and no `rollback()` — it only closes. Both routers (`backend/app/api/tasks.py:106`, `backend/app/api/files.py:90` and `:278`, `backend/app/api/engagements.py:190` and `:210`) and services (`backend/app/services/file_service.py:168`, `backend/app/services/chat_service.py`, `backend/app/services/pd_scorecard_service.py`, `backend/app/services/bba_service.py`, and eleven others) call `commit()` directly, sometimes both within a single request.

**Gotcha:** because `get_db` never rolls back, an unhandled exception after a partial `flush()` relies on `Session.close()` discarding the transaction. That is correct SQLAlchemy behaviour, but it means a handler that catches an exception, keeps going, and later commits will persist the earlier partial writes. `backend/app/api/engagements.py:203-213` is exactly that shape: the tool-creation failure is caught and swallowed, then execution continues to the response.

### The `file_loader` caching layer

`backend/app/utils/file_loader.py` resolves everything from three class constants (`:13-15`):

```python
BASE_DIR    = Path(__file__).resolve().parent.parent.parent   # backend/
FILES_DIR   = BASE_DIR / "files"
PROMPTS_DIR = FILES_DIR / "prompts"
```

| Method | Reads | Cached | Line |
| --- | --- | --- | --- |
| `load_json(filename)` | `backend/files/<name>.json` (appends `.json` if absent) | `@lru_cache(maxsize=32)` | `:19` |
| `load_prompt(name)` | `backend/files/prompts/<name>.md` (appends `.md` if absent) | `@lru_cache(maxsize=32)` | `:46` |
| `load_diagnostic_questions()` | `diagnostic-surveyjs.json` | via `load_json` | `:71` |
| `load_scoring_map()` | `scoring_map.json` | via `load_json` | `:76` |
| `load_scoring_map_for_type(t)` | type-specific scoring JSON | `@lru_cache(maxsize=8)` | `:82` |
| `load_prompt_for_type(name, t)` | type dir, then generic fallback | `@lru_cache(maxsize=32)` | `:106` |
| `load_task_library()` | `task_library.json` | via `load_json` | `:143` |
| `clear_cache()` | clears the four `lru_cache`s | — | `:148` |

Six module-level convenience wrappers (`:157-184`) forward to the classmethods. Decorator order is `@classmethod` over `@lru_cache`, so the cache wraps the underlying function and `cls` is part of the key. Cached values are the parsed `dict` or the full file `str`, held for the life of the process.

**Dispatch on engagement type.** Both type-aware loaders take `engagement_type`, whose only two recognised values are `'sale_ready'` and `'value_builder'`:

- `load_scoring_map_for_type` (`:82`) maps to two files — `prompts/sale-ready/SCORING_MAP_COMPLETE.json` and `prompts/value-builder/SCORING_MAP_VALUE_BUILDER.json` (`:91-94`). An unrecognised type **silently falls back to the value-builder map** (`scoring_map_paths.get(engagement_type, scoring_map_paths['value_builder'])`, `:96`) and only raises `FileNotFoundError` if that file is missing too.
- `load_prompt_for_type` (`:106`) maps `sale_ready -> sale-ready/` and `value_builder -> value-builder/` (`:122-125`), checks `prompts/<type-dir>/<name>.md` first (`:129-132`), and falls back to `prompts/<name>.md` (`:135`). An unrecognised type skips the type directory entirely and goes straight to the generic prompt; if that is also missing it raises `FileNotFoundError`.

`backend/app/services/diagnostic_service.py:22-29` imports all six convenience functions and is the main consumer.

**Gotcha:** the cache is never invalidated by file mtime. Editing a prompt or scoring map on a running server has no effect until the process restarts — and because the fallback branch of `load_prompt_for_type` is inside the cached call, adding a type-specific prompt after the generic one has been read once will keep serving the generic text for the rest of the process's life. `clear_cache()` exists but is only wired for tests. Strategy Workbook makes this worse by loading all three of its prompts in the service constructor (`backend/app/services/strategy_workbook_service.py:31-33`), warming the cache on first instantiation.

**Gotcha:** four newer tools bypass `FileLoader` entirely and read prompts uncached on every call — `load_bba_prompt` (`backend/app/services/bba_conversation_engine.py:20-37`, reads `files/prompts/bba/`), `load_sbp_prompt` (`backend/app/services/sbp_conversation_engine.py:28`, reads `files/prompts/strategic-business-plan/`), `load_pd_scorecard_prompt` (`backend/app/services/pd_scorecard_engine.py:18-37`), and `load_roles_matrix_prompt` (`backend/app/services/roles_matrix_engine.py:17-36`). Two prompt-loading conventions coexist, with opposite reload semantics.

### Frontend entry points

Detail belongs to *Frontend Architecture*; the boundary-crossing facts only.

- `frontend/src/main.tsx:61` — `createRoot(document.getElementById("root")!).render(<App />)`. Before that it monkey-patches `window.fetch` (`:29-48`): `isTokenExpired` (`:7`) base64url-decodes the stored JWT payload with native `atob` and, when `exp` has passed, clears `auth_token`, dispatches an `auth:token-expired` window event, and returns a synthetic 401 `Response` without a network call. A reactive branch (`:43-46`) does the same clear-and-dispatch on any server 401. A capture-phase `document` click listener (`:53-59`) runs the same check for UI interactions that issue no fetch.
- `frontend/src/App.tsx:119-133` — provider nesting, outermost first:

```
<Provider store={store}>                 redux store: 17 slices (store/index.ts:24-40)
  <QueryClientProvider client={queryClient}>   App.tsx:45
    <AuthProvider>                       context/AuthContext.tsx
      <TooltipProvider>
        <Toaster /> <Sonner />
        <BrowserRouter>
          <AppRoutes />                  App.tsx:61
```

- Routing (`frontend/src/App.tsx:61-117`): public `/`, `/login`, `/auth/callback`, `/verify-email`; everything under `/dashboard` is wrapped in `ProtectedRoute` (`:47`), which reads `useAuth()`, renders a "Checking authentication…" div while `isLoading`, and `<Navigate to="/login" replace />` when unauthenticated. `*` falls through to `NotFound` (`:114`).
- Build: plain `vite build` (`frontend/package.json:8`) producing static assets; `build:dev` runs the same with `--mode development`. No SSR, and the backend does not serve the SPA — only `/files`.

### Request lifecycle: `POST /api/tasks`

1. **Component dispatch.** `frontend/src/components/engagement/tasks/TasksList.tsx:117` calls `await dispatch(createTask({ ...taskData, engagementId })).unwrap()`.
2. **Thunk.** `createTask` (`frontend/src/store/slices/tasksReducer.ts:217`) reads `localStorage.getItem('auth_token')`; a missing token throws inside the thunk's own `try`, so it lands in `rejectWithValue('No authentication token found')` rather than propagating. It then converts camelCase UI fields to the backend snake_case body via `mapFrontendTaskToBackend` (`:226`).
3. **Fetch.** `fetch(`${API_BASE_URL}/api/tasks`, { method: 'POST', headers: { Authorization: `Bearer <token>`, 'Content-Type': 'application/json' }, body })` (`:228-235`). `API_BASE_URL` is the file-local constant at `tasksReducer.ts:67`, one of the 55 that fall back to the absolute origin.
4. **Patched fetch.** The wrapper installed at `frontend/src/main.tsx:30` decodes the JWT payload; if `exp` has passed it clears the token, fires `auth:token-expired`, and returns a synthetic 401 without touching the network.
5. **Transport.** With the absolute fallback the browser goes direct to `http://localhost:8000`, so this is cross-origin and a preflight `OPTIONS /api/tasks` precedes it. The Vite proxy is not involved on this path.
6. **CORS.** The outermost middleware (`backend/app/main.py:67`) answers the preflight and, on the real request, checks `Origin` against the nine-entry allow-list.
7. **Session.** `SessionMiddleware` (`backend/app/main.py:56`) decodes the `trinity_session` cookie if present. Unused on this path — the bearer token wins.
8. **Routing.** The path matches `APIRouter(prefix="/api/tasks")` (`backend/app/api/tasks.py:29`) then `@router.post("")` (`:32`).
9. **Dependencies.** `get_db` opens `SessionLocal()` (`backend/app/database.py:107`), checking out a pooled connection. `get_current_user` (`backend/app/utils/auth.py:187`) reads the `Authorization` header (`:211-214`) and calls `decode_and_resolve_user` (`:89`), which tries HS256 with `SECRET_KEY` first (`:112`) and falls back to Auth0 RS256 against the cached JWKS (`:24`, cache cleared and refetched once on `kid` miss at `:46-53`), validates any impersonation session (`:136-163`), resolves the `User` row on the **same** session, and rejects deleted (`:235`) or inactive (`:241`) users with 403. Full detail in *Authentication, Authorization & Impersonation*.
10. **Validation.** The body is parsed into `TaskCreate` (`backend/app/schemas/task.py:26`). A failure here is a 422 produced before the handler body runs.
11. **Handler — existence.** `db.query(Engagement).filter(Engagement.id == task_data.engagement_id).first()`; 404 if missing (`backend/app/api/tasks.py:45-50`).
12. **Handler — authorisation.** `check_engagement_access(engagement, current_user, db=db)` (`backend/app/services/role_check.py:10`); 403 on `False` (`backend/app/api/tasks.py:53-57`). The rule set:

    | Role | Passes when |
    | --- | --- |
    | `SUPER_ADMIN`, `ADMIN` | always (`:36`) |
    | `FIRM_ADMIN` | `user.firm_id` set and `engagement.firm_id == user.firm_id` (`:40-43`) |
    | `ADVISOR` | `engagement.primary_advisor_id == user.id`, membership in `engagement.secondary_advisor_ids`, or an `AdvisorClient` row with `status == "active"` and `is_deleted == False` linking them to `engagement.client_id` (`:46-69`) |
    | `FIRM_ADVISOR` | identical to `ADVISOR` (`:72-93`) |
    | `CLIENT` | `engagement.client_id == user.id` or membership in `engagement.client_ids`; always denied when the caller passed `require_advisor=True` (`:96-105`) |
    | anything else | denied (`:107`) |

13. **Handler — referential checks.** Assigned users must exist and be active (`backend/app/api/tasks.py:60-71`; empty array → 400, unknown id → 404, inactive → 400); a supplied `diagnostic_id` must exist and belong to the same engagement (`:74-85`).
14. **ORM write.** A `Task` (`backend/app/models/task.py:12`, table `tasks`) is constructed with `created_by_user_id` forced to `current_user.id` regardless of what the client sent (`backend/app/api/tasks.py:90`), then `db.add(task)`, `db.commit()`, `db.refresh(task)` (`:105-107`). `id` comes from the Python-side `uuid.uuid4` default (`backend/app/models/task.py:20`); `created_at`/`updated_at` come from Postgres `server_default=func.current_timestamp()` (`:63-64`), which is why the `refresh()` is needed.
15. **Serialise.** `TaskResponse.model_validate(task)` (`backend/app/schemas/task.py:65`, `ConfigDict(from_attributes=True)` at `:67`) projects the ORM object; FastAPI returns 201.
16. **Teardown.** The `finally` in `get_db` (`backend/app/database.py:110-111`) closes the session and returns the connection to the pool.
17. **Response out.** Travels back through `SessionMiddleware` then `CORSMiddleware`, which attaches the `Access-Control-Allow-*` headers.
18. **Back in Redux.** The thunk checks `response.ok` (`tasksReducer.ts:237`), converts the JSON with `mapBackendTaskToFrontend` (`:243`), and the `createTask.fulfilled` case pushes the task onto `state.tasks` (`:398-401`); on failure `rejectWithValue` puts the `detail` string into `state.error` (`:402-405`).

**Gotcha:** `TaskCreate.created_by_user_id` is a **required** field (`backend/app/schemas/task.py:29`) that the handler then ignores in favour of the authenticated user (`backend/app/api/tasks.py:90`). Clients must send a value, any value they send is discarded, and omitting it produces a 422 for a field with no effect. `TaskCreateFromDiagnostic` (`backend/app/schemas/task.py:39`) has the same required field.

**Gotcha:** the `Task` model carries both `assigned_to_user_id` (singular, FK, `backend/app/models/task.py:33`) and `assigned_to_user_ids` (array, `:34`). Only the array is written by `create_task`; the frontend mapper still reads both (`frontend/src/store/slices/tasksReducer.ts:71-74`).

### Where the deferred path diverges: `POST /api/diagnostics/{id}/submit`

`backend/app/api/diagnostics.py:423` follows steps 1–14 above and then breaks the pattern in three architecturally significant ways.

1. **The response is sent before the work happens.** The handler commits `status = "processing"` (`:494-497`), hands `_run_pipeline` to `background_tasks.add_task` (`:499-501`) and returns the diagnostic. HTTP status 200 means "accepted", not "done". Clients discover the outcome by polling `GET /api/diagnostics/{id}`.
2. **The background task owns its own session.** `_run_pipeline` opens a fresh `SessionLocal()` (`backend/app/tasks/diagnostic_tasks.py:87`) because the request session was closed by `get_db`'s `finally` when the response went out, and closes it in its own `finally` (`:265-266`). It is the only place in the backend that does this. Pipeline step semantics are owned by *Diagnostic Engine*; the status table and recovery procedure by *Operations, Diagnostics & Troubleshooting*.
3. **It mutates process-global state.** `_run_pipeline` nulls and rebuilds the shared `ClaudeService._client` (`:84-85`). Because it runs in the API process on the same event loop, that swap is visible to every concurrent request. The comment justifying it cites a "stale event loop" — that reasoning applies to an out-of-process worker, which is not what runs.

**Gotcha:** `POST /api/diagnostics/{id}/cancel` (`backend/app/api/diagnostics.py:508-547`) cancels nothing. It 400s any status other than `processing` (`:530-534`), sets `status = "draft"`, clears `completed_at`, commits and returns; the in-flight pipeline keeps running until its next `check_shutdown` poll notices the change. Its docstring's claim to "cancel the registered background task (if running)" is false, and there is no authorisation check on the endpoint at all — `:535-536` carries the comment `# Optional: add role / access checks here if needed`.

---

## 6. Environments, Configuration & Deployment

Runtime configuration comes from two places: a Pydantic `Settings` object on the backend (`backend/app/config.py`) and Vite's `import.meta.env` on the frontend. There is no config server, no secrets manager and no per-environment config file set — one `.env` per side, read from disk at import time. Everything below was read on branch **`staging`**, the branch under documentation.

### Backend configuration mechanics

`backend/app/config.py` defines a single `Settings(BaseSettings)` class and instantiates it at module scope:

```python
class Config:
    env_file = ".env"
    case_sensitive = True


# Global settings instance
settings = Settings()
```
`backend/app/config.py:96-102`

Three consequences:

1. **`env_file = ".env"` is a relative path.** It resolves against the process working directory, not against `backend/`. Start `uvicorn` from anywhere other than `backend/` and the file is silently not found.
2. **`case_sensitive = True`.** Variable names must match the field names exactly.
3. **Construction happens at import.** Ten fields have no default; if any is missing, `import app.config` raises `ValidationError` before FastAPI starts. `backend/tests/conftest.py:26-41` keeps a hand-synced copy of exactly those ten — `DATABASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_AUDIENCE`, `AUTH0_MANAGEMENT_API_AUDIENCE`, `AUTH0_MANAGEMENT_CLIENT_ID`, `AUTH0_MANAGEMENT_CLIENT_SECRET`, `SECRET_KEY`, `ANTHROPIC_API_KEY` — and injects stubs *only when no `.env` exists*, so the test suite imports on a bare machine. A new required field must be added there by hand; see *Engineering Standards, Workflow & Testing*.

**Gotcha:** `backend/README.md:27` says to "Copy `.env.example` to `.env`". **There is no `.env.example`** — not in the working tree (`ls backend/.env*` returns only `.env`) and not anywhere in git history (`git log --all --diff-filter=A -- backend/.env.example` returns nothing). `backend/README.md:132` also lists it in the project-structure diagram. A new engineer cannot bootstrap the backend from the repo alone; the ten required values must be handed over out of band.

### Complete backend environment variable reference

Every field on `Settings`. "Required" means the field has no default and the app will not import without it. "Local `.env`" refers to the untracked `backend/.env` present in this working tree (see *Secrets handling*); only non-secret facts about it are stated.

| Variable | Type | Default in `config.py` | Required? | What it controls | Notes |
|---|---|---|---|---|---|
| `APP_NAME` | `str` | `"Trinity Platform"` | No | OpenAPI title | `backend/app/main.py:47` |
| `APP_ENV` | `str` | `"development"` | No | Session-cookie `https_only` flag; `environment` field in the `/health` response | `backend/app/main.py:62` sets `https_only=settings.APP_ENV != "development"`. **Any** value other than the literal `development` forces secure cookies — a typo silently breaks login over plain HTTP. Also `backend/app/main.py:151` |
| `DEBUG` | `bool` | `True` | No | `reload=` flag, **only** on the `python -m app.main` path | `backend/app/main.py:169`. Ignored under the `uvicorn` CLI, which is what the README tells you to use |
| `PORT` | `int` | `8000` | No | Listen port, **only** on the `python -m app.main` path | `backend/app/main.py:168`. Same caveat as `DEBUG` |
| `DATABASE_URL` | `str` | — | **Yes** | SQLAlchemy engine URL and the Alembic `sqlalchemy.url` override | `backend/app/database.py:15,33-34`, `backend/alembic/env.py:24` |
| `AUTH0_DOMAIN` | `str` | — | **Yes** | Base host for OIDC discovery, JWKS, `/userinfo`, `/v2/logout` and every Management API call | `backend/app/services/auth_service.py:33`, `backend/app/utils/auth.py:29,67`, `backend/app/api/auth.py:100,149,158,211`, `backend/app/services/auth0_management.py:40,77,195,279,361,394`. Value is a bare host, no scheme — code prepends `https://` |
| `AUTH0_CLIENT_ID` | `str` | — | **Yes** | OAuth client id for Universal Login; also accepted as a valid JWT audience | `backend/app/utils/auth.py:71` |
| `AUTH0_CLIENT_SECRET` | `str` | — | **Yes** | OAuth client secret for the authorization-code exchange | Secret |
| `AUTH0_AUDIENCE` | `str` | — | **Yes** | One of the two accepted `aud` values when verifying tokens | `backend/app/utils/auth.py:71`: `valid_audiences = {settings.AUTH0_AUDIENCE, settings.AUTH0_CLIENT_ID}`. See gotcha below |
| `AUTH0_ALGORITHMS` | `str` | `"RS256"` | No | Signature algorithm passed to `jwt.decode` | `backend/app/utils/auth.py:65` — typed as a single `str`, wrapped in a list at the call site, so a comma-separated value would not work |
| `AUTH0_USERNAME_NAMESPACE` | `str` | `"https://your-app.com/username"` | No | Custom-claim key read off the Auth0 ID token to recover a username | `backend/app/api/auth.py:123`. The default is an unedited placeholder and is **not** set in the local `.env`, so this lookup returns `None` in practice |
| `AUTH0_MANAGEMENT_API_AUDIENCE` | `str` | — | **Yes** | `audience` in the client-credentials grant for the Management API | `backend/app/services/auth0_management.py:40-45` |
| `AUTH0_MANAGEMENT_CLIENT_ID` | `str` | — | **Yes** | Management API M2M client id | `backend/app/services/auth0_management.py:43` |
| `AUTH0_MANAGEMENT_CLIENT_SECRET` | `str` | — | **Yes** | Management API M2M client secret | Secret. `backend/app/services/auth0_management.py:44` |
| `FRONTEND_URL` | `str` | `"http://localhost:8080"` | No | First CORS allowed origin; post-login redirect target; Auth0 logout `returnTo`; password-reset ticket `result_url` | `backend/app/main.py:70`, `backend/app/api/auth.py:146,155,176,189,207`, `backend/app/services/auth0_management.py:287`. **The single most important value to change per environment** |
| `SECRET_KEY` | `str` | — | **Yes** | Signing key for Starlette `SessionMiddleware` (cookie `trinity_session`, `max_age` 7 days, `same_site="lax"`) | `backend/app/main.py:56-63`. See *Secrets handling* |
| `OPENAI_API_KEY` | `Optional[str]` | `None` | No | OpenAI credential | `backend/app/services/openai_service.py:43`. The provider is not wired into `main.py` — the `OpenAIService` import at `backend/app/main.py:30` and its startup init at `:129` are commented out. Legacy/rollback only; the pin lives in *Technology Stack & Dependencies* |
| `OPENAI_MODEL` | `str` | `"gpt-4o"` | No | OpenAI model id | `backend/app/services/openai_service.py:480,573,773,849`. Local `.env` sets a different value than the default |
| `OPENAI_TEMPERATURE` | `float` | `1.0` | No | OpenAI sampling temperature | `backend/app/services/openai_service.py:35`. Validated — see *Field validators* |
| `OPENAI_TIMEOUT` | `Optional[float]` | `None` (no timeout) | No | Request timeout in seconds | `backend/app/services/openai_service.py:53-54,383-385` |
| `ANTHROPIC_API_KEY` | `str` | — | **Yes** | Claude credential; the client is constructed once at startup | `backend/app/main.py:125` (`ClaudeService.initialize_client()`), `backend/app/services/claude_service.py:35` |
| `ANTHROPIC_MODEL` | `str` | `"claude-opus-4-6"` | No | Default model for every Claude call that does not pass one | `backend/app/services/claude_service.py:209,521,625,667,829,894`, `backend/app/services/chat_service.py:217,293`, `backend/app/services/strategy_workbook_service.py:443` |
| `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP1` | `Optional[str]` | `"claude-sonnet-4-6"` | No | Model override for Strategy Workbook step 1 | `backend/app/services/strategy_workbook_service.py:256` — `... STEP1 or settings.ANTHROPIC_MODEL` |
| `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP2` | `Optional[str]` | `"claude-sonnet-4-6"` | No | Model override for Strategy Workbook step 2 | `backend/app/services/strategy_workbook_service.py:304` |
| `ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2` | `Optional[int]` | `None` | No | Max output tokens for Strategy Workbook step 2 | `backend/app/services/strategy_workbook_service.py:305-306` — falls back to `ANTHROPIC_MAX_TOKENS` when unset |
| `ANTHROPIC_TEMPERATURE` | `float` | `0.5` | No | Claude sampling temperature, read once in the service constructor | `backend/app/services/claude_service.py:27`. Validated — see *Field validators* |
| `ANTHROPIC_TIMEOUT` | `Optional[float]` | `1800.0` | No | Claude client timeout in seconds | `backend/app/services/claude_service.py:33` (`settings.ANTHROPIC_TIMEOUT or 600.0`); error text at `:414-416`. Local `.env` overrides the default |
| `ANTHROPIC_MAX_TOKENS` | `int` | `128000` | No | Default max output tokens | `backend/app/services/claude_service.py:254`. The inline comment at `config.py:54` scopes this number to Claude Opus 4.6; the local `.env` pairs it with a Sonnet model |
| `LLM_PROVIDER` | `str` | `"claude"` | No | *Nothing.* | **Dead setting.** `grep -rn "LLM_PROVIDER" backend/app` finds only its own declaration (`backend/app/config.py:55`) and a docstring line (`backend/app/services/openai_service.py:8`). No branch reads it — `backend/app/main.py:31` imports `ClaudeService` unconditionally |
| `CELERY_BROKER_URL` | `str` | `"redis://localhost:6379/0"` | No | *Nothing.* | **Dead setting** (`backend/app/config.py:58`). No broker, worker tier or cache service runs — see the gotcha below |
| `CELERY_RESULT_BACKEND` | `str` | `"redis://localhost:6379/0"` | No | *Nothing.* | **Dead setting** (`backend/app/config.py:59`) |
| `UPLOAD_DIR` | `str` | `"uploads"` | No | Base directory for the uploads of **three** tools: BBA POC, Roles Matrix and PD Scorecard | `backend/app/api/upload_poc.py:101`, `backend/app/api/roles_matrix.py:56`, `backend/app/api/pd_scorecard.py:80`. **Relative path** — resolves against the process CWD, so the same deployment writes to different places depending on where it was launched. See the two-roots note below |
| `RESEND_API_KEY` | `str` | `""` | No | Resend API credential, assigned per send | `backend/app/services/email_service.py:144,275`. Empty default means email fails at call time, not at startup |
| `RESEND_FROM_EMAIL` | `str` | `"noreply@benchmarkbusinessadvisory.com.au"` | No | `from` header on outbound mail | `backend/app/services/email_service.py:146,277`. Overridden in the local `.env` |
| `RESEND_REPLY_TO` | `str` | `"benchmarkbusinessadvisoryau@gmail.com"` | No | `reply_to` header | `backend/app/services/email_service.py:148,279`. Not set in the local `.env`, so the gmail.com default is live |
| `FROM_EMAIL` | `Optional[str]` | `None` | No | *Nothing.* | **Dead setting.** No reference anywhere under `backend/app` outside `config.py:68` |
| `SMTP_HOST` | `str` | `"smtp.gmail.com"` | No | *Nothing* | **Legacy / unused.** Block labelled "Gmail SMTP — legacy, unused" at `backend/app/config.py:70`; verified — no reference outside `config.py` |
| `SMTP_PORT` | `int` | `587` | No | *Nothing* | Legacy / unused |
| `SMTP_USERNAME` | `str` | `""` | No | *Nothing* | Legacy / unused. A personal address is nonetheless populated in the local `.env` |
| `SMTP_PASSWORD` | `str` | `""` | No | *Nothing* | Legacy / unused. A Google app password is populated in the local `.env` — **revoke at handover** |
| `SMTP_FROM_EMAIL` | `str` | `""` | No | *Nothing* | Legacy / unused |
| `GOOGLE_DRIVE_ENABLED` | `bool` | `False` | No | *Nothing* | Declared at `backend/app/config.py:77-80`, referenced by no other file under `backend/app/` — see *Google Drive* below |
| `GOOGLE_DRIVE_CREDENTIALS_FILE` | `Optional[str]` | `None` | No | *Nothing* | Declared at `backend/app/config.py:77-80`, referenced by no other file under `backend/app/` |
| `GOOGLE_DRIVE_FOLDER_ID` | `Optional[str]` | `None` | No | *Nothing* | Declared at `backend/app/config.py:77-80`, referenced by no other file under `backend/app/` |

**Gotcha — the Celery settings describe infrastructure that does not exist.** All background work runs in-process through FastAPI `BackgroundTasks`; there is no broker, no worker and no Redis. The `celery`/`redis` packages are nevertheless pinned and must be installed, because `backend/app/tasks/diagnostic_tasks.py:14-18` imports Celery at module scope and `backend/app/api/diagnostics.py:500` imports `_run_pipeline` from that module. Removing the dependency means moving `_run_pipeline` out of that file first. The execution model itself is in *System Architecture*; the operational consequences are in *Operations, Diagnostics & Troubleshooting*.

**Two upload roots exist and only one is served.** `UPLOAD_DIR` is not the root behind the `/files` URL prefix:

| Root | Written by | Served at `/files/…`? |
|---|---|---|
| `backend/files/uploads/{diagnostic,sbp,strategy-workbook,users}` | diagnostic uploads, SBP (`backend/app/api/strategic_business_plan.py:49`, `backend/app/services/sbp_conversation_engine.py:60` — both hard-code the path and ignore `UPLOAD_DIR`), Strategy Workbook, profile pictures | **Yes** — `app.mount("/files", StaticFiles(...))` at `backend/app/main.py:115` |
| `settings.UPLOAD_DIR` → `<cwd>/uploads/{bba,roles-matrix,pd-scorecard}` | `upload_poc.py:101`, `roles_matrix.py:56`, `pd_scorecard.py:80` | **No.** No mount covers it; nothing serves that tree over HTTP |

One variable is read from the process environment but **not** declared on `Settings`:

| Variable | Read at | Purpose |
|---|---|---|
| `TEST_DATABASE_URL` | `backend/tests/conftest.py:86` | Points DB-touching tests at a database other than `DATABASE_URL`. Falls back to `settings.DATABASE_URL` when unset. This is the only direct `os.environ` read outside test bootstrap code |

`backend/tests/test_claude_integration.py:20` additionally skips its whole module unless `ANTHROPIC_API_KEY` is present in the process environment.

#### Google Drive: declared, never read

`grep -rn GOOGLE_DRIVE backend --include=*.py` returns **three hits, all of them the declarations themselves** (`backend/app/config.py:78-80`, under the `# Google Drive` comment at `:77`). No application code reads `GOOGLE_DRIVE_ENABLED`, `GOOGLE_DRIVE_CREDENTIALS_FILE` or `GOOGLE_DRIVE_FOLDER_ID`.

The config surface is not the only residue. `strategy_workbooks.drive_file_id` is declared with the comment "Google Drive file ID for the generated workbook" (`backend/app/models/strategy_workbook.py:42-43`) and serialised in `to_dict()` (`:81`) — **nothing ever writes it**. **No Google client library is pinned** in `backend/requirements.txt`: no `google-api-python-client`, `google-auth`, `gspread` or `oauth2client`. Strategy Workbook exports are streamed to the browser, not uploaded anywhere. A stale compiled artefact sits in the tree — `backend/app/services/__pycache__/google_drive_service.cpython-312.pyc` — with no corresponding `.py` source; the source exists in git history only on the unmerged branch `fix/google-drive-imp` (local and `origin/`), absent from `main`, `staging` and every other merged branch. The `.pyc` is residue from that branch having been checked out here.

The local `.env` still sets `GOOGLE_DRIVE_ENABLED=true` and names a service-account JSON that is present on disk (`backend/trinity-platform-b690f5c862c7.json`).

**Gotcha:** the setting says "enabled", a schema column is reserved, and the credentials file exists, so this reads as live infrastructure. Nothing merged loads any of it. Treat the service-account key as an unused-but-live credential to be revoked, not as a dependency, and confirm at handover that revoking it breaks nothing — see *Handover Checklist & Open Questions*.

#### Field validators

Two, both on temperature, both raising `ValueError` during `Settings()` construction — i.e. at import, so a bad value is a hard startup failure, not a runtime error:

```python
@field_validator("OPENAI_TEMPERATURE")
@classmethod
def validate_temperature(cls, v: float) -> float:
    if not 0.0 <= v <= 2.0:
        raise ValueError("OPENAI_TEMPERATURE must be between 0.0 and 2.0")
    return v

@field_validator("ANTHROPIC_TEMPERATURE")
@classmethod
def validate_anthropic_temperature(cls, v: float) -> float:
    if not 0.0 <= v <= 1.0:
        raise ValueError("ANTHROPIC_TEMPERATURE must be between 0.0 and 1.0")
    return v
```
`backend/app/config.py:82-94`

| Validator | Field | Accepts | Rejects |
|---|---|---|---|
| `validate_temperature` | `OPENAI_TEMPERATURE` | `0.0 <= v <= 2.0` inclusive | anything below `0.0` or above `2.0` |
| `validate_anthropic_temperature` | `ANTHROPIC_TEMPERATURE` | `0.0 <= v <= 1.0` inclusive | anything below `0.0` or above `1.0` |

The ranges differ (`2.0` vs `1.0`) because the vendor APIs differ. Nothing else on `Settings` is validated — `DATABASE_URL`, every Auth0 field and every timeout are accepted as-is.

#### Auth0 audience: a live inconsistency

`backend/app/utils/auth.py:62-77` verifies with `options={"verify_aud": False}` and then checks `aud` by hand against **either** `AUTH0_AUDIENCE` **or** `AUTH0_CLIENT_ID` (a list-valued `aud` matches on set intersection). The login flow at `backend/app/api/auth.py:62-68` deliberately requests **no** API audience:

```python
return await oauth.auth0.authorize_redirect(
    request,
    redirect_uri=str(redirect_uri),
    **auth_params
    # Don't request any API audience - only user info
    # This prevents the "Authorize App" consent screen
)
```

Issued tokens therefore carry `aud = client_id` and match on the second branch. The `AUTH0_AUDIENCE` value in the local `.env` is written **without a URL scheme** (unlike `AUTH0_MANAGEMENT_API_AUDIENCE`, which has one), so it could never be a valid Auth0 API identifier — but because that branch never matches, nothing breaks today. Token verification itself is covered in *Authentication, Authorization & Impersonation*.

**Gotcha:** if anyone switches the login flow to request an API audience, verification fails until `AUTH0_AUDIENCE` is corrected to a full `https://…` identifier. The defect is latent, not by design.

### Database configuration

`backend/app/database.py` builds the engine and distinguishes local from remote hosts:

```python
_url = make_url(settings.DATABASE_URL)
_is_local = _url.host in (None, "localhost", "127.0.0.1", "::1")
...
if not _is_local:
    # Render's external Postgres endpoint requires TLS.
    _connect_args.setdefault("sslmode", _url.query.get("sslmode", "require"))
```
`backend/app/database.py:15-30`

| Engine option | Value | Why (from the file's own comments) |
|---|---|---|
| `pool_pre_ping` | `True` | Verify connections before using them |
| `pool_size` / `max_overflow` | `10` / `10` | "Keep connections warm so we re-dial (and re-resolve DNS) rarely" |
| `pool_recycle` | `1800` | "Recycle before Render's idle cutoff" |
| `pool_timeout` | `30` | |
| `echo` | `False` | SQL logging off (also see the logger level overrides at `backend/app/main.py:41-43`) |
| `connect_timeout` | `10` | psycopg2 connect arg |
| TCP keepalives | `keepalives=1`, idle 30s, interval 10s, count 5 | Stop NAT/firewalls silently dropping the link to Render |
| `sslmode` | `require` (remote hosts only) | Render's external endpoint mandates TLS |

A `do_connect` event listener (`backend/app/database.py:60-88`) retries **new** DBAPI connections up to three times with exponential backoff (`_CONNECT_RETRIES = 3`, `_CONNECT_BACKOFF = 0.5`), but only when the error message contains one of seven transient substrings (`backend/app/database.py:46-54`: DNS translation/resolution failures, "connection refused", "connection timed out", "server closed the connection unexpectedly", "connection reset by peer"). Everything else — bad password, missing database — fails immediately.

The file is written throughout around a **remote, latency- and DNS-sensitive Postgres**. That is a direct signal this codebase has always run against a hosted database, including in development.

#### Alembic

`backend/alembic.ini:56` carries the stock placeholder `sqlalchemy.url = driver://user:pass@localhost/dbname`. It is overwritten at runtime:

```python
from app.config import settings
config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)
```
`backend/alembic/env.py:18-24`

So **Alembic and the app always target the same database**, and Alembic inherits the same `.env`-relative-path constraint — it must be run from `backend/`. `prepend_sys_path = .` (`backend/alembic.ini:13`) plus the `sys.path.insert` at `backend/alembic/env.py:13` make `app` importable; `script_location = alembic` (`backend/alembic.ini:5`) is likewise relative.

`env.py` installs two autogenerate filters, both worth knowing before you run `alembic revision --autogenerate`:

- `include_object` (`backend/alembic/env.py:53-59`) suppresses the eight named redundant `UNIQUE (id)` constraints listed in `EXEMPT_UNIQUE_CONSTRAINTS` (`:41-50` — on `conversations`, `diagnostics`, `engagements`, `firms`, `media`, `subscriptions`, `tasks`, `users`). They exist in the database but not in the models; a foreign key is bound to each one's index rather than to the primary key, so dropping them would force ~56 foreign keys to be rebuilt.
- `strip_comment_directives` (`backend/alembic/env.py:81-96`, with helper `_is_comment_only` at `:62-78`) drops comment-only diffs so `autogenerate` and `alembic check` report structural drift only. An `AlterColumnOp` that also changes type, nullability, server default or name is not treated as comment-only and stays visible.

There are 80 revision files in `backend/alembic/versions/`. Schema detail, including the orphan tables added by migrations with no model behind them, is in *Data Model & Database*.

**Gotcha, quoted from `backend/README.md:73-75`:** *"`alembic upgrade head` cannot build a database **from empty** in this repo — an early revision runs `ALTER TABLE advisor_client` before that table is created. Upgrading an existing database works fine."* You cannot stand up a fresh environment by migration. A new database has to be seeded from a dump of an existing one.

### Frontend configuration

`frontend/.env` is a single line with no trailing newline, and **is tracked by git**:

```
VITE_API_BASE_URL=http://localhost:8000
```

`frontend/vite.config.ts` reads it for the dev-server proxy target; application code reads the same variable through `import.meta.env`:

```ts
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.VITE_API_BASE_URL || "http://localhost:8000";

  return {
    server: {
      host: "::",
      port: 8080,
      allowedHosts: ["*"],
      proxy: {
        "/api": { target: apiTarget, changeOrigin: true, secure: false },
        "/files": { target: apiTarget, changeOrigin: true, secure: false },
      },
    },
    plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
    resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  };
});
```
`frontend/vite.config.ts:7-36`

| Setting | Value | Effect |
|---|---|---|
| `server.host` | `"::"` | Binds all interfaces (IPv6 wildcard), so the dev server is reachable from the LAN |
| `server.port` | `8080` | Matches the backend's `FRONTEND_URL` default and its CORS allow-list |
| `server.allowedHosts` | `["*"]` | See gotcha below |
| `server.proxy["/api"]` | → `apiTarget` | Forwards API calls, rewriting `Origin` |
| `server.proxy["/files"]` | → `apiTarget` | Forwards the static uploads mount (`backend/app/main.py:115`) |
| `resolve.alias["@"]` | `./src` | The `@/…` imports used throughout |
| `plugins` | `lovable-tagger` in `development` mode only | Residue of the Lovable origin — see *Deployment* |

**Gotcha — `allowedHosts: ["*"]` does not do what it looks like.** In Vite 5.4.19 (`frontend/node_modules/vite/dist/node/chunks/dep-C6uTJdX2.js:59249-59290`) the allow-all value is the boolean `true`; an array is matched by **exact hostname**, or by a leading-dot suffix rule. The string `"*"` is treated as a literal hostname and matches nothing real. Localhost, `*.localhost` and any IPv4 literal are always allowed regardless. Tunnelling the dev server through ngrok/Cloudflare or a custom hostname still returns `Blocked request. This host is not allowed.` The config gives a false impression that this was handled.

#### Dev-proxy vs direct-fetch: which wins

`VITE_API_BASE_URL` is consumed as a copy-pasted module-level constant in **56 files under `frontend/src`, 58 occurrences in total** (two files declare it twice: `frontend/src/components/engagement/form.tsx` and `frontend/src/pages/dashboard/StrategyWorkbookPage.tsx`). Two fallback conventions coexist:

| Convention | Occurrences | Example |
|---|---|---|
| `import.meta.env.VITE_API_BASE_URL \|\| 'http://localhost:8000'` | 57 | `frontend/src/lib/clientFetcher.ts:4`, `frontend/src/lib/aiPrivacyService.ts:1`, `frontend/src/pages/Login.tsx:7`, every file under `frontend/src/store/slices/` |
| `import.meta.env.VITE_API_BASE_URL \|\| ''` | 1 | `frontend/src/context/AuthContext.tsx:18` |

Requests are then built as absolute URLs, e.g. `fetch(\`${API_BASE_URL}/api/engagements\`, …)` (`frontend/src/lib/clientFetcher.ts:39`).

**The direct fetch wins.** With `VITE_API_BASE_URL=http://localhost:8000` set — the committed value — every one of those constants becomes an absolute cross-origin URL. The browser goes straight to `:8000` and the Vite proxy for `/api` and `/files` is **never exercised**. Cross-origin rules apply, which is why `backend/app/main.py:67-83` maintains an explicit nine-entry CORS allow-list (`settings.FRONTEND_URL` plus eight hard-coded `localhost`/`127.0.0.1` origins on ports 5173, 3000, 8080, 8000) with `allow_credentials=True`.

If `VITE_API_BASE_URL` were unset or empty you would get a **split brain**, not a clean fall-back to the proxy: `AuthContext.tsx` alone would issue same-origin relative requests through the proxy, while the other 55 files would hard-code `http://localhost:8000` and keep going direct — the two halves of the app would talk to different origins. The proxy entries are exercised only by `AuthContext`'s calls in that configuration, and by nothing at all in the configuration anyone actually runs. The client-side consequences are in *Frontend Architecture*.

**Gotcha:** because the base URL is baked into the bundle at build time, there is no runtime way to repoint a built bundle at a different API. `VITE_API_BASE_URL` must be correct **at `npm run build` time**, and the committed value in `frontend/.env` is `http://localhost:8000` on `main`, `staging`, `origin/main`, `origin/deploy` and `origin/url-changes` alike (verified with `git show <branch>:frontend/.env`). A build from a clean checkout of any of those branches, with no CI overriding the value, produces a bundle that talks to localhost.

`frontend/package.json:6-12` scripts:

| Script | Command |
|---|---|
| `dev` | `vite` |
| `build` | `vite build` |
| `build:dev` | `vite build --mode development` |
| `lint` | `eslint .` |
| `preview` | `vite preview` |

`build` is bare `vite build` with no `tsc` step, so type errors do not fail it — see *Engineering Standards, Workflow & Testing*.

### Environment matrix

| Environment | Frontend URL | Backend URL | Database | Auth0 tenant | Notes |
|---|---|---|---|---|---|
| **Local development** | `http://localhost:8080` (`frontend/vite.config.ts:14`; `FRONTEND_URL` default at `backend/app/config.py:35`) | `http://localhost:8000` (`frontend/.env`; `PORT` default at `backend/app/config.py:16`) | **Render-hosted PostgreSQL, `oregon-postgres.render.com`, database `trinity_db_stag`, `?sslmode=require`** — from `DATABASE_URL` in the untracked `backend/.env` | `dev-i35a4hkouf6bs25n.au.auth0.com` (an Auth0 *dev* tenant, AU region) | `APP_ENV=development`, `DEBUG=True`. See the risk callout below |
| **Staging** | TO CONFIRM | TO CONFIRM | TO CONFIRM whether a deployed staging backend shares `trinity_db_stag`, which is what the local `.env` points at | TO CONFIRM (likely the same dev tenant) | The `staging` branch exists locally and on `origin`; this working tree is checked out on it |
| **Production** | TO CONFIRM | TO CONFIRM | TO CONFIRM | TO CONFIRM | Nothing in the repository names a production host, domain, database or tenant |

**Risk — local development runs against a shared remote database.** The `backend/.env` in this tree is unambiguously a *local development* config: `APP_ENV=development`, `DEBUG=True`, `FRONTEND_URL=http://localhost:8080`, `PORT=8000`. But `DATABASE_URL` points at a **hosted Render PostgreSQL instance**, not at a local server. Two commented-out alternatives sit directly above it — one for `localhost:5432/trinity_db`, one for a *different* Render database (`trinitydb`) — so switching targets is a matter of moving a `#`, with nothing to indicate which is authoritative.

Consequences, all of them live:

- Every developer's `alembic upgrade head` mutates the schema everyone else is working against. Sibling Alembic revisions colliding because all branches share one dev Postgres is a failure mode this project has already hit. The idempotent `inspector` guards in `backend/alembic/versions/f7a1b2c3d4e5_self_service_saas.py:31-41`, written "because several environments have drifted from the migration history", are a written record of it.
- `backend/README.md:53-71` documents running DB-touching tests "against your local database from `DATABASE_URL`" and reassures that "Running against your dev database leaves no trace". That reassurance is scoped to the transaction-rollback fixture (`db_session`, `backend/tests/conftest.py:98-116`) only; the *destination* is remote and shared. `TEST_DATABASE_URL` exists to opt out and should be treated as mandatory, not optional.
- A `git pull` that lands a new migration, plus a careless `alembic upgrade head`, is a shared-environment incident rather than a local one.
- Local development requires network reachability to Render — hence the retry machinery in `backend/app/database.py`.

### Deployment

**The `staging` branch carries no Dockerfile, no CI workflow and no platform manifest.** Verified:

```
$ git ls-files | grep -Ei "dockerfile|docker-compose|procfile|render\.yaml|vercel\.json|netlify\.toml|\.github/|fly\.toml|app\.yaml|\.vscode"
.github/pull_request_template.md
.vscode/launch.json
docker-compose.yml
```

`.github/` holds a PR template and no `workflows/` directory. There is no `render.yaml` despite the database being Render-hosted, no `vercel.json`, `netlify.toml`, `Procfile`, `app.yaml` or `fly.toml`. `docker-compose.yml` at the repo root is unused and is not part of any run path — see *Technology Stack & Dependencies*. `.vscode/launch.json` is a local FastAPI debug config (`module: uvicorn`, `--reload --host 0.0.0.0 --port 8000`, `cwd: ${workspaceFolder}/backend`, `envFile: ${workspaceFolder}/backend/.env`), not a deployment artefact.

**What that implies.** There is no automated build, no image, no infrastructure-as-code and no pipeline on any merged branch. Whatever is deployed is deployed manually or through a hosting platform's own dashboard-driven git integration, and its configuration lives entirely outside this repository. Nothing in the tree tells a new owner where the running system is, how it is started, or where its environment variables are set. `gunicorn==24.1.1` is pinned in `backend/requirements.txt:47` alongside `uvicorn[standard]==0.38.0` (`:3`) and is referenced by no script, README, Procfile or manifest on a merged branch — the production start command is not recorded anywhere.

**A complete deployment exists, unmerged.** Branch `feature/azure-deployment` (local and on `origin`; **2 commits ahead of `staging`, 59 behind**) adds a full Azure Container Apps + Static Web Apps deployment: `infra/main.bicep` and `infra/README.md`, `backend/Dockerfile`, `.github/workflows/deploy-backend.yml` and `deploy-frontend.yml`, `frontend/staticwebapp.config.json`, and `backend/app/services/storage_service.py` — a local-disk/blob storage abstraction that replaces direct filesystem writes, needed because Container Apps replicas neither share nor persist local disk. The frontend workflow also demonstrates the intended fix for the baked-in base URL: `VITE_API_BASE_URL` supplied as a build-time CI secret instead of coming from the committed `frontend/.env`. Full file inventory, workflow triggers and required secrets are in *Unmerged Work on Other Branches*. **This is the single highest-value unmerged branch in the repository, and it is 59 commits behind.**

**Other deployment signals:**

1. **Render-hosted database.** `backend/app/database.py:19,29,38` names Render explicitly in comments and tunes the pool around Render's idle cutoff and TLS requirement; the active `DATABASE_URL` host is `…oregon-postgres.render.com`. Whether the *backend service* is also on Render is not stated anywhere.
2. **Lovable origin of the frontend.** `frontend/README.md` is an unmodified Lovable scaffold: it names a Lovable project URL, states "Changes made via Lovable will be committed automatically to this repo", and answers "How can I deploy this project?" with "open Lovable and click Share -> Publish". `lovable-tagger` is still an active dev dependency and plugin (`frontend/package.json:78`, `frontend/vite.config.ts:4,29`). Whether that publish path is the live deploy mechanism or dead history is unresolved.
3. **Deployment-flavoured branch names.** `origin/deploy` and `origin/url-changes` exist; `origin/deploy`'s three most recent commits are `Merge pull request #5 from 46-Bytes/url-changes`, `submit api integration`, `Refactor API base URL handling across components`. Its committed `frontend/.env` is still `http://localhost:8000`.

**Remote:**

```
origin  https://github.com/46-Bytes/Trinity-Platform.git (fetch)
origin  https://github.com/46-Bytes/Trinity-Platform.git (push)
```

`origin/HEAD` → `origin/main`. This working tree is on `staging`. There are 221 local and 233 remote branches, overwhelmingly short-lived `fix/…` and `feature/…` branches never deleted after merge — see *Unmerged Work on Other Branches*.

### Local setup runbook

From a clean checkout. **You will need `backend/.env` handed to you** — there is no template in the repo (see the earlier gotcha).

#### Backend — Windows (PowerShell)

```powershell
cd Trinity-Platform\backend
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

# Place the supplied .env at Trinity-Platform\backend\.env before continuing.
# Set DATABASE_URL to a database you are allowed to migrate.

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

#### Backend — macOS / Linux

```bash
cd Trinity-Platform/backend
python -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt

# Place the supplied .env at Trinity-Platform/backend/.env before continuing.

alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

`backend/requirements-dev.txt` is `-r requirements.txt` plus `pytest==8.3.4`. Use it, not `requirements.txt`, for local work (`backend/README.md:20-24`).

Every one of these commands must run **from `backend/`** — `.env` discovery, `alembic.ini`'s `script_location = alembic`, `prepend_sys_path = .`, and `UPLOAD_DIR`'s relative default all depend on it.

**Gotcha — venv name mismatch.** `backend/README.md:9` says `python -m venv venv`, but the tracked `.vscode/launch.json` points its interpreter at `${workspaceFolder}/backend/venv-trinity/Scripts/python.exe`. Follow the README and F5 in VS Code will not resolve. Either create the venv as `venv-trinity` or fix the launch config locally. Note `backend/.gitignore:8` ignores `venv/` but not `venv-trinity/`.

**Gotcha — `alembic upgrade head` on a shared database.** Read the risk callout in *Environment matrix* first. Confirm which database `DATABASE_URL` names before running it.

#### Frontend — all platforms

```bash
cd Trinity-Platform/frontend
npm i
npm run dev            # serves on http://localhost:8080
```

Node 20 is the version the Azure branch's CI pins; nothing on a merged branch declares an engine constraint. `frontend/.env` already ships with `VITE_API_BASE_URL=http://localhost:8000`, matching the backend default — no edit needed for a standard local run.

#### Running tests

```bash
cd Trinity-Platform/backend
pytest tests/test_program_deliverable_status.py -v      # pure, no database
pytest tests/test_program_deliverable_validation.py -v  # pure, no database

export TEST_DATABASE_URL=<a database you own>           # strongly recommended
pytest tests/test_program_deliverable_mutations.py -v   # needs a migrated database
```

If the DB target has not been migrated, the DB tests skip with instructions rather than failing en masse (`backend/tests/conftest.py:69-93`).

**Gotcha:** a bare `pytest` also collects `tests/test_claude_service.py`, whose async tests need `pytest-asyncio` — not currently a dependency (`backend/README.md:77-79`). Run specific files. The suite's full shape is in *Engineering Standards, Workflow & Testing*.

#### Auth0 application settings

From `backend/README.md:83-96`. Create a **Regular Web Application** in the Auth0 dashboard and set:

| Setting | Value as written in `backend/README.md` |
|---|---|
| Allowed Callback URLs | `http://localhost:8000/api/auth/callback` |
| Allowed Logout URLs | `http://localhost:8000, http://localhost:5173` |
| Allowed Web Origins | `http://localhost:5173` |

Then enable a database connection under **Authentication → Database** (`Username-Password-Authentication` or equivalent).

The callback URL is correct and self-consistent: `backend/app/api/auth.py:53` builds it with `request.url_for('callback')`, the route is named `callback` at `:71`, and the router is mounted with `prefix="/api/auth"` at `:28` — resolving to exactly `http://localhost:8000/api/auth/callback`.

**Gotcha — the logout and web-origin values in the README are stale.** They name port **5173** (the Vite default), but this project's dev server runs on **8080** (`frontend/vite.config.ts:14`) and `FRONTEND_URL` defaults to `http://localhost:8080` (`backend/app/config.py:35`). Logout sends Auth0 `returnTo = f"{settings.FRONTEND_URL}/login"` (`backend/app/api/auth.py:207`) — i.e. `http://localhost:8080/login`, which is not in the README's Allowed Logout URLs and will be rejected. The same applies to the error redirects at `backend/app/api/auth.py:146,155,189` and the password-reset `result_url` at `backend/app/services/auth0_management.py:287`. Add `http://localhost:8080` to both Allowed Logout URLs and Allowed Web Origins.

### Secrets handling

Three configuration files sit in the working tree:

| File | On disk | **Tracked by git?** | Contents |
|---|---|---|---|
| `backend/.env` | Yes | **No** | Auth0 app + Management API credentials, a Render Postgres connection string with embedded password, OpenAI and Anthropic API keys, a Resend API key, and a Gmail app password |
| `backend/trinity-platform-b690f5c862c7.json` | Yes | **No** | A Google Cloud service-account key (private key material) |
| `frontend/.env` | Yes | **Yes — tracked** | `VITE_API_BASE_URL` only. Not a secret |

The first two are **out-of-band handover artefacts**: they exist only on developer machines, they have never been in the repository, and a new owner cannot run the backend without receiving them by some channel outside git. Neither is reproduced in this document. Who currently holds them, and through what channel they will be transferred, is an open item — see *Handover Checklist & Open Questions*.

Verified rather than assumed:

```
$ git ls-files --error-unmatch backend/.env
error: pathspec 'backend/.env' did not match any file(s) known to git

$ git ls-files | grep -i 'trinity-platform-.*json'      # (no output)

$ git ls-files --error-unmatch frontend/.env
frontend/.env

$ git log --oneline --all -- backend/.env                       # (no output)
$ git log --oneline --all -- "backend/trinity-platform-*.json"  # (no output)
```

Neither secret file is tracked, and neither has ever been committed on any branch. `backend/.gitignore` handles both deliberately — it ignores `.env` and `.env.local` (`:27-28`), then names the credential shapes explicitly rather than blanket-ignoring `*.json`, with a comment explaining that tracked JSON fixtures under `backend/files/` would otherwise be swept up:

```
# Cloud service-account keys. These carry a live private_key - a blanket
# *.json cannot be used here because tracked fixtures under files/ are JSON,
# so the credential shapes are named explicitly instead.
trinity-platform-*.json
*service-account*.json
*service_account*.json
*.serviceaccount.json
*credentials*.json
gcp-key*.json
```
`backend/.gitignore:30-38`

There is **no root-level `.gitignore`** on `staging` — `backend/.gitignore` and `frontend/.gitignore` are the only two tracked. (`feature/azure-deployment` adds one.)

**Still bad:** the secrets are plaintext on developer machines, inside a OneDrive-synced directory in this checkout, and have been passed between developers by hand (the SMTP block names a personal Gmail account). Being untracked prevents GitHub exposure; it does not make them safe.

#### Rotate at handover

Every credential in `backend/.env` should be treated as compromised-by-sharing and rotated:

| Credential | Where to rotate | Notes |
|---|---|---|
| `AUTH0_CLIENT_SECRET` | Auth0 dashboard → Application → Settings | |
| `AUTH0_MANAGEMENT_CLIENT_SECRET` | Auth0 dashboard → the M2M application | Grants Management API access — creates, updates and deletes users (`backend/app/services/auth0_management.py:195,361,394`) |
| `DATABASE_URL` password | Render dashboard → the Postgres instance | Embedded in the connection string |
| `ANTHROPIC_API_KEY` | Anthropic console | The only LLM key actually in use |
| `OPENAI_API_KEY` | OpenAI dashboard | Unused by running code; rotate or revoke outright |
| `RESEND_API_KEY` | Resend dashboard | |
| `SMTP_PASSWORD` | Google account → App passwords | A personal Gmail app password for a legacy, unused code path. **Revoke, do not rotate** |
| Google service-account key | Google Cloud console → IAM → Service accounts → Keys | Nothing on a merged branch reads it (see *Google Drive: declared, never read*). **Delete the key and the service account** unless a use is identified |
| `SECRET_KEY` | Generate a new one | See below |

**Gotcha — `SECRET_KEY` is not a key.** In the checked-out `.env` the value is a 75-character string containing spaces and the words `python` and `secrets` — i.e. the *instruction text* for generating a key, never executed. That string is the signing key for the `trinity_session` cookie (`backend/app/main.py:56-63`). Generate a real one before any deployment:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 7. Data Model & Database

PostgreSQL, accessed through SQLAlchemy declarative models and versioned with Alembic. `backend/app/models/` is the source of truth for application code; `backend/alembic/versions/` is the source of truth for what is actually in the database. The two have drifted, measurably and in both directions, and that drift is load-bearing knowledge for anyone generating a migration — see [Autogenerate picks up pre-existing drift](#autogenerate-picks-up-pre-existing-drift--hand-trim-every-revision).

### Engine and session

`backend/app/database.py` builds one module-level `Engine` from `settings.DATABASE_URL`. `backend/app/config.py:19` declares `DATABASE_URL: str` with no default, so the process will not start without it.

| Setting | Value | Why |
|---|---|---|
| `pool_pre_ping` | `True` | Revalidate pooled connections before handing them out (`backend/app/database.py:35`) |
| `pool_size` / `max_overflow` | `10` / `10` | Keep connections warm so DNS is re-resolved rarely (`backend/app/database.py:36-37`) |
| `pool_recycle` | `1800` | Recycle before the hosted Postgres idle cutoff |
| `pool_timeout` | `30` | |
| `echo` | `False` | SQL logging off |
| `connect_args` | `connect_timeout=10`, `keepalives=1`, `keepalives_idle=30`, `keepalives_interval=10`, `keepalives_count=5` (`backend/app/database.py:21-27`) | Stops NAT/firewalls silently dropping idle connections |
| `sslmode` | `require`, **only when the host is not local** (`backend/app/database.py:15-16,28-30`) | The hosted endpoint requires TLS; `localhost`/`127.0.0.1`/`::1`/no-host does not. An explicit `sslmode` in the URL query wins. |

`backend/app/database.py:60-88` registers a `do_connect` listener that retries **new** DBAPI connections up to three times with exponential backoff (0.5 s base) against a fixed allow-list of seven transient error substrings (`backend/app/database.py:46-54`): `could not translate host name`, `name or service not known`, `temporary failure in name resolution`, `connection refused`, `connection timed out`, `server closed the connection unexpectedly`, `connection reset by peer`. Anything else — bad password, missing database — raises immediately.

**Gotcha:** `pool_pre_ping` only revalidates *pooled* connections; it does nothing when the pool must dial a fresh one. The docstring at `backend/app/database.py:65-67` says so explicitly. Do not delete the `do_connect` listener as "redundant with pre_ping".

`SessionLocal` is `sessionmaker(autocommit=False, autoflush=False, bind=engine)` (`backend/app/database.py:92`). `Base = declarative_base()` (`backend/app/database.py:95`) — every model inherits from it, and `get_db()` (`backend/app/database.py:98-111`) is the FastAPI dependency that yields a session and closes it in `finally`. There is **no `Base.metadata.create_all()` anywhere in the repo** outside `backend/venv/` (verified across `backend/app/`, `backend/scripts/`, `backend/seed/`, `backend/tests/`), so migrations or a schema dump are the only ways a schema comes into existence.

### Entity list

Every class registered in `backend/app/models/__init__.py`. **This list is derived from that file and therefore cannot see the fourteen tables that exist in the database with no model at all** — see [Tables with no model: the self-service tier](#tables-with-no-model-the-self-service-tier) and [Tables with no model: the Sale Ready programme](#tables-with-no-model-the-sale-ready-programme).

| Table | Model class | Module | Purpose |
|---|---|---|---|
| `users` | `User` | `backend/app/models/user.py` | Authenticated principals: advisors, clients, admins, firm staff. Auth0 `sub` and/or a password hash. |
| `firms` | `Firm` | `backend/app/models/firm.py` | Multi-advisor organisation; owns seats, billing email and exactly one firm-admin user. |
| `subscriptions` | `Subscription` | `backend/app/models/subscription.py` | Plan name, seat count and monthly price. |
| `advisor_client` | `AdvisorClient` | `backend/app/models/adv_client.py` | Many-to-many bridge between advisor users and client users, with its own `status`. |
| `engagements` | `Engagement` | `backend/app/models/engagement.py` | The central workspace: one client-advisor working relationship. Parent of nearly every tool record. |
| `diagnostics` | `Diagnostic` | `backend/app/models/diagnostic.py` | A business health assessment: questions, responses, scores, AI analysis, report. |
| `conversations` | `Conversation` | `backend/app/models/conversation.py` | A chat session between a user and the AI, categorised (`general`, `diagnostic`, `finance`, `legal`, `operations`, …). |
| `messages` | `Message` | `backend/app/models/message.py` | One `user` or `assistant` turn inside a conversation, plus raw provider response JSON. |
| `notes` | `Note` | `backend/app/models/note.py` | Free-text documentation attached to an engagement, optionally to a diagnostic or task. |
| `tasks` | `Task` | `backend/app/models/task.py` | Action items, manual or generated from a diagnostic or a module deliverable. |
| `media` | `Media` | `backend/app/models/media.py` | Uploaded files and their LLM-provider file ids. |
| `diagnostic_media` | *(bare `Table`, no class)* | `backend/app/models/media.py:13-19` | Association table: diagnostics ↔ media, many-to-many. Composite PK + `created_at`. |
| `document_templates` | `DocumentTemplate` | `backend/app/models/document_template.py` | `.docx` templates stored as `LargeBinary` **inside the database**. |
| `impersonation_sessions` | `ImpersonationSession` | `backend/app/models/impersonation.py` | Audit record of a superadmin impersonating another user (`active` / `ended`). |
| `ai_field_privacy` | `AIFieldPrivacy` | `backend/app/models/ai_field_privacy.py` | Per-(`questionnaire_type`, `field_name`) flag deciding whether a field is sent to the AI. Absent row = included. |
| `bba` | `BBA` | `backend/app/models/bba.py` | Business Benchmark Analysis: a 9-step wizard from file upload through findings, 12-month plan, Excel task planner and slide deck. |
| `strategy_workbooks` | `StrategyWorkbook` | `backend/app/models/strategy_workbook.py` | Strategy workshop workbook generation session (uploads → extracted data → generated file). |
| `strategic_business_plans` | `StrategicBusinessPlan` | `backend/app/models/strategic_business_plan.py` | 6-step strategic plan wizard: cross-analysis, section-by-section drafting, export, slides. |
| `roles_matrices` | `RolesMatrix` | `backend/app/models/roles_matrix.py` | Roles & Responsibilities matrix build for the HR Planning Tool "Job Roles" tab. |
| `pd_scorecards` | `PDScorecard` | `backend/app/models/pd_scorecard.py` | One Position Description + Scorecard build for a client; holds the source matrix and shared inputs. |
| `pd_scorecard_roles` | `PDScorecardRole` | `backend/app/models/pd_scorecard.py` | One role inside a build, with its own PD draft, scorecard draft and approval state. |
| `program_module_deliverable` | `ProgramModuleDeliverable` | `backend/app/models/program_deliverable.py` | **Shared library** of preset deliverables, authored once per (`program_type`, `module_code`, `deliverable_key`). |
| `engagement_module_deliverable` | `EngagementModuleDeliverable` | `backend/app/models/program_deliverable.py` | **Sparse** per-engagement completion/scope state, and the home for advisor-added deliverables. |
| `program_module_content` | `ProgramModuleContent` | `backend/app/models/program_guide.py` | Admin-authored module card content: focus, purpose, sessions, guardrails, tables — one JSONB column per spec section. |
| `engagement_program_module_state` | `EngagementProgramModuleState` | `backend/app/models/program_guide.py` | The advisor's manual module-order override for one engagement (recommended order is computed live, not stored). |
| `engagement_module_checklist_item` | `EngagementModuleChecklistItem` | `backend/app/models/program_guide.py` | Tick-off state for a module's preparation checklist. **Schema only — no API, service or UI references it** (docstring at `backend/app/models/program_guide.py:168-170`; verified by grep across `backend/app/` and `frontend/src/`). |

How the last five tables are used at runtime is covered in *Value Builder Programme — Program Guide & Deliverables*; the schema-level invariant that governs the deliverable pair is in [`is_complete` / `is_in_scope` and sparse rows](#is_complete--is_in_scope-and-sparse-rows) below.

### ERD

Real foreign keys only. `-->` means a declared `ForeignKey`; `- ->` means a UUID column that *names* another table in its comment but carries **no** constraint.

```
                          firms
     firm_admin_id (UNIQUE, RESTRICT, use_alter) --> users.id
     subscription_id (SET NULL)                  --> subscriptions.id

   firms 1 ──── 0..N users.firm_id        (SET NULL, indexed)
   firms 1 ──── 0..N engagements.firm_id  (SET NULL, indexed)
   firms.clients[]  - -> users.id         (NO FK, no index)

  users 1 ──── 0..N advisor_client.advisor_id  (CASCADE)
  users 1 ──── 0..N advisor_client.client_id   (CASCADE)
              UNIQUE (advisor_id, client_id) = uq_advisor_client

  users 1 ──── 0..N media.user_id                               (CASCADE)
  users 1 ──── 0..N conversations.user_id                       (CASCADE)
  conversations 1 ──── 0..N messages.conversation_id            (CASCADE,
                                                    order_by created_at)
  users 1 ──── 0..N impersonation_sessions.original_user_id     (CASCADE)
  users 1 ──── 0..N impersonation_sessions.impersonated_user_id (CASCADE)
  users 1 ──── 0..N ai_field_privacy.updated_by_user_id         (SET NULL)

  engagements
    |-- 0..N diagnostics.engagement_id                      (CASCADE, NOT NULL)
    |-- 0..N tasks.engagement_id                            (CASCADE, NOT NULL)
    |-- 0..N notes.engagement_id                            (CASCADE, NOT NULL)
    |-- 0..N bba.engagement_id                              (CASCADE, nullable)
    |-- 0..N strategic_business_plans.engagement_id         (CASCADE, nullable)
    |-- 0..N strategy_workbooks.engagement_id               (SET NULL, nullable)
    |-- 0..N roles_matrices.engagement_id                   (SET NULL, nullable)
    |-- 0..N pd_scorecards.engagement_id                    (SET NULL, nullable)
    |-- 0..N engagement_module_deliverable.engagement_id    (CASCADE)
    |-- 0..N engagement_module_checklist_item.engagement_id (CASCADE)
    `-- 0..1 engagement_program_module_state.engagement_id  (CASCADE, UNIQUE)

    engagements.client_id               - -> users.id  (NO FK, indexed)
    engagements.primary_advisor_id      - -> users.id  (NO FK, indexed)
    engagements.client_ids[]            - -> users.id  (NO FK, no index)
    engagements.secondary_advisor_ids[] - -> users.id  (NO FK, no index)

  diagnostics
    |-- created_by_user_id   --> users.id           (CASCADE, NOT NULL)
    |-- completed_by_user_id --> users.id           (SET NULL)
    |-- conversation_id      --> conversations.id   (SET NULL)
    |-- 0..N tasks.diagnostic_id                    (SET NULL)
    |-- 0..N notes.diagnostic_id                    (SET NULL)
    |-- 0..N bba.diagnostic_id                      (SET NULL)
    |-- 0..N strategy_workbooks.diagnostic_id       (SET NULL)
    |-- 0..N strategic_business_plans.diagnostic_id (SET NULL)
    `-- M..N media  via  diagnostic_media(diagnostic_id, media_id)  both CASCADE

  tasks
    |-- assigned_to_user_id  --> users.id  (SET NULL)
    |-- created_by_user_id   --> users.id  (CASCADE, NOT NULL)
    |-- assigned_to_user_ids[] - -> users.id (NO FK; GIN index)
    `-- source_deliverable_id  - -> program_module_deliverable.id
                                 OR engagement_module_deliverable.id
                                 (POLYMORPHIC, deliberately NO FK; btree index)

  notes.author_id --> users.id (CASCADE), notes.task_id --> tasks.id (SET NULL)
  notes.read_by[] - -> users.id (NO FK)

  tool records -> users (creator):
    bba.created_by_user_id                      --> users.id (CASCADE, NOT NULL)
    strategic_business_plans.created_by_user_id --> users.id (CASCADE, NOT NULL)
    roles_matrices.created_by_user_id           --> users.id (CASCADE, NOT NULL)
    pd_scorecards.created_by_user_id            --> users.id (CASCADE, NOT NULL)
    strategy_workbooks.created_by_user_id       --> users.id (SET NULL, nullable)
    document_templates.uploaded_by_user_id      - -> users.id (NO FK, NOT NULL)

  pd_scorecards 1 ──── 0..N pd_scorecard_roles.pd_scorecard_id (CASCADE,
                              order_by sort_order;
                              ix_pd_scorecard_roles_parent_order)

  program_module_deliverable 1 ──── 0..N engagement_module_deliverable
                                     .library_deliverable_id (CASCADE, NULLABLE)
      UNIQUE (engagement_id, library_deliverable_id)
      NULL library_deliverable_id = advisor-added, unconstrained in count
      engagement_module_deliverable.completed_by_user_id  --> users.id (SET NULL)
      engagement_module_deliverable.scoped_out_by_user_id --> users.id (SET NULL)
      engagement_module_deliverable.created_by_user_id    --> users.id (SET NULL)

  program_module_content  UNIQUE (program_type, module_code)
      .preparation_checklist[].key == engagement_module_checklist_item
                                      .checklist_item_key  (by convention,
                                                            not by FK)
  engagement_program_module_state.custom_order_set_by_user_id --> users.id
                                                                  (SET NULL)
  engagement_module_checklist_item.checked_by_user_id --> users.id (SET NULL)
      UNIQUE (engagement_id, module_code, checklist_item_key)
```

**Gotcha:** `engagements` has **no foreign key to `users` at all**. `client_id` and `primary_advisor_id` were created as bare `sa.UUID()` columns in `backend/alembic/versions/4ff8aece5340_engagement_diagnostic_notes_tasks_table.py:24-25` and are still bare on the model (`backend/app/models/engagement.py:24,28`). Deleting a user leaves dangling engagement references; nothing at the database level prevents it. The `Engagement.client` relationship is declared `viewonly=True` with an explicit `primaryjoin="foreign(Engagement.client_id) == User.id"` (`backend/app/models/engagement.py:47-53`) precisely because there is no constraint to infer from.

### Column reference — high-traffic entities

#### `users` — `backend/app/models/user.py:102-287`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID(as_uuid=True)` | no | `uuid.uuid4` (Python) | PK |
| `auth0_id` | `String(255)` | **yes** | — | UNIQUE, indexed. NULL for email/password users |
| `hashed_password` | `String(255)` | yes | — | NULL for Auth0-only users |
| `email` | `String(255)` | no | — | **No column-level UNIQUE.** Uniqueness comes from the partial index `ix_users_email_active` |
| `name`, `first_name`, `last_name`, `nickname`, `business_name` | `String(255)` | yes | — | |
| `picture`, `bio` | `Text` | yes | — | |
| `email_verified` | `Boolean` | no | `False` (Python) | |
| `is_active` | `Boolean` | no | `True` (Python) | |
| `is_deleted` | `Boolean` | no | `False` (Python) | Soft-delete flag; drives the partial index |
| `role` | `UserRoleType(50)` — a `TypeDecorator` over `String` | no | `UserRole.ADVISOR` (Python) | See [`UserRoleType`](#userroletype-the-mixed-case-role-enum) |
| `created_at` | `DateTime` | no | `datetime.utcnow` (Python) | Naive UTC |
| `updated_at` | `DateTime` | no | `datetime.utcnow`, `onupdate=datetime.utcnow` | |
| `last_login` | `DateTime` | yes | — | |
| `firm_id` | `UUID` | yes | — | FK → `firms.id` `ON DELETE SET NULL`, indexed |
| `account_type` | `String(20)` | no | `'advisory'` (server) | **In the database only** — added by `backend/alembic/versions/f7a1b2c3d4e5_self_service_saas.py:49-58`, absent from the model. `'advisory'` vs `'self_service'`. See [the self-service tier](#tables-with-no-model-the-self-service-tier) |

`__table_args__` (`backend/app/models/user.py:111-118`):
```python
Index('ix_users_email_active', 'email', unique=True,
      postgresql_where=sa_text('is_deleted = false'))
```

#### `engagements` — `backend/app/models/engagement.py`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4` (Python) | PK |
| `firm_id` | `UUID` | yes | — | FK → `firms.id` SET NULL, indexed. NULL for solo advisors |
| `client_id` | `UUID` | yes | — | Indexed, **no FK**. "kept for backward compatibility" |
| `client_ids` | `ARRAY(UUID)` | yes | — | **No index.** The current multi-client field |
| `primary_advisor_id` | `UUID` | yes | — | Indexed, **no FK**. Made nullable by `f7a1b2c3d4e5_self_service_saas.py:88-95` |
| `secondary_advisor_ids` | `ARRAY(UUID)` | yes | — | **No index** |
| `engagement_name` | `String(255)` | no | — | |
| `business_name` | `String(255)` | yes | — | |
| `industry` | `String(100)` | yes | — | |
| `description` | `Text` | yes | — | |
| `tool` | `String(100)` | yes | — | `backend/app/models/engagement.py:36`, "Selected tool for the engagement". `ProgramModuleDeliverable.program_type` and `ProgramModuleContent.program_type` both document themselves as matching it (`backend/app/models/program_deliverable.py:38`, `backend/app/models/program_guide.py:31`) |
| `status` | `String(50)` | no | `'active'` (**server**) | Indexed. Comment: `active, paused, completed, archived` |
| `is_deleted` | `Boolean` | no | `'false'` (server) | |
| `created_at` | `DateTime` | no | `func.current_timestamp()` (server) | |
| `updated_at` | `DateTime` | no | `func.current_timestamp()` server, `onupdate=func.current_timestamp()` | |
| `completed_at` | `DateTime` | yes | — | |

**Gotcha:** `primary_advisor_id` was declared NOT NULL on the model long after the database allowed NULL. The comment at `backend/app/models/engagement.py:26-27` records the fix. Treat model nullability here as a claim to verify, not a guarantee. The migration's own `downgrade()` refuses to restore NOT NULL when any row has a NULL (`f7a1b2c3d4e5_self_service_saas.py:200-211`).

#### `diagnostics` — `backend/app/models/diagnostic.py`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4` | PK |
| `engagement_id` | `UUID` | no | — | FK → `engagements.id` CASCADE, indexed |
| `created_by_user_id` | `UUID` | no | — | FK → `users.id` CASCADE, indexed |
| `completed_by_user_id` | `UUID` | yes | — | FK → `users.id` SET NULL, indexed |
| `conversation_id` | `UUID` | yes | — | FK → `conversations.id` SET NULL, indexed |
| `status` | `String(50)` | no | `'draft'` (server) | Indexed. Authoritative set: `draft`, `in_progress`, `processing`, `completed`, `failed`, `archived` |
| `diagnostic_type` | `String(100)` | no | `'business_health_assessment'` (server) | |
| `diagnostic_version` | `String(20)` | no | `'1.0'` (server) | |
| `questions` | `JSONB` | **no** | — | The whole questionnaire, copied in from the JSON fixture at creation. The comment at `backend/app/models/diagnostic.py:36` says "All 200 questions"; `backend/files/diagnostic-surveyjs.json` actually holds **9 pages and 272 top-level elements** (not all of them scored questions). The comment and the class docstring at `:14` are stale — measure, do not trust the number |
| `user_responses` | `JSONB` | yes | — | |
| `scoring_data` | `JSONB` | yes | — | Question- and module-level scores |
| `ai_analysis` | `JSONB` | yes | — | Model-generated insights and recommendations |
| `module_scores` | `JSONB` | yes | — | The 8 module scores (M1–M8) |
| `overall_score` | `Numeric(3,1)` | yes | — | 0–5, one decimal |
| `report_url` | `Text` | yes | — | |
| `report_html` | `Text` | yes | — | |
| `tasks_generated_count` | `Integer` | yes | `'0'` (server) | |
| `ai_model_used` | `String(100)` | yes | — | |
| `ai_tokens_used` | `Integer` | yes | — | |
| `tag` | `String(255)` | yes | — | Advisor-only organisational tag |
| `celery_task_id` | `String(255)` | yes | — | `backend/app/models/diagnostic.py:61`, added by migration revision `1902d32c0ce6`. **Always NULL; no code reads or writes it** (grep across `backend/app/`, `backend/scripts/`, `backend/seed/`, `backend/tests/` returns only the model line). Dead column — see [Debt visible from the schema](#debt-visible-from-the-schema) |
| `is_deleted` | `Boolean` | no | `'false'` (server) | |
| `created_at` / `updated_at` | `DateTime` | no | `current_timestamp()` server; `updated_at` has `onupdate` | |
| `started_at`, `completed_at` | `DateTime` | yes | — | |

**Gotcha:** the model's own `status` comment (`backend/app/models/diagnostic.py:31`) reads `"draft, in_progress, processing, completed, archived"` and **omits `failed`**, which the running code writes at `backend/app/tasks/diagnostic_tasks.py:227` and `:260` and which the API documents (`backend/app/api/diagnostics.py:450-452`, `:563`). Anything generated from that comment — a validator, an enum, a UI filter — will silently exclude every failed run. The six-value set in the table above is authoritative. Status transitions and who writes them are in *Diagnostic Engine*.

#### `tasks` — `backend/app/models/task.py`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4` | PK |
| `engagement_id` | `UUID` | no | — | FK → `engagements.id` CASCADE, indexed |
| `diagnostic_id` | `UUID` | yes | — | FK → `diagnostics.id` SET NULL, indexed |
| `source_deliverable_id` | `UUID` | yes | — | Indexed (`ix_tasks_source_deliverable_id`), **polymorphic, no FK** |
| `assigned_to_user_id` | `UUID` | yes | — | FK → `users.id` SET NULL, indexed |
| `assigned_to_user_ids` | `ARRAY(UUID)` | yes | — | Model says `index=True`; the migration creates it as GIN (`add_assigned_to_user_ids_to_tasks.py:27`) |
| `created_by_user_id` | `UUID` | no | — | FK → `users.id` CASCADE, indexed |
| `title` | `String(255)` | no | — | |
| `description` | `Text` | yes | — | |
| `task_type` | `String(50)` | no | `'manual'` (server) | `manual`, `diagnostic_generated`, `deliverable_generated` |
| `status` | `String(50)` | no | `'pending'` (server) | Indexed. `pending, in_progress, completed, cancelled` |
| `priority` | `String(20)` | no | `'medium'` (server) | Indexed. `low, medium, high, critical` |
| `priority_rank` | `Integer` | yes | — | 1 = highest, from the AI |
| `module_reference` | `String(50)` | yes | — | e.g. `M1` |
| `impact_level`, `effort_level` | `String(20)` | yes | — | `low, medium, high` |
| `due_date` | `Date` | yes | — | Indexed. **`Date`, not `DateTime`** |
| `completed_at` | `DateTime` | yes | — | |
| `is_deleted` | `Boolean` | no | `'false'` (server) | |
| `created_at` / `updated_at` | `DateTime` | no | `current_timestamp()`; `updated_at` has `onupdate` | |
| `section` | `String(20)` | yes | — | **In the database only** — added by `backend/alembic/versions/add_sale_ready_program_tables.py:21`, absent from the model. See [the Sale Ready programme](#tables-with-no-model-the-sale-ready-programme) |

#### `media` — `backend/app/models/media.py`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4` | PK |
| `user_id` | `UUID` | no | — | FK → `users.id` CASCADE, indexed |
| `file_name` | `String(255)` | no | — | Original filename |
| `file_path` | `Text` | no | — | Storage path (local or S3) |
| `file_size` | `Integer` | yes | — | Bytes |
| `file_type` | `String(100)` | yes | — | MIME type |
| `file_extension` | `String(20)` | yes | — | |
| `openai_file_id` | `String(255)` | yes | — | UNIQUE + indexed. Legacy, "preserved for rollback" |
| `openai_purpose` | `String(50)` | yes | — | Legacy |
| `openai_uploaded_at` | `DateTime` | yes | — | Legacy |
| `llm_file_id` | `String(255)` | yes | — | Indexed (not unique). Current provider-agnostic field |
| `llm_provider` | `String(50)` | yes | — | `claude`, `openai` |
| `llm_uploaded_at` | `DateTime` | yes | — | |
| `description` | `Text` | yes | — | |
| `question_field_name` | `String(255)` | yes | — | Which diagnostic question this file answers |
| `tag` | `String(255)` | yes | — | Advisor-only |
| `is_active` | `Boolean` | no | `'true'` (server) | |
| `created_at` / `updated_at` | `DateTime` | no | `current_timestamp()`; `updated_at` has `onupdate` | |
| `deleted_at` | `DateTime` | yes | — | **Media soft-deletes with a timestamp, not an `is_deleted` boolean.** The only table in the model set that does |

#### `firms` — `backend/app/models/firm.py`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4` | PK |
| `firm_name` | `String(255)` | no | — | |
| `firm_admin_id` | `UUID` | **no** | — | UNIQUE + indexed. FK → `users.id` `ON DELETE RESTRICT`, declared `use_alter=True` |
| `subscription_id` | `UUID` | yes | — | FK → `subscriptions.id` SET NULL, indexed. The index was originally UNIQUE; `remove_unique_subscription_id_from_firms.py` (rev id `remove_unique_sub_id`) recreates it non-unique so several firms may share a subscription |
| `subscription_plan` | `String(50)` | yes | — | Denormalised copy of the plan name |
| `seat_count` | `Integer` | no | `5` (Python) | Minimum 5 per the comment |
| `seats_used` | `Integer` | no | `1` (Python) | |
| `billing_email` | `String(255)` | yes | — | |
| `clients` | `ARRAY(UUID)` | yes | `None` | Client user ids on this firm. No index, no FK |
| `is_active` | `Boolean` | no | `True` (Python) | `backend/app/models/firm.py:38`. **`firms` has no `is_deleted` and no `deleted_at`** — `is_active` is the only flag |
| `created_at` / `updated_at` | `DateTime` | no | `datetime.utcnow` (Python); `updated_at` has `onupdate` | |

`use_alter=True` on `firm_admin_id` exists to break the `firms ↔ users` FK cycle when SQLAlchemy sorts tables for metadata-level creation (`backend/app/models/firm.py:24-25`). The relationship `Firm.advisors` must specify `foreign_keys="User.firm_id"` because `firm_admin_id` is a second join path between the same two tables (`backend/app/models/firm.py:45-46`).

**Gotcha:** the `firms_firm_admin_id_fkey` constraint is **missing from some databases**. `create_firms_and_subscriptions_tables.py` (rev id `create_firms_subs`) declares the foreign key only inside its `if 'firms' not in tables` branch (line 69); the `else` branch at line 73 creates an index and nothing else, so a cloned or pre-existing database never received it. `backend/alembic/versions/add_firms_firm_admin_fk.py` — the current head — adds it where absent, and raises `RuntimeError` rather than skipping if any firm points at a nonexistent user (`add_firms_firm_admin_fk.py:59-70`).

#### `subscriptions` — `backend/app/models/subscription.py`

| Column | Type | Nullable | Default | Notes |
|---|---|---|---|---|
| `id` | `UUID` | no | `uuid4` | PK |
| `plan_name` | `String(50)` | no | — | |
| `seat_count` | `Integer` | no | — | |
| `monthly_price` | `Numeric(10,2)` | no | — | |
| `status` | `String(20)` | no | `"active"` (Python) | `active, cancelled, past_due, trialing`. Note this is a *plan* status — `subscriptions` has no delete or active flag of any kind (`backend/app/models/subscription.py:19-25`) |
| `created_at` / `updated_at` | `DateTime` | no | `datetime.utcnow` (Python); `updated_at` has `onupdate` | |
| `user_id` | `UUID` | yes | — | **Database only.** FK `fk_subscriptions_user_id` → `users.id` CASCADE + `ix_subscriptions_user_id`, added by `f7a1b2c3d4e5_self_service_saas.py:101-109` |
| `program` | `String(50)` | yes | — | **Database only.** `value_builder` or `sale_ready` (`f7a1b2c3d4e5_self_service_saas.py:112-116`) |
| `provider` | `String(20)` | no | `'manual'` (server) | **Database only.** `manual` or `stripe` (`f7a1b2c3d4e5_self_service_saas.py:119-123`) |
| `price`, `start_date`, `end_date`, `billing_period`, `currency`, `next_billing_date` | environment-dependent | yes | — | **Database only, and created by no migration in this repo.** They exist in some environments out-of-band; `fix_price_column_nullable.py` (rev `fix_price_nullable`) and `fix_subscription_columns_nullable.py` (rev `fix_subscription_cols`) only *relax* them to nullable where present |

Columns `create_firms_and_subscriptions_tables.py:34-40` created but that are **no longer** drift: `current_period_start`, `current_period_end`, `cancel_at_period_end`, `cancelled_at` and `firm_id` are dropped by `a8d3b2d2caf9_add_bba_task_planner_columns.py:56-67`; `stripe_subscription_id` / `stripe_customer_id` are dropped by `align_schema_with_models.py` (docstring point 2). Do not re-add them expecting the model to notice.

`Subscription` declares no relationships at all; the join runs the other way via `Firm.subscription` with an explicit `primaryjoin` (`backend/app/models/subscription.py:27-30`, `backend/app/models/firm.py:48`).

#### Declared on the model but never written

| Column | Where | Status |
|---|---|---|
| `strategy_workbooks.drive_file_id` | `backend/app/models/strategy_workbook.py:42-43` | Declared `Text`, nullable, commented "Google Drive file ID for the generated workbook", and serialised by `to_dict()` (`:81`) — so it reaches the API response as a permanent `null`. **Nothing ever writes it.** There is no Google client library in `backend/requirements.txt` and the `GOOGLE_DRIVE_*` settings have no reader; see *Environments, Configuration & Deployment* |
| `diagnostics.celery_task_id` | `backend/app/models/diagnostic.py:61` | Always NULL; no code path reads or writes it |

### Tables with no model: the self-service tier

`backend/alembic/versions/f7a1b2c3d4e5_self_service_saas.py` ("Feature 7") adds a self-service signup tier to the schema. On `staging` it has **no application code at all** — no models, no services, no routers, no frontend. Grepping `backend/app/` and `frontend/src/` for `account_type` or `self_service` returns exactly one hit, and it is a comment.

| Change | Detail |
|---|---|
| `users.account_type` | `String(20)` NOT NULL `server_default='advisory'`; `'advisory'` \| `'self_service'` — how the account was provisioned (`:49-58`). **Not on the `User` model** |
| `engagements.primary_advisor_id` | Altered to nullable (`:89-95`) — a self-service engagement has no advisor |
| `subscriptions.user_id` / `.program` / `.provider` | Owner-scoped subscription columns plus `fk_subscriptions_user_id` and `ix_subscriptions_user_id` (`:101-123`). None on the `Subscription` model |
| `owner_team_members` (table) | Created at `:129-149` with three indexes. No model, no query anywhere |
| `signup_intents` (table) | Created at `:155-173` with two indexes. No model, no query anywhere |
| `userrole` enum label `team_member` | Added at `:67-83`, preceded by an explicit `op.execute("COMMIT")` at `:66` because `ALTER TYPE … ADD VALUE` cannot run inside a transaction on older PostgreSQL. Not a member of the Python `UserRole` enum |

**The consequence is live and it is an authorisation gap.** `backend/app/services/deliverable_permissions.py:20-30` documents it precisely: a true self-service owner is `UserRole.CLIENT` **and** `account_type == 'self_service'`, while an advisor-provisioned client is `CLIENT` + `'advisory'`; "account_type exists in the database but is not on the User model on this branch, so the two cannot be told apart in code". The current deliverables rule denies all clients, so the gap is harmless *today*. Any future rule that must treat an advisory client differently from a self-service owner is blocked until `account_type` is added to the `User` model — that is the prerequisite, and it is a one-line model change plus whatever backfill the environments need.

The application code for this tier lives unmerged on `feature/self-service` (`backend/app/models/owner_team_member.py`, `backend/app/models/signup_intent.py`, `backend/app/services/self_service.py`) — see *Unmerged Work on Other Branches*. The migration is written idempotently with inspector guards (`:31-41`) "because several environments have drifted from the migration history"; read that as a warning about the shared development database.

### Tables with no model: the Sale Ready programme

`backend/alembic/versions/add_sale_ready_program_tables.py` (revision id `add_sale_ready_program_tables`, down-revision `add_program_guide_tables`) creates the Sale Ready analogue of the Value Builder schema — stages instead of modules, task templates, a due-diligence checklist and a document register:

| Table | Created at | Shape |
|---|---|---|
| `program_stage` | `:24` | `(program_type, stage_code)` unique, `stage_type`, `default_order`, `title`, `is_active`; index `ix_program_stage_type_order` |
| `program_task_template` | `:40` | Per-stage task presets with `section`, `priority`, `default_order`, `due_offset_days`; index `ix_program_task_template_type_stage` |
| `program_dd_template` | `:57` | Due-diligence item library |
| `engagement_stage_state` | `:74` | Per-engagement stage progress |
| `engagement_dd_item` | `:89` | Per-engagement due-diligence item state |
| `engagement_document_register_entry` | `:110` | Per-engagement document register |

It also adds `tasks.section VARCHAR(20)` (`:21`), which is why the shared `tasks` table carries a column no model declares.

**Nothing on `staging` references any of it** — no SQLAlchemy model, no schema, no service, no router, no frontend; grepping `backend/app/` and `frontend/src/` for the six table names returns no source hits. The application layer exists unmerged on `feature/sale-ready-management` (`backend/app/models/sale_ready.py`, `backend/app/schemas/sale_ready.py`, `backend/app/services/sale_ready_service.py`, `backend/app/api/sale_ready.py`, `backend/scripts/seed_sale_ready_content.py`, three fixtures under `backend/files/sale_ready/`, and `frontend/src/questions/questions_sale_ready.json`) — see *Unmerged Work on Other Branches*. Treat the Value Builder tables as the only live programme schema. Anyone extending Sale Ready must decide up front whether to adopt these tables by merging that branch or to drop them; leaving them is what forces the hand-trimming rule below.

**Gotcha:** stale bytecode for the unmerged code is present in the working tree — `backend/app/models/__pycache__/sale_ready.cpython-312.pyc` and `backend/app/services/__pycache__/sale_ready_service.cpython-312.pyc` exist with no corresponding `.py`. A grep that includes `__pycache__` will report the feature as present. Grep source only.

### Conventions — rules to follow

1. **UUID primary keys, generated in Python.** Every table uses `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)`. There is no `server_default=gen_random_uuid()` anywhere, so a raw `INSERT` that omits `id` will fail. Always insert through the ORM or supply the id yourself.
2. **JSONB for AI payloads and semi-structured state.** Never `JSON`, never `Text` holding JSON. This covers diagnostic `questions` / `user_responses` / `scoring_data` / `ai_analysis` / `module_scores`, every BBA wizard step, every SBP section array, `Message.response_data` / `message_metadata`, `Note.attachments`, and all of `program_module_content`. When a shape matters, document it in the column's `comment=` — `backend/app/models/program_guide.py:47-106` is the model to imitate.
3. **ARRAY columns exist and change how you query.** `engagements.client_ids`, `engagements.secondary_advisor_ids`, `tasks.assigned_to_user_ids`, `notes.read_by`, `notes.tags` (`ARRAY(String)`), `firms.clients`, `strategy_workbooks.uploaded_media_ids`. Membership is tested with raw SQL containment, not an ORM operator:
   ```python
   text("client_ids @> ARRAY[:uid]::uuid[]").bindparams(uid=client_user_id)
   ```
   including `backend/app/services/dashboard_service.py:267,380`, `backend/app/api/engagements.py:276,289`, `backend/app/api/tasks.py:273-295`, `backend/app/api/note.py:158,166`, and `backend/app/services/login_check.py:52` — the last of these is `text("clients @> ARRAY[:user_id]::uuid[]")` against `firms.clients` **on the login path**, which makes it the most consequential of them. Follow that pattern rather than inventing a new one. **Only `tasks.assigned_to_user_ids` has a GIN index** (`backend/alembic/versions/add_assigned_to_user_ids_to_tasks.py:27`); `client_ids`, `secondary_advisor_ids` and `firms.clients` have none, so every `@>` against them — login included — is a sequential scan. Add a GIN index before scaling those queries.
4. **Soft deletes are `is_deleted BOOLEAN NOT NULL DEFAULT false`** on `users`, `engagements`, `diagnostics`, `tasks`, `notes`, `conversations`, `messages`, `advisor_client`, `bba`, `strategy_workbooks`, `strategic_business_plans`, `roles_matrices`, `pd_scorecards`, `pd_scorecard_roles`, `engagement_module_deliverable`. Three exceptions: `media` uses a nullable `deleted_at` timestamp; `firms` has `is_active` and no delete flag; and `document_templates`, `impersonation_sessions`, `ai_field_privacy`, `subscriptions`, `program_module_content`, `program_module_deliverable`, `engagement_program_module_state` and `engagement_module_checklist_item` have neither. Every read path must filter explicitly — nothing is automatic.
5. **`users.email` uniqueness is a partial index, not a constraint.** `ix_users_email_active` is `UNIQUE (email) WHERE is_deleted = FALSE`, declared on the model (`backend/app/models/user.py:111-118`) and created by `backend/alembic/versions/partial_unique_email_active_users.py` (revision id **`partial_email_idx`**), which dropped the old global `ix_users_email`. This is what lets an address be re-registered after a soft delete. Do not "fix" it back into a plain unique constraint — you will break re-registration and fail on any historical duplicate.
6. **`created_at` / `updated_at` on almost every table**, with `updated_at` always carrying an `onupdate`. Two idioms coexist and must not be mixed within a table:
   - Python-side (`default=datetime.utcnow`, `onupdate=datetime.utcnow`) — `users`, `firms`, `subscriptions`, `impersonation_sessions`. These are `datetime.utcnow`, i.e. naive UTC.
   - Server-side (`server_default=func.current_timestamp()`, `onupdate=func.current_timestamp()`) — everything else.

   Two tables break the pair: `impersonation_sessions` has `created_at` and `ended_at` but **no `updated_at`**; `ai_field_privacy` has `updated_at` (server default + `onupdate`) but **no `created_at`**.
7. **`server_default` vs Python `default`.** Use `server_default` for a value the database must supply on rows written outside the ORM (migration backfills, raw SQL) and for anything a migration adds `NOT NULL` — `server_default='false'` on a new boolean is what makes the `ADD COLUMN` succeed against existing rows. Use a Python `default` when the value is a callable (`uuid.uuid4`, `datetime.utcnow`) or genuinely application-level. The two are not interchangeable in autogenerate: a Python-only default is invisible to the database and will not show as drift, while a mismatched `server_default` will.
8. **`comment=` on columns is the in-repo data dictionary.** Almost every column carries one, and several are long-form design rationale (`backend/app/models/program_guide.py:61-99`, `backend/app/models/task.py:26-32`). Treat writing one as mandatory for any new column. Alembic is configured to *ignore* comment-only diffs (see [Migrations](#migrations)), so a stale comment is never flagged — the diagnostic `status` and `questions` comments above are both wrong today. Keep them accurate by hand, and never generate code from one without checking it.
9. **No `CheckConstraint` anywhere.** Stated explicitly at `backend/app/models/program_deliverable.py:124-125` and `backend/app/services/program_deliverable_service.py:16-17`. Every cross-column invariant is enforced in the service layer. If you add one, you are breaking the convention, and existing rows may not satisfy it.

### `UserRoleType`: the mixed-case role enum

`backend/app/models/user.py:24-99`. This is the single most surprising thing in the data model.

The Python enum is all-lowercase (`backend/app/models/user.py:14-21`):

| `UserRole` member | Python `.value` | Value written to PostgreSQL |
|---|---|---|
| `ADVISOR` | `advisor` | **`ADVISOR`** |
| `CLIENT` | `client` | **`CLIENT`** |
| `ADMIN` | `admin` | **`ADMIN`** |
| `SUPER_ADMIN` | `super_admin` | **`SUPER_ADMIN`** |
| `FIRM_ADMIN` | `firm_admin` | **`firm_admin`** (lowercase) |
| `FIRM_ADVISOR` | `firm_advisor` | **`firm_advisor`** (lowercase) |

The column stores **mixed case** because of how the two groups arrived. `backend/alembic/versions/ec0b9b4c6fec_users_table.py:32` created the column as a PostgreSQL `ENUM` named `userrole` with four uppercase labels:

```python
sa.Column('role', sa.Enum('ADVISOR', 'CLIENT', 'ADMIN', 'SUPER_ADMIN', name='userrole'), nullable=False, ...)
```

When firm roles were added, `backend/fix_userrole_enum.sql` appended them with `ALTER TYPE userrole ADD VALUE` using the **lowercase** spellings — matching the Python values, not the existing uppercase convention. The type has been mixed-case ever since.

`UserRoleType` is a `TypeDecorator` over `String` (`impl = String`, `cache_ok = True`, `__init__(length=50)`) that bridges the gap:

- **`process_bind_param`** (write path, `backend/app/models/user.py:36-75`) takes a `UserRole` *or* a bare string, lowercases it, and looks it up in a hard-coded `db_value_map` — **the map is written out twice**, once for the enum branch (lines 48-55) and once for the string branch (lines 60-67). The four original roles map to their uppercase spellings; the two firm roles map to themselves in lowercase. A string not in the map is validated against `[e.value for e in UserRole]` and raises `ValueError` if unknown; otherwise it falls through to `.upper()`.
- **`process_result_value`** (read path, `backend/app/models/user.py:77-99`) normalises whatever the database returns through a second hard-coded `lowercase_map` that accepts **both** casings for the firm roles (`FIRM_ADMIN` and `firm_admin` both → `firm_admin`), then constructs `UserRole(normalized)`. If that raises `ValueError` it returns the raw value rather than propagating.

Why it exists: the column was migrated from a native PG `ENUM` to the decorator's `VARCHAR(50)` by `backend/alembic/versions/c457376982ac_conversations_and_messages.py:59-62` and again by `backend/alembic/versions/662a7acdc7ea_first_name_last_name.py:23-26` — both `from app.models.user import UserRoleType` directly. Existing row values were not rewritten. So the column now holds free text in two casing conventions, and the decorator is the only thing keeping application code able to write `UserRole.FIRM_ADMIN` and compare against it.

**Gotcha:** two alembic revisions import a live application model. Renaming or moving `UserRoleType` breaks historical migrations.

**Adding a role requires four coordinated edits. Miss any one and it fails differently:**

| What you change | What breaks if you skip it |
|---|---|
| Add the member to `class UserRole` | `process_result_value` cannot construct the enum and returns a raw string; every `user.role == UserRole.X` comparison (94 direct `== UserRole` / `!= UserRole` sites, out of 196 `UserRole.` references across `backend/app/`) returns `False`, so the user is silently treated as having no permissions rather than being rejected. |
| Add the entry to **both** `db_value_map` blocks in `process_bind_param` | The fallback `value_str.upper()` writes an uppercase spelling. It persists (the column is `VARCHAR`), but never matches your intended lowercase-convention role again, producing a permanently mis-cased row. |
| Add the entry to `lowercase_map` in `process_result_value` | The fallback `value_str.lower()` happens to work for single-case values, but any role whose DB spelling differs from `python_value.lower()` reads back wrong. |
| Add the label to the PG type where it still exists | Environments whose column is still the native `userrole` enum reject the `INSERT` with `invalid input value for enum userrole`. Use the guarded pattern in `backend/fix_userrole_enum.sql` (`DO $$ … IF NOT EXISTS (SELECT 1 FROM pg_enum …) THEN ALTER TYPE userrole ADD VALUE …`). Note `ALTER TYPE … ADD VALUE` cannot run inside a transaction on PG < 12 — `f7a1b2c3d4e5_self_service_saas.py:66` issues an explicit `op.execute("COMMIT")` first. |

**Gotcha:** `team_member` was already added to the `userrole` type by `backend/alembic/versions/f7a1b2c3d4e5_self_service_saas.py:67-83`, but it is **not** a member of the Python `UserRole` enum and no code references it. A row with that role reads back as the raw string `'team_member'` and matches nothing.

### `is_complete` / `is_in_scope` and sparse rows

Read the module docstring at `backend/app/models/program_deliverable.py:1-18` — it is the specification. What follows is the schema-level invariant; the API, service and UI that sit on top of it are in *Value Builder Programme — Program Guide & Deliverables*.

**The template/instance split.** `program_module_deliverable` is a shared library authored once per (`program_type`, `module_code`, `deliverable_key`) — `UniqueConstraint(..., name='uq_program_module_deliverable_type_module_key')` at `backend/app/models/program_deliverable.py:87`. `engagement_module_deliverable` holds per-engagement state and, for preset instances, **no copy of the authored text** — `title`, `description` and `is_mandatory` must be `NULL` and are read live from the library row. That is what makes a library edit visible to every live engagement immediately. Presets are never deleted; `is_active=False` retires one (`backend/app/models/program_deliverable.py:81`).

**The sparse-row rule: an absent row means "incomplete and in scope."** A row in `engagement_module_deliverable` is created only when someone ticks a deliverable off or scopes it out. Consequences you must design around:

- Adding a new preset to the library makes it appear on **every** live engagement with **no backfill** — the default state is expressible as the absence of a row.
- Any status computation must start from the library list and left-join the instance table, treating a missing join as `is_complete = false, is_in_scope = true`. Counting rows in `engagement_module_deliverable` gives the wrong answer. `backend/app/services/program_deliverable_service.py:1-20` describes the query shape: the library LEFT JOINed to its sparse instances, `UNION ALL` the advisor-added rows, with `COALESCE` defaults on the library leg.
- `UniqueConstraint('engagement_id', 'library_deliverable_id')` enforces at most one instance per (engagement, preset). Because PostgreSQL treats NULLs as distinct in a unique index, the same constraint places **no limit** on advisor-added rows (`library_deliverable_id IS NULL`) — deliberate, and documented at `backend/app/models/program_deliverable.py:175-179`. The constraint doubles as the join index for status computation.

**Why completion and scope are two booleans, not one status column** (`backend/app/models/program_deliverable.py:127-130`): scoping a *completed* deliverable out and then back in must leave `is_complete` untouched. A single `status` enum would collapse `completed` and `scoped_out` into one slot and forget the completion on the way back. Each flag carries its own actor and timestamp: `completed_by_user_id` / `completed_at`, `scoped_out_by_user_id` / `scoped_out_at`.

**Two row kinds, discriminated by `library_deliverable_id`:**

| | `library_deliverable_id IS NOT NULL` (preset) | `library_deliverable_id IS NULL` (advisor-added) |
|---|---|---|
| `title` / `description` / `is_mandatory` | MUST be NULL; read from the library | Carried on the row |
| `module_code` | Denormalised copy | Authoritative |
| Removal | Scoped out, **never** deleted | Soft-deleted via `is_deleted` |
| Count per engagement | At most one (unique constraint) | Unbounded |

These invariants are enforced in the service layer only — there are no check constraints (`backend/app/models/program_deliverable.py:123-125`).

**Related design:** `tasks.source_deliverable_id` is a nullable UUID with **no** foreign key, holding the *library* id for a preset and the *instance* id for an advisor-added deliverable — two tables, so no single FK could express it. The rationale at `backend/alembic/versions/add_task_source_deliverable.py:1-22` is explicit: `engagement_module_deliverable.library_deliverable_id` is `ON DELETE CASCADE`, so an FK here would have deleted a client's tasks the first time a preset was retired. Tasks must outlive their deliverable being scoped out or retired.

### Migrations

#### Configuration

| Thing | Where | Value |
|---|---|---|
| Script location | `backend/alembic.ini:5` | `alembic` |
| `prepend_sys_path` | `backend/alembic.ini:13` | `.` |
| `sqlalchemy.url` in the ini | `backend/alembic.ini:56` | A **placeholder** (`driver://user:pass@localhost/dbname`) that is always overridden |
| Real URL | `backend/alembic/env.py:24` | `config.set_main_option('sqlalchemy.url', settings.DATABASE_URL)` — migrations target whatever `DATABASE_URL` the environment sets. There is no `-x` override and no separate migration URL. |
| `target_metadata` | `backend/alembic/env.py:31` | `Base.metadata`, populated by importing `app.models` at `backend/alembic/env.py:15-17` |
| File template | `backend/alembic.ini:9` (commented out) | Alembic default `%(rev)s_%(slug)s` |
| `version_locations` | `backend/alembic.ini:40` (commented out) | Default: `alembic/versions` |

`env.py` installs two autogenerate filters, applied in both online and offline mode (`backend/alembic/env.py:99-132`):

- **`include_object`** (`backend/alembic/env.py:53-59`) suppresses eight `<table>_id_key` unique constraints listed in `EXEMPT_UNIQUE_CONSTRAINTS` (`backend/alembic/env.py:41-50`): on `conversations`, `diagnostics`, `engagements`, `firms`, `media`, `subscriptions`, `tasks`, `users`. These duplicate each table's primary key, are real in the database, and are deliberately absent from the models. The comment explains that a foreign key is bound to each one's *index* rather than to the primary key, so dropping them would fail or force **~56** foreign keys to be rebuilt. The exemption lives in `env.py` rather than on the models so a database built from metadata does not inherit the redundancy.
- **`strip_comment_directives`** (`backend/alembic/env.py:81-96`) drops comment-only diffs from generated revisions and from `alembic check`, so only structural drift is reported. An `AlterColumnOp` that *also* changes type, nullability, server default or name is correctly kept (`backend/alembic/env.py:62-78`). **Consequence: column comments are never enforced or reconciled.** Several tables were created by guarded migrations that never applied theirs.

**Gotcha:** the exemption list in `env.py` (8 constraints) and the drop list in `backend/alembic/versions/drop_redundant_uniques.py:39-53` (13 constraints) do not match. `drop_redundant_uniques` also targets `advisor_client_id_key`, `bba_id_key`, `impersonation_sessions_id_key`, `messages_id_key`, `notes_id_key`, `strategy_workbooks_id_key` and `document_templates_file_name_key`, while `firms_id_key` and `subscriptions_id_key` are exempt in `env.py` but not in the drop list. Its `upgrade()` skips any constraint a foreign key depends on (`drop_redundant_uniques.py:109-117`); the docstring records that local and production drop all 13, whereas the shared staging database has 45 dependent foreign keys across 6 tables and keeps those 6. So which of the 13 survive is **environment-specific**, and the `env.py` exemption list is not a complete description of what autogenerate will see.

#### Naming convention actually in use

Two conventions coexist across the 80 revision files in `backend/alembic/versions/`:

| Style | Example filename | Revision id |
|---|---|---|
| Alembic default: `<12-hex>_<slug>.py` | `4a3c2b1d0e9f_hotfix_add_is_deleted_to_engagements.py` | the hex prefix |
| Hand-written: `<descriptive_slug>.py` | `add_task_source_deliverable.py`, `drop_redundant_uniques.py` | a **human-readable string** |

**Gotcha:** the filename and the revision id frequently disagree. Always read the `revision =` line — never infer an id from a filename. Real examples:

| Filename | Actual `revision` |
|---|---|
| `partial_unique_email_active_users.py` | `partial_email_idx` |
| `fix_price_column_nullable.py` | `fix_price_nullable` |
| `fix_subscription_columns_nullable.py` | `fix_subscription_cols` |
| `create_firms_and_subscriptions_tables.py` | `create_firms_subs` |
| `add_assigned_to_user_ids_to_tasks.py` | `add_assigned_to_user_ids` |
| `add_strategic_business_plans_table.py` | `add_sbp_table` |
| `add_monthly_price_and_firm_id_to_subscriptions.py` | `add_monthly_price_firm_id` |
| `remove_unique_subscription_id_from_firms.py` | `remove_unique_sub_id` |
| `merge_heads_662a7acdc7ea_7a0c72f39586.py` | `a1b2c3d4e5f6` |
| `merge_all_heads.py` | `merge_all_current_heads` |
| `add_card_tables_and_deliverable_session.py` | `add_tables_and_session` |

Filename prefixes also lie about *kind*: `merge_card_notes.py` and `103dd474bf97_merge_llm_provider_and_document_.py` are named "merge" but each has a **single** `down_revision` — they are ordinary revisions, not merges.

#### Creating and applying a migration

```bash
cd backend
# DATABASE_URL must be set (env or backend/.env) — env.py reads it via app.config

alembic current            # what this database is stamped at
alembic heads              # how many heads the script directory has
alembic history --verbose  # the graph

alembic revision --autogenerate -m "short description"
#  -> HAND-TRIM the generated file (see below) before doing anything else

alembic upgrade head
alembic downgrade -1
```

Almost every recent revision is written **idempotently**, with `sa.inspect(op.get_bind())` guards around each operation — see `backend/alembic/versions/f7a1b2c3d4e5_self_service_saas.py:30-42`, `add_program_deliverable_tables.py:33-68`, `align_schema_with_models.py`, `add_firms_firm_admin_fk.py:40-47`, `create_orphan_tables.py:34-38`. The stated reason, repeated in a dozen docstrings, is that *several environments have drifted from the migration history*. Match that style: write guards, and make the revision a no-op where the state already matches. Some also handle offline (`--sql`) mode explicitly — `_offline()` returns `op.get_context().as_sql` and emits full DDL because there is no connection to inspect (`add_task_source_deliverable.py:49-54`, `add_program_deliverable_tables.py:33-38`).

#### Autogenerate picks up pre-existing drift — hand-trim every revision

`docs/ROLES_MATRIX_TOOL.md:119-125` records the rule for one table:

> `alembic revision --autogenerate` in this repo picks up a large amount of pre-existing drift unrelated to this table (dead columns on `users`, `subscriptions`, `strategy_workbooks`, plus comment and constraint noise). Trim the generated revision down to the `create_table('roles_matrices')` call and its three `create_index` calls before applying it.

**Generalise it: every autogenerated revision in this repo must be hand-trimmed to only the intended changes before it is applied.** Autogenerate compares `Base.metadata` — the 26 model tables — against a database holding 40, so it emits `op.drop_table` for each of the fourteen orphans:

| Orphan tables autogenerate will drop | Created by |
|---|---|
| `owner_team_members`, `signup_intents` | `f7a1b2c3d4e5_self_service_saas.py:129-173` — see [the self-service tier](#tables-with-no-model-the-self-service-tier) |
| `program_stage`, `program_task_template`, `program_dd_template`, `engagement_stage_state`, `engagement_dd_item`, `engagement_document_register_entry` | `add_sale_ready_program_tables.py:24-110` — see [the Sale Ready programme](#tables-with-no-model-the-sale-ready-programme) |

And these columns exist in the database but not on their model, so autogenerate emits `op.drop_column`:

| Column | Added by |
|---|---|
| `users.account_type` | `f7a1b2c3d4e5_self_service_saas.py:49-58` |
| `tasks.section` | `add_sale_ready_program_tables.py:21` |
| `subscriptions.user_id`, `.program`, `.provider` | `f7a1b2c3d4e5_self_service_saas.py:101-123` |
| `subscriptions.price`, `.start_date`, `.end_date`, `.billing_period`, `.currency`, `.next_billing_date` | No migration in this repo — out-of-band, environment-dependent. Only *relaxed* to nullable by `fix_price_column_nullable.py` / `fix_subscription_columns_nullable.py` |

An untrimmed `--autogenerate` revision applied to production would drop eight tables and up to eleven columns, taking the self-service and Sale Ready schemas with it and making both unmerged branches unmergeable.

#### The multi-head problem

The revision graph is heavily branched: **14** of the 80 files have a tuple `down_revision`, i.e. are real merges. Reading `revision` / `down_revision` across all 80, the graph currently converges on a **single base** (`ec0b9b4c6fec`) and a **single head**, `add_firms_firm_admin_fk` (`backend/alembic/versions/add_firms_firm_admin_fk.py:29-30`), reached via `0cfcd28150eb` ← (`add_task_source_deliverable`, `merge_roles_matrix_deliverables`). No dangling parents.

Merge revisions in the repo, for orientation:

| Revision id | File | Merges |
|---|---|---|
| `a1b2c3d4e5f6` | `merge_heads_662a7acdc7ea_7a0c72f39586.py` | `662a7acdc7ea`, `7a0c72f39586` |
| `2eb0a6a49983` | `2eb0a6a49983_merge_task_and_firm_branches.py` | `b2465e2f298a`, `c143e0142bb9` |
| `merge_all_current_heads` | `merge_all_heads.py` | `fix_subscription_cols`, `7a0c72f39586` |
| `dd5fedfeefbf` | `dd5fedfeefbf_merge_heads_add_bba_report_columns_and_.py` | `add_bba_report_columns`, `d7ffe8426a29` |
| `merge_b7f4c3e1a2d8_add_read_by` | `merge_heads_b7f4c3e1a2d8_add_read_by.py` | `b7f4c3e1a2d8`, `add_read_by_to_notes` |
| `1e095a9ba82f` | `1e095a9ba82f_merge_client_ids_and_bba_stored_files_.py` | `add_bba_stored_files`, `f71d9e32e953` |
| `merge_strategy_workbooks` | `merge_strategy_workbooks_and_presentation.py` | `add_strategy_workbooks`, `1e095a9ba82f` |
| `merge_bba_sw_ctx` | `merge_bba_and_sw_diagnostic_ctx.py` | `bba_diagnostic_ctx`, `sw_diagnostic_ctx` |
| `add_sbp_table` | `add_strategic_business_plans_table.py` | `1902d32c0ce6`, `add_llm_provider_fields` |
| `e8404c561e86` | `e8404c561e86_merge_program_guide_and_self_service.py` | `add_program_guide_tables`, `f7a1b2c3d4e5` |
| `merge_deliverable_sale_ready` | `merge_deliverable_and_sale_ready.py` | `add_program_deliverable_tables`, `add_sale_ready_program_tables` |
| `merge_pd_scorecard_cleanup` | `merge_pd_scorecard_cleanup.py` | `50f7a483da0a`, `align_schema_models` |
| `merge_roles_matrix_deliverables` | `merge_roles_matrix_deliverables_merge_roles_matrix_and_pd_scorecard_.py` | `add_program_deliverable_tables`, `drop_redundant_uniques` |
| `0cfcd28150eb` | `0cfcd28150eb_merge_add_task_source_deliverable_and_.py` | `add_task_source_deliverable`, `merge_roles_matrix_deliverables` |

Note `add_sbp_table` is a merge that also carries real DDL — a merge revision is not always empty here. Note also that `e8404c561e86` and `merge_deliverable_sale_ready` are what pulled the two orphan schemas into the mainline history: their DDL is on the trunk even though their application code is not.

**The rule when branches collide: restore the sibling revision files and run `alembic merge heads`. Never `alembic stamp` past them.**

```bash
alembic heads                         # confirm there is more than one
alembic merge heads -m "merge <a> and <b>"
alembic upgrade head
```

A merge revision is normally an empty `upgrade()`/`downgrade()` pair whose `down_revision` is a tuple of the colliding heads (`0cfcd28150eb_merge_add_task_source_deliverable_and_.py`). It reconciles the *history* without touching the schema.

**Why stamping is destructive here.** `alembic stamp <rev>` rewrites the `alembic_version` table to say "this database is at `<rev>`" **without running any DDL**. In this repo that is worse than usual for three compounding reasons:

1. **All branches share one development Postgres.** Sibling revisions created on different feature branches collide precisely because they land in the same `alembic_version` table. Stamping to clear the collision tells that shared database it has schema it does not have — and every other branch's developer inherits the lie.
2. **The revisions you stamp over are the ones that carry the drift repairs.** `align_schema_with_models.py`, `drop_redundant_uniques.py`, `create_orphan_tables.py`, `add_firms_firm_admin_fk.py` exist specifically to reconcile environments that already diverged. Skipping them re-opens the divergence permanently, and because they are guarded no-ops when already applied, **re-running them is free** — there is never a reason to stamp instead.
3. **The skipped DDL is unrecoverable from history.** Once `alembic_version` says a revision ran, `alembic upgrade` will never run it again. The only recovery is to hand-write a new revision that redoes the missed work, or to stamp backwards and hope every intervening revision is idempotent.

Deleting a colliding revision file has the same effect: it orphans any database already stamped at it (`Can't locate revision identified by …`). **Restore, then merge.**

#### Gotcha: `alembic upgrade head` may not build a database from empty

`backend/README.md:73-75` states it plainly:

> Note that `alembic upgrade head` cannot build a database **from empty** in this repo — an early revision runs `ALTER TABLE advisor_client` before that table is created. Upgrading an existing database works fine.

**Plan for a fresh environment needing a schema dump (`pg_dump --schema-only` from a known-good database, restored and then stamped at the current head), not a replay of the migration history.** There is no `create_all()` fallback anywhere in the repo to lean on instead. `backend/tests/conftest.py` reflects the same assumption: the database tests `pytest.skip` with instructions (`backend/tests/conftest.py:72,93`) rather than creating a schema, and the skip message reads "Or set `TEST_DATABASE_URL` to a database that is already migrated." How the suite consumes that database is covered in *Engineering Standards, Workflow & Testing*.

Nuance worth knowing before you spend a day on it: `backend/alembic/versions/create_orphan_tables.py:1-21` was written on 2026-08-24 to fix exactly the failure the README describes (`relation "advisor_client" does not exist` at `a8d3b2d2caf9_add_bba_task_planner_columns`), and walking the graph confirms `create_orphan_tables` **is** an ancestor of `a8d3b2d2caf9`. `a8d3b2d2caf9` has itself since been rewritten with inspector guards (`a8d3b2d2caf9_add_bba_task_planner_columns.py:19-33`). The README paragraph has not been revised. It may now be stale — but nobody has demonstrated a clean from-empty build, and `a8d3b2d2caf9` still contains unguarded `op.alter_column` calls against `engagements`, `tasks` and `users`, so treat the warning as live until someone proves otherwise. Proving it either way is a half-day task against a throwaway database and is on the open-questions list in *Handover Checklist & Open Questions*.

### Debt visible from the schema

| Item | Where | Disposition |
|---|---|---|
| `diagnostics.celery_task_id` | `backend/app/models/diagnostic.py:61`, revision `1902d32c0ce6` | Vestige of an abandoned worker design. All background work runs in-process via FastAPI `BackgroundTasks`; there is no broker, worker tier or cache service in the running system. The column is always NULL. Drop it in the same revision that removes the rest of that scaffolding, not before — see *Operations, Diagnostics & Troubleshooting* |
| Fourteen tables with no model | Two migrations, above | Merge the owning branch or drop the tables. Leaving them is what makes every `--autogenerate` dangerous |
| `users.account_type` off the model | `f7a1b2c3d4e5_self_service_saas.py:49-58` | Blocks any authorisation rule that distinguishes a self-service owner from an advisory client |
| `strategy_workbooks.drive_file_id` | `backend/app/models/strategy_workbook.py:42-43` | Serialised into API responses as a permanent `null` for an integration that does not exist |
| Six `subscriptions` columns created out-of-band | No migration in this repo | Environment-dependent; reconcile or document per environment before anyone trusts `alembic check` |
| No `CheckConstraint`, no FK from `engagements` to `users` | Model-wide | Referential integrity for the central table is application-enforced only |

### Related sections

Role semantics, the `UserRole` permission matrix and the impersonation flow are in *Authentication, Authorization & Impersonation*. The endpoints that read and write these tables are in *Core Domain Modules*. The diagnostic pipeline that fills `diagnostics` is in *Diagnostic Engine*; the tool tables are in *AI Tools — BBA, Strategy Workbook & Strategic Business Plan* and *AI Tools — Roles Matrix, PD & Scorecard*; the programme tables are in *Value Builder Programme — Program Guide & Deliverables*. Runbook procedures for a stuck or drifted database are in *Operations, Diagnostics & Troubleshooting*. This section does not duplicate them.

---

## 8. Authentication, Authorization & Impersonation

Everything below is traced to code on branch `staging`. Where behaviour differs from `IMPERSONATION_ARCHITECTURE.md`, the code wins; the drift is catalogued in *Corrections to `IMPERSONATION_ARCHITECTURE.md`* below.

### The two authentication paths

There are exactly two ways a caller obtains a token. Both end with a **locally-signed HS256 JWT** in the browser's `localStorage` under the key `auth_token`. No Auth0 token is ever handed to the frontend.

#### Auth0 Authorization Code flow (the only path the UI offers)

1. `frontend/src/pages/Login.tsx:14-37` — the "Sign in" button removes `auth_token`, strips any `?error=` from the current URL, and does a full-page navigate to `${VITE_API_BASE_URL}/api/auth/login`, appending `?force_login=true` when the URL carried `error=firm_revoked` or `error=account_suspended`. `Login.tsx:39-48` also clears `auth_token` on mount, so landing on `/login` always drops the token.
2. `backend/app/api/auth.py:34` `GET /api/auth/login` — computes `redirect_uri = request.url_for('callback')` and calls Authlib's `authorize_redirect`. `force_login=true` adds `prompt=login`. The OAuth client (`backend/app/services/auth_service.py:20-44`) registers scope `openid profile email`, a 30 s httpx timeout for the OIDC metadata fetch, and deliberately sets **no** `audience`, which suppresses Auth0's API-consent screen. Authlib stores the OAuth `state`/PKCE material in the signed session cookie — the only real use of `SessionMiddleware`.
3. Auth0 Universal Login authenticates the person and redirects back to `GET /api/auth/callback` (`backend/app/api/auth.py:71`, route `name="callback"`).
4. The callback exchanges the code (`authorize_access_token`), takes `userinfo` from the token response, and falls back to an `httpx` GET on `https://{AUTH0_DOMAIN}/userinfo` if the claim is absent (`backend/app/api/auth.py:89-109`).
5. The ID token is decoded **without signature verification** (`jwt.get_unverified_claims`, `backend/app/api/auth.py:119`) purely to read the custom username claim named by the `AUTH0_USERNAME_NAMESPACE` setting; that value is copied onto `user_info['username']` (`auth.py:123-133`).
6. `AuthService.get_or_create_user` (`backend/app/services/auth_service.py:91`) upserts the `users` row. Lookup is by `auth0_id` (`auth_service.py:116`), then by `email` — an email match with a different `auth0_id` **rewrites `auth0_id`** to link the accounts (`auth_service.py:119-125`). For an existing user the DB role is authoritative and is never overwritten from Auth0; Auth0's role is only used to backfill a NULL role (`auth_service.py:187-190`). New users get `app_metadata.role`, then `user_metadata.role` (`auth_service.py:47-88`), otherwise default `UserRole.ADVISOR` (`auth_service.py:197`). `email_verified` is set to `True` if Auth0 says so, never back to `False` (`auth_service.py:179-181`). A user-uploaded profile picture is never overwritten by Auth0's (`auth_service.py:163-177`).
7. `check_user_login_eligibility` (`backend/app/services/login_check.py:12`) runs. On failure the user is bounced through Auth0's `/v2/logout` with `returnTo=${FRONTEND_URL}/login?error=firm_revoked` or `...?error=account_suspended` (`backend/app/api/auth.py:141-159`) — logging them out of Auth0 first so they can try other credentials.
8. A fresh HS256 JWT is minted with `SECRET_KEY`, claims `sub` (the **local** `users.id`, not the Auth0 `sub`), `email`, `role`, `exp = now + 1 day` (`backend/app/api/auth.py:164-171`).
9. 302 to `${FRONTEND_URL}/auth/callback?token=<url-encoded JWT>` (`backend/app/api/auth.py:172-183`).
10. `frontend/src/pages/AuthCallback.tsx:7-24` reads `?token`, writes it to `localStorage.auth_token`, and `navigate('/dashboard', {replace:true})`; with no token it navigates to `/login`.

Any exception anywhere in the callback is swallowed and turned into `302 → ${FRONTEND_URL}/login?error=authentication_failed` (`backend/app/api/auth.py:185-191`).

**Gotcha:** the token is delivered in a query string, so it lands in browser history and in any proxy/access log that records full URLs.

**Gotcha:** `redirect_uri` comes from `request.url_for('callback')`, i.e. from the inbound request's scheme/host, not from configuration. Behind a TLS-terminating proxy that does not forward `X-Forwarded-Proto` (and with the ASGI server not started with proxy-header support), this generates an `http://` callback that Auth0 will reject.

#### Email + password

1. `POST /api/auth/login-email` with `{email, password}` (`backend/app/api/auth.py:272`, body model `EmailPasswordLogin` at `auth.py:266`).
2. User looked up by `email` only — no `is_deleted` filter (`auth.py:287`). Not found → 401 "Invalid email or password".
3. `user.hashed_password` NULL → 401 "This account does not have a password set. Please use Auth0 login." (`auth.py:296-300`).
4. `verify_password` (`backend/app/utils/password.py:32`) — **passlib `CryptContext(schemes=["pbkdf2_sha256"])`, not bcrypt** (`password.py:12`). The module docstring explains the choice: pbkdf2 avoids bcrypt's 72-byte truncation. Any handover note saying "bcrypt verify" is wrong.
5. `check_user_login_eligibility` again; `firm_revoked` → 403 "Firm account has been revoked", anything else → 403 with the raw message from `login_check` (`auth.py:310-322`).
6. `users.last_login` updated, then an HS256 JWT identical in shape to the callback token (`sub`/`email`/`role`/`exp = now + 1 day`) returned as `{access_token, token_type:"bearer", user}` (`auth.py:324-345`).

**Gotcha — this path is effectively dead.** Nothing in the backend ever *writes* `users.hashed_password`: the only references are the model column (`backend/app/models/user.py:139`), the two reads in `backend/app/api/auth.py:296,303`, and the Alembic column add (`backend/alembic/versions/7a0c72f39586_add_password_field.py:45`). `hash_password` is imported at `backend/app/api/auth.py:20` and never called anywhere. The frontend never calls `/api/auth/login-email` either — `AuthContext.login()` ignores its arguments and redirects to Auth0 (`frontend/src/context/AuthContext.tsx:49-53`). The endpoint is reachable but every real user hits the "no password set" 401.

#### Auth endpoint inventory (`backend/app/api/auth.py`, prefix `/api/auth`)

| Method + path | Line | Auth required | What it does |
|---|---|---|---|
| `GET /api/auth/login` | `:34` | none | Redirect to Auth0 Universal Login; `?force_login=true` → `prompt=login` |
| `GET /api/auth/callback` | `:71` | none | Code exchange, user upsert, eligibility check, mint HS256 JWT, 302 to frontend |
| `GET /api/auth/logout` | `:194` | none | 302 to `https://{AUTH0_DOMAIN}/v2/logout?returnTo={FRONTEND_URL}/login&client_id=…`. Does **not** clear the session cookie or any server state; the frontend removes `auth_token` before calling it (`AuthContext.tsx:55-61`) |
| `GET /api/auth/user` | `:216` | Bearer | `decode_and_resolve_user(token, db)` → `{authenticated: true, user: <to_dict>}`; 401 otherwise |
| `GET /api/auth/check` | `:250` | none | `{"authenticated": request.session.get('user') is not None}` — always `false`, see *`get_current_user` — the dependency every endpoint uses* |
| `POST /api/auth/login-email` | `:272` | none | Email + password, above |
| `POST /api/auth/stop-impersonation` | `:348` | `Depends(get_current_user)` | End impersonation, see *Impersonation, end to end* |
| `GET /api/auth/impersonation-status` | `:455` | `Depends(get_current_user)` | Report impersonation claims, see *Impersonation, end to end* |

**Gotcha:** `frontend/src/pages/VerifyEmail.tsx:21` POSTs to `/api/auth/resend-verification`. **That endpoint does not exist** — no route, handler or reference anywhere in `backend/`. The button silently does nothing (the code only reacts to `response.ok`). The page is also unreachable: `/verify-email` is registered at `frontend/src/App.tsx:67` and nothing in the app ever navigates to it.

### Token verification — `backend/app/utils/auth.py`

`decode_and_resolve_user(token, db, request=None) -> TokenResult` (`backend/app/utils/auth.py:89`) is the single decode path, used by `get_current_user` and by `GET /api/auth/user`. `TokenResult` is a dataclass carrying `user`, `is_impersonation`, `original_user_id`, `impersonation_session_id` (`utils/auth.py:80-86`).

| Step | Code | Behaviour |
|---|---|---|
| 1 | `utils/auth.py:111-117` | **HS256 first**: `jwt.decode(token, SECRET_KEY, algorithms=["HS256"])`. On success reads `sub` → `user_id` and, only when `is_impersonation` is truthy, `original_user_id` and `impersonation_session_id`. `exp` is enforced by python-jose. |
| 2 | `utils/auth.py:118-127` | On any `JWTError`, falls back to `decode_auth0_token`. If that raises anything, logs and raises `401 Invalid token`. |
| 3 | `utils/auth.py:129-133` | Neither `auth0_id` nor `user_id` → `401 Invalid token: missing 'sub' claim`. |
| 4 | `utils/auth.py:136-163` | Impersonation session validation, see *Impersonation, end to end*. |
| 5 | `utils/auth.py:165-171` | Resolve the `User`: by `users.id` when the HS256 branch ran, by `users.auth0_id` when the Auth0 branch ran. |
| 6 | `utils/auth.py:173-177` | No row → `401 User not found`. |

`decode_auth0_token` (`utils/auth.py:56`) does the RS256 half:

- `_get_auth0_jwks()` (`utils/auth.py:24`) GETs `https://{AUTH0_DOMAIN}/.well-known/jwks.json` with a 10 s timeout and stores the whole JWKS in a **module-level global `_jwks_cache`** (`utils/auth.py:21`) with no TTL and no locking.
- `_get_auth0_signing_key(token)` (`utils/auth.py:36`) reads `kid` from the unverified header (missing `kid` → `JWTError`), scans the cached keys, and if the `kid` is absent **clears the cache and refetches once** before raising `Unable to find signing key with kid: …` (`utils/auth.py:46-53`).
- `jwt.decode(..., algorithms=[settings.AUTH0_ALGORITHMS], options={"verify_aud": False}, issuer=f"https://{AUTH0_DOMAIN}/")` (`utils/auth.py:62-68`) — the issuer *is* verified; the audience is verified manually immediately afterwards.
- Manual audience check (`utils/auth.py:69-76`): `valid_audiences = {AUTH0_AUDIENCE, AUTH0_CLIENT_ID}`. A list `aud` is a set intersection; a scalar `aud` is membership. The inline comment explains why — python-jose accepts only one `aud` string, while Auth0 issues ID tokens with `aud = client_id` and access tokens with the API audience.

**Gotcha — decode order is exploitable if `SECRET_KEY` leaks.** HS256 is attempted *first* with a symmetric secret that is also the session-cookie secret (`backend/app/main.py:58`). Anyone holding `SECRET_KEY` can mint a token for any `users.id`, with `role` and the impersonation claims of their choosing. There is no `alg` allow-listing that distinguishes "this token should have been RS256".

**Gotcha — the JWKS cache never expires.** A JWKS fetch failure raises `requests` exceptions inside `decode_auth0_token`, which the caller catches broadly (`except Exception`, `utils/auth.py:122`) and reports as `401 Invalid token` — an Auth0 outage looks like bad credentials.

`is_token_expired` (`utils/auth.py:272`) and `get_token_expiry_time` (`utils/auth.py:305`) take the *Auth0 token dict*, read `access_token`, and use `get_unverified_claims` to read `exp`. Neither is called anywhere in the app; both are re-exported from `backend/app/utils/__init__.py:4-6`, and `get_token_expiry_time` is imported unused at `backend/app/api/auth.py:19`. `decode_auth0_token` is imported at the same line and also unused there.

### `get_current_user` — the dependency every endpoint uses

`backend/app/utils/auth.py:187`.

1. **Bearer first** (`utils/auth.py:211-214`). If `Authorization: Bearer <token>` is present, `decode_and_resolve_user(token, db, request)` runs — `request` *is* passed here, so `request.state` gets populated for impersonation.
2. **Session cookie second** (`utils/auth.py:217-224`). Only if no bearer result: `request.session.get('user')`, then `user_session.get('auth0_id')`, then a lookup on `users.auth0_id`. A session-resolved user is **only ever resolved by `auth0_id`**, and the resulting `TokenResult` has `is_impersonation=False` — impersonation cannot ride a cookie.
3. Neither → `401 Not authenticated` (`utils/auth.py:227-231`).
4. `user.is_deleted` → **403** "User account has been deleted" (`utils/auth.py:235-239`).
5. `not user.is_active` → **403** "User account is inactive" (`utils/auth.py:241-245`).
6. Debug log line, return the `User` (`utils/auth.py:247-249`).

**Gotcha — the session branch is unreachable today.** Nothing in the backend ever writes `request.session[...]`; a grep over `backend/app` finds exactly two references to `request.session`, both reads (`backend/app/utils/auth.py:218`, `backend/app/api/auth.py:258`). Consequently `GET /api/auth/check` always returns `{"authenticated": false}`, and the "two authentication methods" in the docstring (`utils/auth.py:194-198`) are in practice one. The session cookie exists solely for Authlib's OAuth state.

`require_role(allowed_roles)` (`utils/auth.py:252`) is a dependency factory: `user.role not in allowed_roles` → 403 with the required-role list echoed in `detail` (`utils/auth.py:262-266`). It is used in only two modules — `backend/app/api/roles_matrix.py` (11 routes) and `backend/app/api/pd_scorecard.py` (18 routes). Everywhere else role checks are written inline as `if current_user.role not in [...]` inside the handler body.

### `SessionMiddleware` and CORS — `backend/app/main.py`

| Setting | Value | Line |
|---|---|---|
| `secret_key` | `settings.SECRET_KEY` (same secret as the HS256 JWTs) | `backend/app/main.py:58` |
| `session_cookie` | `trinity_session` | `backend/app/main.py:59` |
| `max_age` | `3600 * 24 * 7` (7 days) | `backend/app/main.py:60` |
| `same_site` | `lax` | `backend/app/main.py:61` |
| `https_only` | `settings.APP_ENV != "development"` | `backend/app/main.py:62` |

`SessionMiddleware` is added **before** `CORSMiddleware` (comment at `backend/app/main.py:55`), which in Starlette makes CORS the outer layer and Session the inner one — the reverse of what the comment implies. CORS (`main.py:67-83`) is `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`, with an explicit origin list: `settings.FRONTEND_URL` plus eight hard-coded localhost/127.0.0.1 origins on ports 5173/3000/8080/8000 (`main.py:71-78`), shipped in every environment.

Static: `app.mount("/files", StaticFiles(directory=<backend>/files), name="files")` at `backend/app/main.py:115` — unauthenticated, no dependency; the directory is auto-created at import (`main.py:111-113`).

### Frontend token handling

- **Storage.** `localStorage` key `auth_token`, written in exactly three places: `frontend/src/pages/AuthCallback.tsx:14` (login), `frontend/src/context/AuthContext.tsx:201` (start impersonation), `AuthContext.tsx:253` (stop impersonation). Removed in `Login.tsx:17,42,45`, `AuthContext.tsx:57,132,156`, and `frontend/src/main.tsx:33,44,56`.
- **Bootstrap** (`AuthContext.tsx:69-176`, run from a `useEffect` with a 100 ms delay at `AuthContext.tsx:283-290`). No token → unauthenticated, done. Otherwise it calls `GET /api/auth/impersonation-status` **first**; if that reports `is_impersonating`, it sets `isImpersonating`, `originalUser` and `user` from the response and **returns early — `/api/auth/user` is never hit** (`AuthContext.tsx:99-112`). Otherwise it calls `GET /api/auth/user` and maps `data.user`.
- **When the token is cleared.** A non-OK response from `/api/auth/user`, or an OK response with an unexpected shape, removes `auth_token` (`AuthContext.tsx:132,156`). A thrown fetch error does **not** — the comment at `AuthContext.tsx:167` says so explicitly ("Don't clear token on network errors - might be temporary"), though the auth state is still reset to unauthenticated, so the UI logs out while the token survives in storage.
- **Proactive expiry** (`frontend/src/main.tsx`). `window.fetch` is wrapped (`main.tsx:29-48`): before any request, if the stored token's `exp` claim (decoded with `atob`, `main.tsx:7-23`) is in the past, the token is removed, an `auth:token-expired` CustomEvent is dispatched, and a synthetic `401 {detail:"Token expired"}` `Response` is returned without hitting the network. After a real request, a `401` with a token present clears the token and dispatches the same event. A capture-phase `click` listener (`main.tsx:53-59`) repeats the check for UI-only interactions. `AuthContext.tsx:295-303` turns `auth:token-expired` into an unauthenticated state.
- **Route gate.** `ProtectedRoute` (`frontend/src/App.tsx:47-59`) renders "Checking authentication…" while `isLoading`, redirects to `/login` when `!isAuthenticated`, and otherwise renders children. It wraps the whole `/dashboard` subtree (`App.tsx:70-74`).

**Gotcha:** `ProtectedRoute` checks authentication only — there is **no role gate in the router**. Every dashboard route, including `/dashboard/users`, `/dashboard/firms`, `/dashboard/subscriptions` and `/dashboard/ai-privacy` (`App.tsx:76,96,104,105`), renders for any signed-in user; the pages come back empty or error because the API refuses. Role visibility is a per-component concern (e.g. `frontend/src/pages/dashboard/users/UsersPage.tsx:365`); the routing table itself is covered in *Frontend Architecture*.

### The role model

`UserRole` is a `str`-Enum with six members (`backend/app/models/user.py:14-21`). The DB column uses a `TypeDecorator`, `UserRoleType` (`backend/app/models/user.py:24`), that maps the four original roles to **uppercase** DB values (`ADVISOR`, `CLIENT`, `ADMIN`, `SUPER_ADMIN`) and the two firm roles to **lowercase** (`firm_admin`, `firm_advisor`) on write (`user.py:48-55`), and normalises either casing back to the lowercase Python value on read (`user.py:83-96`). The column default is `UserRole.ADVISOR`, `nullable=False` (`user.py:220-225`).

| Role | Enum value | Who creates them | What they can see | Scope boundary |
|---|---|---|---|---|
| `advisor` | `advisor` | Default for any Auth0 self-signup with no role in metadata (`services/auth_service.py:197`); also `POST /api/users` invite by admin/super_admin (`api/users.py:200`). Also the role a removed firm advisor reverts to (`services/firm_service.py:237`) | Engagements where they are `primary_advisor_id` or in `secondary_advisor_ids`, plus engagements of clients they are actively associated with via `advisor_clients` (`api/engagements.py:266-281`) | No firm; `firm_id` is NULL. Cannot list users, firms or subscriptions |
| `client` | `client` | `POST /api/users` invite (admin/super_admin), or `POST /api/firms/{firm_id}/clients` (`services/firm_service.py:546`) | Engagements where they are `client_id` or listed in `client_ids` (`api/engagements.py:282-291`); their own diagnostics and documents | Denied all program-guide module content (`api/program_guide.py:67`) and all Value Builder deliverable endpoints (`services/deliverable_permissions.py`) |
| `admin` | `admin` | Assigned out-of-band (Auth0 `app_metadata.role`, or by another admin via `PATCH /api/users/{id}`); no endpoint mints one directly | All **non-firm** users and engagements: `list_users` strips firm users and firm clients for plain admins (`api/users.py:96-99`), `list_engagements` filters to `firm_id IS NULL` (`api/engagements.py:256-258`) | Unconditional `True` inside `check_engagement_access`, but the *listing* queries deliberately exclude firm-scoped records. Cannot create firms, list firms, manage subscriptions, delete users, or impersonate |
| `super_admin` | `super_admin` | Assigned out-of-band; there is no endpoint that mints one | Everything. `list_engagements` shows solo engagements by default and firm engagements when `?firm_id=` is supplied (`api/engagements.py:251-255`) | None. Sole holder of: firm creation, firm revoke/reactivate, subscription CRUD, user delete, user detail, user-file download, impersonation |
| `firm_admin` | `firm_admin` | Promoted automatically when a super_admin creates a firm and names them `firm_admin_id` — `firm_service.create_firm` sets `firm_admin.firm_id` and `firm_admin.role = UserRole.FIRM_ADMIN` (`services/firm_service.py:91-92`) | Every engagement whose `engagement.firm_id == user.firm_id`; their firm's advisors, clients, seats and subscription | Hard-bounded by `user.firm_id`. `check_engagement_access` returns `False` for any engagement outside their firm, and `False` outright if their own `firm_id` is NULL (`services/role_check.py:40-43`). Cannot be removed, suspended or reactivated as an advisor (`firm_service.py:211,332,429`) |
| `firm_advisor` | `firm_advisor` | `POST /api/firms/{firm_id}/advisors` → `firm_service.add_advisor_to_firm` creates the Auth0 user with `app_metadata.role=firm_advisor` and the local row with `role=FIRM_ADVISOR`, `firm_id`, incrementing `firm.seats_used` (`services/firm_service.py:157-184`) | Same rule as `advisor`: own primary/secondary engagements plus active `advisor_clients` associations | Assignment rules force firm context — a firm user may only add other `firm_advisor`s from the same firm as secondaries, and only on engagements that have a `firm_id` (`api/engagements.py:152-167`). Suspension (`is_active=False`) blocks login for this role and `firm_admin` specifically (`services/login_check.py:38-40`) |

Seat accounting counts `FIRM_ADVISOR` rows only (active **and** suspended); the firm admin does not consume a billed seat (`api/firms.py:319-328`, `api/firms.py:767-783`).

`User.to_dict()` (`backend/app/models/user.py:266-287`) is what every auth response returns. It emits `role` from the enum member and omits `hashed_password`. The frontend compares it as a lowercase string (`frontend/src/pages/dashboard/users/UsersPage.tsx:365` tests `=== 'super_admin'`).

**Gotcha:** the role model has no way to distinguish a self-service account owner from an advisor-provisioned client — both are `UserRole.CLIENT`. The discriminator column `users.account_type` exists in the database but is not on the `User` model on this branch; see *Data Model & Database*.

### Capability matrix

Legend: ✅ allowed · ❌ 403 · 🔶 allowed but scoped (condition in the note). Every row was read from the guard cited; the two rows marked *(inferred)* are derived from the *absence* of a guard.

| Capability | Guard (file:line) | advisor | client | admin | super_admin | firm_admin | firm_advisor |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| Create firm (`POST /api/firms`) | `api/firms.py:69` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| List firms (`GET /api/firms`) | `api/firms.py:123-133` | ❌ | ❌ | ❌ | ✅ all | 🔶 own firm only | ❌ |
| Get firm detail (`GET /api/firms/{id}`) | `api/firms.py:199-204` | ❌ | 🔶 if `firm_id` matches | ✅ | ✅ | 🔶 own firm | 🔶 own firm |
| Update firm, non-status fields (`PATCH /api/firms/{id}`) | `api/firms.py:233-238` → `can_manage_firm_users` | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | ❌ |
| Revoke / reactivate firm (`is_active` in the PATCH body) | `api/firms.py:227-232` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Add / remove / suspend / reactivate firm advisor | `firm_service.py:124,202,323,421` via `can_manage_firm_users` (no API-level check) | ❌ | ❌ | ❌ | ✅ | 🔶 own firm | ❌ |
| List firm advisors (`GET /api/firms/{id}/advisors`) | `firm_service.py:248-255` | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | 🔶 own firm |
| Advisor's engagements, for the suspension warning | `firm_service.py:271` via `can_view_firm_engagements` | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | ❌ |
| Add client to firm (`POST /api/firms/{id}/clients`) | `firm_service.py:586-591` (no API-level check) | ❌ | ❌ | 🔶 only if `admin.firm_id == firm_id` | ✅ any firm | 🔶 own firm | ❌ |
| Remove client from firm (`DELETE /api/firms/{id}/clients/{cid}`) | `api/firms.py:504,513` | ❌ | ❌ | ❌ | ✅ | 🔶 own firm | ❌ |
| List firm engagements (`GET /api/firms/{id}/engagements`) | `firm_service.py:446` via `can_view_firm_engagements` (no API-level check) | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | ❌ |
| Firm stats (`GET /api/firms/{id}/stats`) | `api/firms.py:730-735` then `can_view_firm_engagements` | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | ❌ |
| Reassign firm engagement | `firm_service.py:514` via `can_assign_advisors` | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | ❌ |
| View firm subscription (`GET /api/firms/{id}/subscription`) | `api/firms.py:665-670` then `can_modify_subscription` | ❌ | ❌ | ✅ | ✅ | 🔶 own firm | ❌ |
| Update seats (`PATCH /api/firms/{id}/seats`) | `firm_service.py:461` via `can_modify_subscription` (no API-level check) | ❌ | ❌ | ❌ | ✅ | 🔶 own firm | ❌ |
| Subscriptions: create / list / get / update / delete | `api/subscriptions.py:42,89,124,150,183` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| List users (`GET /api/users`) | `api/users.py:64` | ❌ | ❌ | 🔶 firm users & firm clients filtered out (`users.py:96-99`) unless `?ids=` is supplied | ✅ | ❌ | ❌ |
| Create (invite) user (`POST /api/users`) | `api/users.py:200` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Update user (`PATCH /api/users/{id}`) | `api/users.py:478` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |
| Delete (soft) user | `api/users.py:548` (plus self-delete 400 at `:557`) | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| User detail page / download a user's file | `api/users.py:280`, `api/users.py:406` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| **Impersonate** | `api/users.py:634` | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ |
| Create engagement | `api/engagements.py:63` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Update engagement / manage secondaries | `api/engagements.py:909` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| List engagements | `api/engagements.py:251-296` | 🔶 own + associated | 🔶 own (`client_id` or `client_ids`) | 🔶 `firm_id IS NULL` | 🔶 solo, or `?firm_id=` | 🔶 own firm (empty if `firm_id` NULL) | 🔶 own + associated |
| Create advisor–client association | `api/adv_client.py:33` | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Run Roles Matrix tool (all 11 routes) | `api/roles_matrix.py:43` `ADVISOR_ROLES` via `require_role` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Run PD & Scorecard tool (all 18 routes) | `api/pd_scorecard.py:58` `_ADVISOR_ROLES` → `READ_ROLES`/`BUILD_SETUP_ROLES`/`ROLE_WORK_ROLES` (all three are the same list today, `:67-73`) via `require_role` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Strategy Workbook / Strategic Business Plan | no role gate; `check_engagement_access` only (`strategy_workbook.py:74,111,494`; `strategic_business_plan.py:63` `_check_plan_access`) | 🔶 | 🔶 *(inferred: client is not excluded)* | ✅ | ✅ | 🔶 | 🔶 |
| Read program-guide module library (`GET /api/program-guide/content`) | `api/program_guide.py:67` | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ |
| Read program-guide module content for an engagement | `api/program_guide.py:90,126,144` `_check_access(require_advisor=True)` | 🔶 | ❌ | ✅ | ✅ | 🔶 own firm | 🔶 |
| Read program-guide **dashboard** (progress + module list) | `api/program_guide.py:111` `_check_access` with no `require_advisor` | 🔶 | 🔶 | ✅ | ✅ | 🔶 own firm | 🔶 |
| Manage Value Builder deliverables (read *and* write) | `services/deliverable_permissions.py:90,108` | 🔶 | ❌ | ✅ | ✅ | 🔶 own firm | 🔶 |
| Create a diagnostic / patch responses / submit / cancel / upload or delete a file / regenerate report | `api/diagnostics.py:78,131,187,261,423,508,720` — auth only, **no role check and no engagement check** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Read a diagnostic, its status, results, or its engagement's list | `_require_diagnostic_access` / `_require_engagement_access` (`diagnostics.py:59,66,579,634,672,704`) | 🔶 | 🔶 | 🔶 | 🔶 | 🔶 | 🔶 |
| Download a diagnostic PDF | `diagnostics.py:846` + owner rule at `:848-852` | 🔶 | 🔶 | 🔶 only if they created or completed it | 🔶 | 🔶 only if they created or completed it | 🔶 |
| Tag a diagnostic | `api/diagnostics.py:776` then `:796` | ✅ | ❌ | ✅ | ✅ | ❌ | ✅ |
| Upload / delete document template | `api/diagnostics.py:1081`, `api/diagnostics.py:1163` | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ |
| Read **and** edit AI field privacy | `api/ai_field_privacy.py:25` `_require_admin` | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ |

*(inferred)* — the Strategy Workbook / SBP row for `client` follows from there being no role guard plus `check_engagement_access` admitting clients; no test covers it. The `firm_admin` exclusion from "tag a diagnostic" is verified but looks unintentional: the list is `[ADVISOR, FIRM_ADVISOR, ADMIN, SUPER_ADMIN]`, and `firm_admin` is the only management role missing.

**Gotcha:** `require_role` is used only in `roles_matrix.py` and `pd_scorecard.py`. Everywhere else an authorization mistake is a missing `if` inside a handler body, not a missing dependency — you will never catch it by reading a route signature.

**Gotcha:** several firm capabilities have **no check at the API layer at all** — `POST/DELETE /api/firms/{id}/advisors`, `POST .../suspend`, `POST .../reactivate`, `POST /api/firms/{id}/clients`, `GET /api/firms/{id}/engagements`, `POST .../reassign`, `PATCH /api/firms/{id}/seats`. The check lives in `backend/app/services/firm_service.py` and surfaces as `ValueError`, which the route converts to **400 "Invalid request data"**, not 403 (e.g. `api/firms.py:271-276`). An authorization failure on these endpoints is indistinguishable from a validation failure.

### `check_engagement_access` — the record-level rule

`backend/app/services/role_check.py:10`, signature `check_engagement_access(engagement, user, require_advisor=False, db=None) -> bool`. Evaluated top to bottom; the first matching role branch returns.

| Role | Rule | Lines |
|---|---|---|
| `super_admin`, `admin` | Unconditional `True` (before `require_advisor` is ever read) | `role_check.py:36-37` |
| `firm_admin` | `True` iff `user.firm_id` is truthy **and** `engagement.firm_id == user.firm_id`; otherwise `False`. A firm_admin with a NULL `firm_id` is denied every engagement | `role_check.py:40-43` |
| `advisor` | `True` if `engagement.primary_advisor_id == user.id`; else `True` if `engagement.secondary_advisor_ids` is non-empty and contains `user.id`; **else** — only when `db is not None` and `engagement.client_id is not None` — `True` if an `AdvisorClient` row exists with `advisor_id == user.id`, `client_id == engagement.client_id`, `status == "active"`, `is_deleted == False`; otherwise `False` | `role_check.py:46-69` |
| `firm_advisor` | Byte-for-byte the same three checks as `advisor` (duplicated block; no `firm_id` comparison of its own) | `role_check.py:72-93` |
| `client` | If `require_advisor` → `False` immediately. Else `True` if `engagement.client_id == user.id`; else `True` if `engagement.client_ids` is non-empty and contains `user.id` (multi-client engagements); otherwise `False` | `role_check.py:96-105` |
| anything else | `False` | `role_check.py:107` |

Two consequences worth internalising:

- **`require_advisor` is only read inside the CLIENT branch.** It therefore means "is not a client", not "is an advisor" — admins, super_admins and firm_admins have already returned `True` above it. `backend/app/services/deliverable_permissions.py:52-56` documents this explicitly.
- **The association fallback silently degrades when `db` is omitted.** A caller invoking `check_engagement_access(engagement, user)` without `db=db` loses the `AdvisorClient` path and will deny an advisor who is legitimately associated with the client but is not named on the engagement. Every current call site in `backend/app/api/*.py` and `backend/app/services/*.py` passes `db=db`.

**Gotcha:** `AdvisorClient.status` is a free `String(50)` documented as "active, inactive, suspended" (`backend/app/models/adv_client.py:24`), not an enum. `role_check.py` filters on `status == "active"` **and** `is_deleted == False`; `api/engagements.py:268-271` filters only on `status == "active"`. The list endpoint and the record-level check therefore disagree for a soft-deleted association.

### `firm_permissions.py` and `deliverable_permissions.py`

**`backend/app/services/firm_permissions.py`** — pure predicates, no HTTP, no DB queries. `is_firm_admin` (`:10`), `is_firm_advisor` (`:15`), `is_firm_member` (`:20`, role in the two firm roles *and* `firm_id` not NULL), and four capability predicates:

| Function | Line | super_admin | admin | firm_admin (matching `firm_id`) | Applied at |
|---|---|:--:|:--:|:--:|---|
| `can_manage_firm_users` | `:25` | ✅ | ❌ | ✅ | `api/firms.py:234`; `firm_service.py:124` (add advisor), `:202` (remove), `:323` (suspend), `:421` (reactivate) |
| `can_view_firm_engagements` | `:34` | ✅ | ✅ | ✅ | `api/firms.py:731`; `firm_service.py:271`, `:446` |
| `can_assign_advisors` | `:43` | ✅ | ✅ | ✅ | `firm_service.py:514` (reassign engagement) |
| `can_modify_subscription` | `:52` | ✅ | ❌ | ✅ | `api/firms.py:666`; `firm_service.py:461` (update seats) |

`is_firm_member` and `is_firm_advisor` have no call sites outside this module.

**Gotcha:** two firm endpoints layer a *looser* role check in front of the predicate, and the outer check runs first. `GET /api/firms/{id}/subscription` (`api/firms.py:665`) and `GET /api/firms/{id}/stats` (`api/firms.py:730`) both read `if current_user.role not in [SUPER_ADMIN, ADMIN]: <then check the predicate>`. A plain `admin` therefore passes the subscription endpoint even though `can_modify_subscription` would deny them. Reading `firm_permissions.py` alone gives the wrong answer for these two routes in the permissive direction — and the same shape appears at `api/firms.py:233`, where `admin` bypasses `can_manage_firm_users` for firm updates.

**`backend/app/services/deliverable_permissions.py`** — the whole access story for the Value Builder deliverables API by design: *"EVERY access decision for the deliverables API is made in this file. No endpoint in `app/api/program_deliverable.py` contains a role check"* (`deliverable_permissions.py:16-18`). Two FastAPI dependencies, `require_deliverable_read` (`:90`) and `require_deliverable_write` (`:108`), each of which:

1. Loads the engagement filtered on `is_deleted == False`, 404 if absent (`_load_engagement`, `:66`).
2. `check_engagement_access(..., require_advisor=True, db=db)` → 403 "You do not have access to this engagement" (`_authorize`, `:76-81`).
3. Rejects `engagement.tool != "value_builder"` with 400 "Deliverables are only available for Value Builder engagements" (`:82-86`).
4. Returns the loaded `Engagement` so handlers do not refetch it.

Effective allow-list `DELIVERABLE_ACCESS_ROLES` = {`advisor`, `firm_advisor`, `firm_admin`, `admin`, `super_admin`} (`:57-63`) — clients are denied both reads and writes. Applied at `backend/app/api/program_deliverable.py:101` (read) and `:111,129,150,174,193,213` (writes). Boundary tests assert the 403s at `backend/tests/test_program_deliverable_api.py:96,99,131,138`; the equivalent program-guide boundaries are at `backend/tests/test_program_guide_api.py:112,121,128,141,162`. What those endpoints actually do with the engagement is covered in *Value Builder Programme — Program Guide & Deliverables*.

The module's docstring flags a real modelling gap: a self-service owner (`users.account_type == 'self_service'`) and an advisory client are both `UserRole.CLIENT`, and `account_type` **exists in the database (migration `f7a1b2c3d4e5`) but is not on the `User` model on this branch**, so the two cannot be distinguished in code (`deliverable_permissions.py:20-31`).

### Login eligibility — `login_check.py`

`check_user_login_eligibility(db, user) -> (bool, error|None)` (`backend/app/services/login_check.py:12`), called from both login paths.

| # | Condition | Result | Line |
|---|---|---|---|
| 1 | `user.is_deleted` | `(False, "Your account has been deleted. Please contact your administrator.")` | `:34-35` |
| 2 | role in {`firm_advisor`, `firm_admin`} **and** `not user.is_active` | `(False, "Your account has been suspended. Please contact your firm administrator.")` | `:38-40` |
| 3 | `user.firm_id` set and that firm has `is_active == False` | `(False, "firm_revoked")` | `:43-46` |
| 4 | role `client`: raw SQL `clients @> ARRAY[:user_id]::uuid[]` against every `firms` row; any match on an **inactive** firm | `(False, "firm_revoked")` | `:49-56` |
| 5 | otherwise | `(True, None)` | `:59` |

**Suspension is not checked for `advisor`, `client`, `admin`, `super_admin`** at step 2 — for those roles the block comes later, from `get_current_user`'s `is_active` 403 (`backend/app/utils/auth.py:241-245`), which means they receive a token and are refused on their first authenticated request rather than at the login redirect.

**Gotcha:** step 4 is a full scan of `firms` with a Postgres array-containment predicate on every client login, and it revokes on *any* inactive firm listing the client — a client shared between an active and a revoked firm is locked out. This is the most consequential of the repo's array-containment queries because it sits on the login path.

### Impersonation, end to end

#### Start — `POST /api/users/{user_id}/impersonate` (`backend/app/api/users.py:615`)

Caller must be authenticated (`Depends(get_current_user)`) and `current_user.role == UserRole.SUPER_ADMIN` (`api/users.py:634`) — the check is inline, not `require_role`. Four rejections follow: target not found → 404 (`:639`); `target_user.role == SUPER_ADMIN` → 403 (`:643`); `not target_user.is_active` → 400 (`:647`); `target_user.id == current_user.id` → 400 (`:651`). There is **no** `is_deleted` check on the target here — a soft-deleted user can be impersonated, though the resulting token is then rejected by `get_current_user`'s 403 on `is_deleted`.

An `impersonation_sessions` row is inserted (`backend/app/models/impersonation.py:12`):

| Column | Type | Notes |
|---|---|---|
| `id` | `UUID(as_uuid=True)` PK, `uuid.uuid4` default | becomes the `impersonation_session_id` claim |
| `original_user_id` | `UUID` FK `users.id ON DELETE CASCADE`, `nullable=False`, indexed | the super_admin |
| `impersonated_user_id` | `UUID` FK `users.id ON DELETE CASCADE`, `nullable=False`, indexed | the target |
| `status` | `String(20)`, default `"active"`, `nullable=False` | only `'active'` and `'ended'` are ever written |
| `created_at` | `DateTime`, default `datetime.utcnow` | naive UTC |
| `ended_at` | `DateTime`, nullable | set on stop |

Relationships `original_user` / `impersonated_user` with backrefs `impersonation_sessions_started` / `impersonation_sessions_received` (`models/impersonation.py:31-32`); explicit indexes on all three of `original_user_id`, `impersonated_user_id`, `status` (`:35-39`). Migration: `backend/alembic/versions/af13aec12199_add_impersonation_sessions.py`.

The minted token is HS256 with `SECRET_KEY`, `exp = int((now + 24 hours).timestamp())` (`api/users.py:665-678`):

```json
{
  "sub": "<impersonated user id>",
  "original_user_id": "<super_admin id>",
  "is_impersonation": true,
  "impersonation_session_id": "<session uuid>",
  "email": "<impersonated email>",
  "role": "<impersonated role, or 'client' if NULL>",
  "exp": 1234567890
}
```

`AuditService.log_impersonation_start(...)` is called (`api/users.py:681-686`), and the response is `{access_token, token_type:"bearer", user, original_user, impersonation_session_id}` (`:688-694`).

#### Per-request validation (`backend/app/utils/auth.py:136-163`)

When the HS256 branch produced `is_impersonation` **and** a `user_id`:

- if `impersonation_session_id` is present, it is coerced to `UUID` and looked up with `status == "active"` (`:144-147`). No row → `401 "Impersonation session has ended"`. A `ValueError`/`TypeError` from the coercion → `401 "Invalid impersonation session"` (`:159-163`).
- on success, and **only when a `request` object was passed**, `request.state.original_user_id` and `request.state.impersonation_session_id` are set for downstream audit use (`:156-158`).
- the current user is then resolved from `sub` (`:165`), i.e. the impersonated user. Every endpoint sees the impersonated identity and nothing else.

`get_original_user(request, db)` (`utils/auth.py:333`) reads `request.state.original_user_id` and returns that `User`. It is imported at `backend/app/api/auth.py:19` and **never used** as a dependency anywhere — so `request.state` is currently written and never read.

**Gotcha:** the `HTTPException(401, "Impersonation session has ended")` raised at `utils/auth.py:150` is inside the `try` whose `except` catches `(ValueError, TypeError)` — `HTTPException` is neither, so it propagates correctly. Do not "simplify" that block without preserving the exception types.

**Gotcha:** if a token carries `is_impersonation: true` but no `impersonation_session_id`, the `if impersonation_session_id:` guard at `utils/auth.py:137` is skipped entirely and the user is resolved from `sub` with no session check. Only a holder of `SECRET_KEY` can produce such a token, and the flag alone grants nothing extra, so the impact is bounded.

**Gotcha:** `GET /api/auth/user` calls `decode_and_resolve_user(token, db)` **without** the `request` argument (`backend/app/api/auth.py:237`), so that endpoint never populates `request.state`.

#### Stop — `POST /api/auth/stop-impersonation` (`backend/app/api/auth.py:348`)

Guarded by `Depends(get_current_user)`, then it re-parses the header itself. Missing/short header → 401 (`:365`). Decodes the bearer token as HS256 only — a `JWTError` is an immediate `401 "Invalid impersonation token"`, Auth0 tokens are not accepted here (`:375-382`). `is_impersonation` false → 400 "Not currently impersonating" (`:388`); missing `original_user_id` **or** `impersonation_session_id` → 400 (`:394`); original user row missing → 404 (`:402`). The session row is set to `status='ended'`, `ended_at=datetime.now(timezone.utc)` — **if the row is found**; a missing row is silently tolerated (`:410-417`). A new normal HS256 token for the original user is minted with `exp = now + 7 days` (note: not 1 day like the login tokens) and `role` defaulting to `"super_admin"` when NULL (`:420-430`). `AuditService.log_impersonation_end` is called (`:433-437`). Response: `{access_token, token_type:"bearer", user}` — no `original_user` key. Any unexpected exception → 500 "Failed to stop impersonation" (`:447-452`).

#### Status — `GET /api/auth/impersonation-status` (`backend/app/api/auth.py:455`)

Requires `Depends(get_current_user)` but then re-parses the header itself. No header → `{"is_impersonating": false}` (`:469-472`). HS256 decode failure → `{"is_impersonating": false}` (`:478-482`, comment: Auth0 tokens have no impersonation flags). Flag false → same (`:488-491`). Otherwise returns `{is_impersonating: true, impersonated_user: current_user.to_dict(), original_user: <dict or null>, impersonation_session_id}` (`:498-503`). Any exception is caught and reported as `{"is_impersonating": false}` (`:505-509`).

#### Frontend

- Trigger: `frontend/src/pages/dashboard/users/UsersPage.tsx:365` renders the "Impersonate" menu item only when `user?.role === 'super_admin' && !isImpersonating && u.role !== 'super_admin'`, and calls `startImpersonation(u.id)` at `:371`.
- `AuthContext.startImpersonation` (`frontend/src/context/AuthContext.tsx:178`) POSTs, overwrites `localStorage.auth_token` with the impersonation token (`:201`), sets `user`/`originalUser`/`isImpersonating`, then hard-navigates to `/dashboard` (`:220`).
- Banner: the only visual affordance for an active session is `frontend/src/components/ImpersonationBanner.tsx`, mounted **unconditionally** between the top bar and the page outlet at `frontend/src/components/layout/DashboardLayout.tsx:35`, so it is present above every dashboard route. The component decides for itself whether to draw anything: `ImpersonationBanner.tsx:9` returns `null` unless `isImpersonating && user && originalUser`. When it does render it shows both identities and a "Stop Impersonation" button.
- `stopImpersonation` (`AuthContext.tsx:227`) captures `originalUser?.role === 'super_admin'` *before* the call (`:235`), POSTs, stores the returned token (`:253`), clears impersonation state, and hard-navigates to `/dashboard/users` for a super_admin or `/dashboard` otherwise (`:269-275`).
- Re-bootstrap on refresh: `loadCurrentUser` calls `/api/auth/impersonation-status` **first** and returns early when it reports impersonation, so `/api/auth/user` is never hit in that case (`AuthContext.tsx:91-112`).

**Gotcha:** `originalUser` is only restored by the status call, and the banner requires it to be non-null. A refresh where `/api/auth/impersonation-status` returns `original_user: null` (the super_admin's row was deleted) leaves the session impersonating with **no banner and no way to stop from the UI** — the only exit is clearing `localStorage`.

#### Sequence

```
 super_admin browser        frontend (AuthContext)        backend                          Postgres
        |                            |                       |                                 |
        |-- click "Impersonate" ---->|                       |                                 |
        |                            |-- POST /api/users/{id}/impersonate                      |
        |                            |   Authorization: Bearer <super_admin HS256>             |
        |                            |---------------------->|                                 |
        |                            |                       | get_current_user -> decode HS256|
        |                            |                       | role == SUPER_ADMIN ?           |
        |                            |                       | target exists / not SA /        |
        |                            |                       | active / not self ?             |
        |                            |                       |-- INSERT impersonation_sessions |
        |                            |                       |   (status='active') ----------->|
        |                            |                       |<--------------- session uuid ---|
        |                            |                       | sign HS256 {sub=target,         |
        |                            |                       |   is_impersonation, orig_id,    |
        |                            |                       |   session_id, exp=+24h}         |
        |                            |                       | AuditService.log_..._start()    |
        |                            |                       |   -> logger.info ONLY           |
        |                            |<-- 200 {access_token, user, original_user,               |
        |                            |         impersonation_session_id} ----------------------|
        |                            | localStorage.auth_token = token                         |
        |<-- location = /dashboard --|                       |                                 |
        |                            |                       |                                 |
        |=== every subsequent request carries the impersonation token ===                      |
        |                            |-- GET /api/<anything> Authorization: Bearer <imp token> |
        |                            |---------------------->|                                 |
        |                            |                       | decode_and_resolve_user:        |
        |                            |                       |  HS256 ok, is_impersonation     |
        |                            |                       |-- SELECT impersonation_sessions |
        |                            |                       |   WHERE id=? AND status='active'|
        |                            |                       |<--- row? no -> 401 "ended" -----|
        |                            |                       | request.state.original_user_id  |
        |                            |                       |   (written, never read)         |
        |                            |                       | user = User(sub) = TARGET       |
        |                            |                       | is_deleted -> 403 / !is_active  |
        |                            |<-- data as the target user ------------------------------|
        |                            |                                                         |
        |-- click "Stop" ----------->|-- POST /api/auth/stop-impersonation ------------------->|
        |                            |                       | HS256 decode (no Auth0 fallback)|
        |                            |                       |-- UPDATE status='ended',        |
        |                            |                       |   ended_at=now ---------------->|
        |                            |                       | sign HS256 {sub=original,       |
        |                            |                       |   exp=+7d}                      |
        |                            |                       | AuditService.log_..._end()      |
        |                            |<-- 200 {access_token, user=original} --------------------|
        |<-- location = /dashboard/users (super_admin) ------|                                 |
```

### Auth0 Management API — `backend/app/services/auth0_management.py`

Everything that provisions or deletes an Auth0 account goes through this class. It authenticates separately from the login flow, with the `AUTH0_MANAGEMENT_*` credentials.

| Method | Line | Auth0 call | Notes |
|---|---|---|---|
| `get_management_token` | `:27` | `POST /oauth/token`, `grant_type=client_credentials` | Class-level cache in `_access_token`/`_token_expiry` (`:23-24`), refreshed 300 s before the reported `expires_in` (default 86400). Not thread-safe; failures raise a generic `Exception`. |
| `get_user_by_email` | `:68` | `GET /api/v2/users-by-email` | Exact match; returns the first user or `None`. |
| `create_user` | `:88` | `POST /api/v2/users` | Connection `Username-Password-Authentication` (`:179`); a 32-char `secrets`-generated password that is never shared; `email_verified: false`, `verify_email: false`; `app_metadata.role = <role>` (`:183-185`); username derived from the email local-part, sanitised, truncated to 8 chars and suffixed with a 6-hex SHA-1 of the full lowercased email to guarantee uniqueness within Auth0's 15-char limit (`:166-171`). A 409 is disambiguated by re-querying by email, so a username collision is not reported as a duplicate email (`:238-247`). |
| `send_password_setup_email` | `:252` | `POST /api/v2/tickets/password-change` | `result_url = {FRONTEND_URL}/login`, `ttl_sec = 432000` (5 days), `mark_email_as_verified: true` (`:286-292`). The ticket link is the call-to-action in the email that `EmailService` then sends — the transport is described in *Core Domain Modules*. Failures here are caught by the caller and downgraded to a warning: the account still exists and the person can use "Forgot Password" (`:226-230`). |
| `update_user_role` | `:348` | `PATCH /api/v2/users/{id}` | Writes `app_metadata.role`. The login flow never reads this back for an existing user — see step 6 of the Auth0 flow above. |
| `delete_user` | `:381` | `DELETE /api/v2/users/{id}` | Called from `api/users.py:608` before the local soft delete commits, so a failed Auth0 delete aborts the whole operation. |

**Gotcha:** the comments and log lines in `send_password_setup_email` say "Gmail SMTP" (`:259`, `:319-320`, `:333`), but `backend/app/services/email_service.py:2-13` sends via the **Resend** API using `RESEND_API_KEY`. The `SMTP_*` settings in `backend/app/config.py:70-75` are labelled "legacy, unused". Trust the code, not the comment.

**Gotcha:** password-setup email is the only way a provisioned user ever gets a credential, and `RESEND_API_KEY` defaults to `""`, so a misconfigured environment silently provisions accounts nobody can log into.

### Audit logging — what it actually does

`backend/app/services/audit_service.py` (93 lines) is **logger-only**. All three static methods (`log_impersonation_start:17`, `log_impersonation_end:44`, `log_impersonation_action:69`) build an f-string, emit it through the standard `logging` module, and wrap that in a `try/except` that downgrades any failure to `logger.error`. The `db: Session` parameter on the first two is accepted and never used. The two live call sites are `AuditService.log_impersonation_start` at `backend/app/api/users.py:681` and `AuditService.log_impersonation_end` at `backend/app/api/auth.py:433`; they write the lines `IMPERSONATION START: Session … ` and `IMPERSONATION END: Session …`. The source states the intent plainly: *"In the future, this could write to a dedicated audit_log table. For now, we use application logs which can be aggregated"* (`audit_service.py:38-39`, repeated at `:63-64`).

**There is no queryable audit trail.** Impersonation history survives only for as long as the host retains stdout; there is no table to query, no retention guarantee, and no way to answer "who impersonated whom, when" from the database. For a platform where a super_admin can act as any client, this is a compliance-relevant gap and should be treated as a required piece of work, not a nice-to-have.

| Claim | Reality |
|---|---|
| Impersonation start/end are recorded | ✅ but only as stdout log lines, plus the `impersonation_sessions` row (a session record, not an audit trail) |
| Actions performed *while* impersonating are recorded | ❌ `log_impersonation_action` has **zero call sites** anywhere in the repo |
| `request.state.original_user_id` is used for audit | ❌ written by `decode_and_resolve_user`, never read; `get_original_user` is imported at `api/auth.py:19` and unused |
| There is an `audit_log` table | ❌ no such model and no such migration |

If a super_admin impersonates a client and edits their engagement, the *only* durable evidence is the `impersonation_sessions` row bracketing the time window. The mutation itself is attributed entirely to the impersonated user, with no `original_user_id` recorded on it.

### Corrections to `IMPERSONATION_ARCHITECTURE.md`

The doc is a useful map but has drifted. Verified corrections:

| Doc claim | Line | Reality |
|---|---|---|
| `get_current_user` "Falls back to unverified decode (for Auth0 tokens)" | `IMPERSONATION_ARCHITECTURE.md:236` | The Auth0 fallback is `decode_auth0_token`, which does full RS256 verification against JWKS with issuer checking and a manual audience check (`backend/app/utils/auth.py:56-77`). Nothing about it is unverified. |
| `services/role_check.py` provides `get_current_user_from_token`, "used by endpoints like chat, files, etc." | `:279-293`, `:679` | No such function exists. `backend/app/services/role_check.py` contains exactly one function, `check_engagement_access`. There is one authentication dependency in the codebase, `get_current_user`. |
| `GET /api/auth/impersonation-status` performs "Session Validation: verifies session is still active" | `:196` | It only inspects token claims (`backend/app/api/auth.py:476-503`). The active-session check happens earlier, inside the `Depends(get_current_user)` that guards the route. |
| The stop-impersonation token carries `"role": "super_admin"` | `:181` | It carries `original_user.role.value`; `"super_admin"` is only the fallback when the role is NULL (`backend/app/api/auth.py:426`). |
| The banner renders on `if (!isImpersonating) return null` | `:403` | It also requires `user` and `originalUser` to be non-null (`frontend/src/components/ImpersonationBanner.tsx:9`) — see the refresh gotcha above. |
| Migration filename `XXXXX_add_impersonation_sessions.py` | `:81` | `backend/alembic/versions/af13aec12199_add_impersonation_sessions.py`. |

The doc's own security list (`:659-667`) is accurate as far as it goes but omits everything in *Security posture* below.

### Security posture

Enforced today:

- Auth0 Universal Login is the only interactive credential path; the backend never sees a password for Auth0 users (`backend/app/api/auth.py:34`, `frontend/src/pages/Login.tsx:36`).
- Auth0 RS256 tokens are verified against JWKS with issuer checking and explicit audience checking (`backend/app/utils/auth.py:56-77`).
- Deleted (`is_deleted`) and inactive (`is_active == False`) users are refused on every authenticated request with 403 (`backend/app/utils/auth.py:235-245`), independently of `login_check`. Because `get_current_user` re-reads the row on every request, a role change or deletion takes effect on the next call.
- Revoked firms and suspended firm staff are blocked at login, and the Auth0 session is torn down first so the block cannot be bypassed by a silent re-auth (`backend/app/api/auth.py:141-159`, `backend/app/services/login_check.py`).
- Impersonation is super_admin-only, cannot target a super_admin or self, is bounded by a DB row re-checked on every request, and expires in 24 hours (`backend/app/api/users.py:634-676`, `backend/app/utils/auth.py:136-163`).
- Deliverables and program-guide module content have a single, tested choke point (`backend/app/services/deliverable_permissions.py`, `backend/tests/test_program_deliverable_api.py`, `backend/tests/test_program_guide_api.py`).
- Frontend expiry handling is proactive: `frontend/src/main.tsx:29-48` wraps `window.fetch` to short-circuit an already-expired token into a synthetic 401, plus a capture-phase click listener (`main.tsx:53-59`) and a reactive 401 handler, all of which clear `auth_token` and dispatch `auth:token-expired`, which `frontend/src/context/AuthContext.tsx:295-303` turns into a logout.
- The partial unique index `ix_users_email_active` (`backend/app/models/user.py:111-118`) keeps one live account per email while allowing re-registration after a soft delete.

Concrete weaknesses, each factual:

| # | Observation | Reference |
|---|---|---|
| 1 | **HS256 is attempted before RS256** with `SECRET_KEY`, which is also the session-cookie secret. Anyone with that value can forge any identity, any role, and the impersonation claims; nothing pins a token to the algorithm it should have used. | `backend/app/utils/auth.py:110-127`, `backend/app/main.py:58` |
| 2 | **Tokens live in `localStorage`**, readable by any script on the origin; there is no `httpOnly`-cookie option in the codebase. | `frontend/src/pages/AuthCallback.tsx:14`, `frontend/src/context/AuthContext.tsx:73` |
| 3 | **The token is passed through a URL query string** on the Auth0 return leg, so it enters browser history and any URL-logging intermediary. | `backend/app/api/auth.py:172-176` |
| 4 | **The CORS allowlist is hardcoded and ships eight `localhost`/`127.0.0.1` origins in every environment** (ports 5173/3000/8080/8000) alongside `settings.FRONTEND_URL`, together with `allow_credentials=True`, `allow_methods=["*"]`, `allow_headers=["*"]`. Nothing narrows the list per environment. | `backend/app/main.py:67-83`, origins at `:71-78` |
| 5 | **`/files` is an unauthenticated static mount** over `backend/files` with no dependency of any kind — anyone who can guess or obtain a path reads the file. `backend/app/services/auth_service.py:165-166` shows user-uploaded profile pictures living under `/files/uploads/users/...`. | `backend/app/main.py:115` |
| 6 | **No rate limiting anywhere.** No `slowapi`, no limiter middleware and no per-IP counters exist in `backend/app` or `backend/requirements.txt`: `POST /api/auth/login-email`, `POST /api/users/{id}/impersonate` and every other endpoint accept unlimited attempts. | grep for `slowapi\|limiter\|rate_limit\|Limiter` over `backend/app` and `backend/requirements.txt` returns nothing |
| 7 | **No refresh tokens and no rotation.** A single bearer token is valid for 1 day (login), 24 hours (impersonation) or 7 days (post-stop-impersonation); there is no revocation list and no rotation on use, so a stolen token is valid until `exp`. | `backend/app/api/auth.py:164,330,421`, `backend/app/api/users.py:666` |
| 8 | **Inconsistent token lifetimes**: stopping impersonation hands the super_admin a **7-day** token, longer than the 1-day token a normal login produces. | `backend/app/api/auth.py:421` vs `:164`, `:330` |
| 9 | **The ID token is parsed unverified** in the callback (only to read the username claim), so a hostile value in that claim would be trusted for `users.username`/`nickname`. The token came from the Auth0 code exchange over TLS, which bounds the risk. | `backend/app/api/auth.py:114-133` |
| 10 | **Account linking is by email alone**: an Auth0 login whose email matches an existing row rewrites that row's `auth0_id`. If any Auth0 connection permits an unverified email, this is an account-takeover primitive. `email_verified` is read but never gates the link. | `backend/app/services/auth_service.py:119-125`, `:179-181` |
| 11 | **Seven diagnostic endpoints are authentication-only** — no role check and no `check_engagement_access`: create, patch responses, upload file, delete file, submit, cancel, regenerate report. Any signed-in user who knows a `diagnostic_id` can overwrite its responses and submit it, starting the AI pipeline. Reads, the engagement listing and the PDF download *are* scoped. Pipeline behaviour is described in *Diagnostic Engine*. | `backend/app/api/diagnostics.py:78,131,187,261,423,508,720` vs `:59,66,704,846` |
| 12 | **`GET /api/strategy-workbook/{workbook_id}` is authentication-only**, and the module has no shared access helper — only 3 of its 10 routes call `check_engagement_access`. `strategic_business_plan.py` is better (25 of 28 routes call `_check_plan_access`) but that helper no-ops when the plan has no `engagement_id` or its engagement is soft-deleted. See *AI Tools — BBA, Strategy Workbook & Strategic Business Plan*. | `backend/app/api/strategy_workbook.py:435-458`, `backend/app/api/strategic_business_plan.py:63-72` |
| 13 | **`GET /api/auth/check` and the whole session-cookie auth branch are dead** — nothing writes `request.session['user']` — so the "cookie fallback" that appears to be a second auth method silently never fires. | `backend/app/utils/auth.py:216-224`, `backend/app/api/auth.py:250-261` |
| 14 | **The audit trail is log-only**: impersonation start and end reach stdout and nothing else, actions taken under impersonation are attributed solely to the impersonated user, and there is no `audit_log` table to query. | `backend/app/services/audit_service.py:38-39`, `backend/app/api/users.py:681`, `backend/app/api/auth.py:433` |
| 15 | **`require_role` compares `user.role not in allowed_roles`** where `user.role` may be a raw string if the DB holds a value `UserRoleType.process_result_value` cannot map — it returns the raw value on `ValueError`. `require_role` then fails closed, as do the many inline `if current_user.role not in [...]` checks, so a malformed role denies everything rather than granting anything. | `backend/app/utils/auth.py:262`, `backend/app/models/user.py:95-99` |
| 16 | **Authorization failures on firm endpoints surface as 400, not 403**, because `firm_service` raises `ValueError` and the routes map that to `400 "Invalid request data"`. Monitoring cannot distinguish a permission probe from a bad payload. | `backend/app/api/firms.py:271-276`, `:296-301`, `:431-436`, `:456-461`, `:639-644`, `:704-709` |

---

## 9. Core Domain Modules

The non-AI-tool domain modules: the organisational spine (firms, subscriptions, users, advisor–client associations), the workspace (engagements, notes, tasks), and the supporting services (transactional email, files/media, chat, dashboard, settings, AI field privacy). The AI tools themselves have their own sections — *Diagnostic Engine*, *AI Tools — BBA, Strategy Workbook & Strategic Business Plan*, *AI Tools — Roles Matrix, PD & Scorecard*, *Value Builder Programme — Program Guide & Deliverables*. This section describes only where they attach.

### Conventions shared by every module

**Roles** — six values, `backend/app/models/user.py:14-21`:

| Python value | Stored DB value | Meaning |
|---|---|---|
| `advisor` | `ADVISOR` | Solo advisor, no `firm_id` |
| `client` | `CLIENT` | Business owner |
| `admin` | `ADMIN` | Platform admin, non-firm data only |
| `super_admin` | `SUPER_ADMIN` | Full platform access |
| `firm_admin` | `firm_admin` | One per firm; manages seats, advisors, clients |
| `firm_advisor` | `firm_advisor` | Advisor employed by a firm |

**Gotcha:** the DB enum is mixed-case — the four original roles are stored UPPERCASE, the two firm roles lowercase. `UserRoleType` (`backend/app/models/user.py:24-99`) is a `TypeDecorator` translating both ways on every read/write. Raw SQL against `users.role` must reproduce the stored casing or it silently matches nothing.

**Engagement access check** — nearly every read/write outside `firms.py` funnels through `check_engagement_access(engagement, user, require_advisor=False, db=None)` in `backend/app/services/role_check.py:10-107`:

| Role | Access granted when |
|---|---|
| `super_admin`, `admin` | always (`role_check.py:36-37`) |
| `firm_admin` | `user.firm_id` set **and** `engagement.firm_id == user.firm_id` |
| `advisor` (`:46-69`), `firm_advisor` (`:72-93`) | is `primary_advisor_id`, **or** in `secondary_advisor_ids`, **or** has an `active`, non-deleted `AdvisorClient` row for `engagement.client_id` (requires `db` to be passed) |
| `client` (`:96-105`) | is `engagement.client_id` **or** in `engagement.client_ids`; always denied when `require_advisor=True` |

**Gotcha:** the `AdvisorClient` fallback only fires when the caller passes `db=` **and** `engagement.client_id is not None`. Call sites that omit `db` silently narrow access to primary/secondary advisors only.

**Soft delete is inconsistent across modules.** `users`, `engagements`, `tasks`, `notes`, `conversations`, `messages`, `advisor_client` and `diagnostics` all carry `is_deleted BOOLEAN`. `media` instead uses `deleted_at TIMESTAMP` plus `is_active BOOLEAN`. `firms` has no `is_deleted` and no `deleted_at` — only `is_active` (`backend/app/models/firm.py:38`), which is a revocation switch rather than a delete. `subscriptions` has neither a delete flag nor an active flag (`backend/app/models/subscription.py:19-25`); its `status` string is the only lifecycle signal and nothing enforces it. Several endpoints hard-delete rows despite the column existing (noted per module below).

**PostgreSQL array containment** is used for the `_ids` array columns, always as raw SQL text:

```python
text("secondary_advisor_ids @> ARRAY[:user_id]::uuid[]").bindparams(user_id=current_user.id)
```

The most consequential occurrence is on the **login path**: `backend/app/services/login_check.py:52` runs `text("clients @> ARRAY[:user_id]::uuid[]")` against every firm to decide whether a client belongs to a revoked firm, so a broken containment query blocks sign-in rather than degrading a list view. The others are `engagements.py:276` and `:289`; `note.py:158` and `:166`; `tasks.py:273,275,284,295`; `dashboard_service.py:267,380`. All of them tie those queries to Postgres and bypass the ORM's identity mapping.

---

### Firms

**Purpose.** A firm is a multi-advisor organisation. It owns a seat allowance, a set of `firm_advisor` users, a list of client users, and all engagements created under it. Solo advisors have `firm_id = NULL` and never touch this module.

**Key entities.** `Firm` (`backend/app/models/firm.py`), plus the `User.firm_id` foreign key.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `firm_name` | String(255) NOT NULL | |
| `firm_admin_id` | UUID FK→`users.id` **UNIQUE** NOT NULL indexed | `ondelete=RESTRICT`, `use_alter=True` to break the firms↔users FK cycle (`firm.py:25`) |
| `subscription_id` | UUID FK→`subscriptions.id` indexed | `ondelete=SET NULL` |
| `subscription_plan` | String(50) | Denormalised copy of `Subscription.plan_name` |
| `seat_count` | Integer NOT NULL, default 5 | Purchased seats |
| `seats_used` | Integer NOT NULL, **default 1** | Stored counter (see accounting below) |
| `billing_email` | String(255) | Defaults to firm admin's email |
| `clients` | `ARRAY(UUID)` nullable | Client user IDs belonging to this firm |
| `is_active` | Boolean NOT NULL default true | Only `super_admin` may flip it; `false` blocks login for the firm's users |
| `created_at` / `updated_at` | DateTime NOT NULL | |

**The three-way structure.**

- **Firm ↔ firm_admin** is a `UNIQUE` FK on `firms.firm_admin_id`. Exactly one firm admin per firm, and one user can admin at most one firm. The firm admin is *also* linked back through `users.firm_id`, so two FK paths connect the tables — which is why `Firm.advisors` must declare `foreign_keys="User.firm_id"` explicitly (`firm.py:46`).
- **Firm ↔ firm_advisor** is `users.firm_id` + `role = firm_advisor`. `Firm.advisors` covers both firm admins and firm advisors, so most call sites re-filter on role.
- **Firm ↔ clients** is *not* a foreign key. It is the `firms.clients` UUID array, maintained by hand in `FirmService.add_client_to_firm` with an explicit `flag_modified(firm, "clients")` (`firm_service.py:687-691`) because SQLAlchemy does not track in-place list mutation.

**Gotcha:** clients are tracked in *two* places — `firms.clients` (the array) and `users.firm_id`. `add_client_to_firm` writes both, but `remove_client` (`firms.py:495-560`) only sets `client.is_deleted = True` and deliberately **leaves the ID in `firm.clients`**. Every reader must join against `users` and filter `is_deleted == False` (as `list_firms` does at `firms.py:150-156`) or it will count ghosts.

**Endpoints** (`backend/app/api/firms.py`, prefix `/api/firms`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `` | `super_admin` only (`firms.py:69`) | Creates a firm. `firm_admin_id` required (400 otherwise); `subscription_id` required inside the service (`firm_service.py:74`). Promotes the named user to `firm_admin`, sets their `firm_id`, seeds `seats_used = 0`, copies `subscription.plan_name` into `firm.subscription_plan`. Rejects a user who already has a `firm_id`, and `seat_count < 5` |
| GET | `` | `super_admin` (all), `firm_admin` (own firm only) — **`admin` gets 403** (`firms.py:129-133`) | `skip`/`limit` (default 100, max 1000), ordered `created_at DESC`; enriched with `firm_admin_name/email`, live `advisors_count` (`firm_advisor` only) and `clients_count` (non-deleted clients from the array). Returns the **stored** `seats_used` (`firms.py:172`) |
| GET | `/{firm_id}` | `super_admin`, `admin`, or **any** user whose `firm_id` matches | Raw firm row as `FirmDetailResponse` |
| PATCH | `/{firm_id}` | `is_active` → `super_admin` only; other fields → `super_admin`, `admin`, or `can_manage_firm_users` | Blind `setattr` of the three fields `FirmUpdate` accepts: `firm_name`, `billing_email`, `is_active` |
| POST | `/{firm_id}/advisors` | `can_manage_firm_users` = `super_admin`, firm's `firm_admin` | Creates a brand-new `firm_advisor` in Auth0 **and** locally; increments `seats_used`. Rejects any existing email outright |
| DELETE | `/{firm_id}/advisors/{advisor_id}` | same | 204. Reassigns their primary firm engagements to the firm admin, strips them from all `secondary_advisor_ids` in the firm, clears `firm_id`, demotes to `advisor`, sets `is_active=False`, decrements `seats_used` |
| GET | `/{firm_id}/advisors` | `super_admin`, `admin`, firm's `firm_admin`, firm's `firm_advisor` (`firm_service.py:248-255`) | **Active** `firm_advisor` users, plus recomputed `seats_used` = count of *all* `firm_advisor` in the firm (active **and** suspended) and `seats_available` |
| GET | `/{firm_id}/advisors/{advisor_id}/engagements` | `can_view_firm_engagements` = `super_admin`, `admin`, firm's `firm_admin` | `{primary: [...], secondary: [...]}`, non-deleted only — powers the suspension warning dialog |
| POST | `/{firm_id}/advisors/{advisor_id}/suspend` | `can_manage_firm_users` | Sets `is_active=False`. **Requires** a `reassignments` map when the advisor is primary anywhere |
| POST | `/{firm_id}/advisors/{advisor_id}/reactivate` | `can_manage_firm_users` | Sets `is_active=True`. Does **not** restore any engagement assignment |
| POST | `/{firm_id}/clients` | `super_admin`; or `firm_admin`/`admin` whose `firm_id` matches (`firm_service.py:586-591`) | Creates or attaches a client; appends to `firms.clients`; optionally creates an `AdvisorClient` row and emails the advisor |
| DELETE | `/{firm_id}/clients/{client_id}` | `super_admin`, firm's `firm_admin` | 204. Soft-deletes the client user and **hard-deletes** their operational data (see below) |
| GET | `/{firm_id}/engagements` | `can_view_firm_engagements` | All firm engagements including soft-deleted (`firm_service.py:449-451` applies no `is_deleted` filter), `created_at DESC`, paginated in Python |
| POST | `/{firm_id}/engagements/{engagement_id}/reassign` | `can_assign_advisors` = `super_admin`, `admin`, firm's `firm_admin` | Changes `primary_advisor_id`; new advisor must be in the same firm |
| GET | `/{firm_id}/subscription` | `super_admin`, `admin`, or `can_modify_subscription` | Resolves via `firm.subscription_id` |
| PATCH | `/{firm_id}/seats` | `can_modify_subscription` = `super_admin`, firm's `firm_admin` | Changes `seat_count`, recomputes `subscription.monthly_price` |
| GET | `/{firm_id}/stats` | `super_admin`, `admin`, `can_view_firm_engagements` | Returns `firm_id`, `firm_name`, `advisors_count`, `active_advisors_count`, `seats_used`, `seats_available`, `engagements_count`, `active_engagements`, `diagnostics_count`, `tasks_count` |

Permission helpers live in `backend/app/services/firm_permissions.py`: `can_manage_firm_users` and `can_modify_subscription` admit `super_admin` + the firm's own `firm_admin`; `can_view_firm_engagements` and `can_assign_advisors` additionally admit plain `admin`.

**Seat accounting — where `seats_used` moves.** There are two competing definitions and they do not always agree.

| Event | `firm.seats_used` (stored column) | Recomputed count (`COUNT(users WHERE firm_id AND role=firm_advisor)`) |
|---|---|---|
| `create_firm` | set to `0` (`firm_service.py:81`) | 0 |
| `add_advisor_to_firm` | `+= 1` (`firm_service.py:182`) | +1 |
| `remove_advisor_from_firm` | `-= 1` (`firm_service.py:240`) | −1 (user leaves the firm) |
| `suspend_advisor` | **unchanged** — explicit comment at `firm_service.py:392-393` | unchanged (query counts active + suspended) |
| `reactivate_advisor` | unchanged | unchanged |
| adding/removing a **client** | unchanged | unchanged |

The **gate** for adding an advisor reads the stored column (`if firm.seats_used >= firm.seat_count`, `firm_service.py:132`), and `update_seat_count` refuses to shrink below it (`firm_service.py:464`). The two **display** endpoints ignore the column and recompute: `GET /{firm_id}/advisors` (`firms.py:322-328`) and `GET /{firm_id}/stats` (`firms.py:768-783`). `GET /api/firms` (`firms.py:172`) returns the stored column.

**Gotcha:** the firms list and the firm detail pages therefore show two different `seats_used` values for the same firm whenever the column drifts (a failed transaction, a manual DB edit, data written before the counter existed). The recomputed value is the honest one; the stored one is the one that blocks you from adding an advisor. Firm Admins never consume a billed seat under either definition — both exclude `role = firm_admin`. The model default for the column is `1`, while `create_firm` explicitly seeds `0`.

**Suspend/reactivate mechanics** (`firm_service.py:302-442`). Suspension is not a status field; it is `users.is_active = False` while `firm_id` stays set. Before flipping it, `suspend_advisor`:

1. Rejects suspending the Firm Admin, and rejects an already-inactive advisor.
2. If the advisor is `primary_advisor_id` on any firm engagement, requires a `reassignments` dict (`{engagement_id: new_advisor_id}`) covering *every* one of them.
3. Strips the advisor from every `secondary_advisor_ids` array in the firm.

Reactivation only flips `is_active` back. The advisor does not regain the engagements taken from them — those reassignments and secondary-list removals are permanent.

**Gotcha:** the replacement-advisor validation (`firm_service.py:363-367`) checks only `User.firm_id == firm_id` and `is_active == True`. It never checks the role, so an engagement can be reassigned to a **client** who happens to belong to the firm.

**Gotcha:** `AdvisorSuspendRequest.reassignments` is typed `Dict[str, str]` (`backend/app/schemas/firm.py:163-168`) and converted to UUIDs in the endpoint (`firms.py:416-420`) with a shadowed loop variable (`for eng_id, advisor_id in ...` reuses the path parameter name). It works, but a malformed UUID raises a bare `ValueError` reported as the generic `"Invalid request data"` 400.

**Engagement reassignment bug.** `FirmService.reassign_engagement` (`firm_service.py:522-530`) reads the old advisor *after* overwriting it:

```python
engagement.primary_advisor_id = new_primary_advisor_id
old_advisor_id = engagement.primary_advisor_id   # this is now the NEW advisor
if engagement.secondary_advisor_ids and old_advisor_id in engagement.secondary_advisor_ids:
    engagement.secondary_advisor_ids = [aid for aid in ... if aid != old_advisor_id]
```

The intent was to remove the displaced advisor from the secondary list; the effect is to remove the *incoming* advisor from it. The displaced advisor stays a secondary advisor and keeps access.

**Gotcha:** `EngagementReassignRequest` (`backend/app/schemas/firm.py:157-160`) requires an `engagement_id` field in the request body even though it is already a path parameter — and the body value is never read.

**Client removal is destructive.** `DELETE /api/firms/{firm_id}/clients/{client_id}` (`firms.py:495-560`) soft-deletes the *user* and flips every `active` `AdvisorClient` row for them to `inactive` (`firms.py:526`), then for that client's engagements issues real `DELETE` statements against `tasks`, `notes`, `diagnostics` and `bba`, soft-deletes the engagements, and hard-deletes all the client's `media`, `conversations`, and any `bba` rows they created. This is the only place in the codebase that destroys engagement work products.

**Gotcha:** the engagement set it destroys is found with `Engagement.client_id == client.id` only (`firms.py:532`). On a multi-client engagement where this client is in `client_ids` but not `client_id`, the engagement and its children survive with a soft-deleted client.

**Gotcha:** `FirmEngagementResponse` (`backend/app/schemas/firm.py:115-129`) declares `client_id: UUID` and `primary_advisor_id: UUID` as non-optional, while both columns are nullable. `GET /{firm_id}/engagements` and the reassign endpoint 500 on validation for any firm engagement with either field NULL.

**Frontend.** `firmReducer` (`frontend/src/store/slices/firmReducer.ts`). Pages: `frontend/src/pages/dashboard/firm/Firms.tsx` (list) and `frontend/src/pages/dashboard/firm/firmDetails/` — `FirmDetailsLayout.tsx` with child routes `FirmDetailsClients`, `FirmDetailsAdvisors`, `FirmDetailsEngagements`, `FirmDetailsTasks`, `FirmDetailsSubscription`. Routed at `/dashboard/firms` and `/dashboard/firms/:firmId/*` (`frontend/src/App.tsx:96-103`). `frontend/src/pages/dashboard/components/FirmAdminDashboard.tsx` renders the firm-admin home.

---

### Subscriptions

**Purpose.** A billing record describing a plan, a seat allowance and a monthly price. It exists independently of firms and is attached to one by `firms.subscription_id`.

**Key entity.** `Subscription` (`backend/app/models/subscription.py:19-25`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `plan_name` | String(50) NOT NULL | Free text; examples in the column comment are `professional`, `enterprise` |
| `seat_count` | Integer NOT NULL | |
| `monthly_price` | Numeric(10,2) NOT NULL | |
| `status` | String(20) NOT NULL default `active` | Column comment lists `active, cancelled, past_due, trialing` |
| `created_at` / `updated_at` | DateTime NOT NULL | |

There is no `is_deleted`, no `deleted_at` and no `is_active`. A subscription is either present or hard-deleted.

**Status values are not enforced anywhere.** `POST /api/subscriptions` hardcodes `"active"` (`subscriptions.py:57`); `PATCH` accepts any string ≤ 20 chars (`SubscriptionUpdate.status: Optional[str] = Field(None, max_length=20)`, `backend/app/schemas/subscription.py:26`). The four documented values are a convention — no enum, no CHECK, no validator.

**Link to a firm.** One-directional: `firms.subscription_id → subscriptions.id`, `ondelete=SET NULL`. There is no `firm_id` on `Subscription`; the model comment at `subscription.py:27-29` says to reverse-look-up through `Firm`, and both `subscriptions.py:96-99` and `firms.py:673-676` do exactly that. `FirmService.create_firm` notes that **multiple firms may share one subscription** (`firm_service.py:71`) — nothing prevents it, and `DELETE /api/subscriptions/{id}` only checks for the *first* firm using it.

**Endpoints** (`backend/app/api/subscriptions.py`, prefix `/api/subscriptions`) — every one is `super_admin` only:

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `` | `super_admin` | Creates a subscription. `SubscriptionCreate` takes `plan_name`, `seat_count` (ge=1), `billing_period` (`monthly`/`annual`), `price`, `currency`. When `billing_period.lower() == "annual"`, stores `price / 12` as `monthly_price`. Status forced to `active` |
| GET | `` | `super_admin` | Lists all, `created_at DESC`, `skip`/`limit` (default 100, max 1000); optional `firm_id` filter resolved via `Firm.subscription_id` |
| GET | `/{subscription_id}` | `super_admin` | Single record |
| PATCH | `/{subscription_id}` | `super_admin` | Blind `setattr` of `plan_name`, `seat_count`, `monthly_price`, `status` |
| DELETE | `/{subscription_id}` | `super_admin` | 204; refuses with 400 if any firm references it |

Additionally `GET /api/firms/{firm_id}/subscription` (in the firms router) exposes the attached subscription to the firm's own `firm_admin`.

**Gotcha:** `SubscriptionCreate.seat_count` allows `ge=1`, but a firm's minimum is 5 (`firm_service.py:63-64`, `:467-468`, `SeatUpdateRequest.seat_count: ge=5`). A 1-seat subscription can be created and attached to a firm whose `seat_count` is 5.

**Seat price recomputation.** `FirmService.update_seat_count` (`firm_service.py:479-484`) hardcodes the pricing formula:

```python
base_price = 299.00
additional_seats = max(0, new_seat_count - 5)
subscription.monthly_price = base_price + (additional_seats * 50.00)
subscription.seat_count = new_seat_count
```

$299 base for 5 seats, $50 per seat beyond. This overwrites whatever price the subscription was created with, and it ignores `billing_period` — an annual subscription silently becomes monthly-priced the first time anyone changes the seat count.

**Payment provider: there is none on this branch.** Grepping the tracked backend sources (`backend/app/`, `backend/tool_service/`) for `stripe`, `paypal`, `braintree`, `chargebee` and `payment` returns exactly one hit — a comment at `backend/app/services/firm_service.py:489`: `# TODO: Trigger billing update webhook/API call to payment provider`.

`backend/app/services/billing/` exists as a directory containing **only** `__pycache__/` with four stale `.pyc` files (`__init__`, `base`, `catalogue`, `manual`); the `.py` sources are not in the tree and not tracked by git. A stale `backend/app/api/__pycache__/self_service.cpython-312.pyc` sits beside them with no `self_service.py` source. Both are compiled residue from a branch checked out into this working copy — the billing package and its self-service signup tier are covered in *Unmerged Work on Other Branches*.

On this branch, billing is manual bookkeeping. Creating a subscription, changing a seat count, or cancelling has no external effect: no charge is raised, no invoice is issued, no webhook fires. Treat `subscriptions` as a record-keeping table a human must reconcile against whatever real billing system exists off-platform.

**Gotcha:** two different classes named `SubscriptionResponse` serve the same entity. The one in `backend/app/schemas/firm.py:134-147` (used by `GET /api/firms/{id}/subscription`) declares `firm_id`, `cancel_at_period_end` and `cancelled_at` — three fields that do not exist on the model. They validate because all three have defaults, so that endpoint always returns `firm_id: null`, `cancel_at_period_end: false`, `cancelled_at: null`. The one in `backend/app/schemas/subscription.py:28-38` (used by the subscriptions router) omits them.

**Gotcha:** `SubscriptionCreate.currency` (default `"USD"`) is accepted, never read and never persisted.

**Frontend.** `subscriptionReducer` (`frontend/src/store/slices/subscriptionReducer.ts`), pages `frontend/src/pages/dashboard/Subscriptions.tsx` (`/dashboard/subscriptions`) and `frontend/src/pages/dashboard/firm/firmDetails/FirmDetailsSubscription.tsx`.

---

### Users

**Purpose.** Identity and profile for every actor. Backs Auth0 accounts, holds role and firm membership.

**Key entity.** `User` (`backend/app/models/user.py:102-287`). Notable columns beyond the obvious: `auth0_id` (nullable, unique — NULL for email/password users), `hashed_password` (nullable), `business_name` (client's company), `picture`, `bio`, `email_verified`, `is_active`, `is_deleted`, `firm_id` (FK→`firms.id`, `SET NULL`), `last_login`.

Email uniqueness is a **partial index**, not a column constraint (`user.py:111-118`):

```python
Index('ix_users_email_active', 'email', unique=True,
      postgresql_where=sa_text('is_deleted = false'))
```

So an address frees up for re-registration once the old user is soft-deleted. Application-level duplicate checks must include `is_deleted == False` — `create_user` (`users.py:216`) and `AuthService.create_invited_user` (`auth_service.py:299-302`) do; `FirmService.add_advisor_to_firm` (`firm_service.py:136`) and `add_client_to_firm` (`firm_service.py:594`) **do not**, so a soft-deleted user blocks re-adding them to a firm.

**Endpoints** (`backend/app/api/users.py`, prefix `/api/users`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| GET | `` | `admin`, `super_admin` | Paginated list — see below |
| POST | `` | `admin`, `super_admin` | Admin invitation — provisions in Auth0 then locally |
| GET | `/{user_id}` | `super_admin` only | Detail page payload: profile + files + diagnostics + engagement count |
| GET | `/{user_id}/files/{file_id}/download` | `super_admin` only | Streams a `Media` file from disk |
| PATCH | `/{user_id}` | `admin`, `super_admin` | Updates `name` (re-splitting into first/last), `role`, `is_active`, `business_name` — the four fields `UserUpdate` accepts |
| DELETE | `/{user_id}` | `super_admin` only | Soft delete with wide cascade. Returns **200** with `{"message": "User deleted successfully"}`, not 204 |
| POST | `/{user_id}/impersonate` | `super_admin` only | Issues an impersonation JWT — see *Authentication, Authorization & Impersonation* |

**Pagination.** `GET /api/users` (`users.py:44-160`) takes `skip` (default 0) and `limit` (**default 10**, no upper bound), plus `role`, `q` (ILIKE across `name`, `email`, `first_name`, `last_name`, `nickname`) and `ids` (comma-separated UUIDs; a malformed value is a 400). It returns `PaginatedUsersResponse { users, total, skip, limit }`, with `total` computed before the offset/limit. Ordering is `updated_at DESC, created_at DESC`. Soft-deleted users are always excluded.

Visibility narrows for plain `admin` (`users.py:96-108`): unless `ids` was supplied, admins cannot see `firm_admin`/`firm_advisor` users at all, nor any client that has a `firm_id`. Passing `ids` bypasses that filter entirely — which is how a super-admin viewing a firm's client list fetches those users by ID.

**Gotcha:** `limit` has no ceiling. `GET /api/users?limit=1000000` is accepted and serialises every user in the database.

**Creation — Auth0 is provisioned via the Management API.** `Auth0Management.create_user` (`backend/app/services/auth0_management.py:87-249`):

1. Fetches and caches a Management API token via `POST https://{AUTH0_DOMAIN}/oauth/token` using `AUTH0_MANAGEMENT_CLIENT_ID`, `AUTH0_MANAGEMENT_CLIENT_SECRET`, `AUTH0_MANAGEMENT_API_AUDIENCE` (`auth0_management.py:40-58`), expiring it 300s early.
2. Generates a 32-character random password with `secrets.choice`, never disclosed to anyone.
3. Derives an Auth0 username from the email local-part, sanitised to `[a-zA-Z0-9._-]`, padded or truncated into Auth0's 15-char window, then rewritten as `f"{base[:8]}-{sha1(email.lower())[:6]}"[:15]` (`auth0_management.py:170-171`) so `paula@a.com` and `paula@b.com` cannot collide.
4. `POST https://{AUTH0_DOMAIN}/api/v2/users` with `connection: "Username-Password-Authentication"`, `email_verified: false`, `verify_email: false`, `app_metadata: {role}`, plus `given_name`/`family_name` when supplied.
5. On HTTP 409, disambiguates: re-queries `GET /api/v2/users-by-email` and reports either "email already exists" or "username already taken" (`auth0_management.py:234-249`).

`AuthService.create_invited_user` (`backend/app/services/auth_service.py:264-346`) wraps this and writes the local row with the returned `auth0_id`, `email_verified=False`, `is_active=True`, and `picture` from the Auth0 payload.

**Password-setup ticket.** Auth0's own verification email is suppressed (`verify_email: false`). Instead, `Auth0Management.send_password_setup_email` (`auth0_management.py:251-345`) calls `POST https://{AUTH0_DOMAIN}/api/v2/tickets/password-change` with `result_url = {FRONTEND_URL}/login`, `ttl_sec: 432000` (5 days) and `mark_email_as_verified: true`, then hands the resulting ticket URL to `EmailService.send_password_setup_email` (`auth0_management.py:321-325`). Delivery mechanics are in the *Transactional email* subsection below.

Env vars in play here: `AUTH0_DOMAIN`, `AUTH0_MANAGEMENT_CLIENT_ID`, `AUTH0_MANAGEMENT_CLIENT_SECRET`, `AUTH0_MANAGEMENT_API_AUDIENCE`, `FRONTEND_URL`.

**Gotcha:** email failure is swallowed. `create_user` catches it and logs "User created in Auth0 — they can use 'Forgot Password'" (`auth0_management.py:226-230`). The user exists and is billable but has received nothing.

**Soft delete semantics.** `DELETE /api/users/{user_id}` (`users.py:537-612`) is `super_admin` only, refuses self-deletion, requires the target to be non-deleted, and:

| Target | Action |
|---|---|
| Non-deleted engagements where the user is `primary_advisor_id` or `client_id` | `is_deleted = True` |
| Those engagements' `tasks`, `notes`, `diagnostics`, `bba`, `strategy_workbooks`, `strategic_business_plans` | `is_deleted = True` |
| All their `conversations` and those conversations' `messages` | `is_deleted = True` |
| All `advisor_client` rows on either side | `is_deleted = True` |
| Their non-deleted `media` | `deleted_at = utcnow()`, `is_active = False` |
| The user row | `is_deleted = True`, `is_active = False` |
| Auth0 | `Auth0Management.delete_user(auth0_id)` — called **before** `db.commit()`, so an Auth0 failure raises and leaves the local rows untouched |

**Gotcha:** cascade only follows `primary_advisor_id` and `client_id`. An engagement where the deleted user was a *secondary* advisor, or a member of `client_ids` but not `client_id`, survives with a dangling reference. `firms.clients` is never touched, so a deleted client's UUID stays in the array.

**User detail page data.** `GET /api/users/{user_id}` returns `UserDetailResponse` (`backend/app/schemas/user.py:73-77`) = the standard user fields plus:

- `files: List[UserFileResponse]` — all `Media` rows for that user with `deleted_at IS NULL`, newest first (`id`, `file_name`, `file_size`, `file_type`, `file_extension`, `created_at`, `description`, `question_field_name`).
- `diagnostics: List[UserDiagnosticResponse]` — `id`, `engagement_id`, `status`, `overall_score`, `report_url`, `created_at`, `completed_at`.
- `engagements_count: int`.

The engagement set is assembled in three passes (`users.py:313-347`): direct (`client_id` or `primary_advisor_id`), then *all* engagements of the user's firm if they have one, then a full table scan of engagements with a non-null `secondary_advisor_ids` filtered in Python. Diagnostics are then fetched for that union.

**Gotcha:** none of those three queries filters `is_deleted`, so the count and the diagnostics list include soft-deleted records; and the firm pass means a firm advisor's count includes every engagement in their firm, not just theirs.

**Per-user file download.** `GET /api/users/{user_id}/files/{file_id}/download` (`users.py:393-465`), `super_admin` only. Looks up the `Media` row scoped to that user with `deleted_at IS NULL`, checks `Path(media.file_path).exists()`, maps the extension to a MIME type from a hardcoded 10-entry table (`pdf, jpg, jpeg, png, gif, doc, docx, xls, xlsx, txt`; falling back to `application/octet-stream`), and returns a `FileResponse` with `Content-Disposition: attachment` and the original `file_name`.

**Frontend.** `userReducer` and `clientReducer` (`frontend/src/store/slices/`). Pages: `frontend/src/pages/dashboard/users/UsersPage.tsx` (`/dashboard/users`), `frontend/src/pages/dashboard/users/details/UserDetailPage.tsx` (`/dashboard/users/:id`), `frontend/src/pages/dashboard/ClientsPage.tsx`, `frontend/src/pages/dashboard/AdvisorsPage.tsx` with `frontend/src/pages/dashboard/advisors/`.

---

### Transactional email

**Purpose.** All outbound mail from the platform. Two templates, both triggered by provisioning events, both fire-and-forget.

`backend/app/services/email_service.py` (290 lines) is the only sender. It uses the `resend` SDK (`email_service.py:5`) and assigns `resend.api_key = settings.RESEND_API_KEY` **inside each send** (`:144` and `:275`) rather than once at import, then calls `resend.Emails.send({...})`. Both templates are inline HTML+text strings in the module.

| Method | Trigger | Subject |
|---|---|---|
| `send_password_setup_email` (`email_service.py:16`) | `Auth0Management` after minting a password-change ticket (`backend/app/services/auth0_management.py:321-325`); the ticket URL is the email's only CTA | `Set Up Your Password - Trinity Platform` |
| `send_client_added_notification` (`email_service.py:162`) | `FirmService.add_client_to_firm` after a firm client is created and associated (`backend/app/services/firm_service.py:725-731`) | `New Client Assigned to You - Trinity Platform` |

Envelope fields come from settings: `from` is `RESEND_FROM_EMAIL`, `reply_to` is `RESEND_REPLY_TO` (`backend/app/config.py:66-67`). There is no HTML templating engine, no queue and no retry — the send is a synchronous HTTP call inside the request that triggered it.

Both methods catch their own exceptions, log, and **return `bool`** rather than raising. `firm_service.py:735-739` wraps the call in a second `try/except` so a mail failure logs a warning and does not fail client creation; `auth0_management.py:327-328` takes the opposite line and raises when the send returns `False`, which `create_user` then catches (see the Users gotcha above). Net effect: no caller surfaces a mail failure to the API client.

**Gotcha — the code still says Gmail SMTP.** `auth0_management.py:320` logs `"Step 2: Sending custom email via Gmail SMTP..."`, `:328` raises `"Failed to send email via Gmail SMTP"`, and `:333` returns `"email_provider": "Gmail SMTP"` in the response dict. All of that is stale; the send is Resend. The `SMTP_*` settings block (`backend/app/config.py:70-75`) is labelled "legacy, unused" and has no reader anywhere under `backend/app/`.

**Gotcha — a missing key fails silently.** `RESEND_API_KEY` defaults to `""` (`backend/app/config.py:65`), so a misconfigured environment does not fail at startup; it degrades to sending nothing. Because the password-setup email is the **only** way a provisioned user receives a credential, an unset key means every new advisor and client is created successfully and can never sign in. Verify this variable first when new users report they got no invitation.

---

### Advisor–client associations (`advisor_client`)

**Purpose.** A many-to-many link between an advisor and a client that exists **independently of any engagement**. It answers "which clients may this advisor work with?" — a question engagements cannot answer, because an engagement only exists once work has started.

**Key entity.** `AdvisorClient` (`backend/app/models/adv_client.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `advisor_id` | UUID FK→`users.id` `ondelete=CASCADE` indexed | |
| `client_id` | UUID FK→`users.id` `ondelete=CASCADE` indexed | |
| `status` | String(50) NOT NULL `server_default='active'` indexed | Comment: `active, inactive, suspended` |
| `is_deleted` | Boolean NOT NULL `server_default='false'` | |
| `created_at` / `updated_at` | DateTime NOT NULL `server_default=current_timestamp()` | |

Constraint: `UniqueConstraint('advisor_id', 'client_id', name='uq_advisor_client')` — one row per pair, **not** scoped by `is_deleted`, so a soft-deleted association permanently blocks recreating that pair.

**Why it exists alongside engagements.** Three jobs:

1. **Pre-engagement roster.** `GET /api/engagements/user-role-data` builds an advisor's client dropdown *from this table*, not from engagements. Without a row here, an advisor has nobody to create an engagement with.
2. **Creation gate.** `create_engagement` requires an `active`, non-deleted association: for a `firm_advisor` the client must be associated with *them specifically* (`engagements.py:95-102`); for a `firm_admin` any active association for that client is accepted and its `advisor_id` becomes the engagement's primary advisor (`engagements.py:83-93`).
3. **Access widening.**

**How it widens engagement access.** `check_engagement_access` (`role_check.py:54-67` for `advisor`, `:78-91` for `firm_advisor`) grants access to an engagement the advisor is *neither primary nor secondary on*, provided an `active`, non-deleted `AdvisorClient` row links them to `engagement.client_id`. The same clause is duplicated as a SQL subquery in `list_engagements` (`engagements.py:268-280`) and in `get_firm_advisor_dashboard_stats` (`dashboard_service.py:364-385`).

**Gotcha:** the widening keys on `engagement.client_id` (the legacy scalar), never on `client_ids`. On a multi-client engagement, an advisor associated only with the second or third client gets no access. This is the sharpest edge of the `client_id` / `client_ids` split described in the *Engagements* subsection below.

**Gotcha:** the `list_engagements` widening subquery filters `status == "active"` but **omits** `is_deleted == False` (`engagements.py:268-271`); `dashboard_service.py:364-368` does include it, and the Python `check_engagement_access` includes both. So `GET /api/engagements` can list an engagement that `GET /api/engagements/{id}` then denies, when the association is soft-deleted but still `active`.

**Endpoints** (`backend/app/api/adv_client.py`, prefix `/api/advisor-client`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `` | `admin`, `super_admin`, `firm_admin` | Creates an association. Validates advisor role ∈ {`advisor`, `firm_advisor`}, client role = `client`, client not soft-deleted; for a `firm_advisor` both parties must have the **same non-null** `firm_id`. 409 on an existing non-deleted pair. `status` comes from the request (default `"active"`) |
| GET | `` | `admin`/`super_admin`/`firm_admin` see all; `advisor`/`firm_advisor` see rows where they are the advisor; `client` sees rows where they are the client; anything else 403 | Filters: `advisor_id`, `client_id`, `status_filter`, `skip`, `limit` (default 100, max 1000) |
| GET | `/{association_id}` | `admin`, `super_admin`; the advisor on the row; the client on the row. **`firm_admin` always 403** — it is absent from the admin list at `adv_client.py:191` and is not an advisor/client role, so it falls through to the final `else` | Single association with advisor/client names |
| PATCH | `/{association_id}` | `admin`, `super_admin`, or the advisor on the row (`firm_admin` 403) | Updates `status` only |
| DELETE | `/{association_id}` | `admin`, `super_admin`, `firm_admin`, or the advisor on the row | 204. **Hard delete** (`db.delete`, `adv_client.py:317`), despite `is_deleted` existing |

`GET /{association_id}`, `PATCH` and `DELETE` all filter `is_deleted == False` when loading the row; the list endpoint (`adv_client.py:121-144`) **does not** — soft-deleted associations are returned by `GET /api/advisor-client`. Both list and get additionally skip or 404 any association whose client is soft-deleted (`adv_client.py:151-153`, `:218-223`) — the row survives, it is just hidden.

**Where rows are created outside this router.** `FirmService.add_client_to_firm` creates one when `primary_advisor_id` is supplied (`firm_service.py:693-721`), after validating the advisor exists, is in the same firm, and is an active `FIRM_ADVISOR` (explicitly rejecting `FIRM_ADMIN`), then notifies them by email (see *Transactional email* above).

**Where status is changed outside this router.** `DELETE /api/firms/{firm_id}/clients/{client_id}` bulk-updates every `active` association for that client to `inactive` (`firms.py:526`). `DELETE /api/users/{user_id}` sets `is_deleted = True` on both sides (`users.py:593-595`).

**Gotcha:** `status` accepts any string. `AdvisorClientCreate`/`AdvisorClientUpdate` (`backend/app/schemas/adv_client.py`) declare it as a plain `str`, nothing validates it against `active | inactive | suspended`, and every consumer only ever tests `== 'active'` — so a typo silently revokes access.

**Frontend.** `advisorClientReducer` (`frontend/src/store/slices/advisorClientReducer.ts`), consumed by `ClientsPage.tsx`, `AdvisorsPage.tsx` and `FirmDetailsClients.tsx`.

---

### Engagements

**Purpose.** The central workspace. Every diagnostic, task, note, generated document and engagement-scoped chat hangs off an engagement.

**Key entity.** `Engagement` (`backend/app/models/engagement.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `firm_id` | UUID FK→`firms.id` `SET NULL`, nullable indexed | NULL for solo-advisor engagements |
| `client_id` | UUID nullable indexed | **No FK.** "kept for backward compatibility" |
| `client_ids` | `ARRAY(UUID)` nullable | The current representation |
| `primary_advisor_id` | UUID nullable indexed | **No FK.** Model comment (`engagement.py:26-27`) records that it was declared NOT NULL while the DB already allowed NULL |
| `secondary_advisor_ids` | `ARRAY(UUID)` nullable | |
| `engagement_name` | String(255) NOT NULL | |
| `business_name`, `industry`, `description` | String(255) / String(100) / Text | |
| `tool` | String(100) nullable (`engagement.py:35`) | Selected tool; drives bootstrap |
| `status` | String(50) NOT NULL `server_default='active'` indexed | Comment: `active, paused, completed, archived` |
| `is_deleted` | Boolean NOT NULL `server_default='false'` | |
| `created_at` / `updated_at` / `completed_at` | DateTime | |

Cascade relationships (`engagement.py:54-61`): `diagnostics`, `tasks`, `notes`, `bba_projects`, `strategic_business_plans` all `cascade="all, delete-orphan"`; `strategy_workbooks`, `roles_matrices`, `pd_scorecards` do not. There is also a read-only `client` relationship joined on `client_id` (`engagement.py:47-53`).

**`client_id` vs `client_ids`.** Both are written on creation: `client_ids = [client_id]` (`engagements.py:173`). The add/remove-client endpoints keep them in sync by setting `client_id = new_client_ids[0]` (`engagements.py:1170-1171`, `:1266`). Readers follow a fixed fallback:

```python
client_ids_to_fetch = engagement.client_ids if engagement.client_ids else []
if not client_ids_to_fetch and engagement.client_id:
    client_ids_to_fetch = [engagement.client_id]
```

repeated verbatim at `engagements.py:363-366, 648-651, 988-991, 1177-1179, 1272-1274`, `:1160-1162`, `:1242-1244`, and again in `tasks.py:334-336`.

**Gotcha:** the two fields diverge in meaning. `client_id` is "the first client"; `client_ids` is "all clients". The array is rebuilt with `list(set(...))` (`engagements.py:1165`), so order is *not* stable, and reordering changes which client `client_id` points at. Everything that keys on `client_id` alone — the `AdvisorClient` access widening, `check_engagement_access`'s association fallback, `dashboard_service`'s advisor engagement query, the firm-engagement listing's client-name lookup, the firm client-removal cascade — silently ignores clients 2..n.

**Endpoints** (`backend/app/api/engagements.py`, prefix `/api/engagements`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `` | `advisor`, `admin`, `super_admin`, `firm_admin`, `firm_advisor` | Creates the engagement and bootstraps the selected tool |
| GET | `` | all roles (scoped) | Role-filtered list with per-engagement counts |
| GET | `/user-role-data` | all roles | Role-appropriate client/advisor pick-lists |
| GET | `/{engagement_id}` | `check_engagement_access` | Detail |
| GET | `/{engagement_id}/generated-documents` | `check_engagement_access` | Downloadable deliverables from follow-up tools |
| GET | `/{engagement_id}/secondary-advisor-candidates` | `check_engagement_access(require_advisor=True)` | Eligible secondary advisors |
| PATCH | `/{engagement_id}` | the five advisor/admin roles **and** `check_engagement_access(require_advisor=True)` | Update, with secondary-advisor validation |
| POST | `/{engagement_id}/clients` | same | Adds clients from the caller's eligible set |
| DELETE | `/{engagement_id}/clients/{client_id}` | same | Removes a client; refuses to remove the last one |
| DELETE | `/{engagement_id}` | `admin`, `super_admin`, `firm_admin` only | 204; soft delete with cascade |

**Creation** (`engagements.py:51-223`). Sequence:

1. Role gate (the five roles above).
2. Client must exist with `role = client`.
3. Primary advisor resolution depends on **who is creating**:
   - `firm_admin` → looks up *any* `active`, non-deleted `AdvisorClient` for the client and uses **that row's** `advisor_id`, ignoring the submitted `primary_advisor_id`. 400 if none exists.
   - `firm_advisor` → requires an association with *themselves*; forces `primary_advisor_id = current_user.id`.
   - everyone else → uses the submitted `primary_advisor_id` as-is.
4. Primary advisor must have role ∈ {`advisor`, `firm_advisor`, `firm_admin`}.
5. `firm_id` auto-filled from `current_user.firm_id` for firm roles when not supplied.
6. Secondary advisors: de-duplicated (a duplicate in the payload is a 400), must not include the primary, and validated by caller class — `admin`/`super_admin`/`advisor` may only add **active solo** `advisor` users (`firm_id IS NULL`); `firm_admin`/`firm_advisor` may only add active `firm_advisor` users **from the same firm**, and are refused outright if `firm_id` is NULL.
7. Row is inserted and committed.
8. If `tool` is set, the tool is bootstrapped (below). Failure is caught, `print`ed as a warning, and **does not fail creation** (`engagements.py:211-213`).

**Gotcha:** `EngagementCreate.primary_advisor_id` is a required field (`backend/app/schemas/engagement.py:25`) even for `firm_admin` and `firm_advisor` callers, whose submitted value is then discarded.

**Tool bootstrap.** `engagements.py:194-213` mutates `sys.path` at request time to import `backend/tool_service/tool_selector.py`, then calls `create_tool_for_engagement(db, engagement_id, tool_type, created_by_user_id)`. That function:

```python
if tool_type in ('diagnostic', 'value_builder', 'sale_ready'):
    service = get_diagnostic_service(db)
    return await service.create_diagnostic(engagement_id=..., created_by_user_id=...)
elif tool_type == 'kpi_builder':
    return _create_kpi_builder(...)   # placeholder dict, no model exists
else:
    return None                       # unknown tool: silently no-op
```

So **all three of `diagnostic`, `value_builder` and `sale_ready` create the same `Diagnostic` row.** The distinction between them is carried by `engagement.tool` and read downstream — `diagnostic_service` uses it to pick the scoring map and the AI-privacy questionnaire type (`diagnostic_service.py:338-352`), and the Value Builder programme routers reject any engagement whose `tool != "value_builder"`. `kpi_builder` returns a placeholder dict and persists nothing. Any other value is a silent no-op.

**Gotcha:** `backend/tool_service/` (84 lines, one coroutine) is the only Python package under `backend/` that is not inside `app/`, yet it imports `app.*` modules. It is reached solely by the `sys.path` append inside this function body (`engagements.py:197-206`); nothing else in the repo references it and no test covers it. Folding it into `app/services/` would remove the path hack — see *System Architecture*.

**Listing** (`engagements.py:226-409`). Base filter is `is_deleted == False`. Visibility:

| Role | Sees |
|---|---|
| `super_admin` | with `?firm_id=X` → that firm's; without → **only engagements where `firm_id IS NULL`** |
| `admin` | only `firm_id IS NULL` |
| `firm_admin` | all engagements in their firm (empty if they have no `firm_id`) |
| `advisor`, `firm_advisor` | primary **or** secondary **or** client-associated (via `AdvisorClient`) |
| `client` | `client_id == me` **or** `me ∈ client_ids` |

Filters: `status_filter`, `search` (ILIKE on `engagement_name`/`business_name`), `skip`, `limit` (default 100, max 1000). Ordering `created_at DESC`. Each row is enriched with `diagnostics_count`, `tasks_count`, `pending_tasks_count`, `notes_count`, `documents_count` — five separate count queries per engagement, plus client and advisor name lookups. **N+1 by construction.**

**Gotcha — a GET that writes.** `engagements.py:348-360`: if any diagnostic on the engagement is `completed` (the probe query does not filter `is_deleted`) and the engagement's own status is not, the handler sets `status = "completed"`, backfills `completed_at`, and `db.commit()`s — inside a list request. The status change is invisible in `GET /api/engagements/{id}`, which does not run this logic, so a single-engagement fetch can show `active` for an engagement the list has already flipped to `completed`.

**`GET /user-role-data`** (`engagements.py:412-618`). Powers the "who can I work with?" pickers. Declared **before** `/{engagement_id}`, which is why the literal path is not swallowed by the UUID route.

| Caller role | Response shape |
|---|---|
| `advisor`, `firm_advisor` (first branch, `:425`) | `{user_role: "advisor", clients: [...]}` — clients from **their own** active `AdvisorClient` rows, filtered to active non-deleted `client` users |
| `firm_admin` (`:453`) | `{user_role: "firm_admin", clients: [...], advisors: [...]}` — clients from `firm.clients`, advisors = active `firm_admin` + `firm_advisor` in the firm |
| `firm_advisor` (second branch, `:502`) | `{user_role: "firm_advisor", clients: [...], advisors: [...]}` — clients from **the whole firm's** `clients` array |
| `client` (`:551`) | `{user_role: "client", advisors: [...]}` — associated advisors, further filtered to same-firm `firm_advisor` when the client has a `firm_id`, or to `advisor` with `firm_id IS NULL` when they do not |
| `admin`, `super_admin` (`:593`) | `{user_role: "admin", clients: [...], advisors: [...]}` — all active non-deleted clients with `firm_id IS NULL`, all active `advisor` users |
| anything else | 403 |

**Gotcha:** `firm_advisor` is matched by the **first** branch (`current_user.role in [ADVISOR, FIRM_ADVISOR]` at `:425`) and returns `user_role: "advisor"` with only their associated clients and **no advisors array**. The dedicated `elif current_user.role == UserRole.FIRM_ADVISOR` block at `:502-549` is unreachable dead code.

**Client add/remove eligibility.** `get_eligible_clients_for_user` (`engagements.py:1015-1103`) is the gate for `POST /{id}/clients`: `super_admin` → any active non-deleted client; `admin` → those with `firm_id IS NULL`; `advisor` → their active associations; `firm_admin` → `firm.clients` restricted to users whose `firm_id` matches; `firm_advisor` → their active associations restricted to the same firm. Requested clients outside that set are a 403.

**Generated documents** (`engagements.py:675-811`). Aggregates downloadable deliverables from the three follow-up tools, taking only the **most recently updated** record per tool (`max(..., key=lambda r: r.updated_at)`) so a reset replaces rather than accumulates. Emits `GeneratedDocumentItem { id, tool, name, file_type, generated_at, download_url, download_method }`:

| Tool | Condition | File | Method |
|---|---|---|---|
| BBA | `bba.expanded_findings` | `… - Findings & Recommendations.docx` → `/api/poc/{id}/export/docx` | POST |
| BBA | `bba.task_planner_tasks` | `… - Task Planner.xlsx` → `/api/poc/{id}/tasks/export/excel` | POST |
| BBA | `bba.presentation_slides["slides"]` | `… - Presentation.pptx` → `/api/poc/{id}/presentation/export/pptx` | POST |
| Strategy Workbook | `generated_workbook_path` set | `Strategy Workshop Workbook.xlsx` → `/api/strategy-workbook/{id}/download` | GET |
| Business Planner | `plan.final_plan` | `… - Strategic Business Plan.docx` → `/api/strategic-business-plan/{id}/export/docx` | GET |
| Business Planner | `plan.employee_plan` | `… - Employee Strategy Document.docx` → `…/export/employee-docx` | GET |
| Business Planner | `plan.presentation_slides` | `… - Presentation.pptx` → `…/presentation/export` | GET |

The Diagnostic report is deliberately excluded — the frontend lists it from the diagnostics it already fetches (`engagements.py:685-688`). The exporters themselves are described in *AI Tools — BBA, Strategy Workbook & Strategic Business Plan*.

**Secondary-advisor candidates** (`engagements.py:814-884`). Requires advisor-level access. Candidate pool depends on the **caller's** role, not the engagement's: `admin`/`super_admin`/`advisor` get active non-deleted solo `advisor` users; `firm_admin`/`firm_advisor` get active non-deleted `firm_advisor` users from `engagement.firm_id`, or an empty list if the engagement is solo. The current primary advisor is excluded. Consumed by `frontend/src/pages/dashboard/Engagement/SecondaryAdvisorDialog.tsx`.

**Gotcha:** the candidate query excludes only `primary_advisor_id` — advisors already in `secondary_advisor_ids` are still listed. The PATCH then rejects the whole array if it duplicates, so the UI must de-duplicate itself.

**Gotcha:** `PATCH /{engagement_id}` loads the row without an `is_deleted` filter (`engagements.py:900`), unlike every other engagement-scoped handler. A soft-deleted engagement is still editable by anyone with advisor access.

**Soft delete** (`engagements.py:1297-1377`). `admin`, `super_admin`, `firm_admin` only (notably **not** the engagement's own advisor). It first deletes generated files from disk (`StrategyWorkbook.generated_workbook_path`, `StrategicBusinessPlan.generated_report_path` and `generated_employee_report_path`) with `os.remove`, then soft-deletes the `media` linked through `diagnostic_media` (`deleted_at` + `is_active=False`), then sets `is_deleted = True` on `tasks`, `notes`, `diagnostics`, `bba`, `strategy_workbooks`, `strategic_business_plans`, and finally the engagement. The docstring at `:1306-1307` claiming a hard delete of children is wrong — everything is soft.

**Frontend.** `engagementReducer` and `toolReducer` (`frontend/src/store/slices/`). Pages: `frontend/src/pages/dashboard/Engagement/EngagementsPage.tsx` (`/dashboard/engagements`), `EngagementDetailPage.tsx` (`/dashboard/engagements/:engagementId`) with tabs Overview / Tasks / Diagnostic / Value Builder / Tools / Chat Bot (`EngagementDetailPage.tsx:741-748`), plus `DeleteEngagementDialog.tsx`, `SecondaryAdvisorDialog.tsx`, `frontend/src/components/engagement/AddClientsDialog.tsx`, `FollowUpToolsTab.tsx` and `overview/GeneratedFilesList.tsx`.

---

### Notes

**Purpose.** Freeform documentation attached to an engagement, optionally to a diagnostic or a task, with per-note visibility and per-user read tracking.

**Key entity.** `Note` (`backend/app/models/note.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `engagement_id` | UUID FK `CASCADE` NOT NULL indexed | |
| `diagnostic_id` | UUID FK→`diagnostics.id` `SET NULL` indexed | Optional |
| `author_id` | UUID FK→`users.id` `CASCADE` NOT NULL indexed | |
| `task_id` | UUID FK→`tasks.id` `SET NULL` indexed | Optional — this is what makes task comment threads |
| `title` | String(255) nullable | |
| `content` | Text NOT NULL | |
| `note_type` | String(50) NOT NULL default `general` indexed | `general, meeting, observation, decision, progress_update` |
| `is_pinned` | Boolean NOT NULL default false | |
| `visibility` | String(50) NOT NULL default `all` | `all, advisor_only, client_only` |
| `tags` | `ARRAY(String)` nullable | |
| `attachments` | JSONB nullable | Array of `{file_name, file_url, file_type, file_size, uploaded_at}` (typed by `NoteAttachment`, `backend/app/schemas/note.py`) |
| `read_by` | `ARRAY(UUID)` NOT NULL `server_default="{}"` | Read tracking |
| `is_deleted` | Boolean NOT NULL default false | |
| `created_at` (indexed) / `updated_at` | DateTime NOT NULL | |

**Who can see what** — `check_note_visibility(note, user)` (`note.py:26-48`), applied *after* engagement access:

| `visibility` | Visible to |
|---|---|
| any | `super_admin`, `admin`, `firm_admin` — unconditional short-circuit at `note.py:38-39` |
| `all` | everyone with engagement access |
| `advisor_only` | `advisor`, `firm_advisor`, `firm_admin` |
| `client_only` | `client` **only** — plain `advisor` and `firm_advisor` are excluded |
| anything else | nobody (falls through to `return False`) |

**Gotcha:** `firm_admin` appears in both the admin short-circuit and the advisor set, so the second membership never matters. An unrecognised `visibility` string makes the note invisible to non-admins — and nothing validates the value on write, so a typo hides a note permanently.

**Endpoints** (`backend/app/api/note.py`, prefix `/api/notes`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `` | anyone authenticated (see gotcha) | Creates a note; `author_id` forced to the caller; `read_by` seeded with `[author_id]`; validates `task_id` belongs to the same engagement |
| GET | `` | with `task_id`: anyone. Without `task_id`: `super_admin`, `admin`, `advisor`, `client` only | Lists notes; filters `engagement_id`, `task_id`, `skip`, `limit` (default 100, max 1000); ordered `is_pinned DESC, created_at DESC` |
| GET | `/{note_id}` | engagement access + visibility | Single note |
| POST | `/{note_id}/read` | engagement access + visibility | Appends caller to `read_by` (idempotent) |
| PATCH | `/{note_id}` | engagement access **and** (`super_admin`/`admin`, the author, or an `advisor` who is primary/secondary) | Blind `setattr` of any `NoteUpdate` field |
| DELETE | `/{note_id}` | same as PATCH | 204. **Hard delete** (`db.delete`, `note.py:410`), despite `is_deleted` existing |

**Gotcha — `POST /api/notes` has no access check.** `create_note` (`note.py:51-106`) verifies the engagement exists and that any `task_id` belongs to it, but **never calls `check_engagement_access`**. Any authenticated user who knows an engagement UUID can write a note into it, at any visibility. Every other note endpoint checks.

**Gotcha — `GET /api/notes` 403s for firm roles, even with `engagement_id`.** The role branch (`note.py:147-173`) sits in the `else` of `if task_id:`, so it runs on every request that does not pass `task_id` — including requests that *do* pass `engagement_id`. It handles `super_admin`/`admin`, `advisor`, `client`, then `else: raise 403`. `firm_admin` and `firm_advisor` fall into the `else` and get "Invalid user role." The engagement notes modal calls `fetchEngagementNotes`, which sends only `engagement_id` (`frontend/src/store/slices/notesReducer.ts:294-306`), so firm users cannot list engagement notes at all. Only the task-scoped thread (which passes `task_id`) works for them.

**Gotcha — pagination is broken.** `note.py:176` fetches `limit * 2` rows, filters them by visibility in Python, and breaks at `limit`. `skip` is applied to the pre-filter set, so pages overlap and can drop notes. Any engagement where more than half the notes are hidden from the caller returns a short page that looks like the end of the list.

**Gotcha — PATCH/DELETE exclude firm advisors.** The `can_update`/`can_delete` expressions (`note.py:334-341`, `:395-402`) test `current_user.role == UserRole.ADVISOR` and never `FIRM_ADVISOR` or `FIRM_ADMIN`. A firm advisor who is the engagement's primary advisor cannot edit a note they did not author.

**Read tracking.** `read_by` is a UUID array seeded with the author on creation. `POST /{note_id}/read` reassigns (rather than mutates) the list so SQLAlchemy detects the change (`note.py:288-293`). It is consumed by the task list, which computes `unread_notes_count_for_current_user` per task (`tasks.py:341-359`) by loading that task's non-deleted notes, applying `check_note_visibility`, and counting those where the caller is not in `read_by`.

**Frontend.** `notesReducer` (`frontend/src/store/slices/notesReducer.ts`). Components: `frontend/src/components/engagement/notes/EngagementNotesModal.tsx`, `notes/NoteCard.tsx`, and — confusingly — `frontend/src/components/engagement/tasks/NoteForm.tsx` and `tasks/NotesList.tsx` for the task-scoped thread.

---

### Tasks

**Purpose.** Action items on an engagement. Created by hand, in bulk from a diagnostic, from a chat message, or from a Value Builder programme deliverable.

**Key entity.** `Task` (`backend/app/models/task.py`):

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `engagement_id` | UUID FK `CASCADE` NOT NULL indexed | |
| `diagnostic_id` | UUID FK `SET NULL` indexed | Set when auto-generated from a diagnostic |
| `source_deliverable_id` | UUID nullable indexed, **no FK** | Value Builder deliverable linkage |
| `assigned_to_user_id` | UUID FK `SET NULL` indexed | **Legacy scalar** |
| `assigned_to_user_ids` | `ARRAY(UUID)` nullable indexed | Current representation |
| `created_by_user_id` | UUID FK `CASCADE` NOT NULL indexed | |
| `title` | String(255) NOT NULL | |
| `description` | Text nullable | |
| `task_type` | String(50) NOT NULL default `manual` | Comment says `manual, diagnostic_generated`; code also writes `chat_generated` and `deliverable_generated` |
| `status` | String(50) NOT NULL default `pending` indexed | `pending, in_progress, completed, cancelled` |
| `priority` | String(20) NOT NULL default `medium` indexed | `low, medium, high, critical` |
| `priority_rank` | Integer nullable | AI-assigned rank, 1 = highest |
| `module_reference` | String(50) nullable | Diagnostic module (`M1`, `M2`…) or a Value Builder module code |
| `impact_level` | String(20) nullable | `low, medium, high` |
| `effort_level` | String(20) nullable | `low, medium, high` |
| `due_date` | Date nullable indexed | |
| `completed_at` | DateTime nullable | Managed by the PATCH handler |
| `is_deleted` | Boolean NOT NULL default false | |

**Gotcha:** none of `status`, `priority`, `task_type`, `impact_level`, `effort_level` is an enum or CHECK constraint. The documented value sets are conventions. `TaskBase` documents `priority` as `low, medium, high, critical` (`backend/app/schemas/task.py:17`) while the `list_tasks` query parameter documents it as `low, medium, high, urgent` (`tasks.py:228`) — the two disagree and neither is enforced.

**Endpoints** (`backend/app/api/tasks.py`, prefix `/api/tasks`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `` | `check_engagement_access` (any role incl. `client`) | Manual creation |
| POST | `/from-diagnostic` | `check_engagement_access` | Bulk creation from AI recommendations |
| GET | `` | all roles (scoped) | Filtered list with derived fields |
| GET | `/{task_id}` | `check_engagement_access` | Single task |
| PATCH | `/{task_id}` | engagement access **and** admin / firm_admin-of-firm / creator / assignee / primary-or-secondary advisor | Update |
| DELETE | `/{task_id}` | engagement access **and** admin / firm_admin-of-firm / creator / primary-or-secondary advisor (**not** assignee) | 204. **Hard delete** (`db.delete`, `tasks.py:563`) |

**Manual creation** (`tasks.py:32-109`). Requires engagement access. `created_by_user_id` is forced to the caller regardless of the payload (`tasks.py:90`) — `TaskCreate` declares the field required, so clients must send a value that is then discarded. `assigned_to_user_ids`, if present, must be non-empty, must all resolve to real users, and **all must be `is_active`** (`tasks.py:60-71`). A `diagnostic_id`, if present, must belong to the same engagement.

**`/from-diagnostic` bulk creation** (`tasks.py:112-218`). Takes `BulkTaskCreate { tasks: [TaskCreateFromDiagnostic] }`, where each item requires `engagement_id`, `diagnostic_id` and `created_by_user_id`. Validates that all tasks share **one** `engagement_id` and one `diagnostic_id`, that the caller has engagement access, and that the diagnostic belongs to that engagement. Every created task has `status` forced to `"pending"` regardless of input (`tasks.py:201`); `task_type` defaults to `"diagnostic_generated"` (`schemas/task.py:49`) and `created_by_user_id` is again overridden with the caller. All rows are added then committed in a single transaction.

**Gotcha:** the bulk path checks that assigned users **exist** but omits the `is_active` check the single-task path performs (`tasks.py:180-191`). Inactive users can be assigned in bulk but not one at a time.

**`source_deliverable_id` and the Value Builder programme.** This column is deliberately unconstrained — the model comment (`task.py:26-32`) records that it holds *either* a library id (preset deliverable) *or* an instance id (advisor-added deliverable), which are two different tables and therefore admit no single FK. The absence of a constraint is what lets a task outlive its deliverable being scoped out or retired.

It is written in exactly one place: `ProgramDeliverableService.generate_tasks_for_module` (`backend/app/services/program_deliverable_service.py:602-655`), which runs **only** from an advisor's explicit "Create tasks" click. Per deliverable state it skips anything that already has tasks, is scoped out, or is complete, then creates:

```python
Task(engagement_id=engagement.id, created_by_user_id=user_id,
     title=state.title, description=state.description,
     task_type=TASK_TYPE_DELIVERABLE,      # "deliverable_generated"
     status="pending",
     priority="high" if state.mandatory else "medium",
     module_reference=module_code,
     source_deliverable_id=state.deliverable_id)
```

It is read back by `_task_counts_by_deliverable` (`program_deliverable_service.py:271-290`), which groups non-deleted tasks by `source_deliverable_id` to drive the per-deliverable `task_count` badge. Because it filters `is_deleted == False`, deleting a task makes "Create tasks" available again for that deliverable — and since `DELETE /api/tasks/{id}` hard-deletes, the row is gone rather than flagged, which produces the same result by a different mechanism. The deliverable side of this is in *Value Builder Programme — Program Guide & Deliverables*.

**Gotcha:** `source_deliverable_id` is not exposed on `TaskResponse` or `TaskListItem`, and cannot be set through the task API at all. It is invisible to any consumer of `/api/tasks`.

**Assignment arrays.** `assigned_to_user_ids` is the live field: written on create, filtered with `@>` containment (`tasks.py:273,295`), rendered as a comma-joined name string in `assigned_to_name` (`tasks.py:320-325`), and permission-checked in PATCH (`tasks.py:455`). The scalar `assigned_to_user_id` is never written by any endpoint in `tasks.py` — but `get_firm_advisor_dashboard_stats` still counts against it (`dashboard_service.py:416`), so the firm-advisor "Total Tasks" tile only counts tasks the advisor *created*, never tasks assigned to them.

**Filtering and listing** (`tasks.py:221-371`). Base filter `is_deleted == False`. With `engagement_id`, access is checked and the list is scoped to it. Without it:

| Role | Sees |
|---|---|
| `super_admin` | all tasks |
| `admin` | tasks in engagements with `firm_id IS NULL` |
| `firm_admin` | tasks in their firm's engagements (empty if no `firm_id`) |
| `advisor`, `firm_advisor` | created-by-me **or** assigned-to-me **or** engagement primary/secondary |
| `client` | tasks in engagements where they are `client_id` or in `client_ids` |
| anything else | 403 |

Other filters: `assigned_to_user_id` (array containment), `status_filter`, `priority_filter`, `skip`, `limit` (default 100, max 1000). Ordering is `priority DESC, due_date ASC NULLS LAST, created_at DESC`.

**Gotcha:** `priority` is a `String`, so `ORDER BY priority DESC` sorts **alphabetically descending** — `medium` > `low` > `high` > `critical`. The highest-priority tasks sort last. `priority_rank` exists as a proper integer but is never used for ordering.

Derived per-row fields: `engagement_name`, `assigned_to_name`, `created_by_name`, `client_names`, `unread_notes_count_for_current_user` — each a separate query per task, so the list is N+1 several times over.

**Update mechanics** (`tasks.py:410-505`). Permission is engagement access **plus** one of, in `elif` order: admin role; `firm_admin` whose `firm_id` matches the engagement's; task creator; current assignee; primary/secondary advisor. Setting `status = "completed"` stamps `completed_at = now(UTC)`; moving away from `completed` clears it (`tasks.py:492-497`). Reassignment re-validates that all assignees exist and are active.

**Gotcha:** because the permission chain is `elif`, a `firm_admin` whose firm does not match the engagement is rejected even if they created the task.

**Gotcha:** `TaskUpdate` only accepts `title`, `description`, `status`, `priority`, `assigned_to_user_ids`, `due_date`, `completed_at`. `priority_rank`, `module_reference`, `impact_level`, `effort_level` and `task_type` are **write-once at creation** — there is no endpoint to correct them.

**Frontend.** `tasksReducer` (`frontend/src/store/slices/tasksReducer.ts`), `frontend/src/lib/taskUtils.ts`. Pages/components: `frontend/src/pages/dashboard/TasksPage.tsx` (`/dashboard/tasks`), `frontend/src/pages/dashboard/firm/firmDetails/FirmDetailsTasks.tsx`, `frontend/src/components/engagement/tasks/{TasksList,TaskItem,TaskForm}.tsx`.

---

### Files & media

**Purpose.** User-uploaded documents, attached to diagnostics for AI analysis and to users as profile pictures.

**Key entity.** `Media` (`backend/app/models/media.py`), plus the `diagnostic_media` association table (`media.py:13-19`, composite PK `(diagnostic_id, media_id)`, both `ondelete=CASCADE`, plus `created_at`).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `user_id` | UUID FK `CASCADE` NOT NULL indexed | Uploader |
| `file_name` | String(255) NOT NULL | **Original** filename |
| `file_path` | Text NOT NULL | Absolute on-disk path |
| `file_size` | Integer nullable | Bytes, measured after write |
| `file_type` | String(100) nullable | MIME type from the upload part |
| `file_extension` | String(20) nullable | Lowercased, no dot |
| `openai_file_id` | String(255) **UNIQUE** indexed | Legacy |
| `openai_purpose`, `openai_uploaded_at` | String(50), DateTime | Legacy |
| `llm_file_id` | String(255) indexed | Current provider file id |
| `llm_provider` | String(50) | `claude` \| `openai` |
| `llm_uploaded_at` | DateTime | |
| `description` | Text | |
| `question_field_name` | String(255) | Which diagnostic question the file answers |
| `tag` | String(255) (`media.py:61`) | Free-text label, "advisor-only" |
| `is_active` | Boolean NOT NULL default true | |
| `created_at` / `updated_at` / `deleted_at` | DateTime | `deleted_at` is the soft-delete marker |

**`llm_file_id` / `llm_provider` / `openai_file_id`.** The `openai_*` triple predates the Claude migration and is retained for rollback (model comment, `media.py:42`); the pinned OpenAI dependency that rollback would need is covered in *Technology Stack & Dependencies*. The `llm_*` triple is the provider-agnostic replacement. On upload, `FileService.upload_file` (`file_service.py:143-166`) calls `claude_service.upload_file(file_path, purpose="user_data")` and then writes **both** sets from the same response:

```python
media.llm_file_id = llm_file.get("id"); media.llm_provider = "claude"
media.llm_uploaded_at = now
media.openai_file_id = llm_file.get("id")      # legacy mirror
media.openai_purpose = llm_file.get("purpose") or "user_data"
media.openai_uploaded_at = media.llm_uploaded_at
```

So `openai_file_id` today holds a **Claude** file id despite its name, and both columns hold the same value. Downstream AI code passes these ids to the provider so the model can read the document without the bytes being re-sent. `Media.__repr__` prefers `llm_file_id` and falls back to `openai_file_id`. A provider-upload failure is caught and printed; the local row is still committed with both ids NULL (`file_service.py:164-166`).

**Gotcha:** `openai_file_id` is `UNIQUE`. Because it mirrors `llm_file_id`, two rows can never share a provider file id — fine today, but it means the same physical upload cannot be registered twice.

**Upload validation.** `FileService.ALLOWED_EXTENSIONS` (`backend/app/services/file_service.py:28-37`) — exactly these 15, matched case-insensitively on the substring after the last dot:

```
pdf, doc, docx, txt, rtf,
xls, xlsx, csv,
jpg, jpeg, png, gif, webp,
zip
```

`FileService.MAX_FILE_SIZE = 10 * 1024 * 1024` (10 MB, `file_service.py:40`). The size check is `if hasattr(file, 'size') and file.size and file.size > MAX_FILE_SIZE` (`file_service.py:69`) — best-effort, skipped entirely when the framework does not populate `size`. The endpoint additionally caps a single request at `MAX_UPLOAD_FILES = 20` (`backend/app/api/files.py:24`).

**Gotcha — validation errors never reach the client.** `_validate_file` raises `HTTPException`, but `upload_files` wraps each per-file call in `except Exception` and just `print`s (`file_service.py:197-209`). `HTTPException` is an `Exception`, so a disallowed extension or an oversize file is silently skipped and the endpoint still returns **201** with a shorter `files` array. The uploader is told nothing.

**On-disk layout.** `FileService` anchors at `backend/files/uploads`, computed from `Path(__file__).resolve().parents[2]` (`file_service.py:50-52`):

```
backend/files/
├── uploads/
│   ├── diagnostic/{diagnostic_id}/{uuid4}.{ext}     # when diagnostic_id is supplied
│   ├── users/{user_id}/{uuid4}.{ext}                # when it is not
│   ├── users/{user_id}/profilepicture/profilepicture_{epoch}.{jpg|png}
│   ├── sbp/{plan_id}/…                              # Strategic Business Plan
│   └── strategy-workbook/…
├── prompts/            # system, category, and per-tool prompt directories
├── templates/
├── program_guide/
├── exports/
└── scoring_map.json, task_library.json, diagnostic-surveyjs.json
```

Stored filenames are `uuid4()` — the original name survives only in `Media.file_name`, which is what the download endpoint sends back as `Content-Disposition`.

**`UPLOAD_DIR` is a separate, second tree.** `settings.UPLOAD_DIR` defaults to the relative string `"uploads"` (`backend/app/config.py:62`). Each consumer resolves a relative value against `Path(__file__).resolve().parent.parent.parent`, i.e. `backend/` — *not* the process CWD — giving `backend/uploads/`, a different directory from `backend/files/uploads/`. Its three users each append their own subdirectory:

| Caller | Directory |
|---|---|
| `backend/app/api/upload_poc.py:100-104` | `backend/uploads/bba` |
| `backend/app/api/roles_matrix.py:54-59` | `backend/uploads/roles-matrix` |
| `backend/app/api/pd_scorecard.py:78-83` | `backend/uploads/pd-scorecard` |

Core file uploads never touch it. Both trees exist on disk today.

**Gotcha:** only `backend/files` is served over HTTP. Anything written under `backend/uploads` — BBA, Roles Matrix and PD Scorecard source uploads — needs its own download endpoint.

**Static `/files` mount.** `backend/app/main.py:111-115`:

```python
base_dir = Path(__file__).resolve().parents[1]     # backend/
files_dir = base_dir / "files"
files_dir.mkdir(exist_ok=True)
app.mount("/files", StaticFiles(directory=str(files_dir)), name="files")
```

**Gotcha — the mount has no authentication.** `StaticFiles` carries no dependency, so `GET /files/...` serves *anything* under `backend/files` to an anonymous caller who can guess or obtain the path. That includes every uploaded document under `files/uploads/**` (path-guessable if a diagnostic or user UUID leaks) **and** the entire `files/prompts/` directory — `system_prompt.md`, `admin_mode.md`, every category prompt, the diagnostic scoring prompts, and the per-tool prompt directories. Profile pictures rely on this: `settings.py:131` stores `user.picture = f"/files/{rel_path}"`.

Separately, the files **API** router is mounted at `/api` + its own `/files` prefix (`main.py:89`, `files.py:22`), so its real paths are `/api/files/...`. Two different things answer to a path containing `files`.

**Endpoints** (`backend/app/api/files.py`, effective prefix `/api/files`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| POST | `/upload` | any authenticated user | Multipart `files[]` (max 20) + optional `diagnostic_id`, `question_field_name`, `description`. Stores locally, uploads to Claude, attaches to the diagnostic. Returns 201 `{success, message, files[]}` |
| GET | `/diagnostic/{diagnostic_id}` | any authenticated user | Lists **all** media attached to a non-deleted diagnostic (`file_service.py:220-232` applies no `deleted_at`/`is_active` filter); unknown or deleted diagnostic returns an empty list |
| DELETE | `/{file_id}` | **only the uploader** (`media.user_id == current_user.id`) | Soft delete by default; `?hard_delete=true` removes the row and the file from disk |
| GET | `/user/files` | any authenticated user (own) | Lists the caller's `is_active` media, newest first |
| PATCH | `/{file_id}/tag` | `advisor`, `firm_advisor`, `admin`, `super_admin` | Sets or clears `Media.tag` (empty/whitespace → NULL) |

**Gotcha — the upload and diagnostic-listing endpoints have no engagement authorization.** `upload_files` (`files.py:27-108`) accepts any `diagnostic_id`, looks the diagnostic up, and appends the media — it never calls `check_engagement_access`. `get_diagnostic_files` (`files.py:111-143`) likewise lists any diagnostic's attachments to any authenticated caller. Only `/{file_id}/tag` performs an access check, and it does so by walking `media.diagnostics` and testing engagement access on each (`files.py:263-275`), admitting `admin`/`super_admin` unconditionally.

**Gotcha — the `description` form field is accepted and dropped.** `files.py:32` declares it, but `upload_files` never forwards it to `FileService.upload_files`, whose signature has no `description` parameter (`file_service.py:173-180`). The value is silently discarded; only the single-file `upload_file` supports it, and nothing calls that path with it.

**Soft delete.** `delete_file(hard_delete=False)` sets `is_active = False` and `deleted_at = now(UTC)` (`file_service.py:284-287`); the file stays on disk. `hard_delete=True` `os.remove`s the file then `db.delete`s the row. Readers are inconsistent: `get_user_files` filters `is_active == True`, `users.py:294-297` and `dashboard_service.py:302` filter `deleted_at IS NULL`, `engagements.py:344-345` filters both, and `get_diagnostic_files` filters neither.

**The document tag system.** Media and diagnostics each carry a free-text `tag VARCHAR(255)` for advisor-side organisation — `backend/app/models/media.py:61` and `backend/app/models/diagnostic.py:57-58`, both commented "advisor-only". `PATCH /api/files/{file_id}/tag` (`backend/app/api/files.py:233`) is the only writer of either column. There is no controlled vocabulary, no uniqueness constraint and no index on either column, so tags cannot be filtered on server-side and are searched only by loading rows.

On the client, a dedicated Redux slice `frontend/src/store/slices/tagReducer.ts` (208 lines, mounted as `tag` at `frontend/src/store/index.ts:29`) holds two maps — `mediaTags` (mediaId → tag) and `diagnosticTags` (diagnosticId → tag). It hydrates `mediaTags` by fanning out one `GET /api/files/diagnostic/{id}` per diagnostic inside a `Promise.all` (`tagReducer.ts:35-59`) and swallowing per-request failures, so a document list over N diagnostics issues N parallel requests and silently shows blank tags for any that fail.

**Frontend.** `tagReducer` (also calling `/api/files/{mediaId}/tag` and `/api/diagnostics/{id}/tag`), `frontend/src/pages/dashboard/DocumentsPage.tsx` (`/dashboard/documents`).

---

### Chat

**Purpose.** A category-scoped conversation with Trinity AI, grounded in a completed diagnostic and in the engagement's generated tool documents. The Claude client and prompt-loading mechanics are in *AI Layer — Claude Integration & Prompt System*; this subsection covers the conversation model and its scoping.

**Key entities.** `Conversation` (`backend/app/models/conversation.py`) — `user_id` (FK `CASCADE`), `category` (String(50) NOT NULL, `server_default='general'`, indexed), `title` (String(255) nullable), `is_deleted`. `Message` (`backend/app/models/message.py`) — `conversation_id` (FK `CASCADE`), `role` (String(20), `user`/`assistant`, indexed), `message` (Text NOT NULL), `response_data` JSONB, `message_metadata` JSONB, `is_deleted`. `Diagnostic.conversation_id` links a diagnostic to its conversation.

**Engagement scoping is encoded in the title string.** There is no `engagement_id` column on `Conversation`. `ChatService._build_engagement_scope_token` (`chat_service.py:148-150`) produces `"[engagement:{uuid}]"`, and `_build_scoped_conversation_title` (`:152-159`) appends it to e.g. `"Financial Chat"`. Lookup is an `ILIKE '%[engagement:uuid]%'` against `Conversation.title` (`chat_service.py:98`), and `send_message` re-validates the token is present or raises (`chat_service.py:237-242`).

**Gotcha:** engagement membership is a substring match on a user-visible text column. Renaming a conversation title breaks its engagement binding. General-category conversations with no engagement get `title = NULL` (`chat_service.py:157`).

**Endpoints** (`backend/app/api/chat.py`, prefix `/api/chat`) — conversation reads are scoped to the caller by `ChatService.get_conversation`, which returns `None` when `conversation.user_id != user_id`:

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| GET | `/conversations` | any authenticated user | Own non-deleted conversations, `updated_at DESC` |
| POST | `/conversations` | any authenticated user | Get-or-create by `(user_id, category[, engagement scope token])`; optionally links a `diagnostic_id` |
| GET | `/conversations/{id}` | owner only | Single conversation |
| GET | `/conversations/{id}/messages` | owner only | Chronological messages, optional `limit` (1–200) |
| POST | `/conversations/{id}/messages` | owner only | Sends a message, calls Claude, persists both turns. Query param `engagement_id` |
| POST | `/messages/{message_id}/create-task` | any authenticated user | Creates a task from an assistant message. `engagement_id` is a **required** query param |
| POST | `/messages/{message_id}/create-note` | any authenticated user | Creates a note from an assistant message (broken — see below) |

**Category-scoped prompts.** `_get_category_prompt` (`chat_service.py:420-481`) tries `load_prompt(f"category_prompt_{category}")`, then retries against a normalisation map (`finance`→`financial`, `legal`→`legal-licensing`, `hr`/`people`→`human-resources`, `dd`→`due-diligence`, `brand`/`ip`/`intangibles`→`brand-ip-intangibles`, `ops`→`operations`, `customer`→`customers`, `general`→`general`), then falls back to a four-entry hardcoded dict, then `None`.

Category prompt files present in `backend/files/prompts/`:

| File | Category value |
|---|---|
| `category_prompt_brand-ip-intangibles.md` | `brand-ip-intangibles` |
| `category_prompt_customers.md` | `customers` |
| `category_prompt_diagnostic.md` | `diagnostic` |
| `category_prompt_due-diligence.md` | `due-diligence` |
| `category_prompt_financial.md` | `financial` |
| `category_prompt_human-resources.md` | `human-resources` |
| `category_prompt_legal-licensing.md` | `legal-licensing` |
| `category_prompt_operations.md` | `operations` |
| `category_prompt_tax.md` | `tax` |

The base prompt is `system_prompt.md`; `admin_mode.md` also lives there, alongside the diagnostic prompts (`diagnostic_json_extract.md`, `diagnostic_qa_confirmation.md`, `diagnostic_summary.md`, `advice_prompt_diagnostic.md`, `scoring_prompt*.md`, `initial_task_prompt.md`) and per-tool subdirectories (`bba/`, `sale-ready/`, `value-builder/`, `strategy-workbook/`, `strategic-business-plan/`, `roles-matrix/`, `pd-scorecard/`).

The UI offers nine categories (`frontend/src/components/engagement/chatbot/EngagementChatbot.tsx:43-53`): `general`, `financial`, `legal-licensing`, `operations`, `human-resources`, `customers`, `tax`, `due-diligence`, `brand-ip-intangibles`.

**Gotcha:** the two lists do not line up. There is **no `category_prompt_general.md`**, so the UI's default category always falls through to the hardcoded one-liner `"This is a general business advisory conversation. Provide helpful business advice."` And `category_prompt_diagnostic.md` exists but no UI category selects it, so it is dead unless a caller posts `category: "diagnostic"` directly.

**System prompt assembly** (`_build_system_prompt`, `chat_service.py:378-418`) — concatenated in this order:

1. `system_prompt.md` (or a hardcoded fallback paragraph if the file is missing).
2. `"\n\nThe user's name is {user.name}."` when available.
3. The category prompt.
4. The diagnostic context.
5. A condensed context block from the engagement's generated tool documents (`_get_engagement_documents_context`, `chat_service.py:550+`) — BBA, Strategy Workbook and Strategic Business Plan, most-recent record per tool, scoped to the engagement and gated by `check_engagement_access` for the **conversation owner** (`chat_service.py:571-575`).

**Diagnostic context is injected into every category** (`_get_diagnostic_context`, `chat_service.py:483-548`). It searches in three widening steps, each taking the newest `status == "completed"`, non-deleted hit by `completed_at DESC`:

1. `Diagnostic.conversation_id == conversation.id`
2. `Diagnostic.engagement_id == engagement_id` (from the query param)
3. `Diagnostic.created_by_user_id == conversation.user_id` — **any** completed diagnostic of that user

It then serialises the **entire** diagnostic as JSON into the system prompt: `id`, `engagement_id`, `created_by_user_id`, `status`, `diagnostic_type`, `diagnostic_version`, `overall_score`, `started_at`, `completed_at`, `questions`, `module_scores`, `scoring_data`, `ai_analysis`, `user_responses`.

**Gotcha:** step 3 is a cross-engagement fallback with **no access check**. A user with completed diagnostics on several engagements can have engagement A's full diagnostic JSON injected into a chat opened under engagement B, whenever the `engagement_id` query param is absent or that engagement has no completed diagnostic.

**Gotcha:** this bypasses AI Field Privacy. `user_responses` is dumped verbatim; `get_ai_excluded_fields` is never consulted here — see the *AI field privacy* subsection below.

**Message send** (`chat_service.py:210-300`). Saves the user message, loads the **first** `limit` non-deleted messages ordered `created_at ASC`, builds `[system, ...history, current]`, and calls `claude_service.generate_completion(temperature=0.7, reasoning_effort="low", max_output_tokens=1000)` with `model=None` (so `settings.ANTHROPIC_MODEL`). On any exception the assistant message becomes a canned apology and `response_data` holds `{"error": str(e)}` — a **201** is still returned. `response_data` otherwise records `model`, `tokens_used`, `prompt_tokens`, `completion_tokens`; `message_metadata` records `{model}`.

**Gotcha:** the API passes `limit=10` (`chat.py:211`), and the query is `ORDER BY created_at ASC LIMIT 10` — the **ten oldest** messages, not the ten most recent. Past ten turns the model stops seeing recent context and keeps re-reading the opening of the conversation.

**Create-task / create-note off a message.**

- `create_task_from_message` (`chat_service.py:716-762`) loads the assistant message and creates one `Task` with `title = f"Task from chat: {message[:100]}..."`, `description` = the full message, `task_type="chat_generated"`, `status="pending"`, `priority="medium"`. The docstring says "Uses GPT to extract task information" — it does not; there is no extraction. Returns `1`.
- `create_note_from_message` (`chat_service.py:764-803`) is **broken**. It constructs `Note(engagement_id=..., created_by_user_id=..., content=..., note_type="chat_generated")`. `Note` has no `created_by_user_id` column (it has `author_id`, `backend/app/models/note.py:26`), so the declarative constructor raises `TypeError`. The endpoint's generic handler turns this into a **500**. This endpoint cannot have worked since the column was named `author_id`.

Neither service method verifies the caller has access to the `engagement_id` they pass, nor that the message belongs to a conversation they own.

**Corrections to `CHAT_WORKFLOW_EXPLANATION.md`.** That document (repo root) is stale in six places:

| Doc claims | Code does |
|---|---|
| "Calling OpenAI API / Model: gpt-4o" (`:357-372`) | `claude_service.generate_completion(...)`, model from `settings.ANTHROPIC_MODEL` (default `claude-opus-4-6`, `backend/app/config.py:48`) |
| "Last 50 messages included" (`:539`, `:569`) | API passes `limit=10`, and takes the **oldest** 10 |
| Diagnostic context = `ai_analysis.summary` + `ai_analysis.advisorReport` + `user_responses` (`:292-305`, `:487-493`) | The **entire** diagnostic serialised as one JSON blob (`chat_service.py:525-547`) |
| "category selector with 11 options" (`:53`) | 9 in the UI, 9 category prompt files, and the two sets differ (`general` has no file; `diagnostic` has a file but no UI entry) |
| Conversations keyed on `(user, category)` (`:79-85`) | Also on the `[engagement:{uuid}]` title token; `send_message` rejects a mismatch |
| No mention of tool-document context | `_get_engagement_documents_context` appends BBA / Workbook / SBP summaries to every system prompt |

Its emoji-heavy step logs also no longer match; most of that logging has been removed or reduced.

**Frontend.** `frontend/src/components/engagement/chatbot/EngagementChatbot.tsx` and `ChatMessage.tsx`, rendered as the Chat Bot tab of `EngagementDetailPage.tsx`. It gates on the diagnostic being `completed` before showing the category selector, and resets all state when `engagementId` changes to prevent cross-engagement leakage (`EngagementChatbot.tsx:76-84`). There is no Redux slice for chat — the component holds its own state.

---

### Dashboard

**Purpose.** Role-specific landing statistics plus a platform activity time series.

**Endpoints** (`backend/app/api/dashboard.py`, prefix `/api/dashboard`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| GET | `/stats` | `super_admin`, `client`, `firm_advisor` | Returns one of three differently-shaped responses |
| GET | `/activity` | `super_admin` only | Daily counts over `days` (1–90, default 7) |

**Gotcha:** `/stats` is a 403 for `advisor`, `admin` and `firm_admin` (`dashboard.py:70`). Those dashboards are assembled client-side from other endpoints.

**Three response shapes** — the route declares `response_model=Union[DashboardStatsResponse, ClientDashboardStatsResponse, FirmAdvisorDashboardStatsResponse]`. Schemas in `backend/app/schemas/dashboard.py`.

`DashboardStatsResponse` (super admin, `dashboard_service.get_superadmin_dashboard_stats`) — every metric is an all-time total paired with a month-over-month delta string:

| Field | Source |
|---|---|
| `total_users` | `COUNT(users WHERE is_deleted = false)` |
| `total_users_change` / `_change_type` | `"{±N%} this month"` / `positive` \| `negative` \| `neutral` |
| `active_engagements` | `COUNT(engagements WHERE status='active' AND NOT is_deleted)` |
| `active_engagements_change` / `_change_type` | as above |
| `total_firms` | `COUNT(firms)` |
| `total_firms_change` / `_change_type` | as above |
| `ai_generations` | `COUNT(diagnostics WHERE status='completed' AND NOT is_deleted)` |
| `ai_generations_change` / `_change_type` | as above |
| `recent_ai_generations` | 5 most recent completed non-deleted diagnostics with a `completed_at` → `{user_name, engagement_name, completed_at, time_ago}`; the name prefers `completed_by_user_id`, falling back to `created_by_user_id` |

`calculate_percentage_change` (`dashboard_service.py:23-40`) returns `"+N"` (a raw count, not a percentage) when the previous month was zero and the current is positive, and `"0%"`/`neutral` when both are zero. `format_time_ago` produces `"Just now"`, `"{n}m ago"`, `"{n}h ago"`, `"{n}d ago"`, or `"%b %d, %Y"` beyond 7 days.

`ClientDashboardStatsResponse` (client) — no deltas, two embedded lists:

| Field | Source |
|---|---|
| `total_tasks` | All non-deleted tasks in the client's engagements |
| `total_documents` | `COUNT(media WHERE user_id = me AND deleted_at IS NULL)` |
| `total_diagnostics` | Non-deleted diagnostics in those engagements |
| `latest_tasks` | Up to **20** `ClientTaskItem {id, title, status, priority, engagement_name, created_at}`, `created_at DESC` |
| `recent_documents` | Up to **20** `ClientDocumentItem {id, file_name, file_size, created_at}`, `created_at DESC` |

Engagements are found via `client_id == me OR client_ids @> [me]`, with an early return of all-zeros when the client has none.

**Gotcha:** the endpoint docstring says "Recent Documents: List of recent documents (first 3)" (`dashboard.py:48`) — the service returns 20 (`dashboard_service.py:308`), with a comment noting the frontend paginates. The engagement query (`dashboard_service.py:264-269`) does **not** filter `is_deleted`, so a client's counts include soft-deleted engagements.

`FirmAdvisorDashboardStatsResponse` (firm advisor) — five bare integers, no lists, no deltas:

| Field | Source |
|---|---|
| `active_clients` | Count of `active`, non-deleted `AdvisorClient` rows where they are the advisor |
| `total_engagements` | Distinct non-deleted engagements (scoped to their firm when set) where they are primary, secondary, or the `client_id` is one of their associated clients |
| `total_documents` | Distinct `media` with `deleted_at IS NULL`, joined through `diagnostic_media` to those engagements' non-deleted diagnostics |
| `total_tasks` | Non-deleted tasks in those engagements where `assigned_to_user_id == me OR created_by_user_id == me` |
| `total_diagnostics` | Non-deleted diagnostics in those engagements |

**Gotcha:** `total_tasks` tests the **legacy scalar** `assigned_to_user_id` (`dashboard_service.py:416`), which no endpoint in `tasks.py` ever writes. In practice this tile counts only tasks the advisor created.

**Activity feed** (`backend/app/services/activity_service.py`). `get_superadmin_activity_data(db, days)` builds the full inclusive date list from `today - (days-1)` to `today`, runs four independent `GROUP BY CAST(col AS Date)` queries, and zero-fills gaps. Returns `ActivityDataResponse { data: [ActivityDataPoint {date, users, engagements, firms, ai_generations}] }`:

| Series | Query |
|---|---|
| `users` | `users.created_at` (no `is_deleted` filter — differs from `/stats`) |
| `engagements` | `engagements.created_at WHERE NOT is_deleted` |
| `firms` | `firms.created_at` |
| `ai_generations` | `diagnostics.completed_at WHERE status='completed' AND completed_at IS NOT NULL` (no `is_deleted` filter — differs from `/stats`) |

The AI series buckets on `completed_at`, while `/stats` buckets its month-over-month deltas on `created_at` (`dashboard_service.py:157,166`). The two views of "AI generations" disagree for any diagnostic started in one month and completed in another.

**Frontend.** `frontend/src/pages/dashboard/DashboardHome.tsx` dispatches on role to `components/{SuperAdminDashboard,AdminDashboard,AdvisorDashboard,ClientDashboard,FirmAdminDashboard}.tsx` (`advisor` and `firm_advisor` both render `AdvisorDashboard`). Only `SuperAdminDashboard` (`/stats` and `/activity`), `ClientDashboard` (`/stats`) and `AdvisorDashboard` call `/api/dashboard/*` — and `AdvisorDashboard` guards its call behind `isFirmAdvisor` (`AdvisorDashboard.tsx:76-86`), so a solo advisor never hits the 403. No Redux slice — these components fetch directly.

---

### Settings

**Purpose.** Self-service profile editing for the logged-in user. Every endpoint operates on `current_user` only; there is no user-id parameter and no cross-user path.

**Endpoints** (`backend/app/api/settings.py`, prefix `/api/settings`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| GET | `/profile` | any authenticated user (own) | Returns `current_user.to_dict()` |
| PUT | `/profile` | any authenticated user (own) | Multipart update of `first_name`, `last_name`, `email`, `bio`, `profile_picture`; returns the refreshed `to_dict()` |
| DELETE | `/profile/picture` | any authenticated user (own) | Deletes the file and clears `User.picture`; returns the refreshed `to_dict()` |

`to_dict()` (`backend/app/models/user.py:266-287`) returns `id`, `auth0_id`, `email`, `name`, `first_name`, `last_name`, `nickname`, `business_name`, `picture`, `bio`, `email_verified`, `is_active`, `is_deleted`, `role`, `firm_id`, `created_at`, `updated_at`, `last_login`.

**Profile update** (`settings.py:33-137`) takes `multipart/form-data`, all parts optional:

- `first_name` / `last_name` — stripped; empty string becomes `NULL`. Whenever either is supplied, `name` is recomposed as `"first last"` (`settings.py:73-79`), falling back to the existing `name` when both end up empty.
- `email` — **silently ignored for any Auth0-backed user.** `settings.py:81-85` is `if user.auth0_id: pass else: user.email = ...`. Since essentially every user has an `auth0_id`, email is effectively read-only, and the API returns 200 as though it changed.
- `bio` — written when the column exists (guarded by `hasattr`, which is always true).

**Picture upload.** Extensions are restricted to `.jpg`, `.jpeg`, `.png` (`settings.py:97`) — a **narrower** set than `FileService.ALLOWED_EXTENSIONS`, enforced by a different code path with no size limit at all. The directory `backend/files/uploads/users/{user_id}/profilepicture/` is created, **every existing file in it is unlinked**, `.jpeg` is normalised to `.jpg`, and the file is written as `profilepicture_{epoch}{ext}`. `User.picture` is then set to `f"/files/{rel_path}"` — a URL served by the unauthenticated static mount described in the *Files & media* subsection above.

**Gotcha:** profile pictures do not go through `FileService` and get **no `Media` row**. They are invisible to `/api/files/user/files`, to the user-detail file list, and to every soft-delete cascade. They are also world-readable at a guessable path (`/files/uploads/users/{user_id}/profilepicture/…`) with no size cap.

**Picture delete** (`settings.py:140-193`) reverses the `/files/` prefix back to a filesystem path, unlinks the file (swallowing errors with a bare `print`), `rmdir`s the directory if empty, and sets `picture = NULL`.

**Frontend.** `frontend/src/pages/dashboard/SettingsPage.tsx` at `/dashboard/settings`, calling `/api/settings/profile` and `/api/settings/profile/picture`. No Redux slice.

---

### AI field privacy

**Purpose.** Lets an admin mark individual questionnaire fields as "do not send to the AI". The client's answer is still captured and stored in full; it is stripped from the payload handed to Claude.

**Storage model.** `AIFieldPrivacy` (`backend/app/models/ai_field_privacy.py`) — one row per `(questionnaire_type, field_name)` pair. **Absence of a row means included.** Only exclusions and explicit re-inclusions are persisted.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `questionnaire_type` | String(50) NOT NULL indexed | `sale_ready` \| `value_builder` |
| `field_name` | String(255) NOT NULL | Matches the `name` key in the questionnaire JSON |
| `include_in_ai` | Boolean NOT NULL default true | `false` = strip from the AI payload |
| `updated_by_user_id` | UUID FK→`users.id` `SET NULL` indexed | Audit |
| `updated_at` | DateTime NOT NULL `server_default`/`onupdate` `current_timestamp()` | Audit |

Constraint: `UniqueConstraint("questionnaire_type", "field_name", name="uq_ai_field_privacy_type_field")`.

**Endpoints** (`backend/app/api/ai_field_privacy.py`, prefix `/api/ai-field-privacy`):

| Method | Path | Roles allowed | What it does |
|---|---|---|---|
| GET | `/{questionnaire_type}` | `admin`, `super_admin` | All stored rows for that type as `{questionnaire_type, fields: [{field_name, include_in_ai, updated_at, updated_by_user_id}]}` |
| PUT | `/{questionnaire_type}` | `admin`, `super_admin` | Upserts a list of `{field_name, include_in_ai}`, stamps `updated_by_user_id`, returns the full refreshed set |

`_require_admin` (`ai_field_privacy.py:26-31`) admits exactly `ADMIN` and `SUPER_ADMIN` — **`firm_admin` cannot edit or even read these settings**; this is a platform-level control, not a per-firm one. `_validate_type` (`:34-39`) enforces `ALLOWED_TYPES = {"sale_ready", "value_builder"}`, rejecting anything else with a 400.

The PUT is a partial upsert: fields absent from the payload keep whatever row they already had. There is no delete — re-including a field means writing `include_in_ai: true`, which leaves a row behind.

**Where the exclusion is applied.** Grepping the backend for the excluded-fields helpers finds exactly **one** application point, `backend/app/services/diagnostic_service.py:349-367`, inside `_process_diagnostic_pipeline` and executed **before Step 1 (the Q&A JSON extract)**:

```python
excluded_fields = get_ai_excluded_fields(self.db, engagement_type)
if excluded_fields:
    logger.info(f"[Pipeline] AI privacy: excluding {len(excluded_fields)} field(s) from AI payload")
    user_responses = {k: v for k, v in user_responses.items() if k not in excluded_fields}
    diagnostic_questions = {
        "pages": [
            {**page,
             "elements": [el for el in page.get("elements", [])
                          if el.get("name") not in excluded_fields]}
            for page in diagnostic_questions.get("pages", [])
        ]
    }
```

Two things are stripped in tandem: the **answers** (`user_responses`) and the **questions** (`diagnostic_questions.pages[].elements`), so Claude never sees the question text either. Both are local rebinds — the comment at `:349-351` notes the shadowing is deliberate so `diagnostic.user_responses` in the database keeps the complete set. Everything downstream in the pipeline (Q&A extract, scoring, report generation) consumes the filtered copies; the pipeline itself is described in *Diagnostic Engine*.

`questionnaire_type` is resolved from `engagement.tool`, defaulting to `'value_builder'` when the engagement is missing (`diagnostic_service.py:338-343`); `get_ai_excluded_fields` applies the same `(questionnaire_type or "value_builder")` fallback (`backend/app/utils/diagnostic_utils.py:35`) so the two cannot drift.

**Gotcha — matching is top-level only.** Both `get_ai_excluded_fields` and the companion `strip_excluded_fields` compare against top-level dict keys. The latter's docstring is explicit: "nested matrixdynamic/multipletext sub-fields are not individually filtered" (`diagnostic_utils.py:45-46`). Excluding a sub-question of a matrix or multi-text control has no effect — the whole parent object is still sent. Excluding the parent removes all of it.

**Gotcha — the pipeline is the only enforcement point.** `get_ai_excluded_fields` has exactly two references in the entire backend: its definition (`diagnostic_utils.py:14`) and `diagnostic_service.py:352` (imported at `diagnostic_service.py:18`). `strip_excluded_fields` is defined and **never called at all** — despite its docstring describing an export path ("so exports strip exactly the fields the pipeline stripped"). Consequently:

- **Chat leaks excluded fields.** `ChatService._get_diagnostic_context` serialises `diagnostic.user_responses` verbatim into the system prompt for every message (`chat_service.py:539`). The stored responses are complete, so an excluded field reaches Claude on the very next chat turn.
- Any other consumer of `diagnostic.user_responses` — report exports, follow-up tools — is likewise unfiltered unless it filters itself.

Treat AI Field Privacy as "excluded from the *diagnostic generation* payload", not "excluded from AI".

**Frontend.** `frontend/src/lib/aiPrivacyService.ts` (`getFieldConfigs` / `updateFieldConfigs`) and `frontend/src/pages/dashboard/AIPrivacyPage.tsx` at `/dashboard/ai-privacy`. The page renders one tab per type, enumerating fields from the bundled questionnaire JSON — `frontend/src/questions/questions_sale_ready.json` and `frontend/src/questions/questions_ValueBuilder.json` (`AIPrivacyPage.tsx:17-18`) — and overlaying stored flags. So the switch list comes from a **frontend** copy of the questionnaire, while the pipeline strips against the **backend** copy (`backend/files/diagnostic-surveyjs.json`). If the two drift, a field can be missing from the toggle UI while still being sent, or toggleable but nonexistent server-side. No Redux slice.

---

## 10. Diagnostic Engine

The Diagnostic engine is the platform's core assessment workflow: a SurveyJS-shaped questionnaire is filled in against an engagement, submitted, then run through a multi-step Claude pipeline that scores every answer, ranks modules, writes an advisor report, and auto-creates tasks.

**Question count, measured.** The backend question file `backend/files/diagnostic-surveyjs.json` has **9 pages and 272 top-level elements**; not all of them are scored questions (the scoring maps carry 134 and 141 keys). The two frontend sets are larger — 311 and 306 elements. The model docstring at `backend/app/models/diagnostic.py:14` and the `questions` column comment at `:36` both say "200 questions"; both are stale and should not be quoted.

**Dispatch, in one place.** `POST /{diagnostic_id}/submit` flips the row to `processing` and hands `_run_pipeline` to FastAPI `BackgroundTasks`, so the pipeline runs on the API process's own event loop after the response is flushed; there is no worker tier. The runbook view of that — what to check when a run hangs, what a restart does to in-flight work, how to unstick a row — belongs to *Operations, Diagnostics & Troubleshooting*. This section owns the **semantics**: what each step computes, which prompt and scoring map it uses, and what it writes back.

Router: `backend/app/api/diagnostics.py` (`prefix="/diagnostics"`, `:44`), mounted at `/api` (`backend/app/main.py:88`), so every path below is `/api/diagnostics/...`.

---

### 1. Diagnostic types

| Concept | Where | Values |
| --- | --- | --- |
| `engagement.tool` | `backend/app/models/engagement.py:36` — `String(100)`, nullable, no enum | `sale_ready`, `value_builder` |
| `diagnostic.diagnostic_type` | `backend/app/models/diagnostic.py:32` — `String(100)`, NOT NULL | server default `business_health_assessment` |

**The type that drives the pipeline is `engagement.tool`, not `diagnostic.diagnostic_type`** (`backend/app/services/diagnostic_service.py:339-343`):

```python
engagement = self.db.query(Engagement).filter(Engagement.id == diagnostic.engagement_id).first()
engagement_type = engagement.tool if engagement else 'value_builder'
scoring_map = load_scoring_map_for_type(engagement_type or 'value_builder')
```

The PDF cover title and the download filename also prefer `engagement.tool`, falling back to `diagnostic_type` only when the tool is unset (`backend/app/services/report_service.py:191-192`, `:2397-2406`). The frontend picks the question set the same way — `<ToolSurvey ... engagementType={engagement?.tool} />` (`frontend/src/pages/dashboard/Engagement/EngagementDetailPage.tsx:811`).

**Gotcha:** `engagement.tool` is nullable with no constraint. A NULL or misspelled tool silently resolves to Value Builder scoring/prompts, because `load_scoring_map_for_type` defaults to `value_builder` for any unknown key — while `ScoringService.get_modules()` and `ReportService` default the other way, to Sale Ready. The two defaults disagree.

#### `load_scoring_map_for_type` / `load_prompt_for_type`

Both in `backend/app/utils/file_loader.py`, both `lru_cache`d — **prompt and scoring-map edits require a backend restart** (`FileLoader.clear_cache()` at `file_loader.py:147-153` is only wired for tests).

`load_scoring_map_for_type` (`file_loader.py:80-102`) is a hard-coded two-entry lookup:

| engagement_type | File | Keys |
| --- | --- | --- |
| `sale_ready` | `backend/files/prompts/sale-ready/SCORING_MAP_COMPLETE.json` | 134 |
| `value_builder` | `backend/files/prompts/value-builder/SCORING_MAP_VALUE_BUILDER.json` | 141 |
| anything else / NULL | falls through to the Value Builder map | 141 |

`load_prompt_for_type(prompt_name, engagement_type)` (`file_loader.py:104-140`) tries `prompts/{sale-ready|value-builder}/{name}.md` first and falls back to `prompts/{name}.md`. Directory mapping: `sale_ready → sale-ready`, `value_builder → value-builder`.

Prompts actually loaded by the pipeline:

| Call site | Loader | Resolves to |
| --- | --- | --- |
| `diagnostic_service.py:394` | `load_prompt("diagnostic_summary")` | `backend/files/prompts/diagnostic_summary.md` (type-agnostic) |
| `diagnostic_service.py:469` | `load_prompt_for_type("scoring_prompt_scoring", type)` | `prompts/{type-dir}/scoring_prompt_scoring.md` |
| `diagnostic_service.py:648` | `load_prompt_for_type("scoring_prompt_report", type)` | `prompts/{type-dir}/scoring_prompt_report.md` |
| `diagnostic_service.py:1104` | `load_prompt("initial_task_prompt")` | `backend/files/prompts/initial_task_prompt.md` (type-agnostic) |

Every other file under `backend/files/prompts/` (including `scoring_prompt.md`, `scoring_prompt_scoring.md`, `scoring_prompt_report.md` at the top level, and each type dir's `scoring_prompt.md`) is unreachable from this pipeline — the type-specific files always exist, so the generic fallback never fires.

#### Sale Ready vs Value Builder

| | Sale Ready | Value Builder |
| --- | --- | --- |
| Question set (frontend) | `frontend/src/questions/questions_sale_ready.json` — 11 pages, 311 elements | `frontend/src/questions/questions_ValueBuilder.json` — 10 pages, 306 elements |
| Extra pages vs legacy set | `tax-compliance`, `due-diligence` | `growth-strategy` |
| Modules | M1–M8 (`SALE_READY_MODULES`, `backend/app/services/scoring_service.py:15-24`) | V1–V11 (`VALUE_BUILDER_MODULES`, `scoring_service.py:27-39`) |
| Scoring-map key counts by module | 134 total: M5 36, M3 35, M1 15, M4 13, M2 10, M6 10, M7 8, M8 7 | 141 total: V7 25, V1 19, V11 19, V9 15, V4 13, V10 11, V8 11, V3 10, V6 7, V5 6, V2 5 |
| Report (Step 3b) output keys | `clientSummary`, `roadmap[]`, `advisorReport`, **`executionPack`** (`bespokeTasks` / `externalEngagements` / `preListing`) | `clientSummary`, **`diagnosticOverview[]`**, `advisorReport` — no `executionPack` |
| Report HTML sections | 1 Roadmap Summary, 2 Advisor Action Brief, 3 Module Assessments, 4 Program Roadmap | 1 Diagnostic Overview, 2 Advisor Brief, 3 Module Assessments |
| Task library injected | Yes — `{MODULE_TASK_LIBRARY}` placeholder at `sale-ready/scoring_prompt_report.md:59` | Placeholder absent, so `task_library` is passed but never substituted |
| Tone rules | sale-readiness / buyer / due-diligence language | forbids sale/buyer/DD language (`value-builder/scoring_prompt_report.md:158`) |

Module codes come back from Claude as bare codes in `scoredRows[].module` (`"M1"`); `ScoringService.get_modules(engagement_type)` (`scoring_service.py:44-49`) turns them into display names. The report prompts ask for `roadmap[].module` in the *combined* form `"M1 Financial Clarity & Reporting"` — see the validation gotcha under *Scoring* below.

**Gotcha:** `backend/files/task_library.json` is keyed only by the eight **Sale Ready** module display names (`"Financial Clarity & Reporting"` … `"Due Diligence Preparation"`). It is still passed into the Value Builder report call (`diagnostic_service.py:656`), where its keys mean nothing and no placeholder consumes it.

---

### 2. Question sets

| File | Shape | Used by |
| --- | --- | --- |
| `frontend/src/questions/questions_sale_ready.json` | 11 pages / 311 elements | `ToolSurvey.tsx:38`, `AIPrivacyPage.tsx:17` |
| `frontend/src/questions/questions_ValueBuilder.json` | 10 pages / 306 elements | `ToolSurvey.tsx:37`, `AIPrivacyPage.tsx:18` |
| `frontend/src/questions/diagnostic-survey.json` | 9 pages / 272 elements | **nothing imports it** — dead |
| `backend/files/diagnostic-surveyjs.json` | 9 pages / 272 elements | `FileLoader.load_diagnostic_questions()` → stored in `diagnostics.questions` at create time, rebuilt in the pipeline, and used for PDF section labelling |

The dead frontend copy and the backend file carry the same 272 element names and page names but are not identical: `industry_type` has extra `otherText`/`otherPlaceholder` keys in the frontend copy, and two elements (`performance_issues_description`, `detailed_explanation_performance_issues`) have different `visibleIf` expressions.

Selection is one line in `frontend/src/components/engagement/tools/ToolSurvey.tsx:85`:

```ts
const surveyData = engagementType === 'sale_ready' ? saleReadySurveyData : valueBuilderSurveyData;
```

Anything other than `'sale_ready'` renders Value Builder.

**Gotcha (the biggest trap in this area):** the backend never loads the per-type question files. `create_diagnostic` stores `load_diagnostic_questions()` — the 272-element legacy set — into `diagnostics.questions` (`diagnostic_service.py:137,146`), and the pipeline rebuilds `diagnostic_questions` from the same file (`:336`). Exactly 40 Sale Ready keys and 40 Value Builder keys are **absent** from that legacy set. For those questions: the Q&A extract keys on the raw field name instead of the title (`_generate_qa_extract`, `diagnostic_service.py:990-998`); the `question_text_map` sent to Claude omits them (`backend/app/services/claude_service.py:692-695`); the PDF "All Responses" table gives them a blank Section and sorts them to the end (`report_service.py:998-1019`); and the PDF `question_text_map` built from `diagnostic.questions` (`diagnostics.py:862-891`) cannot label them. Affected keys include `balance_sheets_reconciled`, `cash_flow_forecast`, `division_7a_loan_arrangements`, `documented_growth_strategy`.

#### Schema

Root object: `{"pages": [...]}` plus survey-level flags present in the live files — `showProgressBar`, `progressBarLocation`, `progressBarShowPageNumbers`, `showTOC`, `autoAdvanceEnabled`, `autoAdvanceAllowComplete` (the backend ignores all of them). Each page is `{"name", "elements": [...]}`. Element keys seen in the live files: `type`, `name`, `title`, `description`, `choices`, `visibleIf`, `maxLength`, `showOtherItem`, `otherText`, `otherPlaceholder`, `allowMultiple`, `waitForUpload`, `columns` (matrixdynamic), `items` (multipletext), `cellType`, `keyName`.

Supported types and the component that renders each (`frontend/src/components/engagement/tools/question-types/index.ts`, dispatched in `ToolQuestion.tsx:167-206`):

| `type` | Component | Stored value shape |
| --- | --- | --- |
| `dropdown` | `DropdownQuestion.tsx` | string (supports `showOtherItem`, writes a sibling `{name}_other` key) |
| `text` | `TextQuestion.tsx` | string |
| `comment` | `CommentQuestion.tsx` | string (honours `maxLength`) |
| `radiogroup` | `RadioGroupQuestions.tsx` | string |
| `checkbox` | `CheckboxQuestion.tsx` | `string[]`; choices may be `"str"` or `{value,text}` |
| `boolean` | `BooleanQuestion.tsx` | boolean |
| `matrixdynamic` | `MatrixDynamicQuestion.tsx` | `Array<Record<columnName, string>>`, add/remove rows |
| `multipletext` | `MultipleTextQuestion.tsx` | `Record<itemName, string>` |
| `file` | `FileQuestion.tsx` | file-metadata object or array (upload endpoint in *Endpoint table* below; attachment rules in *AI Field Privacy in the pipeline*) |

Anything else renders the literal fallback `Unsupported question type: {q.type}` (`ToolQuestion.tsx:204`).

`visibleIf` is evaluated by a hand-rolled parser in `ToolQuestion.tsx:26-158`, supporting `notempty`, `==`, `<>`, `!=`, `>=`, `>`, `<`, `<=`, `allof [..]`, `contains`, plus `and` / `or` / parentheses. **Unrecognised expressions default to visible** (`:120-121`). Evaluation is client-side only: hidden questions render `null`, but answers already stored for them stay in `user_responses` and are still submitted and scored.

**Gotcha:** `allof` is implemented as "value is one of the listed values" (`expectedValues.includes(actualValue)`, `ToolQuestion.tsx:102-109`) — i.e. SurveyJS `anyof` semantics, not `allof`.

---

### 3. The `diagnostics` table

`backend/app/models/diagnostic.py`. Columns an owner needs to know:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | |
| `engagement_id` | UUID FK → engagements, CASCADE | indexed, NOT NULL |
| `created_by_user_id` / `completed_by_user_id` | UUID FK → users | completer is set at submit; drives report visibility (*Endpoint table*) |
| `conversation_id` | UUID FK → conversations | set on completion, links diagnostic chat |
| `status` | `String(50)` NOT NULL, default `draft` | free text — see *Lifecycle state machine* |
| `diagnostic_type` | `String(100)` NOT NULL, default `business_health_assessment` | title/filename fallback only |
| `diagnostic_version` | `String(20)` NOT NULL, default `1.0` | never read by the pipeline |
| `questions` | JSONB NOT NULL | the legacy 272-element survey, copied at create time |
| `user_responses` | JSONB | merged by `PATCH /responses`; never filtered in place |
| `scoring_data` | JSONB | `{scored_rows, allResponses, validation, tokens_used}` |
| `ai_analysis` | JSONB | `{clientSummary, summary, roadmap, advisorReport, advice, allResponses, executionPack, validation}` |
| `module_scores` | JSONB | `{modules: {code: {...}}, ranked: [...]}` |
| `overall_score` | `Numeric(3,1)` | unweighted mean of module averages |
| `report_url` | `Text` | **never assigned anywhere — always NULL** |
| `report_html` | `Text` | the `advisorReport` HTML string only |
| `tasks_generated_count` | `Integer`, default 0 | |
| `ai_model_used` | `String(100)` | `scoring_result["model"]`, i.e. `settings.ANTHROPIC_MODEL`; falls back to the literal `"gpt-4o"` |
| `ai_tokens_used` | `Integer` | scoring tokens + summary tokens only |
| `tag` | `String(255)` | advisor-facing label; auto-set to `"Diagnostic report by Admin"` on admin submit |
| `celery_task_id` | `String(255)`, nullable (`:61`) | **always NULL; never read or written by any code path.** Added by migration `backend/alembic/versions/add_celery_task_id_to_diagnostics.py` (revision `1902d32c0ce6`) |
| `is_deleted` | Boolean NOT NULL | every read filters on `is_deleted == False` |
| `created_at` / `started_at` / `completed_at` / `updated_at` | DateTime | `started_at` set on first `in_progress`; `updated_at` has `onupdate` and is what the stuck-run watchdog reads |

Response schemas live in `backend/app/schemas/diagnostic.py`: `DiagnosticResponse` (base), `DiagnosticDetail` (+ questions/responses/scoring/ai_analysis/module_scores/report_html), `DiagnosticResults` (scores + ai_analysis), `DiagnosticListItem` (+ `engagement_name`). `report_url` is exposed by `DiagnosticResponse` (inherited by Detail and ListItem) and by `DiagnosticResults`, and is always null.

**Gotcha:** `DiagnosticCreate` declares `questions: Dict[str, Any]` as **required** (`schemas/diagnostic.py:23`), but `create_diagnostic` ignores the field entirely and loads from disk. Callers must send something (`RetakeDiagnosticCard.tsx:55` sends `{}`) or the request 422s.

---

### 4. Lifecycle state machine

Status is free-text `String(50)`; there is no DB enum. The authoritative set the running code and API produce is:

**`draft` | `in_progress` | `processing` | `completed` | `failed` | `archived`**

**Gotcha:** the model comment at `backend/app/models/diagnostic.py:31` reads `"draft, in_progress, processing, completed, archived"` — it **omits `failed`**, which the pipeline writes at `backend/app/tasks/diagnostic_tasks.py:227` and `:260` and which the API documents at `backend/app/api/diagnostics.py:450-452` and `:565`. Conversely, `archived` is listed in the comment and never written by any code path. `PATCH /{id}/responses` will write *any* string the caller puts in `status` (`diagnostic_service.py:201-206`); nothing validates it.

```
                 POST /diagnostics/create
                 DiagnosticService.create_diagnostic()  -> status="draft"
                              |
                              v
                        +-----------+
                        |   draft   |<--------------------------+
                        +-----------+                           |
                              |                                 |
   PATCH /{id}/responses with body status="in_progress"         |
   update_responses() also stamps started_at                    |
                              v                                 |
                      +---------------+                         |
                      |  in_progress  |                         |
                      +---------------+                         |
                              |                                 |
        POST /{id}/submit  (diagnostics.py:494-501)              |
        status="processing"; completed_by_user_id set;           |
        BackgroundTasks.add_task(_run_pipeline)                  |
                              v                                 |
                      +--------------+                          |
                      |  processing  |                          |
                      +--------------+                          |
                       |     |      |                           |
       pipeline OK ----+     |      +---- POST /{id}/cancel      |
       _run_pipeline:182-183 |            diagnostics.py:540-541 |
       status="completed"    |            status="draft",        |
       completed_at=now()    |            completed_at=None -----+
              |              |                     (the running pipeline
              v              |                      is NOT stopped; its next
        +-----------+        |                      check_shutdown poll sees
        | completed |        |                      "draft" and raises
        +-----------+        |                      CancelledError, which
                             |                      _run_pipeline:232-246
      any exception ---------+                      re-writes as "draft")
      _run_pipeline:248-263  -> status="failed"

      Watchdog: GET /{id}/status, if status=="processing" and
      now - updated_at > 3600s -> status="failed"
      (diagnostics.py:583-597) — only fires when someone polls
```

| Transition | Performed by |
| --- | --- |
| → `draft` (create) | `DiagnosticService.create_diagnostic`, `diagnostic_service.py:143` |
| → `in_progress` | `update_responses` when the caller passes `status`, `diagnostic_service.py:201-206` (also sets `started_at`) |
| → `processing` | `submit_diagnostic` endpoint, `diagnostics.py:494` |
| → `completed` | `_run_pipeline`, `backend/app/tasks/diagnostic_tasks.py:182-183` (also sets `completed_at`, links a chat conversation `:186-197`, and flips the parent engagement to `completed` `:199-207`) |
| → `failed` (exception) | `_run_pipeline`, `diagnostic_tasks.py:248-263` (status write at `:260`) |
| → `failed` (stuck > 60 min) | `get_diagnostic_status` endpoint, `diagnostics.py:591-597` |
| → `draft` (cancel request) | `cancel_diagnostic_processing`, `diagnostics.py:540-541` |
| → `draft` (cancel observed) | `_run_pipeline`'s `except asyncio.CancelledError`, `diagnostic_tasks.py:232-246` |

#### Cancel does not cancel

`POST /{diagnostic_id}/cancel` (`diagnostics.py:508-547`) **stops nothing.** Three facts an owner must hold together:

1. It rejects any status other than exactly `processing` (400, `:530-534`), then writes `status = "draft"`, clears `completed_at`, commits and returns. The in-flight pipeline keeps running — and keeps spending tokens — until its next `check_shutdown` poll notices the status change.
2. Its own docstring at `:517` claims it "Cancels the registered background task (if running)". That is **false**; there is no task registry and no handle to cancel.
3. It carries the comment `# Optional: add role / access checks here if needed` at `:535-536`. The endpoint is **authenticated only** — any logged-in user who knows a diagnostic UUID can reset someone else's in-flight run.

**Gotcha:** there is no timeout path that flips a stuck diagnostic to `failed` from inside the pipeline. `_run_pipeline` has an `except SoftTimeLimitExceeded` branch at `diagnostic_tasks.py:217-231`, but nothing raises that exception without a Celery worker, so the branch is unreachable. A hung Claude call holds the row at `processing` until `ANTHROPIC_TIMEOUT` (1800 s) expires and the generic `except Exception` at `:248-263` catches it — or until someone polls `GET /{id}/status` and trips the 60-minute watchdog. Neither happens on its own.

Completing a diagnostic also flips `engagement.status` to `completed`; moving off page 1 of the survey flips it to `active` (`ToolSurvey.tsx` `handleNextPage`).

---

### 5. The AI pipeline

Entry point: `backend/app/tasks/diagnostic_tasks.py::_run_pipeline(diagnostic_id_str)` (`:73`).

Before anything else it forces a fresh Anthropic client on the current loop (`diagnostic_tasks.py:84-85`):

```python
ClaudeService._client = None
ClaudeService.initialize_client()
```

It then opens its own `SessionLocal()` (`:87`) — the request-scoped session is already closed — and calls `DiagnosticService._process_diagnostic_pipeline(diagnostic_obj, check_shutdown=True)` (`:103-105`).

#### Setup (`diagnostic_service.py:325-367`)

1. `user_responses = diagnostic.user_responses`
2. `diagnostic_questions = load_diagnostic_questions()` (the legacy file — see *Question sets*)
3. Resolve `engagement_type`, load `scoring_map` for the type, load `task_library`
4. **Apply AI Field Privacy** (see *AI Field Privacy in the pipeline*)

#### Step by step

| # | Purpose | Input | Claude call | Written back |
| --- | --- | --- | --- | --- |
| 1 | Q&A extract for readability | `diagnostic_questions`, `user_responses` | **none** — pure Python (`_generate_qa_extract`, `:971-1000`) | not persisted; passed to Step 6 |
| 2 | Client-facing narrative summary | `user_responses`, JSON-dumped as the user message | `claude_service.generate_summary`, system prompt `prompts/diagnostic_summary.md`, model `settings.ANTHROPIC_MODEL`, `reasoning_effort="medium"` | `ai_analysis.summary` |
| 3a | Score every answer + read uploaded files | `{type}/scoring_prompt_scoring.md`, the full `scoring_map`, `task_library`, `question_text_map`, `user_responses`, `file_context`, PDF `file_ids`, code-execution `file_ids` | `claude_service.process_scoring` → `generate_json_completion`, `reasoning_effort="low"` | nothing yet; returns `scoredRows`, `allResponses`, `moduleAverages`, `fileInsights` |
| 3b | Write the advisor report | `{type}/scoring_prompt_report.md`, `scored_rows`, `all_responses`, `module_averages`, `file_insights`, `task_library`, `summary`; no files attached | `claude_service.generate_report`, `reasoning_effort="low"` (overridden at `:658`) | merged via `scoring_data.update(report_data)` (`:675`) |
| 4 | Deterministic re-scoring | `scored_rows`, `engagement_type` | none | in-memory `module_scores`, `ranked_modules`, `overall_score`, `validation` |
| 5 | Advice | — | **skipped** | `ai_analysis.advice = None` |
| 6 | Auto-generate tasks | `summary`, `json_extract`, `roadmap` | `claude_service.generate_tasks`, prompt `prompts/initial_task_prompt.md`, `reasoning_effort="medium"` | `Task` rows + `tasks_generated_count` |
| 7 | Persist | everything above | none | `scoring_data`, `module_scores`, `overall_score`, `ai_analysis`, `report_html`, `ai_model_used`, `ai_tokens_used`, `tasks_generated_count` |
| — | PDF | the saved diagnostic | none | **nothing** — bytes are generated then discarded |

**Gotcha — temperature is not what the call sites say.** `process_scoring` and `generate_report` pass `temperature=0.3`, but `generate_completion` overrides it: whenever `reasoning_effort` is `low|medium|high` it sets `thinking={"type":"adaptive"}`, `output_config={"effort": ...}` and **`temperature = 1.0`** (`claude_service.py:286-291`). Every diagnostic Claude call sets a reasoning effort, so `0.3` and `settings.ANTHROPIC_TEMPERATURE` are both dead in this workflow.

**Step 1** (`:369-380`) builds `{question_title: answer}` by looking each response key up in the survey's element titles, falling back to the raw key (`:990-998`).

**Step 2** (`:389-402`). The result string becomes `summary`.

**Step 3a** (`:411-638`) is the long one:
- `_get_current_files_from_responses` (`:854-969`) walks `user_responses` for `media_id`s, cross-checks them against `diagnostic.media`, and falls back to `file_name` + `relative_path` matching. Stale files no longer referenced by an answer are deliberately excluded.
- `_build_file_context` (`:1002-1059`) renders a plain-text manifest of the attached documents, appended to the system prompt.
- Files are split by extension (`:438-460`): PDFs become Claude `document` blocks; `csv/txt/text/md/markdown/json/xml/yaml/yml/xlsx/xls` go to the code-execution tool via `tools=[{"type":"code_interpreter","container":{"type":"auto","file_ids":[...]}}]`, which `claude_service.py:216-238` rewrites to `code_execution_20250825` + `container_upload` blocks; `png/jpg/jpeg/gif/webp/zip` are dropped with a log line.
- Any file whose `llm_file_id` is missing or whose `llm_provider != "claude"` is re-uploaded through `claude_service.upload_file` first (`:472-499`).
- The call is wrapped in a one-shot retry (`max_retries = 1`, `:513`) that fires only on file-not-found-shaped errors (`:546-552`): it re-uploads every PDF/CI file, rewrites `media.llm_file_id`/`openai_file_id`, and retries once.
- The API call goes to `client.beta.messages.create` with `betas=["files-api-2025-04-14","prompt-caching-2024-07-31"]` (files present) or just prompt-caching; the whole system prompt is sent as one `cache_control: ephemeral` block (`claude_service.py:277-307`).

**Step 3b** (`:640-675`) re-calls Claude with no files, feeding back the Part-1 output. `report_data` must be a dict or the pipeline raises (`:670-674`).

**Step 4** (`:677-723`) recomputes module scores from `scored_rows` and discards Claude's own `moduleAverages` for persistence — see *Scoring*.

**Step 5** (`:732-735`) is an explicit no-op:

```python
advice = None
step5_elapsed = 0.0
logger.info("[Pipeline] STEP 5 (Advice): Skipped - advisory content is now embedded in advisorReport from scoring step")
```

The advisory narrative now arrives inside `advisorReport` from Step 3b. `backend/files/prompts/advice_prompt_diagnostic.md` and `ClaudeService.generate_advice` (`claude_service.py:814`) are orphaned by this.

**Step 7** (`:764-834`) writes:

```python
diagnostic.scoring_data  = {"scored_rows", "allResponses", "validation", "tokens_used"}
diagnostic.module_scores = {"modules": {m["module"]: m for m in ranked_modules}, "ranked": ranked_modules}
diagnostic.overall_score = overall_score
diagnostic.ai_analysis   = {"clientSummary", "summary", "roadmap", "advisorReport",
                            "advice", "allResponses", "executionPack", "validation"}
diagnostic.report_html   = advisor_report_str
diagnostic.ai_model_used = scoring_result.get("model", "gpt-4o")
diagnostic.ai_tokens_used = scoring tokens + summary tokens
diagnostic.tasks_generated_count = tasks_count
```

Each JSONB assignment is followed by `flag_modified(...)` because SQLAlchemy will not detect in-place JSONB mutation.

`roadmap` is read as `scoring_data.get("diagnosticOverview") or scoring_data.get("roadmap", [])` (`:692`) — that single line is what makes both the Sale Ready (`roadmap`) and Value Builder (`diagnosticOverview`) shapes work.

#### PDF generation inside the pipeline

Back in `_run_pipeline` (`diagnostic_tasks.py:113-179`), after the pipeline returns, a PDF is rendered via `ReportService.generate_pdf_report`, wrapped in its own try/except and treated as non-critical; **the byte count is logged and the bytes are dropped** (`:174`). Nothing stores them; the download endpoint re-renders from scratch every time.

#### `check_shutdown` cooperative cancellation

`_process_diagnostic_pipeline(diagnostic, check_shutdown=False)` takes a flag that `_run_pipeline` always passes as `True`. At each checkpoint it re-reads the row and bails if someone flipped it to `draft`:

```python
if check_shutdown:
    self.db.refresh(diagnostic)
    if diagnostic.status == "draft":
        logger.warning(f"[Pipeline] Task cancelled ... {diagnostic.id}")
        raise asyncio.CancelledError("Task cancelled")
```

Checkpoints: before Step 1 (`:328`), after Step 1 (`:383`), after Step 2 (`:405`), after Step 3a (`:626`), after Step 3b (`:680`), after Step 4 (`:726`), after Step 6 (`:756`).

**Gotcha:** cancellation is only observed *between* steps. Step 3a routinely spends many minutes inside a single `await`, so a cancel issued during scoring does nothing until that call returns — and the tokens are spent regardless. There is no in-flight request abort.

**Gotcha:** the whole of Step 6 sits inside a `try` whose `except Exception` (`:761-762`) only logs a warning. `asyncio.CancelledError` derives from `BaseException`, so the post-Step-6 checkpoint still propagates correctly — but every genuine task-generation failure is swallowed, and a diagnostic can complete with `tasks_generated_count = 0` and no visible error.

---

### 6. AI Field Privacy in the pipeline

Admins mark individual questionnaire fields as excluded from AI processing; rows live in `ai_field_privacy` (`backend/app/models/ai_field_privacy.py`), unique on `(questionnaire_type, field_name)`, `include_in_ai` boolean, absence meaning *included*.

The exclusion is applied in exactly **one** place — `diagnostic_service.py:349-367`, immediately after the data files load and before Step 1:

```python
excluded_fields = get_ai_excluded_fields(self.db, engagement_type)
if excluded_fields:
    user_responses = {k: v for k, v in user_responses.items() if k not in excluded_fields}
    diagnostic_questions = {"pages": [{**page, "elements": [
        el for el in page.get("elements", []) if el.get("name") not in excluded_fields
    ]} for page in diagnostic_questions.get("pages", [])]}
```

`user_responses` is a **local shadow** of `diagnostic.user_responses`; the stored column is untouched. Because every downstream step reads that local, the exclusion propagates to Step 1's extract, Step 2's summary, Step 3a's payload, and — via `_get_current_files_from_responses(..., user_responses_override=user_responses)` (`:420`) — to which uploaded files get attached. Steps 3b and 6 only ever see already-filtered derivatives.

Human-facing exports deliberately do **not** filter. Both the PDF download (`diagnostics.py:915-926`, passing `user_responses_override=diagnostic.user_responses or {}`) and `/generate-document` (`diagnostics.py:1027-1035`) carry explicit comments saying private fields are shown to humans and only withheld from Claude. The survey UI badges excluded questions with "Not sent to AI" (`ToolQuestion.tsx:208-225`), sourced from `getFieldConfigs` in `ToolSurvey.tsx:129-137`.

`get_ai_excluded_fields` and `strip_excluded_fields` live in `backend/app/utils/diagnostic_utils.py:14-58`. Matching is **top-level field names only** — sub-fields of a `matrixdynamic` or `multipletext` cannot be excluded individually (documented at `diagnostic_utils.py:44-46`). `strip_excluded_fields` itself has no callers anywhere in the backend.

---

### 7. Scoring

#### What the scoring map is

`SCORING_MAP_*.json` is a flat `{question_key: {"module": "M1", "values": {"answer text": score}}}`, e.g.

```json
"financial_performance_since_acquisition": {
  "module": "M1",
  "values": {"Better": 5, "Same": 3, "Worse": 1}
}
```

The whole map is serialised into the Step 3a system prompt (`claude_service.py:699-704`), so **Claude does the answer→score mapping, not Python**. `ScoringService.map_response_to_score` / `build_scored_rows` (`scoring_service.py:235-310`) implement the same mapping in Python but nothing calls `build_scored_rows`.

`backend/files/scoring_map.json` (104 keys, M-codes) is legacy: `load_scoring_map` is imported at `diagnostic_service.py:24` and never called.

#### Module averages, overall score, rankings, RAG

All computed in Python from Claude's `scoredRows`, in `backend/app/services/scoring_service.py`:

- `calculate_module_scores(scored_rows, engagement_type)` (`:72-135`) groups rows by `row["module"]`, coerces `row["score"]` to float (skipping unparseable rows with a warning), and averages with `Decimal(...).quantize(Decimal("0.1"), ROUND_HALF_UP)`. Returns `{code: {module, module_name, score, count, total, questions[]}}`.
- `rank_modules(module_scores)` (`:176-210`) sorts ascending by `(score, module code)` — lowest score = rank 1 = highest priority — then stamps `rank` and `rag` onto each dict **in place**, which is why `module_scores.modules` and `.ranked` end up as the same objects.
- `calculate_overall_score(module_scores)` (`:212-233`) is the **unweighted mean of the module averages**, not of the individual question scores — a 5-question module counts as much as a 36-question one.
- `determine_rag_status(score)` (`:137-153`): `< 2.0` → Red, `< 4.0` → Amber, else Green (`RAG_RED_THRESHOLD = 2.0`, `RAG_AMBER_THRESHOLD = 4.0`).
- `determine_severity(score)` (`:155-174`) is a finer five-band scale (`< 1.5` Critical, `< 2.7` High, `< 3.5` Moderate, `< 4.0` Low, else Strong) that does not align to the RAG boundaries. It is **not used by the diagnostic pipeline or the PDF**; its only consumer is `backend/app/services/program_guide_service.py:389` (see *Value Builder Programme — Program Guide & Deliverables*).

The prompts state a different RAG rule ("Red < 2 | Amber >= 2 < 3.9 | Green >= 4", `sale-ready/scoring_prompt_scoring.md:17`, `value-builder/scoring_prompt_scoring.md:20`) plus a six-band `priorityStrength` scale (`0.0-1.4 Red/Critical` … `4.5-5.0 Green/Strong`). Claude's `rag`/`priorityStrength` strings flow into the report HTML text; the Python thresholds drive `module_scores.ranked[].rag`. A 3.95 is Amber to Python and Green to the prompt.

#### Validation and repair

`validate_scoring_data(ai_scoring_data, user_responses, scoring_map)` (`scoring_service.py:312-385`) returns `{"is_valid": bool, "warnings": [], "errors": []}` and is stored in both `scoring_data.validation` and `ai_analysis.validation`. It:

1. Hard-errors (`is_valid = False`) if `scoredRows`/`scored_rows` is empty.
2. Recomputes module scores from `scored_rows` and warns where a roadmap item's `score` differs from the recomputed value by more than 0.1.
3. Warns if `len(scored_rows)` differs from the count of response keys present in the scoring map.

**This is advisory only.** No endpoint surfaces `validation`, no code branches on `is_valid`, and a diagnostic with `is_valid: false` still completes.

**Gotcha:** check 2 is effectively dead. It matches on `roadmap_item["module"] in module_scores`, whose keys are bare codes (`"M1"`), but the report prompts specify `roadmap[].module` as `"M1 Financial Clarity & Reporting"` (`sale-ready/scoring_prompt_report.md:106`). When the model follows the prompt the lookup never hits and no comparison is made.

**Gotcha:** `validate_scoring_data` calls `calculate_module_scores(scored_rows)` without `engagement_type` (`scoring_service.py:345`), so on a Value Builder run the comparison dict is built with Sale Ready module names. Scores are unaffected (grouping is by code); only the throwaway `module_name` is wrong.

The real "repair" is structural, in two places:

- **JSON repair** in `claude_service.generate_json_completion` (`claude_service.py:498-648`): direct parse → strip ` ```json ` fences → `raw_decode` (ignore trailing text) → seek the first `{`/`[` (skip preamble) → `_repair_json` (`:445-487`: fence strip, `raw_decode`, then the **`json_repair` library**, then regex fixes for trailing commas and missing separators) → last-resort follow-up turn at `temperature=0.0` asking for raw JSON only. `_coerce_parsed_to_dict` (`:489-496`) unwraps a top-level list into its first dict.
- **Score coercion** in `calculate_module_scores` (skip unparseable) and `rank_modules` (cast strings, default a non-castable score to `0.0`, `scoring_service.py:192-199`).

Claude's own `moduleAverages` from Step 3a are forwarded to Step 3b labelled "pre-computed and verified" (`claude_service.py:764`) but are **never persisted**; `module_scores` on the row always comes from the Python recomputation.

---

### 8. Task auto-generation

`DiagnosticService._generate_tasks` (`diagnostic_service.py:1061-1223`):

1. **Idempotency**: deletes every existing `Task` with `engagement_id == diagnostic.engagement_id AND diagnostic_id == diagnostic.id AND task_type == "diagnostic_generated"` (`:1082-1101`), so a resubmit replaces rather than duplicates. A failure here is logged, rolled back, and generation continues.
2. Loads `prompts/initial_task_prompt.md`.
3. Calls `claude_service.generate_tasks(task_prompt, diagnostic_summary=summary, json_extract, roadmap)`. The prompt file is appended to a large hard-coded context string in `claude_service.py:844-866` carrying the JSON template and the "only Amber/Red modules, typically 3-8 tasks, every task must cite `data_reference`" rules; `initial_task_prompt.md` repeats and expands them.
4. Parses defensively (`:1119-1144`): accepts a bare list, `{"tasks": [...]}`, or a single task object with a `title`/`name`.
5. For each entry builds a `Task` (`:1176-1187`) with `task_type="diagnostic_generated"`, `status="pending"`, `priority` defaulting to `"medium"`, `title` trimmed to 255 chars, `module_reference` = `category` (or `module_reference`) trimmed to 50 chars, and `description` run through `convert_numbered_list_to_bullets` (`diagnostic_service.py:32-81`, which rewrites `1.`, `1)`, `Step 1.`, `step1)` line prefixes to `- `).
6. Commits once (rolling back and returning 0 on failure), returns the count → `diagnostic.tasks_generated_count`.

`backend/files/task_library.json` is a static `{module display name: [suggested task strings]}` file. It is **not** used to build Task rows. It is injected into the Sale Ready report prompt only, by substituting `{MODULE_TASK_LIBRARY}` in `claude_service.generate_report` (`claude_service.py:755-758`), so the model can draw the report's "Must-Do" items from a fixed vocabulary. It is also passed to `process_scoring`, whose prompt never references it.

`_map_category_to_module` (`diagnostic_service.py:1225-1241`) maps category slugs to M-codes but is dead — the comment at `:1185` says the full category name is stored deliberately. Nothing validates `priority` against the DB column's `String(20)`.

#### `POST /api/tasks/from-diagnostic`

Separate endpoint (`backend/app/api/tasks.py:111-217`), **not** part of the pipeline. It bulk-creates caller-supplied tasks and validates that: the list is non-empty; every task shares one `engagement_id`; the engagement exists and passes `check_engagement_access`; any supplied `diagnostic_id`s are all the same and belong to that engagement; and any `assigned_to_user_ids` all resolve to real users. `created_by_user_id` is forced to the caller and `status` to `pending`; `task_type` is whatever the caller sets, so these tasks are not swept by the pipeline's `diagnostic_generated` cleanup.

---

### 9. Reporting

#### `report_html` and `report_url`

- `report_html` holds **only the `advisorReport` HTML string** returned by Step 3b — no wrapper, no CSS, no `<h1>` (the prompts forbid one). Written at `diagnostic_service.py:820-822` and rewritten from `ai_analysis["advisorReport"]` by `regenerate_report` (`:1287`), awaited from the endpoint at `backend/app/api/diagnostics.py:740`, which performs no AI call.
- `report_url` is declared (`models/diagnostic.py:46`, "S3/storage URL for generated PDF report") and exposed in the schemas, but **no code ever assigns it**. There is no object storage in this workflow; the PDF is rendered on demand.

#### The xhtml2pdf pipeline

`backend/app/services/report_service.py`, entry `ReportService.generate_pdf_report` (`:23-77`) → `_build_html_report` (`:79-236`) → `_html_to_pdf` (`:2344-2387`). The renderer is `xhtml2pdf`'s `pisa.pisaDocument`.

The HTML document is assembled at `:209-234` from a repeating page-header frame plus four blocks:

1. `_build_cover_page` (`:238-284`) — firm name, report title from `engagement.tool` (fallback `diagnostic_type`), business name, client name, lead advisor, date
2. `_build_advisor_report_section` (`:330-677`) — the LLM HTML, heavily post-processed
3. `_build_scoring_section` (`:679-738`) — "5. Scoring Detail" → "5a. Scored Responses" table + "Client Summary" narrative and roadmap table
4. `_build_all_responses_section` (`:983-1180`) — every stored answer as "5b. All Responses", sorted by the survey's page order

`@page { size: A4; margin: 25mm 20mm }` and the header frame come from `_get_css_styles` (`:1941-2216`).

Before rendering, `_build_html_report` reconciles the roadmap: if `ai_analysis.roadmap` is empty it is rebuilt from `module_scores.ranked`, and if both exist they are merged so score/rank/RAG come from the Python recomputation while `whyPriority`/`quickWins` come from the model (`:127-159`).

Markdown → HTML uses `markdown.markdown(text, extensions=["extra","sane_lists","nl2br","fenced_code"])` (`_markdown_to_html`, `:1791-1806`). It is applied to `summary` and `clientSummary`, but the advisor report is converted **only** when it contains no HTML tags (`:342-345`) — running Claude's HTML through the Markdown converter would escape its tags into visible text.

#### Gotcha: the xhtml2pdf negative-`availWidth` crash

xhtml2pdf computes column widths itself. When a table declares `table-layout: fixed` without a `colgroup`, or has more narrow columns than the frame can fit, its internal width arithmetic goes negative and the render aborts — taking the whole PDF with it. It also does not honour `word-wrap` / `overflow-wrap` / `word-break` inside table cells, so long unbroken cell text overflows instead of wrapping. Everything below exists because of those two facts, and **anyone editing report HTML will hit them**:

| Workaround | Where |
| --- | --- |
| Global safe default `table { table-layout: auto }` so content sizes the columns | `report_service.py:2102-2111` |
| Explicit `<colgroup>` + `table-layout: fixed` on the Pre-Listing Readiness Checklist (8% / 92%) | `:492-507` |
| Same for Diagnostic Triggers tables (35 / 20 / 8 / 37) | `:576-598` |
| Same for the Section 1 Roadmap Summary / Diagnostic Overview table (8 / 25 / 15 / 10 / 42) | `:637-658` |
| Catch-all: every remaining class-less LLM table is rewritten to `class="advisor-table"` with `table-layout: auto` | `:667-672` |
| `_pre_wrap_advisor_table_cells` injects `<br/>` into every `<td>` text node at 20 chars, skipping cells with block content | `:1907-1939` |
| `_wrap_cell_text` does the same for hand-built tables (default 35; called with 40 at `:765-767`, 50 at `:1032-1034`, 14 for the Section column at `:1036-1038`), breaking on spaces *and* hyphens and hard-splitting oversized tokens | `:1819-1873` |
| `_break_long_words_in_html` splits >30-char words in HTML text nodes without touching tags | `:1875-1905` |
| Targeted `<br/>` *removal* afterwards, where the pre-wrap over-wrapped a wide column | `:538-549`, `:600-611` |
| Two-pass render: on any first-pass exception, `_strip_markdown_tables` rebuilds every class-less table as a minimal `table-layout: auto` table and retries once | `:2295-2342`, `:2367-2387` |

Because the fallback only strips tables **without** a `class=` attribute (`:2336-2342`), the specific fixers all add `class="advisor-table"` first — so once a table has been "fixed" it is no longer eligible for the emergency retry. Order matters: `_pre_wrap_advisor_table_cells` (`:472`) must run before the per-table fixers so they can strip its `<br/>`s back out.

Other post-processing in `_build_advisor_report_section`: strips the redundant Section 5 response tables (`_strip_response_tables_from_summary`, `:2217-2293`), injects italic subtitles under known headings, inserts `<div class="page-break">` before every `<h2>` and before each module `<h3>` after the first, inserts a break before "External Professional Engagement Plan", and colours module headings and RAG lines red `#cc0000` / amber `#e67e00` / green `#2e7d32` by looking ahead 300 characters for a RAG keyword (`:410-466`).

Filename: `get_download_filename` (`:2389-2427`) → `TrinityAI-Sale-Ready-Report-Last_First.pdf`, `TrinityAI-Value-Builder-Report-...`, or `TrinityAI-Diagnostic-Report-...` for any other type.

---

### 10. The Word template merge engine

Separate from the PDF report, the diagnostics router exposes a second document path: a `{{placeholder}}` merge into `.docx` templates that are stored **in the database**, not on disk.

`document_templates` (`backend/app/models/document_template.py`, registered at `backend/app/models/__init__.py:18`) holds `file_name` (unique, indexed), `display_name`, `file_data` (`LargeBinary`), `file_size`, `uploaded_by_user_id`, `created_at`, `updated_at`.

`backend/app/services/document_template_service.py` (211 lines, singleton via `get_document_template_service()`):

- `PLACEHOLDER_PATTERN = re.compile(r'\{\{(\w+)\}\}')` (`:29`) — word characters only, so a placeholder with a dot, hyphen or space never matches.
- `python-docx` is imported behind `try/except ImportError` setting `DOCX_AVAILABLE` (`:13-17`), and the constructor raises `ImportError` with an install hint when it is False (`:31-36`). The import therefore succeeds even without the library — **the feature can be dark at runtime rather than failing at startup**, surfacing as a 500 on first template call.
- `list_available_templates` (`:38-44`) returns `[{name, display_name}]` ordered by display name.
- `get_template` (`:46-48`) looks up by exact `file_name`.
- `upload_template` (`:50-68`) derives `display_name` from the filename (`_`/`-` → spaces, each word `.capitalize()`) and stores the bytes.
- `delete_template` (`:70-78`) hard-deletes; returns False if absent.
- `extract_placeholders_from_bytes` (`:80-96`) opens the docx and regex-scans every paragraph — top level and inside every table cell — returning the sorted unique set.
- `generate_document` (`:98-200`) resolves each placeholder against `user_responses`, substituting `str(value)` (lists and dicts are stringified verbatim) and `[Not provided]` for a missing or None value, in both body paragraphs and table cells.

**Gotcha:** substitution operates on `paragraph.text` (the joined runs) and rewrites the paragraph as a single run copying only the first run's font name/size/bold/italic (`:150-163`). A placeholder Word split across runs still matches, but **all inline formatting in that paragraph collapses** to the first run's style. `display_name` uses `capitalize()`, so acronyms are lower-cased ("BBA" → "Bba").

Call sites in the router, all via `get_document_template_service()`: `GET /{diagnostic_id}/templates` at `diagnostics.py:948-980` (response model `DocumentTemplateResponse`, `backend/app/schemas/diagnostic.py:96`; service call at `:977`), `POST /{diagnostic_id}/generate-document` at `:1025`, `POST /templates/upload` at `:1106`, and `DELETE /templates/{template_name}` at `:1170`. Admin CRUD **does** exist — see the endpoint table below.

---

### 11. Endpoint table — `/api/diagnostics`

| Method | Path | Purpose | Roles / access |
| --- | --- | --- | --- |
| POST | `/create` (`:78`) | Create a draft diagnostic; ignores the (required) `questions` body field and loads `backend/files/diagnostic-surveyjs.json` | **Authenticated only — no engagement access check** |
| PATCH | `/{diagnostic_id}/responses` (`:131`) | Incremental autosave; merges into `user_responses`, drops keys whose value is `null`, optional free-text `status` | **Authenticated only — no access check** |
| POST | `/{diagnostic_id}/upload-file` (`:187`) | Store a supporting file under `backend/files/uploads/diagnostic/{id}/`, upload it to the LLM, create `Media`, attach to the diagnostic; returns the metadata blob the frontend writes into `user_responses` | **Authenticated only — existence check only** |
| DELETE | `/{diagnostic_id}/delete-file` (`:261`) | Remove one file from `user_responses[field_name]`, soft-delete its `Media`, detach from the diagnostic | **Authenticated only** |
| POST | `/{diagnostic_id}/submit` (`:423`) | 400 if `user_responses` empty; flip to `processing`, set `completed_by_user_id`, dispatch `_run_pipeline`; auto-tags "Diagnostic report by Admin" when submitted by admin/super_admin with an empty tag | **Authenticated only — no access check** |
| POST | `/{diagnostic_id}/cancel` (`:508`) | Writes status back to `draft` and clears `completed_at` (400 unless currently `processing`). **Stops nothing** — see *Cancel does not cancel* | **Authenticated only** — `:535-536` carries an explicit "add role / access checks here if needed" TODO |
| GET | `/{diagnostic_id}/status` (`:551`) | Lightweight poll: `{status, completed_at, error}` (`error` is hard-coded null); auto-fails runs stuck >60 min | Engagement access enforced |
| GET | `/{diagnostic_id}` (`:606`) | Full `DiagnosticDetail` incl. questions, responses, scoring, report | Engagement access + report filtering + role enrichment |
| GET | `/{diagnostic_id}/results` (`:644`) | `DiagnosticResults` (scores + `ai_analysis`); 400 unless `completed` | Engagement access + report filtering |
| GET | `/engagement/{engagement_id}` (`:686`) | List diagnostics for an engagement, newest first | Engagement access; each item filtered and enriched |
| POST | `/{diagnostic_id}/regenerate-report` (`:720`) | Re-copy `ai_analysis.advisorReport` into `report_html`; no AI call (`await service.regenerate_report(...)` at `:740`); 400 unless `completed` | **Authenticated only** |
| PATCH | `/{diagnostic_id}/tag` (`:758`) | Set/clear the advisor tag (form field `tag`) | `advisor`, `firm_advisor`, `admin`, `super_admin`, **and** engagement access unless admin/super_admin |
| GET | `/{diagnostic_id}/download` (`:814`) | Render and stream the PDF | Engagement access; `admin`/`firm_admin` must be creator **or** completer; requires `completed` unless `report_html`/`ai_analysis`/`completed_at` already exists |
| GET | `/{diagnostic_id}/templates` (`:948`) | List `.docx` templates | Engagement access |
| POST | `/{diagnostic_id}/generate-document` (`:983`) | Fill a template from `user_responses`, return the `.docx` named `{YYYY-MM-DD_HH-MM-SS}-{template display name}.docx` | Engagement access; 400 if no responses |
| POST | `/templates/upload` (`:1063`) | Upload a `.docx` template; `.docx` only, rejects duplicate filenames | `admin`, `firm_admin`, `super_admin` |
| DELETE | `/templates/{template_name}` (`:1147`) | Delete a template (hard delete) | `admin`, `firm_admin`, `super_admin` |

Access helpers: `_require_engagement_access` / `_require_diagnostic_access` (`diagnostics.py:46-75`) delegate to `check_engagement_access` (`backend/app/services/role_check.py`), which grants super_admin/admin everything; firm_admin their own firm's engagements; advisor/firm_advisor engagements where they are `primary_advisor_id`, in `secondary_advisor_ids`, or hold an `active`, non-deleted `AdvisorClient` link to `engagement.client_id`; and clients engagements where they are `client_id` or listed in `client_ids`. The full matrix is in *Authentication, Authorization & Impersonation*.

Report filtering: `filter_diagnostic_report_for_user` (`backend/app/utils/diagnostic_utils.py:125-157`) blanks `report_html` and pops `ai_analysis.advisorReport` for `admin`/`firm_admin` users who did not *complete* the diagnostic.

**Gotcha:** it mutates the live SQLAlchemy instance rather than a copy; it works only because these are read paths that never commit. It also computes `is_created_by_user` (`:142`) and never uses it, so being the creator does not grant visibility here — while `GET /download` (`diagnostics.py:848-852`) accepts creator *or* completer. The two rules disagree.

`enrich_diagnostic_with_roles` (`diagnostic_utils.py:88-122`) adds `created_by_user_role` / `completed_by_user_role` (non-null only for admin-family roles) to list and detail responses.

---

### 12. Frontend integration

Reducer: `frontend/src/store/slices/diagnosticReducer.ts`. The wider SPA structure is in *Frontend Architecture*.

**Submit** — `ToolSurvey.handleSubmit` (`frontend/src/components/engagement/tools/ToolSurvey.tsx:597-631`) first PATCHes all responses with `status: 'in_progress'`, toasts `"Submitting diagnostic for AI analysis... This may take 10-15 minutes"`, then dispatches `submitDiagnostic` (`diagnosticReducer.ts:202-236`). The endpoint returns immediately with `status: "processing"`. The `submitDiagnostic.fulfilled` reducer (`:459-483`) sets `isPolling = true` and appends `{id, engagementId, timestamp}` to the `processing_diagnostics` localStorage array. `fetchDiagnosticByEngagement.fulfilled` does the same when it loads a diagnostic already in `processing` (`:401-419`), which is how a page refresh re-arms tracking.

**Three independent pollers run**, all against `GET /{id}/status`:

| | Page-local (`ToolSurvey.tsx:140-260`) | Global (`frontend/src/hooks/useGlobalDiagnosticPolling.ts`) | Engagement page (`EngagementDetailPage.tsx:254-304`) |
| --- | --- | --- | --- |
| Mounted in | the diagnostic tab | `DashboardLayout.tsx:17` — every dashboard page | the engagement detail page |
| Trigger | Redux `isPolling && status === 'processing'` | `processing_diagnostics` entries younger than 30 min | any locally-listed diagnostic with `status === 'processing'` |
| Interval | 10 s (`:228-238`), plus an immediate check on effect entry (`:214-215`) and on `visibilitychange` (`:198-208`) to defeat background-tab throttling | 30 s (`useGlobalDiagnosticPolling.ts:137`); no immediate check — the first tick is 30 s after mount | 10 s (`:301`) |
| On terminal status | the thunk also fetches `GET /{id}` in an isolated try/catch so a failed detail fetch cannot swallow the terminal status (`diagnosticReducer.ts:293-318`) | same thunk | plain `fetch`, then re-fetches the list |
| On completed | `setDiagnosticCompleted()` + `stopPolling()`, remove from localStorage, toast `"✅ Diagnostic processing completed! PDF report is ready for download."` (10 s) | remove from localStorage, toast `"✅ Diagnostic Processing Completed!"` with a **View Report** action navigating to `/dashboard/engagements/{engagementId}`, then `fetchEngagements({})` | updates the row's status, no toast |
| On failed | `stopPolling()`, toast `"❌ Diagnostic processing failed. Please try submitting again."` | toast `"❌ Diagnostic Processing Failed"` | updates the row's status |
| Safety stop | 90-minute `setTimeout` → warning toast (`:241-246`), a 30-min buffer over the backend's 60-min auto-fail | 30-minute age filter on localStorage entries | none |
| Errors | logged, polling continues | logged, polling continues | logged, polling continues |

`notifiedDiagnosticsRef` (a `Set`) makes the global toast fire at most once per diagnostic per page load. On the diagnostic tab the page-local and global pollers both fire, so a completion can raise two toasts.

Because the `/status` watchdog only runs when a request reaches it, these pollers are also the mechanism that eventually fails a stranded run. Close every tab and a run killed by a restart sits at `processing` indefinitely.

**Cancel** — `cancelDiagnosticProcessing` (`diagnosticReducer.ts:238-266`) POSTs `/cancel`; its fulfilled reducer clears `isPolling` and removes the localStorage entry. `ToolSurvey` guards it behind a confirm dialog. The UI implies the run stops; it does not.

**Results and download** — when `status === 'completed'` but `reportHtml` and `aiAnalysis.advisorReport` are both empty, a guard effect re-fetches the diagnostic (`ToolSurvey.tsx:269-278`); a matching guard in `fetchDiagnosticByEngagement.fulfilled` (`:388-397`) stops a stale `processing` response from clobbering a known-completed state. The download banner is gated on `hasExistingReport && status !== 'processing' && canAdminSeeThisReport` (`ToolSurvey.tsx:90-111`), where the last term requires an admin/firm_admin to be the `completed_by_user_id`. Download hits `GET /{id}/download` (`:795`) and saves the blob; the same endpoint is also called from `EngagementDetailPage.tsx:624` and `UserDetailPage.tsx:161`.

Diagnostic creation from the UI happens only in `RetakeDiagnosticCard.tsx:45-56`, which POSTs `/create` with `questions: {}`. `/results` and `/regenerate-report` are not called from anywhere in `frontend/src`.

`frontend/GLOBAL_DIAGNOSTIC_POLLING.md` documents a 5-second interval and a 20-minute safety timeout; the code uses 30 s globally, 10 s page-local and engagement-page, and 90 min. Trust the code.

---

### 13. AI call configuration and timing

A full run is minutes to tens of minutes; Step 3a dominates. The Claude-call settings the pipeline runs under:

| Setting | Value | Where |
| --- | --- | --- |
| Model | `ANTHROPIC_MODEL`, default `claude-opus-4-6` | `backend/app/config.py:48` |
| Max output tokens | `ANTHROPIC_MAX_TOKENS`, default `128000` | `config.py:54` |
| Temperature | `ANTHROPIC_TEMPERATURE`, default `0.5` — unused here (adaptive thinking forces 1.0) | `config.py:52`, `claude_service.py:286-291` |
| Anthropic read timeout | `ANTHROPIC_TIMEOUT`, default **1800.0 s (30 min)**; connect/write/pool 10 s | `config.py:53`, `claude_service.py:33-43` |
| SDK retries | `max_retries=1` | `claude_service.py:42` |
| Submit response headers | `Connection: keep-alive`, `Keep-Alive: timeout=1800, max=100` | `diagnostics.py:469-470` |
| Stuck-run watchdog | 3600 s (60 min), inside `GET /{id}/status` | `diagnostics.py:583` |
| Frontend safety stop | 90 min | `ToolSurvey.tsx:246` |

The submit call itself returns in well under a second; the keep-alive headers are vestigial, left from when processing was synchronous. What has to survive a run is the **server process**, not the HTTP round trip — the pipeline continues on the API worker after the response is flushed. Hosting consequences (worker recycling, replicas, restarts stranding in-flight rows, and how to clear them) are covered in *Operations, Diagnostics & Troubleshooting*.

The one semantic constraint worth repeating here: the 1800 s read timeout only helps if nothing between the app and Anthropic closes the outbound connection first, and a single Step 3a `await` can occupy most of that window.

---

### 14. Debt in this area

- `celery_task_id` (`models/diagnostic.py:61`) is a live column that no code reads or writes.
- `backend/app/tasks/diagnostic_tasks.py` imports `celery` at module scope (`:14-18`) and `backend/app/api/diagnostics.py:500` imports `_run_pipeline` from it, so **the `celery` package must be installed for the API to serve a diagnostic submit** even though no broker or worker runs. Removing the dependency requires moving `_run_pipeline` out of that module first.
- `cleanup_stale_tasks` (`diagnostic_tasks.py:34-50`) would reset `processing` rows to `draft`, but it is bound to a worker-startup signal the API process never emits. Stranded rows therefore never self-heal; they must be cleared through `POST /{id}/cancel`, a `/status` poll that trips the watchdog, or SQL.
- `except SoftTimeLimitExceeded` (`:217-231`) is unreachable for the same reason.
- Dead in the diagnostic path: `backend/files/scoring_map.json`, `ScoringService.build_scored_rows`, `strip_excluded_fields`, `_map_category_to_module`, `ClaudeService.generate_advice`, `advice_prompt_diagnostic.md`, `frontend/src/questions/diagnostic-survey.json`, and every top-level prompt file shadowed by a type-specific one.

---

## 11. AI Layer — Claude Integration & Prompt System

Every LLM call in the platform goes through one file: `backend/app/services/claude_service.py` (947 lines). `AsyncAnthropic` is constructed in exactly one place (`claude_service.py:34`) — there is no second client, no router, no provider switch executed at runtime. Prompts live as Markdown files on disk under `backend/files/prompts/` and are read by five different loaders.

This section is the canonical reference for the client and its call surface: client construction, retry budget, timeouts, temperature resolution, model defaulting, JSON recovery, and the prompt registry. *AI Tools — BBA, Strategy Workbook & Strategic Business Plan* and *AI Tools — Roles Matrix, PD & Scorecard* describe per-tool workflows and defer here for all service mechanics. Pipeline orchestration — which step calls what, in what order — is in *Diagnostic Engine*; runtime dispatch and what to check when a run hangs is in *Operations, Diagnostics & Troubleshooting*.

### Service topology

| Layer | File | Role |
|---|---|---|
| Client + API surface | `backend/app/services/claude_service.py` | The only place `AsyncAnthropic` is constructed and called |
| Retained OpenAI service | `backend/app/services/openai_service.py` (910 lines) | Imported by no module; kept for rollback (see *Provider abstraction — reality check* below; the `openai` pin itself is in *Technology Stack & Dependencies*) |
| Settings | `backend/app/config.py:40-55` | `OPENAI_*`, `ANTHROPIC_*`, `LLM_PROVIDER` |
| Generic prompt/data loader | `backend/app/utils/file_loader.py` | `load_prompt`, `load_prompt_for_type`, `load_json`, `load_scoring_map_for_type`, `load_diagnostic_questions`, `load_task_library` |
| Per-tool prompt loaders | `load_bba_prompt` (`bba_conversation_engine.py:20-37`), `load_roles_matrix_prompt` (`roles_matrix_engine.py:17-36`), `load_pd_scorecard_prompt` (`pd_scorecard_engine.py:18-37`), `load_sbp_prompt` (`sbp_conversation_engine.py:28-35`) | Four hand-rolled loaders that bypass `FileLoader` entirely |

Two import styles coexist and both reach the same class-level client:

```python
from app.services.claude_service import claude_service   # module singleton, claude_service.py:947
from app.services.claude_service import ClaudeService    # then ClaudeService() per engine
```

`ClaudeService()` is cheap — `__init__` only reads `settings.ANTHROPIC_TEMPERATURE` (`claude_service.py:25-27`). The expensive object (the HTTP client) is a class attribute (`:23`), so every instance shares it.

### Client lifecycle

```python
# claude_service.py:29-46
    @classmethod
    def initialize_client(cls):
        """Initialize the Anthropic client once at application startup"""
        if cls._client is None:
            timeout_seconds = settings.ANTHROPIC_TIMEOUT or 600.0
            cls._client = AsyncAnthropic(
                api_key=settings.ANTHROPIC_API_KEY,
                timeout=httpx.Timeout(
                    connect=10.0,
                    read=timeout_seconds,
                    write=10.0,
                    pool=10.0,
                ),
                max_retries=1,
            )
            timeout_str = f"{timeout_seconds} seconds ({timeout_seconds / 60:.1f} minutes)"
            logger.info(f"Claude client initialized with timeout: {timeout_str}")
        return cls._client
```

- `initialize_client()` is idempotent by the `is None` guard (`:32`) — calling it twice is a no-op unless `_client` was first set back to `None`.
- The timeout is asymmetric: 10 s to connect, write and acquire a pool slot, but `ANTHROPIC_TIMEOUT` (default **1800 s**, `config.py:53`) to read the response body. Diagnostic scoring and report calls routinely run for minutes.
- `max_retries=1` (`:42`) means the Anthropic SDK makes at most one automatic retry on top of the first attempt. There is no other retry budget inside the service.
- The `client` property (`:48-56`) raises `RuntimeError("Claude client not initialized…")` rather than lazily constructing one — a deliberate fail-loud.
- Called once at app boot: `backend/app/main.py:118-133` (`@app.on_event("startup")`, call at `:125`).

**The second initialisation site.** The background diagnostic pipeline discards and rebuilds the client on entry:

```python
# backend/app/tasks/diagnostic_tasks.py:82-85
    # Force re-create the AsyncAnthropic client on THIS event loop.
    # The class-level _client may be stale from a previous event loop.
    ClaudeService._client = None
    ClaudeService.initialize_client()
```

**Gotcha:** do not delete those two lines because "the client is already initialised at startup". `AsyncAnthropic` wraps an `httpx.AsyncClient` whose connection pool and anyio synchronisation primitives are bound to the event loop that was running when it was constructed. `_run_pipeline` is written to be loop-agnostic. Today it is dispatched via FastAPI `BackgroundTasks` (`backend/app/api/diagnostics.py:499-501`), which shares the app's loop, so the reset is currently redundant — but any future dispatch that gives the pipeline its own loop (a script, a management command, an `asyncio.run` inside a thread) hands it a client attached to a loop that no longer exists. The failure mode is not a clean error: the first `await self.client.beta.messages.create(...)` raises `RuntimeError: Event loop is closed` (or "bound to a different event loop") from inside httpx/anyio, the pipeline aborts mid-run, and the diagnostic is left in `processing` with a stack trace pointing at httpx rather than at the missing reset.

**Gotcha (the flip side):** the reset leaks. The discarded `AsyncAnthropic` is never `.close()`d, so its connection pool is dropped on the floor once per pipeline run, and any coroutine that grabbed `ClaudeService._client` a moment earlier keeps using the old object while new callers get the new one. Under the current single-loop dispatch this is churn, not corruption, but it is why a long-lived process shows a slowly growing socket count.

### `generate_completion`

`claude_service.py:178-441`. The single entry point; `generate_json_completion` and all five wrappers funnel into it.

| Parameter | Type | Meaning |
|---|---|---|
| `messages` | `List[Dict[str,str]]` | OpenAI-shaped `{"role","content"}`; `system`/`developer` roles are hoisted out |
| `temperature` | `Optional[float]` | Overrides `settings.ANTHROPIC_TEMPERATURE` |
| `json_mode` | `bool` | Appends the hard "raw JSON only" instruction to the system prompt |
| `reasoning_effort` | `Optional[str]` | `"low"`/`"medium"`/`"high"` → adaptive thinking |
| `file_ids` | `Optional[List[str]]` | Claude Files API ids attached as `document` blocks |
| `tools` | `Optional[List[Dict]]` | `code_interpreter` is translated; anything else passes through |
| `model` | `Optional[str]` | Overrides `settings.ANTHROPIC_MODEL` |
| `max_output_tokens` | `Optional[int]` | Overrides `settings.ANTHROPIC_MAX_TOKENS` |
| `system_blocks` | `Optional[List[Dict]]` | Caller-built cached system blocks; bypasses message-derived system extraction |

**Resolution order**

| Value | Order | Code |
|---|---|---|
| Model | explicit `model` arg → `settings.ANTHROPIC_MODEL` | `:209` |
| Max tokens | explicit `max_output_tokens` → `settings.ANTHROPIC_MAX_TOKENS` (128 000) | `:254` |
| Temperature | explicit `temperature` → `self.temperature`, then overridden by the thinking branch | `:255`, `:286-291` |

No caller ever reaches the API with a model the service chose for it: `use_model = model or settings.ANTHROPIC_MODEL` is the whole rule, and the resolved value is what comes back in the response dict's `model` key.

**The temperature special case** (`:286-291`):

```python
            if reasoning_effort and reasoning_effort.lower() in ("low", "medium", "high"):
                params["thinking"] = {"type": "adaptive"}
                params["output_config"] = {"effort": reasoning_effort.lower()}
                params["temperature"] = 1.0
            else:
                params["temperature"] = temp
```

Temperature is forced to `1.0` whenever `reasoning_effort` is one of the three recognised strings — the API rejects a non-1.0 temperature alongside extended thinking. Any other truthy value (`"none"`, `"minimal"`, a typo) falls through to the `else` branch and no thinking is requested. **Gotcha:** callers that pass a temperature *and* a `reasoning_effort` get 1.0 and their temperature is dead. Confirmed dead-temperature call sites: `process_scoring` (`temperature=0.3`, `:721-727`), `generate_report` (`temperature=0.3`, `:799-803`), and chat (`temperature=0.7` with `reasoning_effort="low"`, `chat_service.py:267-273`). Where no `reasoning_effort` is passed the temperature is honoured — e.g. BBA context-capture extraction at `temperature=0.2` (`bba_conversation_engine.py:775-781`).

**Message conversion** (`_convert_messages_to_claude_format`, `:93-174`)

- `system` and `developer` messages are pulled out in order and joined with `\n\n` into one string (`:122-124`, `:173`).
- All other messages pass through with their role and string content.
- File blocks are attached **only to the last message, and only if that last message has `role == "user"`** (`:127-131`). A trailing assistant message silently drops every attachment.
- Block order inside that message: `document` blocks → `container_upload` blocks → the `text` block (`:137-160`).

**Attachment handling** — two routes, matching the description in `docs/ROLES_MATRIX_TOOL.md` ("AI calls" section):

| Input | Block emitted | Where |
|---|---|---|
| PDFs (anything the caller puts in `file_ids`) | `{"type":"document","source":{"type":"file","file_id":…}}` | `:138-146` |
| CSV/XLSX/TXT and friends | `{"type":"container_upload","file_id":…}` plus a `code_execution_20250825` tool | `:148-154`, `:216-238` |

Callers pass code-execution files inside an OpenAI-shaped tool dict, which `generate_completion` rewrites (`:221-230`):

```python
[{"type": "code_interpreter", "container": {"type": "auto", "file_ids": ci_file_ids}}]
# → {"type": "code_execution_20250825", "name": "code_execution"}
```

The split by extension is done by each caller, not by the service. Five near-identical copies exist and they disagree:

| Caller | Code | PDF | Code Interpreter | Third bucket / unknown |
|---|---|---|---|---|
| Roles matrix | `roles_matrix_engine.py:52-91` | `pdf` | `csv,txt,text,md,markdown,json,xml,yaml,yml,xlsx,xls,doc,docx` | unknown → Code Interpreter (warn) |
| BBA | `bba_conversation_engine.py:111-144` | `pdf` | same minus `doc,docx` | unknown → Code Interpreter (warn) |
| SBP | `sbp_conversation_engine.py:62-89` | `pdf` | same minus `doc,docx` | DOCX/PPTX/images text-extracted locally (python-docx/python-pptx) and injected into the user prompt (`:93-…`, `:196-209`) |
| Strategy Workbook | `strategy_workbook_service.py:189-218`, `:379-403` | `pdf` | same minus `doc,docx` | images/zip dropped; unknown → Code Interpreter (warn) |
| Diagnostic pipeline | `diagnostic_service.py:438-457` | `pdf` | same minus `doc,docx` | images/zip dropped with a log line; **anything else silently vanishes** |

**Gotcha:** the diagnostic pipeline's split is the only one with no catch-all. A `.docx` upload is not a PDF, not in `ci_ext`, and not in `image_or_archive_ext`, so it lands in none of the three lists and is never attached — and never logged as filtered. The scoring call proceeds with a document the model never saw.

**System-prompt caching.** Two mutually exclusive paths (`:263-283`):

- **`system_blocks` supplied** — the caller has already built a list of `{"type":"text","text":…,"cache_control":{"type":"ephemeral"}}` blocks. In `json_mode` the JSON instruction is appended to the **last** block's text (`:267-270`), which changes that block's bytes and therefore its cache key; earlier blocks still hit. The BBA, roles-matrix and PD engines use exactly two blocks — base system prompt, then step prompt — so the base prompt keeps its cache entry across every step of a session (`bba_conversation_engine.py:180-183`, `roles_matrix_engine.py:137-140` and `:223-226`, `pd_scorecard_engine.py:140-143`, `:229-232`, `:308-311`). BBA appends a third block carrying the Value Builder taxonomy when the engagement is a Value Builder (`bba_conversation_engine.py:102-109`).
- **No `system_blocks`** — the joined system string from the messages is wrapped in a single ephemeral-cached block (`:274-283`).

**Gotcha:** when `system_blocks` is passed, the system text extracted from `messages` is computed (`:241-245`) and then thrown away. A caller that passes both a `{"role":"system"}` message and `system_blocks` loses the message silently.

Beta headers are always set (`:297-306`): `["prompt-caching-2024-07-31"]`, or `["files-api-2025-04-14", "prompt-caching-2024-07-31"]` when any file is attached. All calls go through `client.beta.messages.create` (`:307`).

**Response assembly** (`:338-402`)

1. Every `text` block in `response.content` is collected and joined with `\n` (`:338-349`) — deliberately, because with code execution Claude often emits preamble text, runs code, then emits the JSON in a later text block.
2. If the result is still empty, `bash_code_execution_tool_result` blocks are mined for text (`:351-367`).
3. Usage is read off `response.usage` (`:369-381`): `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. `tokens_used = input + output` — cache-read tokens are counted at full input price in that number, and cache stats are logged but never returned or persisted.
4. An empty `content` logs a warning with `stop_reason`, `tokens_used` and `response_id` (`:383-390`) but is returned as a success.
5. Return shape, identical to the retained OpenAI service (`:393-402`):

```python
{"content", "model", "tokens_used", "prompt_tokens", "completion_tokens",
 "finish_reason", "response_id", "output_summary"}
```

`output_summary` is hard-coded to `[]` under Claude (`:401`); `strategy_workbook_service.py:283`, `:333` and `:454` still print it in error messages.

### Error handling

Two nested `try` blocks with different jobs.

**Inner** (`:300-336`) wraps only the API call and exists for observability:

| Situation | Behaviour |
|---|---|
| Success | `logger.info("[Claude API] API call succeeded in {elapsed:.2f} seconds")` (`:310`) |
| Any exception | logs elapsed seconds, exception type, message, full traceback, then re-raises unchanged (`:312-336`) |
| `elapsed >= 600` | extra "likely a timeout" line (`:321-322`) — **stale**: the read timeout defaults to 1800 s, so this now fires on slow failures that are not timeouts |
| `status_code == 529` | logs "API overloaded (529). SDK will retry automatically." |
| `status_code == 429` | logs "Rate limit exceeded (429). SDK will retry automatically." |
| `status_code >= 500` | logs "Server error. SDK will retry automatically." |

**Retries are entirely the SDK's.** There is no retry loop in `claude_service.py`. `max_retries=1` (`:42`) means the SDK retries 429/5xx/529/connection errors once. By the time the `except` block runs, that retry has already been spent — the "SDK will retry automatically" lines describe something that already happened. Callers needing more attempts implement their own loops:

| Caller | Code | Policy |
|---|---|---|
| Diagnostic scoring | `diagnostic_service.py:512-600` | `max_retries = 1`; retries only when the error string looks like file-not-found/404, after re-uploading every attached file to the Files API |
| SBP engine | `sbp_conversation_engine.py:230-265` | up to 3 attempts when files are attached (1 otherwise), 2 s then 4 s sleep, and only when `"500"` appears in the error string |

**Outer** (`:404-441`) converts the exception into a plain `Exception` with a human message, matching on the string of the error:

| Match | Raised message |
|---|---|
| `"timeout"` / `"timed out"` (`:413`) | `Claude API request timed out after {ANTHROPIC_TIMEOUT} seconds…` |
| `"api key"` / `"authentication"` (`:420`) | `Claude API authentication failed. Please check your ANTHROPIC_API_KEY…` |
| `"overloaded"` / `"529"` (`:427`) | `Claude API is overloaded after all retries…` |
| `"429"` / `"rate limit"` (`:434`) | `Claude API rate limit exceeded after all retries…` |
| anything else (`:441`) | `Claude Messages API error: {msg}` |

**Gotcha:** the typed `anthropic.APIStatusError` subclasses are flattened into bare `Exception`, so no caller can branch on error type — only on substrings, which is exactly what the two retry loops above are forced to do. And when `ANTHROPIC_TIMEOUT` is unset the timeout message interpolates `None` while the real read timeout is 600 s.

How errors surface: chat swallows them and stores an apology string with `response_data={"error": …}` (`chat_service.py:283-286`); the diagnostic pipeline lets them propagate and marks the diagnostic failed; the tool engines log with `exc_info=True` and re-raise to the API layer.

### `generate_json_completion` — the recovery ladder

`claude_service.py:498-648`. Calls `generate_completion(json_mode=True)` with `model or settings.ANTHROPIC_MODEL` (`:521`), then works down a ladder until something parses.

| # | Attempt | Code | Handles |
|---|---|---|---|
| 1 | `json.loads(content)` | `:531-535` | The happy path |
| 2 | Strip a ```` ```json ```` or bare ```` ``` ```` fence, parse again | `:540-553` | Claude wrapping output in Markdown despite instructions |
| 3 | `JSONDecoder().raw_decode(content)` | `:556-561` | Valid JSON followed by trailing commentary |
| 4 | Find the first `{` or `[`, `raw_decode` from there | `:564-577` | Preamble text before the JSON |
| 5 | `_repair_json()` then parse | `:583-588` | see below |
| 6 | Follow-up turn: original messages + the bad assistant reply + "Output ONLY the raw JSON object", at `temperature=0.0` | `:608-640` | Everything else |
| — | Give up | `:641-646` | `Exception("Failed to parse JSON response after repair attempts: … line N, col M")` |

`_repair_json` (`:445-487`) is itself layered: strip fences → `raw_decode` → the `json_repair` library (`repair_json`, pinned as `json-repair==0.30.3` in `backend/requirements.txt:41`, and re-parsed before it is trusted) → regex structural fixes for trailing commas and missing separators between adjacent objects/arrays.

`_coerce_parsed_to_dict` (`:489-496`) unwraps the case where the model returned a top-level array containing one object; it is applied at every rung.

**Why this exists:** the platform asks for very large structured outputs (a scored multi-hundred-item questionnaire, a 14-section plan, a full roles matrix) from a model that also runs code and narrates. Requiring a clean first-token `{` at those sizes fails often enough that every rung below #1 earns its keep. The `json_instruction` bolted onto the system prompt (`:247-251`) is the first line of defence.

**Gotcha:** rung 6 does not forward `system_blocks` or `reasoning_effort` (`:619-627`). For the BBA, roles-matrix and PD engines — which pass their entire system prompt as `system_blocks` — the retry runs with no system prompt at all, just the bare JSON instruction. It will usually produce parseable JSON, but of a shape nobody specified. If a step reaches rung 6 routinely, fix the prompt or lower `max_output_tokens`; do not rely on the retry.

**When it still fails:** the raised message carries the decode error's line and column, and the log immediately above it holds either three lines of surrounding context or the first 1000 characters of the payload (`:596-606`). The usual root cause is truncation — check the `stop_reason` logged at `:381`; `max_tokens` means the JSON was cut off mid-string and no repair can help. Raise `max_output_tokens` for that call site rather than touching the ladder.

### Convenience wrappers

| Method | Line | Under the hood | Called by |
|---|---|---|---|
| `generate_summary` | `:652-668` | `generate_completion`, `reasoning_effort` default `"medium"` | `diagnostic_service.py:395` — pipeline Step 2, with `diagnostic_summary.md` |
| `process_scoring` | `:670-736` | `generate_json_completion`, `temperature=0.3`, `reasoning_effort` default `"low"` | `diagnostic_service.py:523` — pipeline Step 3a; the only wrapper that takes files and tools |
| `generate_report` | `:738-812` | `generate_json_completion`, `temperature=0.3` | `diagnostic_service.py:650` — pipeline Step 3b; substitutes `{MODULE_TASK_LIBRARY}` (`:755-758`) |
| `generate_advice` | `:814-830` | `generate_completion` | **nobody** — no call site in `backend/app`; dead code superseded by the Part 1 / Part 2 split |
| `generate_tasks` | `:832-895` | `generate_json_completion`, `reasoning_effort` default `"medium"` | `diagnostic_service.py:1107` — 30-day task generation; `initial_task_prompt.md` is appended to a large inline template (`:844-866`) |
| `upload_file` | `:899-943` | `client.beta.files.upload` | `diagnostic_service.py:486` and `:570`, `file_service.py:148`, `api/pd_scorecard.py:278`, `api/roles_matrix.py:230`, `api/strategic_business_plan.py:241`, `api/upload_poc.py:280` |

Every other consumer (BBA, SBP, roles matrix, PD scorecard, strategy workbook, chat) calls `generate_completion` / `generate_json_completion` directly.

**Gotcha:** `upload_file` returns `None` on any failure and only logs it (`:941-943`) — it never raises. Callers that do not check the return value attach an empty file list and get a confidently wrong answer from a model that saw no documents.

`_is_image_file_id` (`:85-91`) is dead code that always returns `False`.

### Model and token configuration

Declared in `backend/app/config.py`. The deployment-side view of these variables — where they are set, which are required at boot — is in *Environments, Configuration & Deployment*; the table below maps each one to the code that reads it.

| Setting | Default | Used by |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required, no default)* | `initialize_client` (`claude_service.py:35`) |
| `ANTHROPIC_MODEL` | `claude-opus-4-6` (`config.py:48`) | Default model for every call; passed explicitly in `generate_summary`, `generate_advice`, `generate_tasks`, `generate_json_completion`, and the workbook precheck |
| `ANTHROPIC_TEMPERATURE` | `0.5` (`:52`) | `ClaudeService.__init__`; validated to 0.0–1.0 (`config.py:89-94`) |
| `ANTHROPIC_TIMEOUT` | `1800.0` (`:53`) | httpx read timeout; `or 600.0` when unset |
| `ANTHROPIC_MAX_TOKENS` | `128000` (`:54`) | Default `max_tokens` when a caller passes none |
| `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP1` | `claude-sonnet-4-6` (`:49`) | Strategy Workbook extraction step (`strategy_workbook_service.py:256`) |
| `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP2` | `claude-sonnet-4-6` (`:50`) | Strategy Workbook normalisation step (`strategy_workbook_service.py:304`) |
| `ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2` | `None` (`:51`) | Explicit override for step 2's output cap (`strategy_workbook_service.py:305-313`) |
| `LLM_PROVIDER` | `"claude"` (`:55`) | Read nowhere in application code — see *Provider abstraction — reality check* below |
| `OPENAI_API_KEY` / `OPENAI_MODEL` / `OPENAI_TEMPERATURE` / `OPENAI_TIMEOUT` | `None` / `gpt-4o` / `1.0` / `None` (`:41-44`) | Only `openai_service.py`, which nothing imports; `OPENAI_TEMPERATURE` validated to 0.0–2.0 (`:82-87`) |

**Why the Strategy Workbook has its own knobs.** It is the only two-model pipeline. Step 1 reads the uploaded documents (PDFs as document blocks plus a Code Interpreter container) and writes free-form extracted findings; Step 2 never sees the documents — it only reshapes step 1's text into the Excel-workbook JSON schema. Neither job needs Opus, so both default to Sonnet, and step 1 is pinned at `max_output_tokens=32000` (`strategy_workbook_service.py:273`). Step 2's cap is the interesting one:

```python
# strategy_workbook_service.py:304-313
        step2_model = settings.ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP2 or settings.ANTHROPIC_MODEL
        configured_step2_max_tokens = settings.ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2
        step2_max_output_tokens = configured_step2_max_tokens or settings.ANTHROPIC_MAX_TOKENS
        if configured_step2_max_tokens is None:
            if "haiku" in step2_model.lower():
                step2_max_output_tokens = min(step2_max_output_tokens, 8192)
            elif "sonnet" in step2_model.lower():
                step2_max_output_tokens = min(step2_max_output_tokens, 16000)
```

The global default of 128 000 is an Opus number; requesting it from a Sonnet or Haiku model is an API error. Rather than teach `generate_completion` about per-model ceilings, the workbook clamps by substring match on the model name and gives operators `ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2` as the escape hatch. **Gotcha:** the clamp is local to this one service. Any other call site that switches to a non-Opus model without passing `max_output_tokens` sends `max_tokens=128000` and is rejected.

Per-call output caps set by callers (none of them configurable):

| Call site | `max_output_tokens` | `reasoning_effort` | Model |
|---|---|---|---|
| Chat reply (`chat_service.py:267-273`) | 1000 | `low` | `settings.ANTHROPIC_MODEL` (the `model` arg defaults to `None`, `chat_service.py:217`) |
| BBA steps 3/4/5/6/7 (`bba_conversation_engine.py:259,341,418,506,616`) | 16384 / 12288 / 8192 / 32768 / 24576 | `medium`, then `low` for 4–7 | default |
| BBA executive summary (`:697-698`) | 8192 | `low` | default |
| BBA context capture (`:775-781`) | 4096 | none (`temperature=0.2` applies) | default |
| BBA task planner (`bba_task_planner_service.py:214-216`) | **unset → 128000** | none | default |
| BBA presentation (`bba_presentation_service.py:78-80`) | **unset → 128000** | none | default |
| Roles matrix extract + build (`roles_matrix_engine.py:182,249`) | 16384 | `medium` | default |
| PD scorecard, all three steps (`pd_scorecard_engine.py:184,267,343`) | 16384 | `medium` | default |
| Strategy Workbook step 1 / step 2 (`strategy_workbook_service.py:273,323`) | 32000 / clamped | none / `low` | Sonnet by default |
| Strategy Workbook precheck (`:438-444`) | 2000 | `low` | `settings.ANTHROPIC_MODEL` explicitly |
| SBP section/revision/themes calls (`sbp_conversation_engine.py:240-244`) | **unset → 128000** | none | default |
| SBP presentation (`sbp_presentation_service.py:61-66`) | 4096 (`max_tokens`) | n/a — calls the SDK directly | hard-coded `claude-sonnet-4-20250514` |
| Diagnostic pipeline (summary / scoring / report / tasks) | **unset → 128000** | medium / low / low / medium | default |

**Gotcha:** `sbp_presentation_service.py:61-66` reaches past the service and calls `self.claude_service.client.messages.create(...)` on the **non-beta** endpoint with a hard-coded model. It gets no prompt caching, no JSON recovery ladder, no token logging, and no `ANTHROPIC_MODEL` respect. It hand-rolls a single regex fence-strip and falls back to a one-slide stub if that fails (`:67-85`).

**Gotcha:** the BBA presentation and task-planner services, and every SBP engine call, pass no `max_output_tokens`, so they request 128 000 output tokens on the default Opus model. Switch `ANTHROPIC_MODEL` to a Sonnet or Haiku id and those four call sites start failing at the API.

### Prompt registry

Everything under `backend/files/prompts/`. Paths are repo-relative. This is the complete tree.

**Root — chat and diagnostic**

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/system_prompt.md` | `chat_service.py:391` in `_build_system_prompt` (`:378`) | Base "Trinity" chat persona: answer first, at most one follow-up, 2–4 sentences, plain ASCII only |
| `backend/files/prompts/category_prompt_financial.md` | `chat_service.py:433` / `:464` via `_get_category_prompt` | Finance-mode chat scope |
| `backend/files/prompts/category_prompt_legal-licensing.md` | same | Legal/licensing chat scope |
| `backend/files/prompts/category_prompt_operations.md` | same | Operations chat scope |
| `backend/files/prompts/category_prompt_human-resources.md` | same | People/HR chat scope |
| `backend/files/prompts/category_prompt_customers.md` | same | Customer/revenue chat scope |
| `backend/files/prompts/category_prompt_tax.md` | same | Tax chat scope |
| `backend/files/prompts/category_prompt_due-diligence.md` | same | Due-diligence chat scope |
| `backend/files/prompts/category_prompt_brand-ip-intangibles.md` | same | Brand/IP chat scope |
| `backend/files/prompts/category_prompt_diagnostic.md` | same, when `conversation.category == "diagnostic"` | Conversational question-by-question diagnostic |
| `backend/files/prompts/diagnostic_summary.md` | `diagnostic_service.py:394` → `generate_summary` | Markdown summary of the owner's responses (pipeline Step 2) |
| `backend/files/prompts/scoring_prompt_scoring.md` | `load_prompt_for_type("scoring_prompt_scoring", …)` **fallback only** | Generic Part 1 scoring/validation prompt |
| `backend/files/prompts/scoring_prompt_report.md` | `load_prompt_for_type("scoring_prompt_report", …)` **fallback only** | Generic Part 2 report prompt |
| `backend/files/prompts/initial_task_prompt.md` | `diagnostic_service.py:1104` → `generate_tasks` | 30-day data-grounded task list rules |
| `backend/files/prompts/scoring_prompt.md` | **no code reference** | Pre-split monolithic scoring+report prompt |
| `backend/files/prompts/advice_prompt_diagnostic.md` | **no code reference** | Pre-split roadmap + advisor-report prompt |
| `backend/files/prompts/admin_mode.md` | **no code reference** | "admin-mode:" prefix behaviour for chat |
| `backend/files/prompts/diagnostic_json_extract.md` | **no code reference** | Structured JSON extraction from a Q&A transcript |
| `backend/files/prompts/diagnostic_qa_confirmation.md` | **no code reference** | Short per-answer confirmations in conversational diagnostics |

`_get_category_prompt` (`chat_service.py:420-475`) tries `category_prompt_{category}.md`, then a normalised alias (`hr → human-resources`, `dd → due-diligence`, `legal → legal-licensing`, …), then falls back to a short inline string. There is no `category_prompt_general.md` on disk, so the `general` category always uses the inline fallback.

**Sale-Ready / Value Builder — the scoring trio per diagnostic type**

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/sale-ready/scoring_prompt_scoring.md` | `load_prompt_for_type("scoring_prompt_scoring", 'sale_ready')` from `diagnostic_service.py:469` | Part 1: map answers via SCORING_MAP, compute module averages, extract `fileInsights` |
| `backend/files/prompts/sale-ready/scoring_prompt_report.md` | `diagnostic_service.py:648` | Part 2: `clientSummary`, roadmap, advisor report; carries the `{MODULE_TASK_LIBRARY}` placeholder at `:59` |
| `backend/files/prompts/sale-ready/scoring_prompt.md` | **no code reference** | Pre-split monolith for Sale-Ready (placeholder at `:103`) |
| `backend/files/prompts/sale-ready/SCORING_MAP_COMPLETE.json` | `FileLoader.load_scoring_map_for_type('sale_ready')` (`file_loader.py:92`) | Question-key → score → module map |
| `backend/files/prompts/value-builder/scoring_prompt_scoring.md` | `load_prompt_for_type(…, 'value_builder')` | Part 1 for the Value Builder taxonomy (V-codes) |
| `backend/files/prompts/value-builder/scoring_prompt_report.md` | `diagnostic_service.py:648` | Part 2 for Value Builder |
| `backend/files/prompts/value-builder/scoring_prompt.md` | **no code reference** | Pre-split monolith for Value Builder |
| `backend/files/prompts/value-builder/SCORING_MAP_VALUE_BUILDER.json` | `FileLoader.load_scoring_map_for_type('value_builder')` (`file_loader.py:93`) | Value Builder scoring map; also the default for any unrecognised engagement type (`file_loader.py:96`) |

`backend/tests/test_program_guide_seed.py:1247-1262` globs `value-builder/scoring_prompt*.md`, extracts every quoted `"V<n> <name>"` string, and asserts the set equals `ScoringService.VALUE_BUILDER_MODULES`. All three files carry V-codes, so the unused monolith is still under test and still has to be kept in sync.

**Gotcha:** `generate_report` substitutes `{MODULE_TASK_LIBRARY}` (`claude_service.py:755-758`), but the placeholder exists only in `sale-ready/scoring_prompt.md` and `sale-ready/scoring_prompt_report.md`. Value Builder reports never receive the task library; the substitution is a silent no-op.

**BBA** — loaded by `load_bba_prompt` (`bba_conversation_engine.py:20-37`)

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/bba/bba_system_prompt.md` | every BBA call (`:174,304,384,467,576,657`, `bba_presentation_service.py:60`, `bba_task_planner_service.py:169`) | House system prompt: report format, tone, British English, bold for headings only |
| `backend/files/prompts/bba/step3_draft_findings.md` | `bba_conversation_engine.py:175` | Top-10 ranked findings from uploaded files |
| `backend/files/prompts/bba/step4_expand_findings.md` | `:305` | One or two paragraphs per finding |
| `backend/files/prompts/bba/step5_snapshot_table.md` | `:385` | Three-column findings/recommendations snapshot |
| `backend/files/prompts/bba/step6_12month_plan.md` | `:468` | 12-month recommendation plan plus its disclaimer |
| `backend/files/prompts/bba/step7_review_edit.md` | `:577` | Apply advisor edits consistently |
| `backend/files/prompts/bba/extract_context_capture.md` | `:728`, with an inline fallback prompt at `:729-742` | Fill the 9 context-capture form fields from a diagnostic report and/or documents |
| `backend/files/prompts/bba/phase2_task_generation.md` | `bba_task_planner_service.py:170` | Advisor/client task rows with hour allocations for the Excel planner |
| `backend/files/prompts/bba/phase3_presentation.md` | `bba_presentation_service.py:61` | Slide content for the PowerPoint export |
| `backend/files/prompts/bba/images/bba_picture.png`, `bba_picture_2.png`, `bba_picture_3.jpg`, `unnamed.jpg`, `unnamed (1).png`, `unnamed (2).jpg`, `unnamed (3).jpg` | `bba_report_export.py:131,146-149,310,769` | Report/branding artwork — **not prompts**; they merely live in the prompts tree |

The BBA executive summary (`:657`) loads only the system prompt and supplies its instructions inline. The task planner and presentation services concatenate system prompt + step prompt into a single `{"role":"system"}` message rather than using `system_blocks`, so they take the single-cached-block path.

**Roles Matrix** — `load_roles_matrix_prompt` (`roles_matrix_engine.py:17-36`)

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/roles-matrix/system_prompt.md` | `:134`, `:220` | Assistant persona plus the exact ten-column "Job Roles" contract (`Name, Role Descriptions, Time, Priorities, Retain, Gain, Lose, Action, Resp, When`) |
| `backend/files/prompts/roles-matrix/extract_responsibilities.md` | `:135` | Per-person responsibilities as JSON under a single `people` key |
| `backend/files/prompts/roles-matrix/build_matrix.md` | `:221` | Turn extracted responsibilities into matrix rows (`matrix_rows`) |

**PD & Role Scorecard** — `load_pd_scorecard_prompt` (`pd_scorecard_engine.py:18-37`)

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/pd-scorecard/system_prompt.md` | `:137`, `:226`, `:305` | HR/org-design persona; PD + half-yearly scorecard per role |
| `backend/files/prompts/pd-scorecard/extract_roles.md` | `:138` | Parse an uploaded roles matrix into rows + distinct roles |
| `backend/files/prompts/pd-scorecard/generate_pd.md` | `:227` | Position Description for one named role |
| `backend/files/prompts/pd-scorecard/generate_scorecard.md` | `:306` | Half-yearly scorecard aligned to that role's approved PD |

**Strategic Business Plan** — `load_sbp_prompt` (`sbp_conversation_engine.py:28-35`); each section prompt is resolved dynamically as `section_{section_key}` (`:410`) from the keys in `DEFAULT_SECTIONS` (`sbp_service.py:17-33`)

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/strategic-business-plan/system_prompt.md` | `:326,405,477,533` (inline fallback `_default_system_prompt`, `:561`) | SBP assistant persona and plan logic flow |
| `backend/files/prompts/strategic-business-plan/cross_analysis.md` | `:331` | Cross-pattern analysis: themes, tensions, correlations, data gaps |
| `backend/files/prompts/strategic-business-plan/emerging_themes.md` | `:538` | Surface emerging themes from approved sections |
| `backend/files/prompts/strategic-business-plan/revision.md` | `:482` | Revise one section against advisor notes |
| `…/section_executive_summary.md` | key `executive_summary` | Executive Summary |
| `…/section_strategic_intent.md` | key `strategic_intent` | Strategic Intent Overview |
| `…/section_business_context.md` | key `business_context` | Business and Context Overview |
| `…/section_external_internal_analysis.md` | key `external_internal_analysis` | External and Internal Analysis |
| `…/section_key_resources_capabilities.md` | key `key_resources_capabilities` | Key Resources and Capabilities |
| `…/section_customer_dynamics.md` | key `customer_dynamics` | Customer Dynamics |
| `…/section_growth_opportunities.md` | key `growth_opportunities` | Growth Opportunities and Strategic Direction |
| `…/section_operations_strategy.md` | key `operations_strategy` | Operational Strategy |
| `…/section_hr_strategy.md` | key `hr_strategy` | HR Strategy |
| `…/section_marketing_sales_strategy.md` | key `marketing_sales_strategy` | Marketing and Sales Strategy |
| `…/section_financial_overview.md` | key `financial_overview` | Financial Overview |
| `…/section_risk_matrix.md` | key `risk_matrix` | Risk Matrix and Analysis |
| `…/section_actions_next_steps.md` | key `actions_next_steps` | Actions List (Implementation Plan) |
| `…/section_strategic_alignment.md` | key `strategic_alignment` | Integrated Strategic Implications and Alignment |

SBP setup extraction (`sbp_conversation_engine.py:276-300`) uses an inline system prompt, not a file.

**Strategy Workbook** — loaded eagerly in `StrategyWorkbookService.__init__` via `FileLoader`, spelling out the subdirectory in the prompt name

| Prompt file | Consumed by | Purpose |
|---|---|---|
| `backend/files/prompts/strategy-workbook/extraction_prompt.md` | `strategy_workbook_service.py:31` → used at `:236` | Step 1: extract strategic content from documents |
| `backend/files/prompts/strategy-workbook/formatting_prompt.md` | `:32` → used at `:290` | Step 2: normalise into the exact Excel-workbook JSON schema |
| `backend/files/prompts/strategy-workbook/precheck_prompt.md` | `:33` → used at `:419` | Judge whether uploads are usable; emit clarification questions |

### Prompt authoring convention

**Format.** Every prompt is a plain Markdown file. The house shape, consistent across `roles-matrix/system_prompt.md`, `bba/step3_draft_findings.md`, `pd-scorecard/generate_pd.md` and the scoring trio:

```markdown
# <Tool or Step name>

## Your Task            <- or ## PURPOSE for the diagnostic scoring prompts
<one paragraph>

## Instructions         <- numbered, imperative
1. ...

## Output Format        <- a fenced json block showing the exact shape

## Guidelines           <- field-level rules, nullability, British English
```

Recurring house rules worth preserving when writing a new one:

- Name the single top-level key and forbid all others (`roles-matrix/extract_responsibilities.md:67`).
- Never invent; leave the cell blank or `null` when the source is silent (`roles-matrix/system_prompt.md:39-40`, `extract_responsibilities.md:71-74`).
- British English spelling throughout (`bba/bba_system_prompt.md:6,33`, `pd-scorecard/system_prompt.md:48`, `strategic-business-plan/system_prompt.md:19`, `roles-matrix/system_prompt.md:45`). The root chat prompt does **not** carry this rule.
- For anything reaching a PDF or DOCX renderer, an ASCII-only clause (`system_prompt.md:38-46`, `scoring_prompt_scoring.md:93-100`).

**Loading and caching.** `FileLoader.load_prompt` (`file_loader.py:44-68`) appends `.md` if missing, resolves against `backend/files/prompts/`, raises `FileNotFoundError` if absent, and is wrapped in `@lru_cache(maxsize=32)`. `maxsize=32` is below the number of distinct prompt names in the tree, so entries can evict and be re-read. `FileLoader.clear_cache()` (`:147-153`) is only useful in tests.

**Gotcha — editing a `FileLoader` prompt requires a process restart, not a new request.** The cache is process-lifetime and keyed on the prompt name, so the first read of a given prompt in the life of the process is the only one that touches disk. Where the load happens in a service constructor the window is even narrower: `StrategyWorkbookService.__init__` reads all three workbook prompts eagerly (`strategy_workbook_service.py:31-33`), so they are warmed the first time any request instantiates the service and stay warm for the process. The same rule holds for every prompt read through `load_prompt` or `load_prompt_for_type`. By contrast, the four per-tool loaders (`load_bba_prompt`, `load_roles_matrix_prompt`, `load_pd_scorecard_prompt`, `load_sbp_prompt`) do a plain `open()` with no cache, so edits to BBA, roles-matrix, PD-scorecard and SBP prompt files take effect on the next call with no restart. Knowing which half of the tree a file lives in is the difference between a one-second edit and a puzzling non-change.

**Per-engagement-type resolution.** `FileLoader.load_prompt_for_type(prompt_name, engagement_type)` (`file_loader.py:104-140`), also `lru_cache`d, in exactly this order:

1. Append `.md` if missing (`:119-120`).
2. Map the engagement type to a directory — `sale_ready → sale-ready`, `value_builder → value-builder`; any other value maps to `None` (`:122-126`).
3. If a directory was mapped **and** `prompts/<dir>/<name>.md` exists, read and return it (`:128-132`).
4. Otherwise fall back to `prompts/<name>.md`; raise `FileNotFoundError` if that does not exist either (`:135-140`).

The type comes from `engagement.tool`, defaulting to `'value_builder'` when there is no engagement (`diagnostic_service.py:342-343`). Both known types have a full trio on disk, so the root-level `scoring_prompt_scoring.md` / `scoring_prompt_report.md` are reachable only for an `engagement.tool` value that is neither — a real possibility, since the column is a free-text `String(100)`, nullable (`backend/app/models/engagement.py:36`).

**Rules for adding a new prompt.**

- Shared across both diagnostic types → `backend/files/prompts/<name>.md`, load with `load_prompt("<name>")`.
- Type-specific → put it at `backend/files/prompts/sale-ready/<name>.md` **and** `backend/files/prompts/value-builder/<name>.md` under the same filename, then load with `load_prompt_for_type("<name>", engagement_type)`. Adding it to only one directory means the other type silently falls back to the root file — or raises `FileNotFoundError` if there is no root file.
- Belongs to a tool (BBA, roles matrix, PD scorecard, SBP) → put it in that tool's subdirectory and use that tool's loader. `FileLoader` resolves only from the prompts root and cannot see a subdirectory unless you spell the path out the way `strategy_workbook_service.py:31` does: `load_prompt("strategy-workbook/extraction_prompt")`.
- A new SBP section needs *both* a `{"key","title"}` entry in `DEFAULT_SECTIONS` (`sbp_service.py:17-33`) and a matching `section_<key>.md`; miss the file and you silently get `_default_section_prompt` (`sbp_conversation_engine.py:596`).
- **Gotcha:** SBP section, revision and cross-analysis prompts are Python `str.format()` templates. `draft_section` interpolates twelve named placeholders — `client_name`, `industry`, `planning_horizon`, `target_audience`, `additional_context`, `cross_analysis`, `advisor_notes`, `emerging_themes`, `approved_sections`, `file_references`, `diagnostic_context`, `custom_instructions` (`sbp_conversation_engine.py:417-429`). A literal `{` or `}` in one of those files (for example a JSON example block) raises `KeyError`/`ValueError` at draft time. Escape them as `{{` / `}}`.
- If the prompt will be sent as a cached system block, keep the stable part (persona, output contract) in the first block and the volatile part in the second, so the base prompt keeps hitting the cache across steps.
- Restart the backend after editing any `FileLoader`-loaded prompt.

### Provider abstraction — reality check

The abstraction is aspirational. What actually happens at runtime:

- `LLM_PROVIDER` is declared at `config.py:55` and read nowhere in `backend/app`. The only other occurrences are two test files that set it as an env default (`backend/tests/test_claude_service.py:30`, `backend/tests/test_claude_integration.py:33`).
- `main.py:118-133` calls `ClaudeService.initialize_client()` unconditionally; the OpenAI equivalent sits commented out at `:128-130`.
- `openai_service.py` is imported by no module. Its own docstring (`:1-12`) is the switch-back procedure, and it is a manual, three-step, edit-the-source procedure — not a config flag.
- Several services still carry OpenAI-era names for Claude objects: `self.openai_service = ClaudeService()` (`bba_conversation_engine.py:54`, `bba_presentation_service.py:39`, `bba_task_planner_service.py:46`), `openai_service = ClaudeService()` in `api/upload_poc.py:239,1544,1698,1815`, `media.openai_file_id` holding Claude file ids (`models/media.py:43`, written alongside `llm_file_id` at `diagnostic_service.py:576-582`), and log lines that say "Calling OpenAI" while calling Claude (`bba_task_planner_service.py:213`, `bba_presentation_service.py:77`). Treat "openai" in an identifier as meaning "LLM".

**To flip back to OpenAI you would have to:** set `OPENAI_API_KEY`; swap the `initialize_client()` call in `main.py`; and change the import in every consumer — `chat_service.py:18`, `diagnostic_service.py:20`, `file_service.py:20`, `strategy_workbook_service.py:15`, `bba_conversation_engine.py:13`, `bba_presentation_service.py:23`, `bba_task_planner_service.py:29`, `sbp_conversation_engine.py:19`, `sbp_presentation_service.py:13`, `roles_matrix_engine.py:11`, `pd_scorecard_engine.py:11`, `api/pd_scorecard.py:24`, `api/roles_matrix.py:24`, `api/strategic_business_plan.py:206`, `api/upload_poc.py:44`, `tasks/diagnostic_tasks.py:25`. You would then still have to reconcile the parts of the interface that are not shared: `OpenAIService.generate_completion` (`openai_service.py:133-143`) accepts no `system_blocks`, and its `model` parameter defaults to the literal `"gpt-5-nano"` rather than `settings.OPENAI_MODEL`; `sbp_presentation_service.py:61` calls the Anthropic SDK directly. Setting `LLM_PROVIDER=openai` on its own changes nothing.

**Tests.** `backend/tests/test_claude_service.py` covers message conversion, document vs `container_upload` blocks, `generate_completion`, `generate_json_completion`, `_repair_json`, `upload_file`, MIME mapping and the OpenAI-compatible return shape, all against a mocked client. `backend/tests/test_claude_integration.py` makes real API calls and is skipped module-wide when `ANTHROPIC_API_KEY` is unset (`:19-22`). Both files use `@pytest.mark.asyncio` — see *Engineering Standards, Workflow & Testing* for why that does not currently run.

### Cost and usage accounting

`tokens_used` (input + output for a single call) is threaded back through every engine's return dict and persisted on each tool's own row.

| Table / model | Columns | Written by |
|---|---|---|
| `diagnostics` (`models/diagnostic.py:54-55`) | `ai_model_used` `String(100)`, `ai_tokens_used` `Integer` | `diagnostic_service.py:825-829` |
| `bbas` (`models/bba.py:120-121`) | same | `bba_service.py:334-335, 489-490, 523-524, 561-562, 594-595` — accumulates with `(existing or 0) + tokens_used`; reset to `None` at `:172-173` |
| `roles_matrices` (`models/roles_matrix.py:61-62`) | same | `roles_matrix_service.py:238-245` (`_record_ai_usage`, called at `:160`, `:189`) |
| `pd_scorecards` (`models/pd_scorecard.py:55-56`) | same | `pd_scorecard_service.py:409-418` (`_record_ai_usage`, called at `:166`, `:288`, `:332`) |
| `strategic_business_plans` (`models/strategic_business_plan.py:98-99`) | same | **nothing** — the columns exist and are serialised at `:149-150`, but no service writes them |
| `messages.response_data` (JSON) | `tokens_used`, `prompt_tokens`, `completion_tokens` | `chat_service.py:276-281` |
| `diagnostics.scoring_data` (JSON) | `tokens_used` for the scoring call only | `diagnostic_service.py:778-782` |

**Gaps, all verified:**

- **No cost anywhere.** No price table, no per-token rate, no dollar figure, no aggregate query. The only `cost`-named code in the backend belongs to subscriptions/billing (`models/subscription.py`, `services/firm_service.py`) and is unrelated to LLM spend. Answering "what did last month cost?" means exporting `ai_tokens_used` per table and pricing it by hand — and even that is wrong, because the model column records only the last model used while the token count is a sum across calls that may have used different models.
- **The diagnostic total under-counts.** `diagnostic_service.py:826-829` sums only the scoring and summary calls. The report call (Step 3b) and the task-generation call are omitted, and those are two of the four largest calls in the pipeline.
- **The diagnostic model default is stale.** `diagnostic.ai_model_used = scoring_result.get("model", "gpt-4o")` (`diagnostic_service.py:825`) — the fallback names a model this system no longer uses.
- **Cache savings are invisible.** `cache_creation_input_tokens` / `cache_read_input_tokens` are read and logged (`claude_service.py:373-380`) but never returned or stored, so the effect of the system-block caching in the BBA/roles-matrix/PD engines cannot be measured from the database.
- **Strategy Workbook and SBP record nothing.** `strategy_workbooks` (`models/strategy_workbook.py`) has no token columns at all; the workbook service only prints token counts into exception messages (`:281-284`, `:331-334`, `:452-455`). `strategic_business_plans` has the columns but no writer.

---

## 12. AI Tools — BBA, Strategy Workbook & Strategic Business Plan

These are the three advisor-facing document-generation tools. All three share a shape: an advisor creates a project (standalone, from an engagement, or from a completed diagnostic), uploads source documents, drives a multi-step LLM pipeline whose output is persisted as JSONB on a single row, edits the result in the browser, and exports an Office file.

Every AI call goes through the shared `ClaudeService` (`backend/app/services/claude_service.py`) — client construction, prompt caching, the `reasoning_effort` side effects that appear in the parameter tables below, model defaulting and the JSON-repair ladder are all described once in *AI Layer — Claude Integration & Prompt System*; this section covers only what is specific to these three tools: their prompt files, their persisted JSONB shapes and their exporters.

All of that work is synchronous and in-process inside the request handler — there is no worker tier (see *System Architecture*). A step-6 BBA generation or an SBP section draft is one long-lived HTTP request; the client-side ceiling is `ANTHROPIC_TIMEOUT`, 1800 s by default.

### Configuration specific to these tools

Three settings exist only for the Strategy Workbook; every other Anthropic and upload variable is tabulated in *Environments, Configuration & Deployment*.

| Env var | Read at | Effect |
|---|---|---|
| `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP1` | `backend/app/services/strategy_workbook_service.py:256` | model for raw extraction; falls back to `ANTHROPIC_MODEL` |
| `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP2` | `strategy_workbook_service.py:304` | model for JSON normalisation; falls back to `ANTHROPIC_MODEL` |
| `ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2` | `strategy_workbook_service.py:305` | output cap for step 2; falls back to `ANTHROPIC_MAX_TOKENS`, then to a per-model clamp (below) |

`UPLOAD_DIR` matters here too, but it is not this section's alone: BBA (`backend/app/api/upload_poc.py:101`), Roles Matrix (`backend/app/api/roles_matrix.py:56`) and PD Scorecard (`backend/app/api/pd_scorecard.py:80`) all resolve their persisted-upload root from it. It resolves to `backend/uploads/` when relative, and **no static mount covers it** — unlike `backend/files/`, which is served at `/files`. Strategy Workbook and SBP write under `backend/files/` instead and are therefore reachable over HTTP. See *Operations, Diagnostics & Troubleshooting*.

### Prompt loading

Prompt loading differs per tool and the difference is operational, not cosmetic.

| Loader function | File | Used by | Cached? |
|---|---|---|---|
| `load_bba_prompt` | `backend/app/services/bba_conversation_engine.py:20-37` | BBA | No — file read on every call, edits are live |
| `FileLoader.load_prompt` | `backend/app/utils/file_loader.py:44-68` | Strategy Workbook | **Yes** — `@lru_cache(maxsize=32)` on the classmethod |
| `load_sbp_prompt` | `backend/app/services/sbp_conversation_engine.py:28-35` | SBP | No — file read on every call |

For the Strategy Workbook the cache is worse than per-request memoisation: all three prompts are loaded in the service **constructor** (`strategy_workbook_service.py:31-33`), so the cache is warmed on first instantiation and a prompt edit requires a **process restart**, not a new request.

---

### BBA — Diagnostic Report Builder

#### 1. Purpose

An advisor uploads a client's financials, board packs and reports, answers a short context questionnaire, and the tool produces a Benchmark-branded diagnostic report: executive summary, findings-and-recommendations snapshot table, ranked expanded findings, a 12-month plan and an implementation timeline, exported as `.docx`. Two follow-on phases turn the same plan into an Excel advisor task list (with optional push into Trinity Tasks) and a branded PowerPoint deck.

**Naming debt — read this first.** The router is `APIRouter(prefix="/api/poc", tags=["bba"])` (`backend/app/api/upload_poc.py:97`), mounted without an extra prefix (`backend/app/main.py:90`). `/api/poc` is the **production BBA prefix**: the module is `upload_poc.py`, the page is `frontend/src/pages/poc/FileUploadPOCPage.tsx`, the components live in `frontend/src/components/poc/`, and the localStorage keys are `bba_*`. Nothing here is a proof of concept — it is the shipped tool at `/dashboard/engagements/:engagementId/bba`, and renaming the prefix breaks the frontend, the launcher hook and both stale README files at once. The two root-level docs (`POC_EXPLANATION.md`, `POC_FILE_UPLOAD_README.md`) describe a `/poc/file-upload` route and `/api/upload`, `/api/upload/mappings` endpoints that **do not exist**; `docs/BBA_TOOL_FLOW.md` is closer but still describes `openai_service.py` as the LLM path.

#### 2. Step-by-step workflow

The UI presents nine steps across three phases (`frontend/src/components/poc/FileUploadPOC.tsx:939-955`): Phase 1 = steps 1–7 (Word report), Phase 2 = step 8 (Task Planner), Phase 3 = step 9 (Presentation).

| Step | What the advisor does | Endpoint(s) | AI prompt used | What gets persisted |
|---|---|---|---|---|
| 0 | Launch the tool | `POST /api/poc/create-project?engagement_id=` or `POST /api/poc/create-from-diagnostic?diagnostic_id=&force_new=` | — | new `bba` row, `status='uploaded'`; from-diagnostic also stores `diagnostic_id`, `diagnostic_context`, prefilled `client_name` |
| 1 | Drag-drop up to 20 files | `POST /api/poc/{project_id}/upload` (multipart) | — | `file_ids`, `file_mappings`, `stored_files`; bytes written to `{UPLOAD_DIR}/bba/{project_id}/{safe_name}`; `status` reset to `'uploaded'` |
| 1b | Re-download an upload (**no frontend caller**) | `GET /api/poc/{project_id}/files/{filename}` | — | — |
| 2 | Autofill then confirm the context questionnaire | `GET /api/poc/{project_id}/extract-context-capture`, then `POST /api/poc/{project_id}/submit-questionnaire` | `bba/extract_context_capture.md` | 9 scalar columns; `status='questionnaire_completed'`, `questionnaire_completed_at` |
| 3 | Generate, reorder and confirm the Top-10 findings | `POST /api/poc/{project_id}/step3/generate`, `POST /api/poc/{project_id}/step3/confirm` | `bba/bba_system_prompt.md` + `bba/step3_draft_findings.md` | `draft_findings`, `draft_findings_edited`; `status='draft_findings'` |
| 4 | Expand findings into paragraphs; inline-edit | `POST .../step4/generate`, `PATCH .../step4/save` | `bba/step4_expand_findings.md` | `expanded_findings`; `status='expanded_findings'` |
| 5 | Generate the snapshot table; inline-edit rows | `POST .../step5-6/generate-parallel` (UI default) or `POST .../step5/generate` (no frontend caller); `PATCH .../step5/save` | `bba/step5_snapshot_table.md` | `snapshot_table`; `status='snapshot_table'` |
| 6 | Review the 12-month plan; add/delete/edit recommendations | pre-generated by the step-5 parallel call, or `POST .../step6/generate`; `PATCH .../step6/plan` | `bba/step6_12month_plan.md` | `twelve_month_plan`, `plan_notes`; `status='twelve_month_plan'` |
| 7 | Auto-generate + edit the exec summary; export Word | `POST .../executive-summary/generate`, `POST .../export/docx` | system prompt + inline instruction | `executive_summary`; on export `final_report`, `report_version += 1`, `status='completed'` |
| 7b | AI edit pass (**no frontend caller**) | `PATCH .../review/edit` | `bba/step7_review_edit.md` | intended to overwrite report sections — it currently writes nothing, see Gotchas |
| 8 | Set advisors/capacity/start month → preview tasks → edit grid → export XLSX and/or push into Trinity Tasks | `POST .../tasks/preview` (saves settings and generates), `PATCH .../tasks`, `POST .../tasks/export/excel`, `PATCH .../tasks/export-status?exported=`; `POST .../tasks/settings` exists with no frontend caller | `bba/phase2_task_generation.md` | `task_planner_settings`, `task_planner_tasks`, `tasks_exported_to_trinity` |
| 9 | Generate slides → edit/add/move/delete → approve → export PPTX | `POST .../presentation/generate`, `POST .../presentation/slides/{slide_index}/edit`, `POST .../presentation/slides/add`, `POST .../presentation/slides/move`, `DELETE .../presentation/slides/{slide_index}`, `POST .../presentation/export/pptx` | `bba/phase3_presentation.md` | `presentation_slides` |
| any | Persist wizard position | `PATCH /api/poc/{project_id}/step-progress` | — | `current_step`, `max_step_reached` |
| any | List / fetch | `GET /api/poc/?engagement_id=`, `GET /api/poc/{project_id}` | — | — |

Prerequisite guards: step 3 requires `file_ids` and `client_name`; step 4 requires `draft_findings`; steps 5, 6 and the exec summary require `expanded_findings`; DOCX export requires `expanded_findings`; task planner and presentation require `twelve_month_plan`.

#### 3. Data model — `bba` (`backend/app/models/bba.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `engagement_id` | UUID FK → `engagements` ON DELETE CASCADE | nullable — standalone projects have none |
| `diagnostic_id` | UUID FK → `diagnostics` ON DELETE SET NULL | set when created from a diagnostic |
| `diagnostic_context` | JSONB | `{report_html?, ai_analysis?, business_name?}` |
| `created_by_user_id` | UUID FK → `users` ON DELETE CASCADE, NOT NULL | the only owner |
| `status` | varchar(50), server default `'uploaded'`, indexed | see progression below |
| `current_step` / `max_step_reached` | int, nullable | schema validates `ge=1, le=9` (`backend/app/schemas/bba.py:60-63`) |
| `file_ids` | JSONB | list of Claude file ids |
| `file_mappings` | JSONB | `{filename: file_id}` |
| `stored_files` | JSONB | `{filename: "project_id/safe_name"}` on-disk relative paths |
| `client_name`, `industry`, `company_size`, `locations` | varchar | Step 2 |
| `exclusions`, `constraints`, `preferred_ranking`, `strategic_priorities` | text | Step 2 |
| `exclude_sale_readiness` | bool, default false | Step 2 |
| `draft_findings` | **JSONB** | `{findings:[{rank,title,summary,priority_area,impact,urgency}], analysis_notes, files_analysed[]}` |
| `draft_findings_edited` | bool, default false | true when `step3/confirm` carries a body; reset to false by every regenerate |
| `expanded_findings` | **JSONB** | `{expanded_findings:[{rank,title,priority_area,paragraphs[],key_points[]}]}` |
| `snapshot_table` | **JSONB** | usually nested: `{snapshot_table:{title, rows:[{rank,priority_area,key_finding,recommendation}]}}` |
| `twelve_month_plan` | **JSONB** | `{plan_notes, recommendations:[{number,title,timing,purpose,key_objectives[],actions[],bba_support,expected_outcomes[]}], timeline_summary:{title, rows:[{rec_number,recommendation,focus_area,timing,key_outcome}]}}` |
| `plan_notes` | text | duplicated out of the plan JSON |
| `executive_summary` | text | |
| `final_report` | JSONB | snapshot `{executive_summary, snapshot_table, expanded_findings, twelve_month_plan, exported_at}` written at DOCX export |
| `report_version` | int, default 1 | incremented on every DOCX export (first export → 2) |
| `tasks_exported_to_trinity` | bool, default false | Phase 2 |
| `task_planner_settings` | **JSONB** | `{lead_advisor, support_advisor, advisor_count, max_hours_per_month, start_month, start_year}` |
| `task_planner_tasks` | **JSONB** | array of Excel rows |
| `task_planner_summary` | **JSONB** | **always written as `None`** (`backend/app/services/bba_task_planner_service.py:259`) |
| `presentation_slides` | **JSONB** | `{slides:[{index,type,title,...,approved}]}` |
| `conversation_history` | JSONB | declared, never written, not in `to_dict()` |
| `ai_model_used`, `ai_tokens_used` | varchar(100) / int | `ai_tokens_used` accumulates across all steps |
| `is_deleted` | bool, default false | filtered in every read, never set to true |
| `created_at`, `updated_at`, `questionnaire_completed_at` | timestamps | |

`to_dict()` also returns a derived `engagement_client_name` (resolved from the engagement's client user) and omits `is_deleted` and `conversation_history`.

**`status` progression** (each value set by the corresponding `BBAService.update_*`, `backend/app/services/bba_service.py`):

`uploaded` → `questionnaire_completed` → `draft_findings` → `expanded_findings` → `snapshot_table` → `twelve_month_plan` → `completed` (on DOCX export).

**Gotcha:** the column comment on `status` lists only `uploaded, questionnaire_completed, draft_findings, expanded_findings, completed` — it omits `snapshot_table` and `twelve_month_plan`, which the service actually writes. Trust the service.

**Gotcha:** `update_files` sets `status='uploaded'` unconditionally (`bba_service.py:267`), so uploading an extra document at step 5 rewinds `status` to `uploaded` while all the step JSONB stays intact. The UI drives off `current_step`/`max_step_reached`, so this is mostly invisible — until something reads `status`.

`current_step` / `max_step_reached` are written only by the frontend via `PATCH /step-progress`; `BBAService.update_step_progress` assigns them verbatim (no `max()` clamp) and nothing keeps them consistent with `status`.

#### 4. AI calls

Every Phase-1 call is built in `backend/app/services/bba_conversation_engine.py`. Steps 3–7 send **two separately cached system blocks** (`bba_system_prompt` + the step prompt, each with `cache_control: {"type":"ephemeral"}`) so the base prompt hits the cache across steps.

| Call | Prompt files | Params | Returned JSON top-level keys |
|---|---|---|---|
| `generate_draft_findings` | system + `step3_draft_findings` | `reasoning_effort="medium"`, `max_output_tokens=16384`, PDFs as `file_ids`, other files via a `code_interpreter` container | `findings[]`, `analysis_notes`, `files_analysed[]` |
| `expand_findings` | system + `step4_expand_findings` | `low`, `12288`, **no files re-attached** | `expanded_findings[]` |
| `generate_snapshot_table` | system + `step5_snapshot_table` | `low`, `8192`, no files | `snapshot_table{title, rows[]}` |
| `generate_12month_plan` | system + `step6_12month_plan` | `low`, `32768`, no files | `plan_notes`, `recommendations[]`, `timeline_summary{}` |
| `apply_edits` | system + `step7_review_edit` | `low`, `24576` | `updated_sections{}`, `changes_made[]`, `warnings[]` |
| `generate_executive_summary` | system prompt sent as a plain `system` **message** (legacy single-block path) | `low`, `8192` | `executive_summary` (string) |
| `extract_context_capture_from_diagnostic_text` | `extract_context_capture` (inline fallback prompt if the file is missing) | `temperature=0.2`, `4096`, uploaded files attached | 9 camelCase keys, filtered to the known set, `companySize` normalised to the enum |
| Phase 2 task generation (`bba_task_planner_service.py`) | system + `phase2_task_generation` concatenated into one system message | **no explicit params** — service defaults apply | `tasks[]` (`rec_number, recommendation, owner, task, advisorHrs, advisor, status, notes, timing`) |
| Phase 3 slides (`bba_presentation_service.py`) | system + `phase3_presentation` concatenated | **no explicit params** | `slides[]`; the service then stamps `index` and defaults `approved=false` |

File routing (`_separate_files_by_type`, `bba_conversation_engine.py:111-145`): `.pdf` → `file_ids` (document blocks); `csv/txt/text/md/markdown/json/xml/yaml/yml/xlsx/xls` → a `code_interpreter` container; anything else defaults to the container with a warning. Falsy file ids are skipped.

Value Builder engagements get an extra cached system block constraining `priority_area` to `ScoringService.VALUE_BUILDER_MODULES` verbatim, so BBA findings map 1:1 onto Program Guide modules without fuzzy matching (`_build_value_builder_taxonomy_block`, applied by `_maybe_add_value_builder_taxonomy` to steps 3, 4 and 5 only — not 6 or 7). The consuming side of that contract is in *Value Builder Programme — Program Guide & Deliverables*.

Prior-diagnostic context is stripped of HTML and truncated to `MAX_DIAGNOSTIC_CHARS = 6000` before injection into the Step 3 user message (`bba_conversation_engine.py:191-204`).

`apply_edits` keyword-matches the edit request to decide which of the four report sections to send as context (`_select_edit_sections`), always including `draft_findings` and falling back to all four when nothing matches.

Reordering: `BBAService.confirm_draft_findings` calls `_reorder_downstream_data` (`bba_service.py:374-462`), which re-ranks `expanded_findings` and `twelve_month_plan.recommendations` **by matching titles**, snapshot rows by old-rank → title → new-rank, and `timeline_summary.rows` by recommendation title. Any title the advisor edits during reorder breaks the match and that item keeps its old rank.

#### 5. Exports

| Output | Format | Library | Template | Destination |
|---|---|---|---|---|
| Diagnostic report | `.docx` | `python-docx` (`backend/app/services/bba_report_export.py`) | none — built programmatically; images from `backend/files/prompts/bba/images/` (`bba_picture.png` full-width, a 4-image grid of `unnamed (2).jpg`/`unnamed (3).jpg`/`unnamed.jpg`/`bba_picture_3.jpg`, `bba_picture_2.png` as the Australia-map banner, and a header logo resolved from `logo.png` → `benchmark_logo.png` → `unnamed (1).png`) | streamed; `Content-Disposition: attachment; filename={Client_Name} - Diagnostic Findings and Recommendations Report.docx` (unquoted, spaces preserved after the client name). Nothing written to disk |
| Advisor task list | `.xlsx` | `openpyxl` (`bba_task_list_export.py`) | none | streamed as `{Client_Name}_Advisor_Task_List.xlsx` |
| Presentation | `.pptx` | `python-pptx` (`bba_pptx_export.py`) | none — programmatic navy/white deck, 16:9 (13.333 × 7.5 in), blank layout `slide_layouts[6]`, `NAVY #1A365D`, Calibri | streamed as `{Client_Name}_Diagnostic_Presentation.pptx` |

The DOCX renders, in order: title page (images + blue banner + client + title + month/year) → executive summary → snapshot table (4 columns `#`/Priority Area/Key Finding/Recommendation, navy `1a365d` header shading) → key findings ranked → 12-month plan (plan notes, per-recommendation blocks) → **Implementation Timeline** table from `timeline_summary`. Each block is skipped if its column is null. The snapshot renderer unwraps both the nested and flat shapes.

The XLSX has one sheet, `Advisor Task List`, columns `Rec #, Recommendation, Owner, Task, Advisor Hrs, Advisor, Status, Notes, Timing`, with list validations on Owner (`Client`/`BBA`), Advisor (derived from the task rows), and Status (`Not yet started`, `In progress`, `Complete`, `Awaiting review`), conditional formatting on Status, and the footer *"Prepared by Benchmark Business Advisory – Confidential."*

The PPTX **only exports slides where `approved` is truthy** and raises `ValueError` (surfaced as 400) if none are. Slide dispatch handles `title`, `executive_summary`, `structure`, `recommendation`, `timeline`, `next_steps`, with a generic content-slide fallback.

#### 6. Frontend

| Concern | Location |
|---|---|
| Page | `frontend/src/pages/poc/FileUploadPOCPage.tsx` |
| Wizard shell (all 9 steps, upload, state restore) | `frontend/src/components/poc/FileUploadPOC.tsx` (1,445 lines) |
| Step components | `ContextCaptureQuestionnaire.tsx`, `DraftFindingsStep.tsx`, `ExpandedFindingsStep.tsx`, `SnapshotTableStep.tsx`, `TwelveMonthPlanStep.tsx`, `ReviewEditStep.tsx`, `TaskPlannerStep.tsx`, `PresentationStep.tsx` (all in `frontend/src/components/poc/`) |
| Redux slice | **none** — BBA is the only one of the three tools with no slice. State lives in `useState` plus localStorage keys `bba_project_id`, `bba_current_step`, `bba_max_step`, `bba_questionnaire_data`, `bba_engagement_id`, and raw `fetch` calls |
| Routes | `/dashboard/engagements/:engagementId/bba` and `/dashboard/ai-tools/bba`, both → `FileUploadPOCPage` (`frontend/src/App.tsx:82,87`) |
| Launcher | `frontend/src/hooks/useToolLaunchers.ts:116-150` (`launchBba` / `runBba`) |

Client-side upload validation in `FileUploadPOC.tsx:32-45`: 100 MB per file and a MIME allowlist (PDF, txt, csv, xls/xlsx, doc/docx, …) — looser than the server, which caps only the file **count** at 20.

Standalone mode (`/dashboard/ai-tools/bba`, no `engagementId`) runs a pre-flight: `GET /api/poc` and, if any project has `max_step_reached >= 2`, shows a *Continue Existing / Start New* card; "Start New" posts `/api/poc/create-project` with no engagement.

`SnapshotTableStep` calls the parallel endpoint, not `step5/generate` — the 12-month plan is generated and saved silently so Step 6 finds it pre-loaded. It also mirrors recommendation reorders to `PATCH /step6/plan`. `ReviewEditStep` auto-fires exec-summary generation on mount when none exists and never calls `/review/edit`.

`TaskPlannerStep` can push rows into Trinity Tasks: it resolves `primary_advisor_id` off `GET /api/engagements/{id}`, deletes existing tasks with `module_reference === 'BBA'` when re-exporting, dispatches `createTask` per row (`moduleReference: 'BBA'`, `taskType: 'manual'`, client-owned rows left unassigned), then fires `PATCH /tasks/export-status?exported=true`.

#### 7. Access control

`get_current_user` on every endpoint. Beyond that there are **two rules**:

- **Creator-only** — every step, generation, save, file-download, task-planner and slide-CRUD endpoint checks `bba.created_by_user_id != current_user.id` → 403. A co-advisor on the same engagement cannot even `GET` the project.
- **Creator-or-engagement** — only three endpoints call `_check_bba_access` (`upload_poc.py:76-95`), which additionally allows anyone passing `check_engagement_access(engagement, user, db)`: `POST /export/docx`, `POST /tasks/export/excel`, `POST /presentation/export/pptx`.

`POST /create-from-diagnostic` checks engagement access on the diagnostic's engagement before creating. **`POST /create-project?engagement_id=` does not** — any authenticated user can create a BBA row against any engagement id (they can then only see their own row, so the impact is a stray row, not a data leak).

`check_engagement_access` (`backend/app/services/role_check.py:10-90`) is the shared gate described in *Authentication, Authorization & Impersonation*.

#### 8. Gotchas

- **Step-7 AI edits are silently dropped.** `step7_review_edit.md` tells the model to return `{updated_sections: {...}, changes_made, warnings}`, but `upload_poc.py:1282-1283` passes the whole parsed object into `BBAService.apply_edits`, which only looks for *top-level* `draft_findings` / `expanded_findings` / `snapshot_table` / `twelve_month_plan` / `executive_summary`. Nothing matches, so the endpoint returns 200 with `changes_made` populated and writes nothing. No frontend calls it today.
- **Exec-summary edits never persist.** `ReviewEditStep.saveSummary()` only calls `setProject(...)` locally (`ReviewEditStep.tsx:188-192`) — there is no PATCH. Refresh and the edit is gone; the exported DOCX uses the last AI-generated text.
- **`PATCH /step6/plan` drops `timeline_summary`.** It rebuilds `twelve_month_plan` as `{plan_notes, recommendations}` only (`upload_poc.py:1213-1223`), so the first plan edit deletes the timeline data and the DOCX's Implementation Timeline table disappears.
- **`step5-6/generate-parallel` runs two LLM calls with `asyncio.gather` and no partial-failure handling** (`upload_poc.py:1136-1139`). If the plan call throws, the snapshot result is discarded too and nothing is saved.
- **The snapshot table has two shapes in the wild.** The AI returns `{snapshot_table:{title, rows}}`; `PATCH /step5/save` writes `{**existing, snapshot_table:{**inner, rows}}`. The DOCX exporter unwraps both, but `BBAPresentationService._build_user_content` reads `snapshot.get("rows")` only (`bba_presentation_service.py:349-350`), so the presentation prompt almost always sees "Not available." for the snapshot section.
- **PPTX export 400s when no slide is approved.** The UI disables the button at `approvedCount === 0`, but the API contract is easy to trip from anywhere else.
- **The Excel export regenerates tasks from scratch** when `task_planner_tasks` is empty (`upload_poc.py:1710-1733`), so a download can trigger a multi-minute LLM call inside the request.
- **There is no delete endpoint.** `BBAService.delete_bba()` exists and does a *hard* `db.delete()`, but no route calls it; `is_deleted` is only ever read.
- **`create-from-diagnostic` re-links rather than creating** when a BBA for the same engagement has `max_step_reached >= 2`, mutating `diagnostic_id` and `diagnostic_context` on the existing row. `force_new=true` instead wipes that row in place (`_reset_bba`, `bba_service.py:127-178`) — same id, all step data gone, no backup.
- **`GET /api/poc` vs `GET /api/poc/`.** The list route is registered at `/api/poc/`; the frontend calls it without the trailing slash and relies on FastAPI's 307 redirect.

---

### Strategy Workbook

#### 1. Purpose

An advisor uploads a client's strategy-workshop material and the tool extracts fourteen structured strategy sections (visioning, business model, market segmentation, Porter's, PESTEL, SWOT, customer/product/competitor analysis, Ansoff growth, financial targets, risks, priorities, actions) and writes them into Benchmark's Strategy Workshop Excel template, preserving its formatting, dropdowns and the Ansoff matrix image. The output is a prefilled `.xlsx` the advisor takes into the workshop.

#### 2. Step-by-step workflow

All paths are prefixed `/api/strategy-workbook` (router prefix `/strategy-workbook`, mounted with `prefix="/api"` at `backend/app/main.py:101`).

| Step | What the advisor does | Endpoint(s) | AI prompt used | What gets persisted |
|---|---|---|---|---|
| 0 | Launch | `POST /create-project?engagement_id=` or `POST /create-from-diagnostic?diagnostic_id=&force_new=` | — | new `strategy_workbooks` row, `status='draft'` |
| 1 | Upload documents (max 20 per call) | `POST /upload` (multipart, `files[]` + optional `workbook_id` form field) | — | `Media` rows via `FileService.upload_files(upload_to_openai=True)` (bytes land in `backend/files/uploads/users/{user_id}/`); ids appended to `uploaded_media_ids`. With no `workbook_id`, a new workbook is created |
| 1b | Automatic suitability check right after upload | `POST /precheck` | `strategy-workbook/precheck_prompt.md` | **nothing** — result returned to the client only |
| 2 | Answer any clarification questions, then extract | `POST /extract` with `{workbook_id, clarification_notes?}` | `extraction_prompt.md` then `formatting_prompt.md` | `extracted_data`; `status` `extracting` → `ready` (or `failed`) |
| 3 | Review the 14 accordion sections, add review notes, generate | `POST /generate` with `{workbook_id, review_notes?}` | — (deterministic openpyxl mapping) | `notes`, `generated_workbook_path`, `status='completed'`, `completed_at` |
| 4 | Download | `GET /{workbook_id}/download` | — | — |
| any | Fetch / list | `GET /{workbook_id}`, `GET /?engagement_id=` | — | — |

#### 3. Data model — `strategy_workbooks` (`backend/app/models/strategy_workbook.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `engagement_id` | UUID FK → `engagements` ON DELETE **SET NULL** | nullable |
| `diagnostic_id` | UUID FK → `diagnostics` ON DELETE SET NULL | |
| `created_by_user_id` | UUID FK → `users` ON DELETE SET NULL, **nullable** | |
| `diagnostic_context` | JSONB | `{report_html?, ai_analysis?}` |
| `status` | varchar(50), default `'draft'`, indexed | see below |
| `uploaded_media_ids` | `ARRAY(UUID)` | a Postgres array of `media.id`, not JSONB |
| `template_path` | text | declared, **never written** |
| `generated_workbook_path` | text | absolute path of the produced xlsx |
| `drive_file_id` | text | declared, never written — part of the dead Google Drive surface described in *Environments, Configuration & Deployment* |
| `extracted_data` | **JSONB** | the 14-key normalised object |
| `notes` | text | advisor review notes |
| `is_deleted` | bool, default false | filtered in every read, never set |
| `created_at`, `updated_at`, `completed_at` | timestamps | |

**`status` progression:** `draft` → `extracting` → `ready` → `completed`. A failed extraction sets `failed` and re-raises (`strategy_workbook_service.py:348-352`).

**Gotcha:** the model comment and `StrategyWorkbookResponse.status` both describe `"draft, extracting, ready, failed"` — they omit `completed`, which `POST /generate` writes (`backend/app/api/strategy_workbook.py:400`). The frontend type does include it (`frontend/src/store/slices/strategyWorkbookReducer.ts:10`).

`extracted_data` is always run through `StrategyWorkbookService._normalize_extracted_data` (`strategy_workbook_service.py:468-526`), which guarantees all 14 keys plus `clarification_questions`, and fills the four SWOT quadrants, the seven risk categories (`legal, financial, operations, people, sm, product, other`) and `financial_targets.{current_fy,next_fy}`.

#### 4. AI calls

Three calls, all in `backend/app/services/strategy_workbook_service.py`.

File routing is repeated verbatim in `extract_data` and `precheck_workbook`, keyed off `media.file_extension`: `pdf` → `file_ids`; `csv/txt/text/md/markdown/json/xml/yaml/yml/xlsx/xls` → `code_interpreter` container; `png/jpg/jpeg/gif/webp/zip` → **dropped with a log line**; anything else → container. Media without an `openai_file_id` is skipped; if nothing usable remains, a `ValueError` becomes a 400.

| Call | Prompt | Model | Output cap / params | Shape |
|---|---|---|---|---|
| Precheck | `precheck_prompt.md` | `ANTHROPIC_MODEL` | `reasoning_effort="low"`, `max_output_tokens=2000`, files attached | `{status: "ok"\|"needs_clarification", clarification_questions:[str], issues:[str], message}` |
| **Step 1 — raw extraction** | `extraction_prompt.md` | `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP1 or ANTHROPIC_MODEL` (`:256`) | `max_output_tokens=32000`, files attached | **free text**, via `generate_completion` (not JSON mode); the prompt explicitly tells the model not to worry about JSON validity |
| **Step 2 — JSON normalisation** | `formatting_prompt.md` | `ANTHROPIC_MODEL_STRATEGY_WORKBOOK_STEP2 or ANTHROPIC_MODEL` (`:304`) | `ANTHROPIC_MAX_TOKENS_STRATEGY_WORKBOOK_STEP2` (`:305`), else `ANTHROPIC_MAX_TOKENS` **capped to 16000 for any model name containing `sonnet`, or 8192 for `haiku`**; `reasoning_effort="low"`; **no files attached** (`:304-324`) | the 14-key object |

The split is deliberate: step 1 reads the documents and optimises for completeness; step 2 never sees the documents and only cleans, type-coerces and fills missing keys. Advisor clarification answers are appended as a third message in step 1 with an explicit instruction that document facts override advisor notes.

`extracted_data` schema (from `formatting_prompt.md` and `_normalize_extracted_data`): `visioning{13 string fields}`, `business_model{6}`, `market_segmentation[]`, `porters_5_forces[]`, `pestel[]`, `swot{strengths,weaknesses,opportunities,threats}`, `customer_analysis[]`, `product_analysis[]`, `competitor_analysis[]`, `growth_opportunities[]`, `financial_targets{current_fy{revenue,gross_profit,net_profit}, next_fy{…}}`, `risks{7 categories}`, `strategic_priorities[]`, `key_actions[]`, plus `clarification_questions[]` (specified in `extraction_prompt.md`, absent from `formatting_prompt.md`'s schema, defaulted to `[]` by the normaliser).

#### 5. Exports

Single output: `.xlsx`, via `openpyxl`, built by `backend/app/services/strategy_workbook_exporter.py` **from a real template** — the only one of the six exporters in this section that uses one: `backend/files/templates/strategy-workbook/Strategy Workbook Template.xlsx` (~41 KB). A missing template raises `FileNotFoundError` in the constructor, surfaced as a 500.

The exporter loads the template's **active** sheet and locates each section by scanning **column 1 only, rows 1–500**, for a case-insensitive substring of the header (`_find_section_start`, `strategy_workbook_exporter.py:146-174`): `VISIONING`, `BUSINESS MODEL`, `MARKET SEGMENTATION`, `PORTERS 5 FORCES`, `PESTEL`, `SWOT`, `CUSTOMER ANALYSIS`, `PRODUCT ANALYSIS`, `COMPETITOR ANALYSIS`, `GROWTH OPPORTUNITIES - ANSOFF`, `FINANCIAL TARGET`, `RISKS`, `STRATEGIC PRIORITIES`, `KEY ACTIONS`. Values are written with `_safe_set_value`, which redirects writes on merged cells to the merge range's top-left cell; SWOT and the other list sections insert formatted rows when the extracted items exceed the template's slots, shifting anchored images to match.

After `wb.save()` the bytes are post-processed: `_patch_ansoff_image_xml` (`:461`) rewrites the drawing XML inside the saved zip so the Ansoff matrix image anchors to the right of the Notes column in the growth section — openpyxl discards Python-level anchor mutations at save time, so the zip is patched directly.

Output is written to `backend/files/uploads/strategy-workbook/{workbook_id}/Strategy_Workshop_Workbook.xlsx` and the absolute path stored in `generated_workbook_path`. `GET /{workbook_id}/download` serves it as a `FileResponse` named `Strategy_Workshop_Workbook.xlsx`.

#### 6. Frontend

| Concern | Location |
|---|---|
| Page | `frontend/src/pages/dashboard/StrategyWorkbookPage.tsx` |
| Step components | `frontend/src/components/strategy-workbook/UploadStep.tsx`, `ClarifyStep.tsx`, `ExtractStep.tsx`, `GenerateStep.tsx` |
| Section display order | `frontend/src/components/strategy-workbook/sectionConfig.ts` (`WORKBOOK_SECTION_ORDER`, 14 key→label pairs; `clarification_questions` deliberately excluded and rendered separately) |
| Redux slice | `frontend/src/store/slices/strategyWorkbookReducer.ts`, mounted as `strategyWorkbook`. Thunks: `uploadDocuments`, `precheckWorkbook`, `extractData`, `generateWorkbook`, `getWorkbook`; reducers `clearError`, `clearWorkbook`, `setReviewNotes`, `setClarificationNotes`, `setClarificationAnswer` |
| Routes | `/dashboard/engagements/:engagementId/strategy-workbook` and `/dashboard/ai-tools/strategy-workbook` (`frontend/src/App.tsx:83,88`) |
| Launcher | `frontend/src/hooks/useToolLaunchers.ts:180-215` (`launchSwWorkbook` / `runStrategyWorkbook`) |

The visible stepper has three phases (Upload / Extract / Generate); `clarify` is an internal fourth state folded into "Extract" (`visibleStep` mapping in `StrategyWorkbookPage.tsx:203-206`). `getCurrentStep()` derives the active step from `currentWorkbook.status` plus `uploadedFiles.length`, with an explicit branch for a reloaded `draft` whose files exist server-side (`uploaded_media_ids` non-empty) but whose Redux `uploadedFiles` array is empty.

`extractData` composes `clarification_notes` client-side by zipping `clarificationQuestions[i]` with `clarificationAnswers[i]` into `Q: …\nA: …` blocks and appending the free-text `clarificationNotes`.

After a successful generate, the slice stores the **download URL** into `currentWorkbook.generated_workbook_path` (`strategyWorkbookReducer.ts:357`) — the client-side field no longer matches the server-side absolute path.

#### 7. Access control

Weakest of the three. `get_current_user` gates every endpoint, but:

| Endpoint | Ownership check |
|---|---|
| `POST /create-project` | engagement access, **only if** `engagement_id` is supplied |
| `POST /create-from-diagnostic` | engagement access on the diagnostic's engagement |
| `POST /upload` | **none** — any authenticated user may attach files to any `workbook_id` |
| `POST /extract`, `POST /precheck`, `POST /generate` | **none** |
| `GET /{workbook_id}` | **none** — returns the full `extracted_data` |
| `GET /{workbook_id}/download` | creator, or `check_engagement_access` on the linked engagement (`strategy_workbook.py:487-498`) |
| `GET /` (list) | scoped to `current_user.id` |

#### 8. Gotchas

- **Any authenticated user can read or mutate any workbook by id.** Only `/download` is guarded. This is the most important finding in this tool.
- **A prompt edit needs a process restart.** The three prompts are `lru_cache`d and loaded in the constructor (`strategy_workbook_service.py:31-33`) — unlike BBA and SBP, where prompt files are re-read per call.
- **`POST /generate` requires `status == 'ready'` and sets it to `'completed'`.** Re-generating afterwards returns 400 (*"Workbook status must be 'ready' to generate"*). There is no re-generate path short of re-running `/extract`.
- **Images and zips are silently dropped** before precheck and extraction. An advisor who uploads scanned pages as PNGs gets a workbook built from whatever is left, with only a server log line to explain it.
- **Section lookup is a text scan of column 1.** Renaming or re-wording a header in `Strategy Workbook Template.xlsx` makes that section silently skip mapping — no error, just empty cells. `GROWTH OPPORTUNITIES - ANSOFF` must match in full or the Ansoff image is not repositioned.
- **Precheck `issues` never reach the UI.** The service returns `{status, clarification_questions, issues, message}` but `StrategyWorkbookPrecheckResponse` (`backend/app/schemas/strategy_workbook.py:67-72`) has no `issues` field, so FastAPI drops it.
- **The upload size limit is 10 MB**, enforced client-side in `UploadStep.tsx:27` and server-side by `FileService.MAX_FILE_SIZE`. The server check is `if hasattr(file, 'size') and file.size and …` (`backend/app/services/file_service.py:69`), so an upload with no reported size bypasses it.
- **`create-from-diagnostic?force_new=true` deletes the previously generated xlsx from disk** and nulls `extracted_data`, `uploaded_media_ids`, `notes`, `template_path`, `generated_workbook_path`, `completed_at`, and reassigns `created_by_user_id` to the caller.

---

### Strategic Business Plan (SBP)

#### 1. Purpose

An advisor uploads a completed Strategy Workbook and supporting materials, the tool runs a cross-pattern analysis across all documents, then drafts fourteen plan sections one at a time with per-section revise/edit/approve/skip control, and assembles them into a Strategic Business Plan `.docx`. Two optional outputs follow: a trimmed employee-facing strategy document and a PowerPoint deck.

#### 2. Step-by-step workflow

All paths are prefixed `/api/strategic-business-plan` (router prefix + `prefix="/api"` at `backend/app/main.py:102`). The UI has six steps (`STEP_LABELS`, `frontend/src/pages/dashboard/StrategicBusinessPlanPage.tsx:21-28`).

| Step | What the advisor does | Endpoint(s) | AI prompt used | What gets persisted |
|---|---|---|---|---|
| 0 | Launch | `POST /create?engagement_id=` or `POST /create-from-diagnostic?diagnostic_id=&force_new=` | — | new row, `status='draft'`, `current_step=1`, `max_step_reached=1` |
| 1 | Upload documents, autofill and save background info | `POST /{plan_id}/upload`, `GET /{plan_id}/extract-setup`, `POST /{plan_id}/setup` | inline system prompt in `SBPConversationEngine.extract_setup` | `file_ids`, `file_mappings`, `stored_files`, `status='uploading'`; then `client_name`, `industry`, `planning_horizon`, `target_audience`, `additional_context` |
| 1b | Wipe and start again | `POST /{plan_id}/reset` | — | everything generated cleared, `status='draft'`, steps → 1 |
| 2 | Run cross-analysis; edit it and add advisor notes | `POST /{plan_id}/cross-analysis`, `PATCH /{plan_id}/cross-analysis` | `strategic-business-plan/system_prompt.md` + `cross_analysis.md` | `cross_analysis`, `cross_analysis_advisor_notes`, `status='analysing'` |
| 3 | Initialise the 14 sections; per section draft → revise → edit → approve or skip; reorder; surface themes | `POST /{plan_id}/initialise-sections`, `POST /{plan_id}/draft-section/{section_key}`, `POST /{plan_id}/revise-section/{section_key}`, `PATCH /{plan_id}/section/{section_key}`, `POST /{plan_id}/approve-section/{section_key}`, `POST /{plan_id}/skip-section/{section_key}`, `POST /{plan_id}/skip-pending-sections`, `PATCH /{plan_id}/reorder-sections`, `POST /{plan_id}/surface-themes` | `section_{key}.md`, `revision.md`, `emerging_themes.md` | `sections[]`, `current_section_index` (set to 0 only), `emerging_themes`, `status='drafting'` |
| 4 | Assemble the plan | `POST /{plan_id}/assemble` (optional `{section_order}`) | — | `final_plan`, `status='reviewing'` |
| 5 | Download the plan; optionally build, edit and download the employee variant | `GET /{plan_id}/export/docx`, `GET /{plan_id}/employee-plan`, `POST /{plan_id}/employee-plan`, `GET /{plan_id}/export/employee-docx` | — | `employee_plan` (persisted); `generated_report_path` / `status='completed'` **assigned but not committed** — see Gotchas |
| 6 | Generate and download the deck | `POST /{plan_id}/presentation/generate`, `GET /{plan_id}/presentation/export` | inline prompt in `SBPPresentationService` | `presentation_slides` |
| any | Wizard position / backward navigation | `PATCH /{plan_id}/step-progress`, `POST /{plan_id}/reset-from-step/{completed_step}` | — | `current_step`, `max_step_reached`, plus cascade clears |
| any | Fetch / list | `GET /{plan_id}`, `GET /?engagement_id=` | — | — |

Upload constraints (`backend/app/api/strategic_business_plan.py:52-53`): per-file 100 MB, extension allowlist `.pdf .docx .xlsx .xls .pptx .txt .csv .png .jpg .jpeg`, no cap on file count. Bytes are stored as `backend/files/uploads/sbp/{plan_id}/{uuid}{ext}`.

#### 3. Data model — `strategic_business_plans` (`backend/app/models/strategic_business_plan.py`)

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `engagement_id` | UUID FK → `engagements` ON DELETE CASCADE | nullable |
| `diagnostic_id` | UUID FK → `diagnostics` ON DELETE SET NULL | |
| `diagnostic_context` | JSONB | `{report_html?, ai_analysis?}` |
| `created_by_user_id` | UUID FK → `users` ON DELETE CASCADE, NOT NULL | never used for authorisation |
| `status` | varchar(50), default `'draft'`, indexed | `draft → uploading → analysing → drafting → reviewing → completed`; the comment also lists `exporting`, which nothing writes, and `completed` is never committed |
| `current_step` / `max_step_reached` | int, nullable | `SBPStepProgressUpdate` validates `ge=1, le=6` |
| `client_name`, `industry`, `planning_horizon`, `target_audience`, `additional_context` | varchar/text | Step 1; `planning_horizon` is a free string in the schema — only the model comment and the extractor's normaliser mention `1-year`/`3-year`/`5-year` |
| `file_ids`, `file_mappings`, `stored_files` | JSONB | `file_mappings` values may be `null` when the Claude upload failed |
| `file_tags` | JSONB | declared, returned by `to_dict()`, read by the Redux slice, **never written by any endpoint** — dead |
| `cross_analysis` | **JSONB** | `{recurring_themes[], tensions[], correlations[], data_gaps[], preliminary_observations[]}` |
| `cross_analysis_advisor_notes` | text | |
| `sections` | **JSONB array** | see per-section shape below |
| `current_section_index` | int | set to `0` by `initialise-sections`, `None` by resets; never advanced |
| `emerging_themes` | **JSONB** | `{themes:[{theme, description, supporting_sections[], signal_strength}], summary}` |
| `final_plan` | **JSONB** | `{sections[], client_name, industry, planning_horizon, target_audience, assembled_at}` |
| `report_version` | int, default 1 | never incremented |
| `generated_report_path`, `generated_employee_report_path` | text | assigned in the exporter but not committed — see Gotchas |
| `employee_variant_requested` | bool, default false | only ever reset to false |
| `employee_plan` | **JSONB** | `{sections:[{key, title, content, included}]}` |
| `presentation_slides` | **JSONB** | `{slides:[…]}` |
| `conversation_history`, `ai_model_used`, `ai_tokens_used` | JSONB / varchar / int | declared, never written |
| `is_deleted`, `created_at`, `updated_at`, `completed_at` | | `is_deleted` filtered in every read, never set |

**The 14 default sections** — `DEFAULT_SECTIONS`, `backend/app/services/sbp_service.py:18-33`, mirrored client-side in `frontend/src/components/strategic-business-plan/sectionConfig.ts` (`PLAN_SECTIONS`) with behaviour flags:

| # | `key` | `title` | Required | Strategic implications | Surface themes after |
|---|---|---|---|---|---|
| 1 | `executive_summary` | Executive Summary | yes | no | no |
| 2 | `strategic_intent` | Strategic Intent Overview | yes | no | no |
| 3 | `business_context` | Business and Context Overview | yes | no | no |
| 4 | `external_internal_analysis` | External and Internal Analysis | yes | **yes** | **yes** |
| 5 | `key_resources_capabilities` | Key Resources and Capabilities | no | no | no |
| 6 | `customer_dynamics` | Customer Dynamics | no | no | no |
| 7 | `growth_opportunities` | Growth Opportunities and Strategic Direction | yes | **yes** | no |
| 8 | `operations_strategy` | Operational Strategy | no | no | no |
| 9 | `hr_strategy` | HR Strategy | no | no | no |
| 10 | `marketing_sales_strategy` | Marketing and Sales Strategy | no | no | no |
| 11 | `financial_overview` | Financial Overview | yes | no | no |
| 12 | `risk_matrix` | Risk Matrix and Analysis | yes | no | no |
| 13 | `actions_next_steps` | Actions List (Implementation Plan) | yes | no | no |
| 14 | `strategic_alignment` | Integrated Strategic Implications and Alignment | no | no | no |

Each entry is created by `_blank_section()` (`sbp_service.py:36-48`) as:

```json
{
  "key": "executive_summary",
  "title": "Executive Summary",
  "status": "pending",
  "content": null,
  "strategic_implications": null,
  "revision_notes": null,
  "revision_history": [],
  "approved_at": null,
  "draft_count": 0
}
```

**Per-section lifecycle** (written by `SBPConversationEngine` and `SBPService`):

| From | Action | To | Side effects |
|---|---|---|---|
| `pending` | `POST /draft-section/{key}` | `drafting` → `drafted` | `content`, `strategic_implications` set; `draft_count += 1`; any previous content pushed onto `revision_history` |
| `drafted` | `POST /revise-section/{key}` | `revision_requested` → `drafted` | `revision_notes` set then cleared; old content + notes + timestamp appended to `revision_history`; `draft_count += 1` |
| `drafted` | `PATCH /section/{key}` | unchanged | `content` / `strategic_implications` overwritten in place, **no history entry, no `draft_count` bump** |
| any | `POST /approve-section/{key}` | `approved` | `approved_at` = ISO now; `revision_notes` cleared |
| any | `POST /skip-section/{key}` | `skipped` | excluded from `final_plan` at assembly |
| `pending` | `POST /skip-pending-sections` | `skipped` | bulk; only touches `pending` |

`revision_history` entries are `{content, strategic_implications, timestamp}` from drafting and `{content, strategic_implications, revision_notes, timestamp}` from revision. Nothing reads it back — there is no restore-a-previous-version endpoint or UI.

**`reset-from-step/{completed_step}`** (`sbp_service.py:436-483`) is the backward-navigation invalidator. It sets `current_step = max_step_reached = completed_step + 1` and clears:

| `completed_step` | Cleared |
|---|---|
| ≤ 1 | `cross_analysis`, advisor notes, all section content (`_reset_sections` → status `pending`, content/implications/notes null, history `[]`, `draft_count` 0, `current_section_index` null), `final_plan`, `emerging_themes`, `generated_report_path`, `presentation_slides` |
| 2 | all section content, `final_plan`, `emerging_themes`, `generated_report_path`, `presentation_slides` |
| 3 | `final_plan`, `generated_report_path`, `presentation_slides`; `status='drafting'` |
| 4 | `generated_report_path`, `presentation_slides` |
| ≥ 5 | nothing cleared; only the step counters move |

**Gotcha:** `reset_from_step` sets `max_step_reached = completed_step + 1` unconditionally, so it *lowers* it — the intent is to force a redo — while `update_step_progress` uses `max(…)` and never lowers it (`sbp_service.py:498`). The two writers disagree about the invariant.

#### 4. AI calls

`backend/app/services/sbp_conversation_engine.py`. Every call funnels through `_call_claude(system_prompt, user_prompt, plan)`, which uses `generate_json_completion` with **no `model`, no `reasoning_effort` and no `max_output_tokens`** — so all SBP generation runs on the service defaults with the full 128k output cap, and the system prompt goes through the legacy single-cached-block path rather than the two-block cached path BBA uses.

File routing (`_separate_files_by_type`, `sbp_conversation_engine.py:62-90`) is three-way, unlike BBA's two-way: ids that do not start with `file_` are skipped entirely; `.pdf` → document blocks; `csv/txt/text/md/markdown/json/xml/yaml/yml/xlsx/xls` → `code_interpreter` container; **everything else (DOCX, PPTX, images) is text-extracted locally** with `python-docx` / `python-pptx` from `backend/files/uploads/sbp/{plan_id}/…` and appended to the user prompt under `## Extracted Document Content`. Images become the literal string `[Image attached: name.png]`.

`_call_claude` retries up to 3 times (2 s then 4 s backoff) but **only** when files are attached and the error string contains `"500"` — covering Claude files not yet being ready (`:229-267`).

| Call | Prompt file(s) | Fallback | Returned keys |
|---|---|---|---|
| `extract_setup` | none — inline system prompt | — | `clientName, industry, planningHorizon, targetAudience, additionalContext`; horizon normalised to `1-year`/`3-year`/`5-year`, defaulting to `3-year` |
| `perform_cross_analysis` | `system_prompt.md` + `cross_analysis.md` | `_default_cross_analysis_prompt()` | `recurring_themes[]`, `tensions[]`, `correlations[]`, `data_gaps[]`, `preliminary_observations[]`; `_strip_html_from_cross_analysis` then scrubs tags from every string before persisting |
| `draft_section` | `system_prompt.md` + `section_{key}.md` | `_default_section_prompt(key)` | `{content: "<html>", strategic_implications: "<html>" or null}` |
| `revise_section` | `system_prompt.md` + `revision.md` | `_default_revision_prompt()` | same |
| `surface_emerging_themes` | `system_prompt.md` + `emerging_themes.md` | `_default_emerging_themes_prompt()` | `{themes[], summary}` |
| presentation | inline, in `SBPPresentationService` | — | a **JSON array** of slides |

All fourteen `section_*.md` files exist in `backend/files/prompts/strategic-business-plan/`, so the `_default_*` fallbacks are dead paths in practice — they exist so a missing file cannot 500 mid-workflow.

User prompts are built with Python `str.format()` over the prompt file. Injected keys differ per call: cross-analysis gets `client_name, industry, planning_horizon, target_audience, additional_context, file_references, diagnostic_context, custom_instructions`; section drafting adds `cross_analysis, advisor_notes, emerging_themes, approved_sections`; revision gets `section_title, current_content, revision_notes, client_name, industry, planning_horizon`; emerging themes gets `client_name, industry, approved_sections, cross_analysis`.

`_get_approved_sections_context` feeds only sections with `status == "approved"` into later drafts, so approving matters for continuity, not just bookkeeping. `system_prompt.md` enforces: British English; bold for headings only; 150–300 words per section; `[REQUIRES CONFIRMATION]` placeholders instead of invention; Strategic Implications only on External and Internal Analysis and Growth Opportunities; and the Executive Summary drafted **after** every other section, even though it is #1 in display order.

#### 5. Exports

| Output | Format | Library | Template | Destination |
|---|---|---|---|---|
| Strategic Business Plan | `.docx` | `python-docx` + `beautifulsoup4` (`backend/app/services/sbp_report_export.py`) | none — programmatic | written to `backend/files/exports/sbp/Strategic_Business_Plan_{Client}_{year}.docx`, served as `FileResponse` |
| Employee Strategy Document | `.docx` | same, `SBPEmployeeExporter(SBPReportExporter)` | none | `backend/files/exports/sbp/Employee_Strategy_Document_{Client}_{year}.docx` |
| Presentation | `.pptx` | `python-pptx` (`sbp_pptx_export.py`) | none — **default python-pptx theme**, `slide_layouts[0]` for `type == "title"` and `[1]` for everything else, 16:9 | `backend/files/exports/sbp/Strategic_Business_Plan_Presentation_{Client}.pptx` |

Unlike BBA, which streams every export, SBP writes its artefacts to disk under `backend/files/exports/sbp/` — which is inside the unauthenticated `/files` static mount. Anyone who can guess the filename can fetch a client's plan.

The main DOCX builds a cover page (STRATEGIC / BUSINESS / PLAN at 36 pt, client name in gold `#C9A227`, `{horizon} Planning Horizon | FY{year}–FY{year+2}`, "Prepared by Benchmark Business Advisory"), a header and footer, a Table of Contents, then one page per section. Section content is HTML from the LLM, converted by `_html_to_docx` via BeautifulSoup with `skip_first_heading=True` so the model's own H1 does not duplicate the chapter title. Each section is preceded by a hard-coded intro paragraph from the `SECTION_INTROS` dict keyed by section key. `executive_summary` renders unnumbered; every other section is numbered sequentially; sections with no `content` are skipped entirely.

The employee exporter renders `plan.employee_plan.sections` where `included` is truthy, falling back to filtering `final_plan.sections` by the employee key list — `executive_summary, strategic_intent, growth_opportunities, operations_strategy, hr_strategy, marketing_sales_strategy` — which is duplicated in `backend/app/api/strategic_business_plan.py:652-659` and in `sbp_report_export.py`.

Filenames are recomputed independently in three places — the exporter, the API's `FileResponse(filename=…)`, and the frontend's `link.download` (`ExportStep.tsx:82-88`) — and agree by coincidence, not by construction.

#### 6. Frontend

| Concern | Location |
|---|---|
| Page | `frontend/src/pages/dashboard/StrategicBusinessPlanPage.tsx` |
| Step components | `SetupUploadStep.tsx` (1), `CrossAnalysisStep.tsx` (2), `SectionDraftingStep.tsx` + `SectionSidebar.tsx` + `SectionEditor.tsx` + `BlockEditor.tsx` (3), `PlanAssemblyStep.tsx` (4), `ExportStep.tsx` + `EmployeeDocumentEditor.tsx` (5), `PresentationStep.tsx` (6) — all under `frontend/src/components/strategic-business-plan/` |
| Section config | `frontend/src/components/strategic-business-plan/sectionConfig.ts` (`PLAN_SECTIONS`) |
| Redux slice | `frontend/src/store/slices/strategicBusinessPlanReducer.ts` (737 lines), mounted as `strategicBusinessPlan`. 23 thunks plus `clearPlan` / `setError`; `extract-setup`, both DOCX exports and the PPTX export are plain `fetch` calls inside components |
| Routes | `/dashboard/engagements/:engagementId/strategic-business-plan` and `/dashboard/ai-tools/strategic-business-plan` (`frontend/src/App.tsx:84,89`) |
| Launcher | `frontend/src/hooks/useToolLaunchers.ts:245-280` (`launchSbp` / `runSbp`) |

`SectionDraftingStep` auto-dispatches `initialiseSections` when `sections` is empty, restores `currentIndex` from `current_section_index`, and auto-dispatches `surfaceThemes` once `external_internal_analysis` reaches `approved` and `emerging_themes` is still null. The theme panel only renders when `currentIndex >= 4`. Reordering is optimistic locally then persisted via `reorderSections`. "Proceed to Plan Assembly" requires every `required: true` section to be `approved` **or** `skipped`; a "skip all remaining" button appears while required sections are still `pending`.

On refresh with an `engagementId` but no navigation state, the page fetches `GET /?engagement_id=` and loads `plans[0]` (most recently updated). Standalone mode runs the same pre-flight against `GET /` and offers Continue / Start New.

#### 7. Access control

`get_current_user` everywhere plus `_check_plan_access(plan, current_user, db)` on every single endpoint (`backend/app/api/strategic_business_plan.py:64-71`) — the most consistent of the three tools. But note its shape:

```python
def _check_plan_access(plan, current_user, db):
    if plan.engagement_id:
        engagement = db.query(Engagement).filter(...).first()
        if engagement and not check_engagement_access(engagement, current_user, db=db):
            raise HTTPException(403, "Access denied")
```

A plan with `engagement_id = None` (created via `/create` with no engagement, i.e. from `/dashboard/ai-tools/strategic-business-plan`) passes the check for **every authenticated user**. Same if the engagement row is soft-deleted, since `engagement` is then `None` and the guard short-circuits. Unlike BBA and Workbook, `created_by_user_id` is never compared. The list endpoints are still scoped to the caller, so an attacker needs the plan id.

#### 8. Gotchas

- **DOCX export never persists its own side effects.** `SBPReportExporter.generate_docx` assigns `plan.generated_report_path`, `plan.status = "completed"` and `plan.completed_at` (`sbp_report_export.py:342-344`), and `generate_employee_docx` assigns `generated_employee_report_path` — but neither has a DB session and the calling endpoint never commits. `SessionLocal` is `sessionmaker(autocommit=False, autoflush=False)` and `get_db` only calls `db.close()`, so the transaction rolls back. **A plan never reaches `status='completed'` and `generated_report_path` stays null** no matter how many times it is exported.
- **Standalone plans are readable and writable by any logged-in user who knows the id.** See access control above.
- **The presentation service hardcodes a model and bypasses the shared client path.** `SBPPresentationService.generate_slides` calls `self.claude_service.client.messages.create(model="claude-sonnet-4-20250514", max_tokens=4096, …)` directly (`sbp_presentation_service.py:61-66`) — a literal, dated model id that ignores `ANTHROPIC_MODEL`, with no prompt caching and none of the JSON-repair handling described in *AI Layer — Claude Integration & Prompt System*. On a parse failure it silently degrades to a one-slide deck containing only the title.
- **SBP slides have no CRUD.** `SBPPresentationSlideEdit` exists (`backend/app/schemas/strategic_business_plan.py:188`) and is imported by the API module, but **no endpoint uses it**. Slides are generate-then-export, with no edit, approve, reorder or delete. The `approved` flag is written `false` and never read — unlike BBA, the SBP PPTX exporter exports every slide.
- **`file_tags` is dead.** The column exists, `to_dict()` returns it, and the slice reads `action.payload.file_tags` to populate a per-file `tag` (`strategicBusinessPlanReducer.ts:533`) — but no endpoint writes it, so every tag is empty.
- **A failed Claude upload stores a `null` file id.** `POST /{plan_id}/upload` logs a warning, sets `file_mappings[filename] = None`, and still returns 200 with `claude_upload_failed: true` per file. The bytes are on disk and in `stored_files`, but for a PDF that means the document is invisible to every later AI call (`_separate_files_by_type` skips non-`file_`-prefixed ids, and only DOCX/PPTX/images get local extraction). The frontend does not surface the flag.
- **Prompt files are `str.format()` templates.** Every literal `{` and `}` in a prompt file must be doubled; adding a JSON example to a section prompt without doubling the braces raises `KeyError` at draft time.
- **`useToolLaunchers.ts` appends `&force_new=true` to `POST /create`**, which takes no such parameter. FastAPI ignores it, so "start fresh" on an engagement with no diagnostic silently creates an *additional* plan rather than resetting.
- **`PATCH /section/{key}` bypasses history.** Manual edits overwrite `content` with no `revision_history` entry, so the AI draft that preceded an advisor's hand-edit is unrecoverable.
- **`get_plan_by_diagnostic` returns `.first()` with no ordering** (`sbp_service.py:127-135`), so with duplicate rows for one diagnostic the "existing" plan returned by `create-from-diagnostic` is non-deterministic — and with `force_new=true` an arbitrary one gets wiped.
- **Section-position restore is a no-op.** `current_section_index` is only ever set to `0` (initialise) or `None` (reset); `SBPService.update_current_section_index` has no caller and no endpoint, so reopening step 3 always lands on section 1.

---

## 13. AI Tools — Roles Matrix, PD & Scorecard

Two advisor-facing generators built to the same pattern: a numbered stepper page, one Redux slice per tool, a `*_service.py` for persistence, a `*_engine.py` for the Claude calls, and exporter modules that stream an Office file to the browser. Neither writes into the Documents module — exports are generated on demand, streamed, and never stored.

Both routers are registered in `backend/app/main.py:106-107` and carry their own `/api` prefix.

```
backend/app/api/roles_matrix.py   →  /api/roles-matrix   (roles_matrix.py:40)
backend/app/api/pd_scorecard.py   →  /api/pd-scorecard   (pd_scorecard.py:44)
```

All five AI calls across both tools go through `ClaudeService.generate_json_completion(...)` with `reasoning_effort="medium"` and `max_output_tokens=16384`, and none passes a `model`, so all five resolve to `settings.ANTHROPIC_MODEL` — see *AI Layer — Claude Integration & Prompt System* for how that resolution and the client itself work.

**Gotcha — every AI step is `await`ed inside the request handler.** These five endpoints are long-running synchronous HTTP requests with no job record and no polling endpoint; a proxy or browser timeout loses both the result and the tokens spent on it:

```
POST /api/roles-matrix/{matrix_id}/extract                        (roles_matrix.py:310)
POST /api/roles-matrix/{matrix_id}/matrix/generate                (roles_matrix.py:367)
POST /api/pd-scorecard/{build_id}/extract                         (pd_scorecard.py:358)
POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/generate     (pd_scorecard.py:451)
POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/generate  (pd_scorecard.py:581)
```

Neither tool defers work anywhere — see *System Architecture* for the in-process execution model.

---

### 1. Roles & Responsibilities Matrix

#### 1.1 Purpose

Takes position descriptions, pasted notes and a hand-typed staff list and produces the rows of the **"Job Roles"** tab of the client's HR Planning Tool workbook. The export is written into a copy of the real template, so the output is the client's own spreadsheet rather than a lookalike.

The governing rule, stated in the system prompt (`backend/files/prompts/roles-matrix/system_prompt.md:39-40`) and enforced again in code:

> If information is missing, leave the cell blank. Do not estimate, infer or guess — a blank cell is always correct when the source is silent.

Three places back it up: the build prompt forbids `"N/A"`, `"TBC"`, `"-"` and empty strings in favour of `null` (`backend/files/prompts/roles-matrix/build_matrix.md:58-59`); `normalise_row()` coerces every value to trimmed text or `None` and drops unknown keys (`backend/app/services/roles_matrix_service.py:248-270`); and the exporter's `_clean()` writes `None` rather than a placeholder (`backend/app/services/roles_matrix_export.py:205-214`).

`docs/ROLES_MATRIX_TOOL.md` is the pre-existing internal doc for this tool. It is accurate on the schema, the template layout and the AI-call shape. Its drifts are listed under *Gotchas*.

#### 1.2 Step-by-step workflow

The module docstring describes four steps (`roles_matrix.py:5-8`); the UI presents **three** (`frontend/src/pages/dashboard/RolesMatrixPage.tsx:20-24`) because review/edit/export all live inside step 3.

| Step | Advisor action | Endpoints | Prompt | Persisted state |
|---|---|---|---|---|
| — | Land on the page; a matrix row is created immediately (or an existing one is offered) | `POST /api/roles-matrix/create-project?engagement_id=` | — | New `roles_matrices` row, `status='inputs'`, `current_step=1`, `max_step_reached=1` (`roles_matrix_service.py:39-52`) |
| 1 — Inputs | Drag in PDs/notes; type key staff names and titles; paste responsibilities/org-chart text; tick which roles go in the matrix | `POST /api/roles-matrix/{matrix_id}/upload` (multipart, ≤20 files), `PATCH /api/roles-matrix/{matrix_id}/inputs` | none (upload only calls the Files API) | `file_ids`, `file_mappings`, `stored_files`; then `staff`, `included_roles`, `pasted_notes` |
| 2 — Extract | Press "Extract responsibilities"; review the per-person cards | `POST /api/roles-matrix/{matrix_id}/extract` | `system_prompt.md` + `extract_responsibilities.md` | `extracted_responsibilities` (`{people:[…]}`), `status='extracted'`, `ai_tokens_used` accumulated, `ai_model_used` |
| 3 — Matrix | Press "Build matrix"; edit cells in the per-role accordion grid; Save; Export | `POST /api/roles-matrix/{matrix_id}/matrix/generate`, `PATCH /api/roles-matrix/{matrix_id}/matrix`, `POST /api/roles-matrix/{matrix_id}/export/excel` | `system_prompt.md` + `build_matrix.md` (generate only) | `matrix_rows`, `matrix_edited`, `status='matrix_built'` → `'completed'` on export, `completed_at` on first export |
| any | Clicking a stepper pill | `PATCH /api/roles-matrix/{matrix_id}/step-progress` | — | `current_step`, `max_step_reached` (`max()`-merged, `roles_matrix_service.py:228`) |

Full endpoint list (all under `/api/roles-matrix`):

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/roles-matrix/` | List the caller's matrices; optional `?engagement_id=` |
| POST | `/api/roles-matrix/create-project` | Create; optional `?engagement_id=` |
| GET | `/api/roles-matrix/{matrix_id}` | Full record via `to_dict()` |
| DELETE | `/api/roles-matrix/{matrix_id}` | Soft delete (`is_deleted=True`) |
| POST | `/api/roles-matrix/{matrix_id}/upload` | Multipart, `files` field, max 20 |
| PATCH | `/api/roles-matrix/{matrix_id}/inputs` | Staff, included roles, pasted notes |
| POST | `/api/roles-matrix/{matrix_id}/extract` | AI step 2 |
| POST | `/api/roles-matrix/{matrix_id}/matrix/generate` | AI step 3 |
| PATCH | `/api/roles-matrix/{matrix_id}/matrix` | Save edited rows |
| PATCH | `/api/roles-matrix/{matrix_id}/step-progress` | `current_step` / `max_step_reached`, both validated 1–4 (`schemas/roles_matrix.py:54-57`) |
| POST | `/api/roles-matrix/{matrix_id}/export/excel` | Stream the workbook |

Preconditions are enforced server-side, not just in the UI:

| Endpoint | Rejects with 400 when |
|---|---|
| `POST /api/roles-matrix/{matrix_id}/upload` | no files, or more than 20 (`roles_matrix.py:194-203`) |
| `POST /api/roles-matrix/{matrix_id}/extract` | no `file_ids` **and** no `pasted_notes` (`roles_matrix.py:321`), or `staff` empty (`roles_matrix.py:326`) |
| `POST /api/roles-matrix/{matrix_id}/matrix/generate` | no `extracted_responsibilities` (`roles_matrix.py:378`) |
| `POST /api/roles-matrix/{matrix_id}/export/excel` | no `matrix_rows` (`roles_matrix.py:475`) |

A missing prompt file surfaces as 500 "Prompt template not found. Please contact support."; a missing Excel template as 500 "Template file not found." (`roles_matrix.py:337-342`, `484-489`).

#### 1.3 The ten output columns

Defined identically in four places — keep them in sync or the export silently shifts columns: `MatrixRow` (`backend/app/schemas/roles_matrix.py:14-29`), `MATRIX_ROW_KEYS` (`roles_matrix_service.py:17-28`), `ROW_KEYS` (`roles_matrix_export.py:36-47`), and `COLUMNS` in the grid (`frontend/src/components/roles-matrix/MatrixStep.tsx:48-59`).

| Excel col | Header (template row 3) | Row key | Rule |
|---|---|---|---|
| A | Name | `name` | Set **only** on the first row of a person's block; `null` on their other rows |
| B | Role Descriptions | `role_description` | One responsibility per row; wraps in the export |
| C | Time | `time` | Verbatim only if stated (`"1hr per week"`); never estimated |
| D | Priorities | `priorities` | Only if the advisor supplied one |
| E | Retain | `retain` | `"Y"` or `null` — no other value valid |
| F | Gain | `gain` | `"Y"` or `null` |
| G | Lose | `lose` | `"Y"` or `null` |
| H | Action | `action` | e.g. `"Transfer to Mary"`; wraps in the export |
| I | Resp | `resp` | Who owns the action, if stated |
| J | When | `when` | Timing of the action, if stated |

The extraction step emits a *different*, richer shape — `{people:[{name, role_title, responsibilities:[{description, time, priority, retain:bool, gain:bool, lose:bool, action, resp, when, source}]}]}` (`extract_responsibilities.md:30-65`). The build step converts booleans to `"Y"`/`null` and `description` → `role_description` (`build_matrix.md:13-17`). Note `priority` (singular) in extraction becomes `priorities` (plural) in the matrix row.

#### 1.4 Data model — `roles_matrices`

`backend/app/models/roles_matrix.py`; created by `backend/alembic/versions/5cba10191710_add_roles_matrices_table.py`.

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | no | PK, `uuid4` default |
| `engagement_id` | UUID | yes | FK `engagements.id` `ON DELETE SET NULL`, indexed. `NULL` ⇒ standalone |
| `created_by_user_id` | UUID | no | FK `users.id` `ON DELETE CASCADE`, indexed |
| `status` | VARCHAR(50) | no | server default `'inputs'`, indexed. Values: `inputs`, `extracted`, `matrix_built`, `completed` |
| `current_step` | INTEGER | yes | 1–4 per the column comment; UI only uses 1–3 |
| `max_step_reached` | INTEGER | yes | `max()`-merged, never decreases |
| `file_ids` | JSONB | yes | `["file-abc123", …]` — Claude Files API ids, de-duplicated on append |
| `file_mappings` | JSONB | yes | `{"pd.pdf": "file-abc123"}` — merged, not replaced |
| `stored_files` | JSONB | yes | `{"pd.pdf": "<matrix_id>/pd.pdf"}` — relative disk path |
| `staff` | JSONB | yes | `[{"name": "...", "role_title": "..."}]` — full replacement on save |
| `included_roles` | JSONB | yes | Role titles confirmed for the matrix |
| `pasted_notes` | TEXT | yes | Free text |
| `extracted_responsibilities` | JSONB | yes | Step-2 output verbatim from the model |
| `matrix_rows` | JSONB | yes | Ordered list, one dict per row, the ten keys above |
| `matrix_edited` | BOOLEAN | no | default `false`; `true` after `PATCH /api/roles-matrix/{matrix_id}/matrix`. Written and serialised, never read |
| `ai_model_used` | VARCHAR(100) | yes | Last model that produced output |
| `ai_tokens_used` | INTEGER | yes | Running total across both AI steps |
| `is_deleted` | BOOLEAN | no | default `false`; every read filters on it |
| `created_at` / `updated_at` | TIMESTAMP | no | `CURRENT_TIMESTAMP`; `updated_at` also set explicitly in the service |
| `completed_at` | TIMESTAMP | yes | Set **once**, on the first successful export (`roles_matrix_service.py:204-205`) |

Indexes: `ix_roles_matrices_created_by_user_id`, `ix_roles_matrices_engagement_id`, `ix_roles_matrices_status`. Relationship: `Engagement.roles_matrices` (`backend/app/models/engagement.py:60`).

**Uploaded file persistence.** Every uploaded byte-stream is written to `<UPLOAD_DIR>/roles-matrix/<matrix_id>/<sanitised-filename>` (`roles_matrix.py:54-59`, `248-252`). `UPLOAD_DIR` defaults to `"uploads"` (`config.py:62`) and is resolved relative to `backend/` when not absolute, so the default is `backend/uploads/roles-matrix/<matrix_id>/`. This is **not** the `/files` static root: `app.mount("/files", …)` serves `backend/files` only (`backend/app/main.py:110-115`), so nothing under `UPLOAD_DIR` is reachable over HTTP and nothing in the app reads these copies back — they are a forensic trail, not a store. Filenames are stripped to alphanumerics plus `. _ -` and space, then truncated to 200 chars (`_sanitize_filename`, `roles_matrix.py:62-69`). A disk-write failure is logged as a warning and swallowed — the upload still succeeds against the Files API and `stored_files` simply has no entry.

`included_roles` are derived client-side from the staff list: each member's `role_title`, falling back to their `name` when no title is typed, de-duplicated (`frontend/src/components/roles-matrix/InputsStep.tsx`, `roleCandidates`). So a member with no title contributes a *person's name* to a list that is otherwise job titles.

#### 1.5 AI calls

`backend/app/services/roles_matrix_engine.py`. Prompts load from `backend/files/prompts/roles-matrix/<name>.md` at call time via `load_roles_matrix_prompt` (`roles_matrix_engine.py:17-36`); a missing file raises `FileNotFoundError`. There is no caching — an edited prompt takes effect on the next call, no restart needed.

Both calls send **two** cached system blocks — the shared system prompt and the step prompt — each with `cache_control: {"type": "ephemeral"}` (`roles_matrix_engine.py:137-140`, `223-226`).

| Call | Attachments | User-message contents | Reads |
|---|---|---|---|
| `extract_responsibilities` | PDFs as `file_ids`; everything else via a `code_interpreter` tool block with `container.file_ids` | formatted staff list, included roles, pasted notes (or "None supplied"), the raw `file_mappings` JSON, optional advisor `custom_instructions` | `parsed_content` wholesale |
| `build_matrix` | **none** — works purely off `extracted_responsibilities` | included-roles ordering, the extraction JSON, optional `custom_instructions` | `parsed.matrix_rows` |

File routing (`_separate_files_by_type`, `roles_matrix_engine.py:56-91`): `.pdf` → document blocks; `csv txt text md markdown json xml yaml yml xlsx xls doc docx` → Code Interpreter container; anything else logs a warning and falls into the Code Interpreter bucket.

The engine is a module-level singleton (`get_roles_matrix_engine()`, `roles_matrix_engine.py:268-277`), so one `ClaudeService` is constructed per process.

#### 1.6 Export

`POST /api/roles-matrix/{matrix_id}/export/excel` → `RolesMatrixExporter.generate_workbook_bytes()` (`backend/app/services/roles_matrix_export.py:80-107`), streamed as `Roles_and_Responsibilities_Matrix.xlsx` (`roles_matrix.py:503`). The call then runs `service.mark_completed(matrix_id)`.

The exporter opens `backend/files/templates/roles-matrix/HR Planning Tool.xlsx` with openpyxl and edits it in memory. Verified directly against the file: one sheet, `Job Roles`, three merges — `A1:J1`, `A2:J2`, `C38:C43` — and:

```
row 1   A1 = "HR MANAGEMENT PLAN"          (merged A1:J1)
row 2   A2 = "Role Analysis"               (merged A2:J2)
row 3   Name | Role Descriptions | Time | Priorities | Retain | Gain | Lose | Action | Resp | When
row 4+  sample data (last populated row is 68)
```

Rows 1–3 are never touched. The write sequence:

1. `_unmerge_data_region` (`:111-122`) — drops every merged range whose `min_row >= 4`, removing the template's `C38:C43` Time merge; the two banner merges survive because they sit on rows 1–2.
2. `_find_last_styled_row` (`:124-137`) — walks column B from row 4 down while cells still have a bottom border, to learn how far the template's formatting reaches.
3. `_clear_data_region` (`:139-144`) — nulls A4:J`max_row`, leaving formatting intact.
4. `_write_rows` (`:148-170`) — one worksheet row per matrix row from row 4. Past `last_styled_row`, `_copy_row_style` clones `_style` from row 5 (`STYLE_SOURCE_ROW`) plus its row height. Columns B and H (`WRAP_COLUMNS = {2, 8}`) get `wrap_text=True` and have their fixed row height cleared so Excel auto-grows the row.
5. `_fit_columns` (`:184-203`) — width = `max(template width, longest value + 2)`, capped at 60.

**Gotcha:** the template's sheet XML declares 1000 rows, so openpyxl reports `max_row == 1000`. `_clear_data_region` therefore walks A4:J1000 on every export. Harmless but slow, and the produced file carries the same 1000 empty rows.

#### 1.7 Frontend files and routes

| File | Purpose |
|---|---|
| `frontend/src/pages/dashboard/RolesMatrixPage.tsx` | Shell, 3-pill stepper, launch pre-flight, step-progress persistence |
| `frontend/src/components/roles-matrix/InputsStep.tsx` | Four input cards: upload (10 MB per-file client cap), key staff, notes, role checkboxes |
| `frontend/src/components/roles-matrix/ExtractStep.tsx` | Extract button and read-only per-person review cards with Retain/Gain/Lose badges |
| `frontend/src/components/roles-matrix/MatrixStep.tsx` | Build/Rebuild, per-role accordion of editable 9-column tables (Name is a separate field above each table), Save, Export |
| `frontend/src/components/roles-matrix/index.ts` | Barrel export |
| `frontend/src/store/slices/rolesMatrixReducer.ts` | 9 thunks + slice; owns the blob download |
| `frontend/src/hooks/useToolLaunchers.ts` | Engagement-side launcher (`tools.roles_matrix`) |
| `frontend/src/components/engagement/FollowUpToolsTab.tsx` | Engagement row + Continue/Start-Fresh dialog |
| `frontend/src/pages/dashboard/AIToolsPage.tsx` | Standalone grid card (`id: 'roles-matrix'`) |

Routes (`frontend/src/App.tsx:85,90`), both rendering the same component inside `ProtectedRoute` + `DashboardLayout`:

```
/dashboard/engagements/:engagementId/roles-matrix
/dashboard/ai-tools/roles-matrix
```

The nine thunks are `createMatrix`, `getMatrix`, `uploadDocuments`, `saveInputs`, `extractResponsibilities`, `generateMatrix`, `saveMatrixRows`, `updateStepProgress`, `exportMatrix`. State is one `currentMatrix` plus six independent booleans (`isLoading`, `isUploading`, `isExtracting`, `isGenerating`, `isSaving`, `isExporting`) and an `error` string; there is no list state. Auth is a bearer token read from `localStorage.auth_token` on every call. The export thunk hard-codes the download filename `Roles_and_Responsibilities_Matrix.xlsx` client-side (`rolesMatrixReducer.ts:328`) rather than reading `Content-Disposition`, and optimistically sets `status = 'completed'` in the store on success (`:466-470`).

Stepper pills are disabled for any step greater than `max_step_reached` (`RolesMatrixPage.tsx:220`).

#### 1.8 Access control

Every endpoint is wrapped in `require_role(ADVISOR_ROLES)` where `ADVISOR_ROLES = [ADVISOR, ADMIN, SUPER_ADMIN, FIRM_ADMIN, FIRM_ADVISOR]` (`roles_matrix.py:43-49`). `CLIENT` gets a 403 at the router (`backend/app/utils/auth.py:252-269`). Record-level checks run afterwards in `_check_matrix_access` (`roles_matrix.py:84-103`):

1. `matrix.created_by_user_id == current_user.id` → allow, unconditionally.
2. Otherwise, if `matrix.engagement_id` is set, load the non-deleted engagement and defer to `check_engagement_access(engagement, user, db=db)` (`backend/app/services/role_check.py:10`).
3. Otherwise → 403.

So a **standalone** matrix is reachable by its creator and nobody else — not even a super-admin, because there is no engagement to defer to. An **engagement-linked** matrix is additionally reachable by anyone passing `check_engagement_access`. In the engagement UI the row is rendered for clients but the Run button is disabled with an "Advisor only" pill (`FollowUpToolsTab.tsx:134-171`).

#### 1.9 Gotchas

**Gotcha — the list endpoint is narrower than the access check.** `GET /api/roles-matrix/?engagement_id=…` calls `get_matrices_by_engagement(engagement_id, current_user.id)`, which filters on `created_by_user_id` (`roles_matrix_service.py:79-80`). A second advisor on the same engagement can open a colleague's matrix by ID but will never see it listed, and the launcher's pre-flight will offer to create a duplicate instead of continuing it.

**Gotcha — editing after export un-completes the matrix.** `update_matrix_rows` unconditionally sets `status='matrix_built'` (`roles_matrix_service.py:188`), so saving one cell on an exported matrix moves it back from `completed`. `completed_at` stays set, so the two fields disagree.

**Gotcha — the standalone launch can resume an engagement's matrix.** On `/dashboard/ai-tools/roles-matrix` the pre-flight fetches with no `engagement_id` filter (`RolesMatrixPage.tsx:66`), and `get_matrices_for_user` returns every matrix the user owns. The "Continue Existing" card can therefore hand back a matrix that belongs to an engagement.

**Gotcha — landing on the page creates a row.** If the pre-flight finds nothing, the page immediately `POST`s `create-project` (`RolesMatrixPage.tsx:85-98`). Navigating in and straight back out leaves an empty `inputs` matrix behind, which the next pre-flight will then offer to continue.

**Gotcha — the export is server-side and ignores the browser's edits.** The UI blocks Export while `isDirty` (`MatrixStep.tsx:158-162`, `:208`), but the endpoint only checks that `matrix_rows` is non-empty, so a direct API call exports whatever was last saved.

**Gotcha — `docs/ROLES_MATRIX_TOOL.md` drift.** Two claims no longer match the code: it describes `MatrixStep.tsx` as "editable grid, **copy for Excel**, export" — there is no copy-for-Excel control in the component; and its access-control section says a matrix is reachable "by its creator, or by anyone with access to the linked engagement" without noting that a standalone matrix has no engagement and is therefore creator-only, or that the list endpoint additionally filters on creator. Its three-step workflow table also disagrees with the module docstring (`roles_matrix.py:5-8`, four steps) and the `current_step` column comment (1–4).

---

### 2. PD & Role Scorecard

#### 2.1 Purpose

Consumes a completed Roles & Responsibilities matrix and produces, **per role**, a seven-section Position Description (`.docx`) and a matching Half-Yearly Role Scorecard (`.xlsx`). The matrix is the only permitted source of responsibilities; uploaded PDs can be flagged as tone-only references.

The flag semantics that drive everything (`backend/files/prompts/pd-scorecard/system_prompt.md:22-32`):

| Matrix flag | Where it lands |
|---|---|
| `Retain` = "Y" | PD *Key Responsibilities* |
| `Gain` = "Y" | PD *Key Responsibilities*, phrased as a present responsibility |
| `Lose` = "Y" | PD *Transition Focus* and scorecard *Transition Milestones* — **never** Key Responsibilities |
| `Action` / `Resp` / `When` | Wording and target date of the transition milestone |

The prompt also mandates "rewrite tasks as outcomes" (`system_prompt.md:38-40`) — the matrix says "Invoicing", the PD says "Ensure invoices are raised promptly and accurately."

#### 2.2 Build/project model

A **build** (`pd_scorecards`) is the project: one client, one source matrix, one set of shared inputs. Each **role** (`pd_scorecard_roles`) is a child carrying its own two drafts and their independent approval state, so roles are finished one at a time and exported separately. Steps 3 and 4 are therefore not linear phases — they are per-role loops the advisor re-enters for each role. This is why every step-3 and step-4 path carries a `roles/{role_id}` segment: the build id alone never identifies a draft.

#### 2.3 Step-by-step workflow

| Step | Advisor action | Endpoints | Prompt | Persisted state |
|---|---|---|---|---|
| — | Land on the page; a build is created (or an existing one offered) | `POST /api/pd-scorecard/create-project?engagement_id=` | — | New `pd_scorecards` row, `status='inputs'`, `current_step=1`, `max_step_reached=1` |
| 1 — Inputs | Type business name and FY range; upload the matrix (+ optional reference PDs); tick which uploads are tone-only; optionally paste the matrix as text | `POST /api/pd-scorecard/{build_id}/upload`, `PATCH /api/pd-scorecard/{build_id}/inputs` | — | `file_ids`, `file_mappings`, `stored_files`; then `client_name`, `fy_range`, `reference_pd_files`, `pasted_notes` |
| 2 — Roles | "Read the matrix"; correct titles/people; untick roles to exclude; add roles by hand | `POST /api/pd-scorecard/{build_id}/extract`, `PATCH /api/pd-scorecard/{build_id}/roles` | `system_prompt.md` + `extract_roles.md` | `matrix_rows` + `status='roles_identified'`; then child rows created/updated, `status='in_progress'`, each role's `source_responsibilities` cached |
| 3 — Position Description *(per role)* | Pick a role; Generate draft; edit the seven sections; Save; Approve; Download Word | `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/generate`, `PATCH /api/pd-scorecard/{build_id}/roles/{role_id}/pd`, `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/approve`, `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/export` | `system_prompt.md` + `generate_pd.md` | `pd_content`, `pd_status` (`draft` on any save, `approved` on approve), `pd_approved_at` |
| 4 — Scorecard *(per role)* | Pick a role (locked until its PD is approved); Generate; edit; Save; Approve; Download Excel | `POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/generate`, `PATCH /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard`, `POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/approve`, `POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/export` | `system_prompt.md` + `generate_scorecard.md` | `scorecard_content`, `scorecard_status`, `scorecard_approved_at`; build `status`/`completed_at` recomputed |
| any | Clicking a stepper pill | `PATCH /api/pd-scorecard/{build_id}/step-progress` | — | `current_step`, `max_step_reached` |

`GET /api/pd-scorecard/{build_id}/roles` also exists (`pd_scorecard.py:434-446`) but no frontend code calls it — `build.roles` arrives embedded in `GET /api/pd-scorecard/{build_id}`.

Server-side gates:

| Endpoint | Rejects with 400 when |
|---|---|
| `POST /api/pd-scorecard/{build_id}/upload` | no files, or more than 20 (`pd_scorecard.py:242-251`) |
| `POST /api/pd-scorecard/{build_id}/extract` | no `file_ids` **and** no `pasted_notes` (`pd_scorecard.py:369`) |
| `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/generate` | build has no `matrix_rows` (`pd_scorecard_engine.py:223`, surfaced as 400 at `pd_scorecard.py:469-471`) |
| `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/approve` | role has no `pd_content` (`pd_scorecard_service.py:300-301`) |
| `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/export` | `pd_content` empty (`pd_scorecard.py:550`) |
| `POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/generate` | `role.pd_status != 'approved'` (`pd_scorecard.py:594`); the engine also re-checks `pd_content` (`pd_scorecard_engine.py:302-303`) |
| `POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/approve` | role has no `scorecard_content` (`pd_scorecard_service.py:344-345`) |
| `POST /api/pd-scorecard/{build_id}/roles/{role_id}/scorecard/export` | `scorecard_content` empty (`pd_scorecard.py:686`) |

`_get_role_or_404` (`pd_scorecard.py:139-148`) 404s on a role id that belongs to a different build or is soft-deleted.

**Step progress** persists on the parent build only (`current_step`, `max_step_reached`, both validated 1–4 in `schemas/pd_scorecard.py:115-118`, `max()`-merged). Which *role* is being worked on is client-only state (`activeRoleId` in the slice), defaulted to the first `included` role on load (`PDScorecardPage.tsx:117-125`) and never persisted.

**Completion.** `approve_scorecard` calls `_refresh_completion` (`pd_scorecard_service.py:360-381`): if there is at least one `included`, non-deleted role and every one of them has both `pd_status == 'approved'` **and** `scorecard_status == 'approved'`, the build goes `completed` and `completed_at` is stamped once; if the build was `completed` and no longer qualifies, it reverts to `in_progress`.

#### 2.4 Data model

Both tables created by `backend/alembic/versions/50f7a483da0a_add_pd_scorecards_and_pd_scorecard_.py`; models in `backend/app/models/pd_scorecard.py`.

##### `pd_scorecards` (parent)

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | no | PK, `uuid4` default |
| `engagement_id` | UUID | yes | FK `engagements.id` `ON DELETE SET NULL`, indexed |
| `created_by_user_id` | UUID | no | FK `users.id` `ON DELETE CASCADE`, indexed |
| `status` | VARCHAR(50) | no | server default `'inputs'`, indexed. Values: `inputs`, `roles_identified`, `in_progress`, `completed` |
| `current_step` / `max_step_reached` | INTEGER | yes | 1–4 |
| `client_name` | VARCHAR(255) | yes | Centred under the PD title |
| `fy_range` | VARCHAR(50) | yes | e.g. `FY25-27`; appended to the PD's Transition Focus heading and the scorecard's Milestones heading |
| `file_ids` | JSONB | yes | Claude file ids, de-duplicated on append |
| `file_mappings` | JSONB | yes | `{"matrix.xlsx": "file-abc123"}` |
| `stored_files` | JSONB | yes | `{"matrix.xlsx": "<build_id>/matrix.xlsx"}` |
| `reference_pd_files` | JSONB | yes | Filenames flagged tone-only; full replacement on save |
| `pasted_notes` | TEXT | yes | Matrix pasted as text, or extra notes |
| `matrix_rows` | JSONB | yes | Parsed matrix, same ten keys as the Roles Matrix tool (`pd_scorecard_service.py:22-33`) |
| `ai_model_used` / `ai_tokens_used` | VARCHAR(100) / INTEGER | yes | Token total accumulates across **all** role-level generations too (`pd_scorecard_service.py:288`, `332`) |
| `is_deleted` | BOOLEAN | no | default `false` |
| `created_at` / `updated_at` | TIMESTAMP | no | |
| `completed_at` | TIMESTAMP | yes | Set once, when every included role first has both approvals |

Indexes: `ix_pd_scorecards_created_by_user_id`, `ix_pd_scorecards_engagement_id`, `ix_pd_scorecards_status`.

##### `pd_scorecard_roles` (child)

| Column | Type | Null | Notes |
|---|---|---|---|
| `id` | UUID | no | PK, `uuid4` default |
| `pd_scorecard_id` | UUID | no | FK `pd_scorecards.id` **`ON DELETE CASCADE`**, indexed |
| `role_title` | VARCHAR(255) | no | Job title, e.g. "General Manager" |
| `person_name` | VARCHAR(255) | yes | Incumbent, where the matrix names one |
| `sort_order` | INTEGER | no | default `0`; rewritten from list position on every `PATCH /api/pd-scorecard/{build_id}/roles` |
| `included` | BOOLEAN | no | default `true`; excluded roles stay in the table and in `to_dict()` |
| `source_responsibilities` | JSONB | yes | `{"retain": [...], "gain": [...], "lose": [...]}` — this role's matrix rows, cached at role-save time |
| `pd_content` | JSONB | yes | The seven PD sections |
| `pd_status` | VARCHAR(50) | no | default `'not_started'`; `not_started` / `draft` / `approved` |
| `pd_approved_at` | TIMESTAMP | yes | Cleared to `NULL` on every save (`pd_scorecard_service.py:284`) |
| `scorecard_content` | JSONB | yes | The four scorecard sections |
| `scorecard_status` | VARCHAR(50) | no | default `'not_started'`; same three values |
| `scorecard_approved_at` | TIMESTAMP | yes | Cleared to `NULL` on every save (`pd_scorecard_service.py:328`) |
| `is_deleted` | BOOLEAN | no | default `false` |
| `created_at` / `updated_at` | TIMESTAMP | no | |

Indexes: `ix_pd_scorecard_roles_pd_scorecard_id` and the composite `ix_pd_scorecard_roles_parent_order` on `(pd_scorecard_id, sort_order)`.

**Parent ↔ child.** ORM: `PDScorecard.roles` with `cascade="all, delete-orphan"`, `order_by="PDScorecardRole.sort_order"`; `PDScorecardRole.pd_scorecard` back-populates. `PDScorecard.to_dict(include_roles=True)` (the default) embeds only non-deleted roles; the list endpoint passes `include_roles=False`. Deleting a build is a **soft** delete of the parent only (`pd_scorecard_service.py:88-97`) — child rows are untouched and remain in the table, since the `ON DELETE CASCADE` only fires on a real row delete, which the app never issues.

**Role reconciliation** (`replace_roles`, `pd_scorecard_service.py:174-229`): incoming roles carrying an `id` are updated in place so their approved drafts survive; roles without one are inserted; existing roles missing from the payload are **soft deleted**, never hard deleted. The build is forced to `in_progress` on every call.

**Row attribution** (`rows_for_role`, `pd_scorecard_service.py:444-472`): walks `matrix_rows` in order carrying the last non-blank `name` forward (mirroring the "name on the first row of the block" convention), keeps rows whose carried name case-insensitively matches `role_title` **or** `person_name`, requires a non-empty `role_description`, and files each row under every flag whose value starts with `Y` (case-insensitive).

**Uploaded file persistence.** `<UPLOAD_DIR>/pd-scorecard/<build_id>/<sanitised-filename>` — same mechanics, same sanitiser, same unserved location and same swallowed-failure behaviour as the Roles Matrix tool (`pd_scorecard.py:78-93`, `296-302`).

#### 2.5 PD and scorecard content shapes

`PDContent` (`backend/app/schemas/pd_scorecard.py:50-61`) — every section is optional in the schema; the exporter renders only the ones with content:

| Key | Type | Renders as |
|---|---|---|
| `position_purpose` | `str?` | 1. Position Purpose — a paragraph |
| `key_responsibilities` | `[{theme, responsibilities[]}]` | 2. Key Responsibilities — bold theme + bullets |
| `decision_making_authority` | `str[]` | 3. Decision-Making Authority |
| `key_relationships` | `str[]` | 4. Key Relationships |
| `kpis` | `str[]` | 5. Key Performance Indicators (KPIs) |
| `behavioural_expectations` | `str[]` | 6. Behavioural Expectations |
| `transition_focus` | `str[]` | 7. Transition Focus *(+ FY range)* — omitted entirely when empty |

`ScorecardContent` (`schemas/pd_scorecard.py:95-100`) — `role_purpose: str?`, `responsibilities: [{focus_area, core_accountability, performance_indicators}]`, `behaviours: [{behavioural_focus, expected_demonstration}]`, `milestones: [{milestone, target_date}]`. The model produces content only; the rating columns, comment columns, 1–5 dropdowns and summary block are added by the exporter (`generate_scorecard.md:7-8`).

#### 2.6 AI calls

`backend/app/services/pd_scorecard_engine.py`; prompts load from `backend/files/prompts/pd-scorecard/<name>.md` at call time via `load_pd_scorecard_prompt` (`pd_scorecard_engine.py:18-37`), uncached, raising `FileNotFoundError` on a missing file. Same two-cached-system-block pattern and the same PDF/Code-Interpreter file split as the Roles Matrix engine (`pd_scorecard_engine.py:49-86`).

| Call | Attachments | User-message contents | Returns |
|---|---|---|---|
| `extract_roles` | PDFs + CI container from `file_mappings` | client name, pasted notes, the reference-PD note, raw `file_mappings` JSON, `custom_instructions` | `parsed.matrix_rows` and `parsed.roles` |
| `generate_pd` | PDFs + CI container (so reference PDs reach the model for tone) | role title (+ incumbent), client, FY range, this role's grouped matrix rows, the reference-PD note, `custom_instructions` | `parsed.pd_content` |
| `generate_scorecard` | **none** | role, client, FY range, the approved `pd_content` JSON, this role's grouped matrix rows, `custom_instructions` | `parsed.scorecard_content` |

`_reference_pd_note` (`pd_scorecard_engine.py:101-112`) names each flagged file and restates in-prompt: "Never carry a responsibility forward from these. All responsibilities come from the matrix." `_role_context` (`:114-120`) uses the cached `source_responsibilities`, falling back to recomputing `rows_for_role` only when it is `NULL`.

`suggested_roles` from step 2 are returned in the HTTP response only (`pd_scorecard.py:404`) — they are held in Redux (`suggestedRoles`) and never persisted; they seed the editable list only while it is still empty (`RolesStep.tsx:67-79`).

#### 2.7 Exports

Neither exporter uses a template file — both build the document from scratch.

**Position Description → `.docx`** (`backend/app/services/pd_export.py`, python-docx). Body style Calibri 11 (`pd_export.py:19-20`). Title block: centred "Position Description" heading (level 0), bold 14 pt role title, 12 pt client name if present (`:104-120`). Sections are numbered *dynamically* — the counter only advances for sections that have content, so a PD missing e.g. KPIs is numbered 1,2,3,4,5 with no gap (`:66-94`). Themed responsibilities render as a bold paragraph followed by `List Bullet` items; a theme with no responsibilities is skipped even if it has a name (`:133-149`). Transition Focus takes `fy_range` appended to its heading. Filename: `"{role title} - Position Description.docx"` via `_download_name` (`pd_scorecard.py:96-100`), which replaces every character outside `[alnum] -_` with a space and collapses runs.

**Scorecard → `.xlsx`** (`backend/app/services/scorecard_export.py`, openpyxl `Workbook()`). Single sheet `H1-H2 Scorecard`, max nine columns (A–I):

| Rows | Section | Columns | Rating dropdowns |
|---|---|---|---|
| 1–2 | `Role Purpose` label + text (row 2 merged A2:I2 — the only merge in the sheet) | A | — |
| next | `Responsibilities and Outcomes (Half-Yearly Review - Self vs Manager)` | 9: Focus Area, Core Accountability, Performance Indicators / Outcomes, H1 Self, H1 Mgr, H1 Comments, H2 Self, H2 Mgr, H2 Comments | D, E, G, H |
| next | `Behaviour and Leadership Expectations` | 8: Behavioural Focus, Expected Demonstration, then the same six | C, D, F, G |
| next | `Transition Milestones ({fy_range} - Self vs Manager)`, or `Transition Milestones (Self vs Manager)` with no FY range | 8: Milestone, Target Date, then the same six | C, D, F, G |
| last | `Half-Yearly Summary` | A only: "Average Self Rating:", "Average Manager Rating:", "Key Discussion Points / Agreed Actions:" | — |

All three data sections — not just Milestones — are skipped entirely when their list is empty (`scorecard_export.py:149-150`, `172-173`, `194-195`); the writer returns `start_row` unchanged so no heading is emitted. The Summary block always renders.

Dropdowns are `DataValidation(type="list", formula1='"1,2,3,4,5"', allow_blank=True, showDropDown=True)` applied by **column letter over the row range the writer itself just emitted** — deliberately never by matching header text, so a dropdown cannot land on a comments column (`scorecard_export.py:8-10`, `253-275`). Columns A, B and C wrap; per-column minimum widths are hard-coded in `MIN_COLUMN_WIDTHS` (A–I, default 12 for anything else), capped at 60. Row 2 is excluded from the width calculation because it is merged (`:288-291`). Filename: `"{role title} - Role Scorecard - Half-Yearly.xlsx"`.

Both exports are `POST` (not `GET`), and the frontend reads the real filename out of `Content-Disposition` before triggering the blob download (`pdScorecardReducer.ts:167-183`).

#### 2.8 Frontend files and routes

| File | Purpose |
|---|---|
| `frontend/src/pages/dashboard/PDScorecardPage.tsx` | Shell, 4-pill stepper, launch pre-flight, `activeRoleId` defaulting, scroll-to-top on step change |
| `frontend/src/components/pd-scorecard/InputsStep.tsx` | Client details, upload with tone-only checkboxes, paste-the-matrix textarea |
| `frontend/src/components/pd-scorecard/RolesStep.tsx` | "Read the matrix", editable role list with include checkboxes |
| `frontend/src/components/pd-scorecard/PDStep.tsx` | Per-role PD editor: purpose textarea, theme cards, five newline-delimited bullet fields, Save / Approve / Download |
| `frontend/src/components/pd-scorecard/ScorecardStep.tsx` | Per-role scorecard editor: purpose, focus-area cards, behaviour rows, milestone rows, Save / Approve / Download |
| `frontend/src/components/pd-scorecard/RolePicker.tsx` | Shared radio list; `track="pd"` or `"scorecard"`; shows only `included` roles and locks a role on the scorecard track until its PD is approved |
| `frontend/src/components/pd-scorecard/index.ts` | Barrel export |
| `frontend/src/store/slices/pdScorecardReducer.ts` | 15 thunks; `mergeRole()` splices a single updated role back into `currentBuild.roles` (`:623-626`) |
| `frontend/src/hooks/useToolLaunchers.ts` | Engagement-side launcher (`tools.pd_scorecard`) |

Routes (`frontend/src/App.tsx:86,91`):

```
/dashboard/engagements/:engagementId/pd-scorecard
/dashboard/ai-tools/pd-scorecard
```

The fifteen thunks are `createBuild`, `getBuild`, `uploadDocuments`, `saveInputs`, `extractRoles`, `saveRoles`, `generatePD`, `savePD`, `approvePD`, `exportPD`, `generateScorecard`, `saveScorecard`, `approveScorecard`, `exportScorecard`, `updateStepProgress`. State (`pdScorecardReducer.ts:133-145`) is `currentBuild`, `suggestedRoles`, `activeRoleId`, seven booleans (`isLoading`, `isUploading`, `isExtracting`, `isGeneratingPD`, `isGeneratingScorecard`, `isSaving`, `isExporting`) and `error`.

Bullet lists are edited as one item per line and round-tripped through `toLines`/`fromLines` (`PDStep.tsx:54-59`), which trim and drop blank lines. Draft state is keyed on `role.id` + `role.updated_at` rather than on content, so the editor does not clobber in-flight typing (`PDStep.tsx:100-104`). Both editors compute `isDirty` by `JSON.stringify` comparison against the server copy and gate the download on `status === 'approved' && !isDirty` (`PDStep.tsx:115-122`, `ScorecardStep.tsx:80-88`). Approving always saves first, so approval covers what is on screen (`PDStep.tsx:144-155`, `ScorecardStep.tsx:112-124`). Exporting a scorecard automatically calls `onBack()` to return the advisor to the PD step to pick the next role (`ScorecardStep.tsx:126-139`).

#### 2.9 Access control

`backend/app/api/pd_scorecard.py:46-73` splits the role list into three, all currently identical to the advisor set (`ADVISOR, ADMIN, SUPER_ADMIN, FIRM_ADMIN, FIRM_ADVISOR`):

| List | Covers | Intended future use (per the in-code comment) |
|---|---|---|
| `BUILD_SETUP_ROLES` | create, delete, upload, inputs, extract, save roles | stays advisor-only — clients work inside a build an advisor set up |
| `ROLE_WORK_ROLES` | generate / save / approve / export both artefacts | add `UserRole.CLIENT` to let clients produce PDs beyond the first two |
| `READ_ROLES` | list, get build, list roles, step-progress | add `UserRole.CLIENT` alongside `ROLE_WORK_ROLES` |

Record-level `_check_build_access` (`pd_scorecard.py:115-136`) is identical in structure to the Roles Matrix version — creator, or engagement access via `check_engagement_access`, else 403 — and the in-code comment notes it needs no change when client access is enabled because `check_engagement_access` already scopes clients to their own engagement.

#### 2.10 Gotchas

**Gotcha — a matrix row with no Retain/Gain/Lose flag is invisible to this tool.** `rows_for_role` only appends a row under a flag whose value starts with `Y` (`pd_scorecard_service.py:467-470`). A responsibility carried through the matrix with all three columns blank never reaches `source_responsibilities` and therefore never reaches the PD.

**Gotcha — role attribution matches the matrix `name` column against `role_title` or `person_name`.** The matrix's Name column normally holds a *person's* name while `role_title` holds a *job title* (and `extract_roles.md:22-25` explicitly tells the model to derive a title). If the advisor clears or never gets a `person_name`, the match set contains only the title and `source_responsibilities` comes back `{"retain": [], "gain": [], "lose": []}` — the PD then generates from nothing. Keep `person_name` populated whenever the matrix is keyed by person.

**Gotcha — `source_responsibilities` is cached at role-save time only.** It is written in the `PATCH /api/pd-scorecard/{build_id}/roles` handler (`pd_scorecard.py:423-428`). Re-running `POST /api/pd-scorecard/{build_id}/extract` replaces `matrix_rows` but does **not** refresh any role's cache; the roles must be saved again. The engine's fallback to `rows_for_role` fires only when the cache is `NULL`, not when it is stale.

**Gotcha — the export endpoints do not require approval.** `POST /api/pd-scorecard/{build_id}/roles/{role_id}/pd/export` and `.../scorecard/export` only check that the content exists (`pd_scorecard.py:550`, `686`). The approved-only rule is enforced purely in the UI (`canDownload` in `PDStep.tsx:122` / `ScorecardStep.tsx:88`).

**Gotcha — excluded roles can still be generated and exported.** Neither `generate_pd` nor `generate_scorecard` checks `role.included`; only `_refresh_completion` (`included_only=True`) and `RolePicker` (`RolePicker.tsx:24`) filter on it.

**Gotcha — editing a completed build leaves the status stale.** `_refresh_completion` runs only from `approve_scorecard`. Saving a PD or scorecard on a `completed` build flips that role back to `draft` but leaves `pd_scorecards.status = 'completed'` and `completed_at` set until some scorecard is approved again.

**Gotcha — a build with every role excluded never completes.** `_refresh_completion` requires `bool(roles)` over the `included_only` set, so a build whose roles are all unticked can never reach `completed`.

**Gotcha — the standalone launch can resume an engagement's build**, and landing on either route auto-creates a build. Identical mechanics to the Roles Matrix gotchas above.

---

### 3. Standalone vs attached to an engagement

Both tools support exactly two launch paths and the difference reduces to one nullable column.

| | Standalone (AI Tools grid) | Attached (engagement) |
|---|---|---|
| Entry point | `AIToolsPage.tsx` card → `navigate(tool.route)` (`:178`) | `FollowUpToolsTab.tsx` Run button → `useToolLaunchers` |
| Reachable from the UI? | **No navigation link exists.** The sidebar's AI Tools entry is unconditionally suppressed — `if (item.href === '/dashboard/ai-tools') return null;` (`frontend/src/components/layout/Sidebar.tsx:186`, comment "AI Tools hidden for now"). The page is reachable only by typing the URL | Yes — the engagement's Tools tab |
| Route | `/dashboard/ai-tools/{roles-matrix\|pd-scorecard}` | `/dashboard/engagements/:engagementId/{roles-matrix\|pd-scorecard}` |
| `useParams().engagementId` | `undefined` | the engagement UUID |
| Creation call | `create-project` with no query | `create-project?engagement_id=<uuid>` |
| Pre-check for an existing project | Runs **inside the page** (`launchState: checking → choose → ready`), unfiltered — lists everything the user owns (`RolesMatrixPage.tsx:59-82`, `PDScorecardPage.tsx:65-88`) | Runs **in the launcher hook** before navigating; filtered by `engagement_id`; shows an `AlertDialog` with a destructive-action warning |
| "Continue" | Page loads the returned record and stays on the route | Navigates with `state.matrixId` / `state.buildId` |
| Second option | Button reads **"Start New"** — clears Redux and lets the page create a new row; the old project is left in place | Button reads **"Start Fresh"** — `DELETE`s the existing project first so the pre-flight stops finding it (`useToolLaunchers.ts:319-326`, `390-397`), then creates |
| Navigation state | none — the page creates the record itself | `state.matrixId` / `state.buildId`, so the page starts at `launchState='ready'` and loads that record instead of creating one |
| DB row | `engagement_id = NULL` | `engagement_id` set; also validated at creation (404 if the engagement is missing/deleted, 403 if the caller has no access) |
| Who else can open it | **Only the creator** — `_check_matrix_access` / `_check_build_access` fall straight through to 403 with no engagement to defer to | Creator, plus anyone passing `check_engagement_access` on that engagement |
| "Back" button target | `/dashboard/ai-tools` | `/dashboard/engagements/:engagementId` |
| Client visibility | `/dashboard/ai-tools` and the tool routes carry only `ProtectedRoute`, no role gate — a client who types the URL renders the page, then every backend call 403s | Row is rendered with an "Advisor only" pill and a disabled Run button |

Nothing else changes: the same page component, the same stepper, the same endpoints, the same prompts and the same exports serve both paths.

**Gotcha:** the engagement dialog warns "Starting fresh will permanently delete all uploaded files, roles and approved drafts" (`useToolLaunchers.ts:544`, `569`). The `DELETE` it issues is a soft delete (`is_deleted = True`); nothing on disk and no child role row is removed, and the record stays queryable by ID.

There is no automatic hand-off between the two tools — the Roles Matrix export must be downloaded and re-uploaded into a PD & Scorecard build by hand, even when both are attached to the same engagement.

---

## 14. Value Builder Programme — Program Guide & Deliverables

The Value Builder programme is a 13-module guided advisory engagement. It is exposed as two FastAPI routers mounted under `/api` (`backend/app/main.py:103-104`) and one frontend tab. Everything here is gated on `Engagement.tool == "value_builder"`; the tab only mounts when that holds and the viewer is not a client (`frontend/src/pages/dashboard/Engagement/EngagementDetailPage.tsx:61`), and it is labelled "Value Builder" in the tab strip (`:745`).

### The 13 modules

The authored catalogue lives in a single JSON fixture — a top-level array of 13 objects, `backend/files/program_guide/value_builder_modules.json` (~165 KB) — and is pushed into Postgres by a seed script. Module titles for V1–V11 are pinned by test to `ScoringService.VALUE_BUILDER_MODULES` (`backend/app/services/scoring_service.py:27-39`), the same taxonomy the diagnostic scores against (`test_fixture_titles_match_the_scoring_taxonomy`, `backend/tests/test_program_guide_seed.py:1265`).

| Code | Title | Focus / purpose (as authored) | Recommended tool keys | Deliverables (mandatory) |
|---|---|---|---|---|
| M0 | Diagnostic Gateway | *PLACEHOLDER* — complete the diagnostic so Trinity can generate report, recommendations and a personalised module path | `diagnostic` | 1 (1) |
| V1 | Financial Management | Financial clarity, cost and margin performance, and a reporting rhythm the owner will actually maintain | `financial_health_summary` | 5 (4) |
| V2 | Strategy & Planning | Direction for the next one to five years, captured in a workshop and written up as a strategic business plan the owner owns | `strategy_workbook`, `strategic_business_plan` | 4 (3) |
| V3 | Leadership & Communications | How leaders behave, who decides what, and how information moves | `leadership_communications_pack` | 3 (3) |
| V4 | People & Structure | The right people in the right roles, with clear accountability, and a structure that matches where the business is going | `people_structure_pack`, `position_description` | 5 (4) |
| V5 | Systems & Processes | How work actually flows, where it breaks, and how it should run | `workflow_analysis_mapping` | 4 (4) |
| V6 | Technology | Technology that supports how the business actually works, rather than getting in its way | `technology_stack_automation` | 6 (5) |
| V7 | Sales & Marketing | Making growth consistent and predictable rather than random | `growth_engine` | 8 (5) |
| V8 | Brand, IP & Protection | What the business owns, what protects it, and whether it can be copied | `brand_ip_audit` | 3 (2) |
| V9 | Owner Independence | Whether the business survives without the owner, and what it would take | `owner_independence` | 3 (3) |
| V10 | Value & Growth | Building an asset rather than running a business | `value_building` | 3 (3) |
| V11 | Risk, Legal, Compliance & Property | What could go wrong, what is not documented, and what nobody has looked at in years | `risk_compliance` | 2 (2) |
| M12 | Re-Diagnostic Capstone | *PLACEHOLDER* — re-run the diagnostic, see value movement, route back through the module library | `diagnostic` | 1 (1) |

Totals: **48 preset deliverables, 40 of them mandatory.** `display_order` in the fixture runs M0 = 0, V1–V11 = 1–11, M12 = 12.

**M0 and M12 are entirely placeholder content and must be replaced before client use.** Each of those two entries carries exactly eight keys — `program_type`, `module_code`, `display_order`, `title`, `purpose`, `preparation_checklist`, `recommended_tools`, `deliverables` — and every prose string in them is prefixed `PLACEHOLDER:`: the purpose, the single preparation-checklist item, and the single deliverable title. This is asserted, not incidental: `test_every_working_module_carries_real_content` (`backend/tests/test_program_guide_seed.py:1177`) requires the set of modules containing the substring `PLACEHOLDER` to be *exactly* `{"M0", "M12"}`, so adding a placeholder anywhere else fails the suite, and writing real M0/M12 copy will require updating that assertion.

V1–V11 are transcribed from specification Parts B–L (one test per module, `test_v1_is_transcribed_from_part_b` … `test_v11_is_transcribed_from_part_l`) and each carries `focus`, `core_outcomes`, `required_inputs`, `preparation_checklist`, `preparation_summary`, `sessions`, `post_session_actions`, `guardrails`, `quality_standards` and real deliverables. `notes`, `tables` and `between_sessions` are optional and appear on some modules only (V2 has `between_sessions` and `notes`; V7 has `notes` and `tables`; V1 has none of the three).

**Gotcha:** of the 15 tool references across the fixture, only two — `strategy_workbook` and `strategic_business_plan` on V2 — are marked `"Existing Trinity tool"`. Eleven carry `"To build, Feature 3"` and render as a "Not built yet" chip (`frontend/src/components/engagement/program-guide/ModuleSessionsPanel.tsx:161-164`; `isToolPending`, `moduleDisplay.ts:93`, matches any status starting `to build`). The two `diagnostic` references on M0/M12 have no `status` at all and are special-cased into a tab-navigation button rather than a tool launcher (`ModuleSessionsPanel.tsx:165-168`).

### Content vs state: the sparse-row design

Five tables, split cleanly between global catalogue and per-engagement state.

| Table | Model | Scope | What it holds |
|---|---|---|---|
| `program_module_content` | `ProgramModuleContent` (`backend/app/models/program_guide.py:13`) | Global, unique on `(program_type, module_code)` | The module card: `focus`, `purpose`, `core_outcomes`, `preparation_checklist`, `preparation_summary`, `sessions`, `between_sessions`, `post_session_actions`, `notes`, `tables`, `guardrails`, `quality_standards`, `recommended_tools`, `required_inputs`, plus a derived display-only `deliverables` string list |
| `program_module_deliverable` | `ProgramModuleDeliverable` (`backend/app/models/program_deliverable.py:26`) | Global, unique on `(program_type, module_code, deliverable_key)` | The preset library: `title`, `description`, `is_mandatory`, `produced_by`, `produced_by_note`, `feeds`, `session`, `display_order`, `is_active` |
| `engagement_program_module_state` | `EngagementProgramModuleState` (`program_guide.py:144`) | At most one row per engagement (`engagement_id` is unique) | Only the advisor's manual `custom_order`, plus `custom_order_set_by_user_id` and `custom_order_set_at` |
| `engagement_module_deliverable` | `EngagementModuleDeliverable` (`program_deliverable.py:112`) | Sparse, per engagement | Completion and scope state, plus advisor-added deliverables |
| `engagement_module_checklist_item` | `EngagementModuleChecklistItem` (`program_guide.py:167`) | Sparse, per engagement | Preparation-checklist tick-off. **Schema only** — the class appears in the model, `models/__init__`, the migrations and one seed-script comment; no API, no service, no frontend reference exists |

**Gotcha:** `ProgramModuleContent.deliverables` is a flat list of title strings written by the seed script from the preset titles (`backend/scripts/seed_program_guide_content.py:533`). It is not a source of truth and the status engine never reads it; the column comment says to retire it once the composed view replaces it.

The critical property is that `engagement_module_deliverable` is **sparse**. A row exists only once someone has ticked a deliverable off or scoped it out. An absent row means "incomplete and in scope". The read query encodes that directly as a `LEFT JOIN` with `COALESCE` defaults (`backend/app/services/program_deliverable_service.py:198-227`):

```python
func.coalesce(EngagementModuleDeliverable.is_in_scope, literal(True)).label("in_scope"),
func.coalesce(EngagementModuleDeliverable.is_complete, literal(False)).label("complete"),
```

Why this matters operationally: **seed a new preset today and it appears on every live engagement on the next page load, with no backfill and no migration.** There is nothing to write per engagement, because "untouched" is represented by the absence of a row. The same property runs in reverse: instances hold no copy of the authored text (`title`, `description`, `is_mandatory` stay NULL on preset instances and are read live from the library row, `program_deliverable_service.py:364-366`), so editing a preset's wording in the fixture and re-seeding changes it everywhere immediately, including on engagements that already completed it. `test_edits_reach_live_engagements` (`backend/tests/test_program_guide_seed.py:170`) pins this.

The composed read is two queries, not one: the preset leg `UNION ALL` the advisor-added leg, then a separate grouped count of tasks per deliverable (`_task_counts_by_deliverable`, `program_deliverable_service.py:271-290`). Sorting is done in Python — presets by library `display_order`, advisor-added after them by creation time via a `1_000_000` sort sentinel (`_ADVISOR_SORT_ORDER`, `:51`).

Advisor-added deliverables live in the *same* table, discriminated by `library_deliverable_id IS NULL`. They carry their own `title`, `module_code` and `is_mandatory` because there is no library row to inherit from. The unique constraint `uq_engagement_module_deliverable_engagement_library` on `(engagement_id, library_deliverable_id)` allows exactly one instance per preset while placing no limit on advisor-added rows, because Postgres treats NULLs as distinct.

### Deliverable semantics

`is_complete` and `is_in_scope` are two independent, non-nullable boolean columns, deliberately not folded into one status field. From the model docstring (`backend/app/models/program_deliverable.py:127-131`):

> Note that is_in_scope is deliberately a separate flag rather than a value folded into a status column: scoping a completed deliverable out and back in leaves is_complete untouched, whereas a single status field would forget it.

The service enforces that by writing disjoint column sets (`program_deliverable_service.py:444-511`):

| Flag | Set by | Audit columns written | Cleared on reverse |
|---|---|---|---|
| `is_complete` | `PUT .../complete` | `completed_by_user_id`, `completed_at` | Both set to NULL when un-completing |
| `is_in_scope` | `PUT .../scope` | `scoped_out_by_user_id`, `scoped_out_at` | Both set to NULL when brought back in scope |

Scoping out is **reversible exclusion, not deletion**. The row is retained; `is_complete` is untouched (`test_scoping_out_preserves_completion`, `test_scoping_back_in_clears_the_scope_stamps`, `backend/tests/test_program_deliverable_mutations.py:114`, `:135`).

Two write paths are no-ops by design. Un-completing a preset that has no instance row, or scoping one back *in* that has no instance row, returns `None` and writes nothing — an absent row already means incomplete and in scope, so materializing one would record no information (`program_deliverable_service.py:460-463`, `:496-499`).

Materialization of a preset's first mutation is wrapped in a savepoint (`self.db.begin_nested()`), because a double click makes the unique constraint fire an `IntegrityError` rather than producing a duplicate; losing that race re-reads what the winner wrote (`:344-376`).

`is_deleted` applies only to advisor-added deliverables. Presets are library content shared by every engagement, so per-engagement removal is meaningless — the mechanism is to scope out. The guard is a pure validator (`program_deliverable_service.py:163-172`):

```python
def assert_advisor_added(library_deliverable_id: Optional[UUID], action: str) -> None:
    if library_deliverable_id is not None:
        raise ValueError(f"Cannot {action} a preset deliverable; scope it out instead")
```

Naming a preset on `PATCH` or `DELETE` therefore yields **400, not 404** — `_resolve_advisor_added` deliberately accepts *both* id spaces so the informative refusal is reachable over HTTP rather than hidden behind a lookup miss (`program_deliverable_service.py:405-435`, pinned by `test_preset_edit_and_delete_are_400_not_404`, `backend/tests/test_program_deliverable_api.py:320`).

A **retired** preset (`is_active = False`) cannot be written against at all: `_get_library_row` filters on `is_active == True` and on the engagement's own `program_type`, so a retired or foreign-program id raises `DeliverableNotFound` (`:328-342`, `test_retired_preset_is_not_resolvable`).

There are **no `CheckConstraint`s anywhere in `backend/app/models`** — the only two occurrences of the word are prose in comments — so every invariant above is service-layer only.

#### Addressing: the polymorphic `deliverable_id`

`deliverable_id` in the API is the **library row id** for a preset and the **instance row id** for an advisor-added deliverable. An untouched preset has no instance row, so it has no instance id — the library id is the only handle that exists. The two ids live in different tables, so there is no ambiguity. `_resolve` also looks up the instance for a preset, so addressing an already-materialized preset by its library id still returns the existing row (`program_deliverable_service.py:378-403`).

#### Module completion

`derive_module_status` is a pure function over `DeliverableState` tuples with no DB access (`program_deliverable_service.py:91-116`):

```python
outstanding_mandatory = sum(1 for s in states if s.in_scope and s.mandatory and not s.complete)
any_acted_on = any(s.complete or not s.in_scope for s in states)
any_complete = any(s.complete for s in states)

if outstanding_mandatory == 0 and any_acted_on:
    return MODULE_STATUS_COMPLETED
elif any_complete:
    return MODULE_STATUS_IN_PROGRESS
else:
    return MODULE_STATUS_NOT_STARTED
```

Consequences, all covered by `backend/tests/test_program_deliverable_status.py`:

- Only **in-scope** mandatory deliverables can block completion.
- The `any_acted_on` guard is load-bearing: without it, a module with no mandatory deliverables and nothing touched would vacuously report `completed` (`test_zero_mandatory_module_nothing_touched`).
- **Gotcha:** scoping out *every* mandatory deliverable, with nothing completed, returns `completed` (`test_all_mandatory_scoped_out_nothing_completed`, `:105`). This is deliberate — the advisor has judged nothing mandatory applies — but a module can show Complete with zero work done.
- A module with no deliverables at all is **absent** from the response mapping rather than mapped to an empty list. Callers must use `.get(code, [])`; the frontend routes this through `statusOf()` (`frontend/src/components/engagement/program-guide/moduleDisplay.ts:56`).
- `task_count` is never read by the status derivation.

### Endpoints

Both routers mount under `/api`.

#### `/api/program-guide` (`backend/app/api/program_guide.py`)

Every engagement-scoped route loads the engagement first (404 if missing or soft-deleted), then authorizes, then applies the `tool` check where present. `check_engagement_access(..., require_advisor=True)` in practice means "is not a `UserRole.CLIENT`": `require_advisor` is tested in exactly one place, inside the CLIENT branch of `backend/app/services/role_check.py:94-97`, so super admins, admins, firm admins, advisors and firm advisors all return True before the flag is read.

| Method | Path | Roles | `tool` check | Returns |
|---|---|---|---|---|
| GET | `/content?program_type=` | Any non-CLIENT, via an explicit `current_user.role == UserRole.CLIENT` refusal in the endpoint (`:67-71`) — not engagement-scoped, so `check_engagement_access` is never called | n/a | `List[ProgramModuleContentItem]` — active cards for a program, by `display_order` |
| GET | `/engagements/{id}` | Advisor + admin | yes | `ProgramGuideView` — every card, ordered, with `effective_rank` / `is_gateway` / `is_capstone` |
| GET | `/engagements/{id}/dashboard` | **Any role with engagement access, owners included** | yes | `ProgramGuideDashboardView` |
| PUT | `/engagements/{id}/order` | Advisor + admin | **no** | `ProgramGuideView` |
| POST | `/engagements/{id}/order/reset` | Advisor + admin | **no** | `ProgramGuideView` |
| GET | `/engagements/{id}/value-movement` | Advisor + admin | **no** | `ValueMovementResponse` |
| GET | `/engagements/{id}/insights` | Advisor + admin | yes | `ProgramGuideInsightsView` |

**Gotcha:** the three routes with no `tool` check are reachable on a Sale-Ready engagement. `PUT /order` there will write an `engagement_program_module_state` row stamped `program_type = "sale_ready"` and the guide view will come back with `order_source: "custom"` over an empty module list.

The dashboard is the only Program Guide read a business owner gets, and the narrowing is in the *payload*, not the guard: `DashboardModuleItem` is deliberately **not** a subclass of `ProgramModuleContentItem`, with an explicit field list (`module_code`, `title`, `effective_rank`, `is_gateway`, `is_capstone`, `status`), so card content cannot leak back in by inheritance (`backend/app/schemas/program_guide.py:59-74`). `test_the_authored_content_is_absent_by_value_too` (`backend/tests/test_program_guide_api.py:190`) asserts this by value, not just by key name.

#### `/api/deliverables` (`backend/app/api/program_deliverable.py`)

Advisor + admin on **every** route, reads included. Owners are denied both reads and writes. All access decisions live in one file, `backend/app/services/deliverable_permissions.py`; there is no role check in the API module. The two dependencies `require_deliverable_read` and `require_deliverable_write` are identical today and stay separate only because their reasons differ. `_authorize` also enforces `engagement.tool == "value_builder"` (400) on every route (`deliverable_permissions.py:82-86`), after the 404 and the 403. The allow-list is `{ADVISOR, FIRM_ADVISOR, FIRM_ADMIN, ADMIN, SUPER_ADMIN}` (`DELIVERABLE_ACCESS_ROLES`, `:57-63`). Every route returns the full `DeliverableView`, so the client replaces state wholesale.

| Method | Path | Effect |
|---|---|---|
| GET | `/engagements/{id}` | The composed deliverables-and-status view |
| PUT | `/engagements/{id}/items/{deliverable_id}/complete` | Body `{is_complete}`; materializes the preset instance if needed |
| PUT | `/engagements/{id}/items/{deliverable_id}/scope` | Body `{is_in_scope}` |
| POST | `/engagements/{id}/items` (201) | Body `{module_code, title, is_mandatory, description?}` |
| PATCH | `/engagements/{id}/items/{deliverable_id}` | Partial; `exclude_unset` so omitted ≠ null. Only `title`, `description`, `is_mandatory`; any other key is a 400 |
| DELETE | `/engagements/{id}/items/{deliverable_id}` | Soft delete; advisor-added only |
| POST | `/engagements/{id}/modules/{module_code}/tasks` (201) | `TaskGenerationResult` |

Error mapping: `DeliverableNotFound` subclasses `ValueError` and **must** be caught before the generic handler in each endpoint, or a stale id becomes indistinguishable from a malformed body (`backend/app/api/program_deliverable.py:44-53`). A missing engagement is 404 and wins over deliverable lookup (`test_unknown_engagement_still_wins_over_deliverable_lookup`, `test_program_deliverable_api.py:343`). The create endpoint has no `DeliverableNotFound` branch because a create resolves nothing.

**Gotcha:** `DeliverableView.modules` is ordered by `sorted(states_by_module)` (`program_deliverable.py:72`) — a **string** sort of module codes, so the array arrives as `M0, M12, V1, V10, V11, V2, …`, not programme order. The frontend never renders that array directly; it indexes by code into a `Map` (`ModuleList.tsx:37-42`) and the slice documents the hazard (`frontend/src/store/slices/deliverablesReducer.ts:50-54`).

### Module ordering

The recommended order is computed **live, never cached**, from the most recent non-deleted BBA ("Recommendations Report Builder") for the engagement that has `draft_findings` (`backend/app/services/program_guide_service.py:126-166`). Findings are sorted by `rank` (missing rank sorts to 999), each finding's freeform `priority_area` is matched to a module code, matched codes come first in rank order, and every unmatched module is appended in default taxonomy order. **The result always contains all eleven V-codes, so the guide is never gated.** Findings that matched nothing are returned in `unmapped_priority_areas`.

`order_source` takes one of four values:

| Value | Meaning |
|---|---|
| `bba` | Derived from the latest BBA findings |
| `custom` | An advisor override is stored in `engagement_program_module_state.custom_order` |
| `default` | No BBA with findings; plain taxonomy order |
| `unsupported` | `engagement.tool != "value_builder"` (order empty) |

`PUT /order` takes `{module_order: [...]}`, which **may be partial** — `get_effective_order` merges the stored override with the computed order and appends anything the advisor did not name, so nothing is ever dropped (`program_guide_service.py:175-188`; `test_a_partial_order_keeps_every_module`, `backend/tests/test_program_guide_api.py:287`). `POST /order/reset` nulls `custom_order`, `custom_order_set_by_user_id` and `custom_order_set_at`, falling back to the computed order.

Both endpoints call the service and then **re-compose the view** rather than returning the service's return value: `set_custom_order` / `reset_custom_order` return an order dict, which is not a `ProgramGuideView` and fails response validation. Both routes 500'd for exactly that reason until `TestModuleOrdering` was added (`backend/tests/test_program_guide_api.py:255-264`) — the reorder buttons had shipped in the UI and were entirely non-functional.

The `modules` array itself is sorted gateway-first, then by `effective_rank` (falling back to `display_order` when rank is null), capstone last (`program_guide_service.py:234-238`). M0 and M12 are not in `VALUE_BUILDER_MODULES`, so their `effective_rank` is `null`; the UI shows a dash and excludes them from the reorder controls (`ModuleList.tsx:82`, `:48`, `:134`).

**Gotcha:** `MODULE_NAME_ALIASES` (`program_guide_service.py:79-82`) maps two retired module names — `"brand, ip & competitive advantage" → V8` and `"people" → V4` — to their codes, because BBA findings store freeform text and old rows are never rewritten. The matcher's order is: exact name → exact code → alias → loose "contains" (`:84-124`). A future rename that *replaces* a word rather than widening one will silently stop matching, dropping the finding into `unmapped_priority_areas` and quietly degrading the order to the default taxonomy. **An entry must be added to that dict every time a name in `VALUE_BUILDER_MODULES` changes.** The UI surfaces unmatched findings in a warning banner (`ProgramGuideTab.tsx:189-200`) precisely because there is no other symptom.

### Insights, dashboard and value-movement

| Endpoint | Inputs | Output | Behaviour when data is missing |
|---|---|---|---|
| `/insights` | Latest **completed**, non-deleted `Diagnostic` (by `completed_at desc`) + latest non-deleted BBA with `draft_findings` | Per-module `module_name`, `score`, `rag`, `severity`, `answered_questions`, `effective_rank` and attributed `findings`; plus `overall_score`, `diagnostic_id`, `diagnostic_completed_at`, `source_bba_id`, `unmatched_findings` | `has_scores` / `has_findings` are independent flags. `modules` **always** carries all 11 V-entries with nulls; a module with no score reports `null`, never `0` |
| `/dashboard` | `get_program_guide_view` narrowed + `get_module_statuses` from the deliverables engine | 13 module rows (code, title, rank, gateway/capstone, status) + `total_modules`, `completed_modules`, `in_progress_modules`, `not_started_modules` | Modules with no deliverables are absent from the status map and default to `not_started` |
| `/value-movement` | The **two** most recent completed diagnostics (`completed_at desc`, limit 2) | Per-module `previous_score`, `current_score`, `delta`, `previous_rag`, `current_rag`, plus overall equivalents and both diagnostic ids | Returns `{"has_comparison": false}` and nothing else below two completed diagnostics |

`score`, `rag` and `severity` all derive from `Diagnostic.module_scores["modules"][code]`. RAG thresholds are `< 2.0` Red, `< 4.0` Amber, else Green; severity bands are `(1.5, Critical), (2.7, High), (3.5, Moderate), (4.0, Low)` with `Strong` above, and deliberately do **not** align to the RAG boundaries (`backend/app/services/scoring_service.py:51-70`, `:138-174`).

`/insights` exists because `/value-movement` answers nothing in the ordinary case — most engagements have exactly one completed diagnostic. It attributes findings with **the same matcher that computes the module order**, so what an advisor reads on a card is exactly what ranked it, and it carries `priority_area` through verbatim so a mismatch is visible on screen (`ModuleDiagnosticPanel.tsx:73-86`).

The dashboard is built by narrowing the full guide view rather than by a second query, so ordering and gateway/capstone handling cannot drift between the two (`program_guide_service.py:250-297`). `total_modules` counts all 13, including the two unranked bookends.

### Task generation from deliverables

`POST /api/deliverables/engagements/{id}/modules/{module_code}/tasks` creates one `Task` per deliverable in that module that does not have one yet. It runs **only** from an explicit advisor click — no mutation path calls it (`program_deliverable_service.py:602-655`).

The skip condition is `if state.task_count or not state.in_scope or state.complete: continue` — deliverables that already have a live task, that are scoped out, or that are already complete. All three remain reachable by hand.

Fields written on the created `Task`:

| Task column | Value |
|---|---|
| `title` / `description` | Copied from the deliverable's effective title/description |
| `task_type` | `"deliverable_generated"` — sits alongside `manual` and `diagnostic_generated` |
| `status` | `"pending"` |
| `priority` | `"high"` if the deliverable is mandatory, else `"medium"` |
| `module_reference` | The module code |
| `created_by_user_id` | The clicking advisor |
| `source_deliverable_id` | The **same polymorphic id** the API addresses the deliverable by |

`Task.source_deliverable_id` is a plain indexed UUID column with **no foreign key**, and the absence is intentional (`backend/app/models/task.py:26-32`): the id may point at either `program_module_deliverable` or `engagement_module_deliverable`, which is two tables and therefore no single FK — and an FK through the library would have cascaded, so retiring a preset would have deleted a client's tasks. `test_scoping_out_leaves_the_task_standing` (`backend/tests/test_deliverable_task_generation.py:289`) pins exactly that.

`task_count` is read back live by `_task_counts_by_deliverable`, grouped by `source_deliverable_id`, excluding soft-deleted tasks — so deleting a task puts the deliverable back within reach of the button rather than stranding it (`test_a_deleted_task_can_be_regenerated`, `:217`).

Response is `{created_count, skipped_count, view}` with **201 even when nothing was created**; zero is a real outcome, not a failure. `skipped_count` is computed in the endpoint as `max(total deliverables in the module − created, 0)`, so it counts every non-created row including already-tasked, scoped-out and complete ones (`backend/app/api/program_deliverable.py:226-233`).

Part A's four prohibitions each have a dedicated test in `test_deliverable_task_generation.py`:

- nothing is created automatically;
- one deliverable may carry several tasks (nothing enforces uniqueness on `source_deliverable_id`; generation simply declines to add a second — `test_several_tasks_per_deliverable_are_expressible`, `:229`);
- task state and deliverable state never move each other — completing every generated task leaves the module at `not_started` (`test_a_module_is_never_completed_by_its_tasks`, `:317`);
- scoping a deliverable out, or soft-deleting an advisor-added one, leaves its tasks standing (`:289`, `:303`).

### Seeding

```bash
# from backend/
python scripts/seed_program_guide_content.py
python scripts/seed_program_guide_content.py --file files/program_guide/value_builder_modules.json
python scripts/seed_program_guide_content.py --dry-run   # validates, then rolls back
```

The script writes both library tables. It is **idempotent**: cards upsert on `(program_type, module_code)`, deliverables on `(program_type, module_code, deliverable_key)`, matching `uq_program_module_deliverable_type_module_key`. Re-running with an unchanged fixture creates nothing (`test_seeding_twice_creates_nothing_the_second_time`, `backend/tests/test_program_guide_seed.py:105`). The summary line reports `created / updated` for cards and `created / updated / retired / reactivated` for deliverables.

The whole fixture is validated **before anything is written** (`validate_fixture`, `backend/scripts/seed_program_guide_content.py:422`), reporting every problem at once rather than failing on the first, so a typo in module nine cannot leave modules one to eight seeded (`test_validation_runs_before_any_write`, `test_every_problem_is_reported_at_once`). It checks: the four required top-level fields (`program_type`, `module_code`, `display_order`, `title`); duplicate `(program_type, module_code)`; `required_inputs[].source` against the three literals in `VALID_INPUT_SOURCES`; `produced_by` against `{trinity_tool, advisor, client}`; `feeds` targets resolving to real module codes in the same fixture; note **and table** `section` against `VALID_NOTE_SECTIONS` (11 values); table row cell counts equalling column counts; `owner` present on `preparation_summary` / `between_sessions` / `post_session_actions` (`duration` deliberately optional); question groups being objects with an `items` list; `recommended_tools[]` carrying `tool_key` and `label`; and key uniqueness across checklist items, sessions, agenda items, options, notes, tables and deliverables.

What happens when the JSON changes after engagements exist:

| Fixture change | Effect |
|---|---|
| A deliverable's text or `is_mandatory` edited | Updated **in place**, id preserved. Visible immediately on every live engagement |
| A deliverable's array position changed | `display_order` = 1-based position in the array, so reordering the array reorders the card with no renumbering by hand |
| A `deliverable_key` disappears | **Retired** (`is_active = False`), never deleted. Hidden from the status query; every engagement's completion and scope history is preserved |
| A retired key returns | The same row is reactivated — same id, same history |
| A new deliverable added | Appears on every live engagement immediately (sparse-row design) |

The retire-don't-delete rule is not cosmetic: `EngagementModuleDeliverable.library_deliverable_id` is `ondelete='CASCADE'` (`program_deliverable.py:140-145`), so deleting a library row would destroy every engagement's state for it. Likewise the upsert must never be a delete-then-recreate, because live instances hold the id as a foreign key. Both are pinned (`test_retiring_preserves_engagement_completion_history`, `test_editing_a_deliverable_preserves_its_id`).

`seed_from_file(path, db=..., dry_run=...)` accepts an existing session, which is how the test suite seeds inside a rolled-back transaction.

The subsystem's Alembic chain, oldest first: `add_program_guide_tables` → `add_program_deliverable_tables` → `add_module_required_inputs` → `add_module_card_sections` → `add_between_sessions_notes` → `add_module_notes` → `merge_card_notes` → `add_tables_and_session` → `add_task_source_deliverable`.

### The render contract test

`backend/tests/test_program_guide_render_contract.py` runs over the **real fixture file**, not a synthetic one, and asserts that what is stored matches what the UI actually draws.

The gap it closes: every rich card section is JSONB, and Pydantic types all of them as `Dict[str, Any]` or `List[Dict[str, Any]]` (`backend/app/schemas/program_guide.py:19-34`), so nothing on the server validates their inner shape. The frontend's TypeScript interfaces in `programGuideReducer.ts:17-131` are hand-written assertions about data no code checks. These tests are the only enforcement of that agreement. The seed script validates the fixture on *write*; this file asks the narrower question of whether the stored shape has somewhere to be *rendered*.

| Class | Invariant |
|---|---|
| `TestSessionsRenderable` | Agenda items carry key + title; session and agenda keys unique (they are React list keys — a duplicate silently drops a step); question groups are objects with a non-empty `items` string list, not bare strings; options carry key/term/definition |
| `TestRequiredInputsRenderable` | `source` is one of the three authored labels; keys unique; **an input sourced "From an earlier module" must state a `fallback` or a `source_note`** — Part A's rule that no module may assume another has run |
| `TestNotesAndTablesRenderable` | Note `section` ∈ the 11 `RENDERABLE_NOTE_SECTIONS`; table `section` ∈ `{business_model_shape, sessions}` only; no row has **more** cells than columns (a short row is padded when drawn); tables, columns and rows carry keys |
| `TestToolsRenderable` | Tool keys unique; **a tool outside `{bba, strategy_workbook, strategic_business_plan, diagnostic}` must carry a `status`**, or the card renders a dead "No launcher" chip |
| `TestGuardrailsAndOutcomesRenderable` | `must_not` entries must start lower-case and must not begin with "Advisors", because the card prefixes each with "Advisors must not"; `core_outcomes` / `quality_standards` hold strings |
| `TestDeliverablesRenderable` | Deliverable keys unique; `feeds` targets exist; **every module has at least one mandatory deliverable** |

**A frontend change can break this test**, and that is the point. The constants in the test file are a mirror of the render logic, verified line by line:

- `RENDERABLE_NOTE_SECTIONS` (11 values) mirrors exactly the 11 `notesForSection(...)` call sites across `ModuleContentPanel.tsx:61,106,120,127`, `ModuleSessionsPanel.tsx:103,121,184,202,221` and `ModuleDetail.tsx:194/200,221`.
- `RENDERABLE_TABLE_SECTIONS` mirrors the two `tablesForSection(...)` call sites — `business_model_shape` in `ModuleContentPanel.tsx:124` and `sessions` in `ModuleSessionsPanel.tsx:229`; a table with no section still renders, via `unsectionedTables` at `ModuleSessionsPanel.tsx:226`.
- The `launchable` set is exactly the four keys of `TOOL_ICONS` (`ModuleSessionsPanel.tsx:32-37`), which is also where the `diagnostic` special case lives.

Removing a section's render site, or narrowing where notes and tables are drawn, without updating those constants leaves the test passing while content silently stops appearing — or, more usefully, adding a new section in the fixture without a render site fails here rather than in a client's browser. `test_feeds_point_at_real_modules` documents in its docstring that `feeds` has backward edges and a deliberate V5/V6 cycle; the companion `test_feeds_may_point_backwards` (`test_program_guide_seed.py:1200`) asserts at least one backward edge exists, so a future "feeds must point forward" assumption fails against real content rather than shipping.

### Frontend

Redux slices, both under `frontend/src/store/slices/`:

- **`programGuideReducer.ts`** — five thunks (`fetchProgramGuide`, `reorderModules`, `resetModuleOrder`, `fetchValueMovement`, `fetchModuleInsights`) and state `{view, valueMovement, insights, isLoading, isReordering, error}` (`:205-212`). Field names are snake_case, mirroring the FastAPI response verbatim. It is also the only place the JSONB shapes are stated at all (`:17-203`). `fetchModuleInsights.rejected` deliberately does **not** set `state.error` — an engagement with no diagnostic and no BBA is normal, and surfacing it as a page-level error would bury an otherwise readable module list (`:389-395`). **Gotcha:** `fetchValueMovement.rejected` *does* set `state.error` (`:383-385`), so a failure on that supplementary read surfaces as a page-level error even though a missing comparison is the ordinary case.
- **`deliverablesReducer.ts`** — seven thunks and state `{view, isLoading, pendingIds, generatingModules, error}`. Every endpoint returns the whole `DeliverableView`, so **every fulfilled case simply replaces state**; there is no patching and therefore no way for the client's idea of a module's status to drift from the server's derivation. Module status is never computed client-side. The five row mutations are registered in a loop because they behave identically — track the id in `pendingIds`, replace the view (`:320-337`). `generateModuleTasks` is registered separately, tracking `moduleCode` in `generatingModules`, and its cases deliberately omit the `PayloadAction` annotation because that narrows the action and drops `meta`, which is where the module code lives (`:302-313`).

Components, all in `frontend/src/components/engagement/program-guide/`:

| File | Role |
|---|---|
| `ProgramGuideTab.tsx` | Entry point. Two views swapped in place (module list ↔ module detail), not routed. Fires **four independent reads on mount** — guide, value-movement, insights, deliverables (`:92-98`). Only the guide can block rendering. Also drops back to the list if the open module vanishes from the guide (`:103-108`) |
| `ModuleList.tsx` | One row per module in server order (nothing is sorted client-side). Shows rank (or a dash), code, title, "N of M required deliverables", RAG/severity badge, status badge, score |
| `ProgramProgressCard.tsx` | Three module-status counters plus a deliverables counter and a percentage bar. **The deliverable figures count only in-scope deliverables**, matching the backend rule — counting scoped-out work in the denominator would show a programme that can never reach 100% |
| `ModuleDetail.tsx` | Two-column grid (`1fr 340px`): diagnostic panel, module-level notes, content panel and sessions panel on the left; deliverables panel, deliverable notes and quality standards on the right (sticky). Header carries a "Why this position" explanation derived from `order_source` and the module's top finding (`rankExplanation`, `:48-87`) |
| `ModuleDiagnosticPanel.tsx` | Generated content, explicitly source-labelled "Generated · from this client's diagnostic". Renders findings with `Matched on "<priority_area>"` shown so a mismatch is visible. Flags "thin evidence" when `answered_questions` is between 1 and 4 |
| `ModuleContentPanel.tsx` / `ModuleSessionsPanel.tsx` | The authored card. Sessions are `Collapsible` (not `Accordion`) with the first open, so two agendas can be compared side by side (`ModuleSessionsPanel.tsx:57`, `:98`) |
| `ModuleDeliverablesPanel.tsx` | **The only part of the Program Guide that writes anything.** Checkbox toggles completion; a dropdown offers scope-out/back-in for all rows and edit/remove for `source === 'advisor'` only. "Create tasks" is badged with the count of in-scope, incomplete, untasked items — i.e. what the click will actually create (`:79`) |
| `ModuleReorderControls.tsx` | Up/down buttons, rendered only when `canReorder` and the module has an `effective_rank`; first/last are judged against the ranked subset so the gateway at index 0 does not disable "move up" on V1 (`ModuleList.tsx:45-48`, `:134-142`) |
| `RetakeDiagnosticCard.tsx` / `ValueMovementView.tsx` | M12 (`is_capstone`) renders this instead of `ModuleDetail`: purpose, the value-movement comparison, and a button that POSTs to `/api/diagnostics/create` and switches to the diagnostic tab |
| `ModulePrimitives.tsx` | `Prose`, `NoteBlocks`, `ReferenceTable`, `BulletList` |
| `moduleDisplay.ts` | Single source for status config, RAG classes, input-source icons, `isToolPending`, `statusOf`, and the note/table section filters. Class strings are written out in full because Tailwind cannot see runtime-assembled class names |

`canReorder` is passed as `isAdmin || isAdvisor` from the engagement page (`EngagementDetailPage.tsx:822`).

The module view therefore renders from three parallel sources at once: authored card content from the guide view, live deliverable state and derived status from the deliverables view, and per-client score/findings from the insights view. Because the fetches race and the guide usually wins, two components guard the gap explicitly — `ModuleDeliverablesPanel` uses `isLoading && !view` to show skeletons instead of "No deliverables for this module yet" (`:67`), and `ModuleList` renders a blank string rather than "No deliverables yet" while `deliverables === null` (`:101-107`), since the latter would be a claim about data that has not arrived.

---

## 15. Frontend Architecture

The frontend is a single-page Vite + React 18 + TypeScript application in `frontend/`, styled with Tailwind and shadcn/ui, with Redux Toolkit as the only real state container. It talks to the FastAPI backend over raw `fetch` with a Bearer token read from `localStorage`. There is no generated API client, no shared HTTP wrapper, and no server-state cache in active use. The API origin is not configured once: `VITE_API_BASE_URL` is re-read with a hand-copied constant in 56 files and one of them disagrees with the other 55 — see *Data fetching conventions*, which is the first thing to fix.

### Entry point and the global fetch interceptor

`frontend/src/main.tsx` is more than a mount point. Before `createRoot(...).render(<App />)` it installs two auth-expiry guards that the rest of the app depends on:

| Layer | Mechanism | Location |
|---|---|---|
| Pre-request | `window.fetch` is monkey-patched. If `localStorage.auth_token` decodes to an expired JWT (native `atob` on the base64url payload, checking `exp`), the network call is skipped and a **synthetic** `401` Response with body `{"detail": "Token expired"}` is returned. | `frontend/src/main.tsx:29-39` |
| Reactive | Any real response with `status === 401` while a token exists clears the token. | `frontend/src/main.tsx:42-47` |
| UI-only | `document.addEventListener('click', ..., { capture: true })` re-checks expiry so purely-local interactions (opening a modal, toggling a switch) still trip the logout. | `frontend/src/main.tsx:53-59` |

The decoder `isTokenExpired` (`frontend/src/main.tsx:7-23`) fails closed: it returns `true` for a token that is not three dot-separated parts, a payload that is not JSON, or a payload whose `exp` is not a number.

All three paths do the same two things: `localStorage.removeItem('auth_token')` and `window.dispatchEvent(new CustomEvent('auth:token-expired'))`. `AuthProvider` listens for that event and resets auth state, which makes `ProtectedRoute` redirect to `/login` (`frontend/src/context/AuthContext.tsx:295-303`). The token's issuance and the Auth0 round trip behind it are covered in *Authentication, Authorization & Impersonation*.

> **Gotcha:** Because `window.fetch` is replaced globally, every request in the app inherits this behaviour. A synthetic 401 is indistinguishable from a server 401 at the call site, so an expired session surfaces as a normal HTTP failure inside whatever thunk made the call. There is no opt-out.

### Provider nesting and why the order matters

`frontend/src/App.tsx:119-133`:

```tsx
const App = () => (
  <Provider store={store}>                     {/* react-redux */}
    <QueryClientProvider client={queryClient}>  {/* @tanstack/react-query */}
      <AuthProvider>                            {/* app auth context */}
        <TooltipProvider>                       {/* radix tooltip */}
          <Toaster />                           {/* shadcn/radix toast */}
          <Sonner />                            {/* sonner toast */}
          <BrowserRouter>
            <AppRoutes />
          </BrowserRouter>
        </TooltipProvider>
      </AuthProvider>
    </QueryClientProvider>
  </Provider>
);
```

- **`Provider` (Redux) outermost** — everything below, including every page, dispatches thunks. It has no dependencies of its own so it is safe at the top.
- **`QueryClientProvider` next** — the `QueryClient` is constructed once at module scope (`frontend/src/App.tsx:45`). Nothing consumes it; see *State management*.
- **`AuthProvider` above the router** — the load-bearing ordering decision. `AuthProvider` uses no React Router navigation: login, logout, `startImpersonation` and `stopImpersonation` all perform full-page `window.location.href` assignments (`frontend/src/context/AuthContext.tsx:52`, `:60`, `:220`, `:271`, `:274`) because the Auth0 round trip goes through the backend and leaves the SPA entirely. Placing it above `BrowserRouter` means it never needs router hooks, while `ProtectedRoute` (`frontend/src/App.tsx:47-59`) — which *is* inside the router — can call `useAuth()`.
- **`TooltipProvider` above the toasters and router** — Radix requires a tooltip provider ancestor for any `Tooltip` rendered anywhere in the tree.
- **Both toasters mounted as siblings before the router** — they are portalled overlays outside `BrowserRouter`, so a route transition cannot unmount an in-flight toast.

`AuthProvider` state is `{ user, isAuthenticated, isLoading }` (`frontend/src/types/auth.ts:17-21`) with `isLoading` initialised to `true` so `ProtectedRoute` waits. On mount it calls `loadCurrentUser` after a 100 ms `setTimeout` (`AuthContext.tsx:283-290`), which hits `GET /api/auth/impersonation-status` first and then `GET /api/auth/user`, mapping the snake_case backend payload to the frontend `User` shape in `mapBackendUserToFrontend` (`AuthContext.tsx:21-38`). `switchRole` is a declared no-op placeholder (`:63-67`).

> **Gotcha:** `AuthContext.tsx` exports only `AuthProvider` and `useAuth`. The `User` type lives in `frontend/src/types/auth.ts`. `frontend/src/lib/clientFetcher.ts:2` imports `User` from `@/context/AuthContext`; that import resolves to nothing and nothing catches it (see *Build and tooling*).

> **Gotcha:** Two independent toast systems are live. `<Toaster />` is shadcn's Radix toast fed by `useToast()` from `frontend/src/hooks/use-toast.ts`; `<Sonner />` is `sonner`. `sonner` is imported in 45 files; shadcn's `useToast` in exactly three (`frontend/src/components/engagement/form.tsx:28`, `frontend/src/pages/dashboard/AdvisorsPage.tsx:43`, `frontend/src/pages/dashboard/ClientsPage.tsx:33`). Prefer `sonner` for new work. `frontend/src/hooks/use-toast.ts:5-6` sets `TOAST_LIMIT = 1` and `TOAST_REMOVE_DELAY = 1000000` (~16 min), so the Radix toaster shows one toast at a time and effectively never auto-dismisses from the queue.

> **Gotcha:** `frontend/src/components/ui/sonner.tsx:1` calls `useTheme()` from `next-themes`, but no `ThemeProvider` is mounted anywhere. The theme always resolves to the `"system"` default. Nothing in `src/` ever adds a `dark` class to the document either, so the entire `.dark` token block in `frontend/src/index.css:101-137` is unreachable.

### Route table

Defined entirely in `AppRoutes` (`frontend/src/App.tsx:61-117`). "Guarded" means the route sits under `<ProtectedRoute>`, which renders the literal string `Checking authentication...` while `isLoading`, and otherwise `<Navigate to="/login" replace />` when unauthenticated.

| Path | Component | Guarded? | Notes |
|---|---|---|---|
| `/` | `Index` | No | Renders `null`; a `useEffect` navigates to `/dashboard` or `/login` on `isAuthenticated` (`frontend/src/pages/Index.tsx`). Does **not** wait for `isLoading` — see Gotcha below. |
| `/login` | `Login` | No | Marketing panel plus a "Sign in" button that sets `window.location.href` to `/api/auth/login` (or `?force_login=true` for `firm_revoked` / `account_suspended`). No credentials handled client-side. Its mount effect deletes `auth_token`. |
| `/auth/callback` | `AuthCallback` | No | Reads `?token=` from the query string, writes it to `localStorage.auth_token`, then `navigate('/dashboard', { replace: true })`; with no token, `/login`. |
| `/verify-email` | `VerifyEmail` | No | Resend flow against `POST /api/auth/resend-verification?email=...`. |
| `/dashboard` | `DashboardLayout` in `ProtectedRoute` | Yes | Layout route; all rows below are children. |
| `/dashboard` (index) | `DashboardHome` | Yes | Role switch — see *Role-specific dashboards*. |
| `/dashboard/users` | `UsersPage` | Yes | Sidebar-visible to `super_admin`, `admin`. |
| `/dashboard/users/:id` | `UserDetailPage` | Yes | |
| `/dashboard/clients` | `ClientsPage` | Yes | Sidebar-visible to `advisor`, `firm_admin`, `firm_advisor`. |
| `/dashboard/advisors` | `AdvisorsPage` | Yes | Sidebar-visible to `firm_admin`. |
| `/dashboard/engagements` | `EngagementsPage` | Yes | Hosts `EngagementForm` (`frontend/src/components/engagement/form.tsx`). |
| `/dashboard/engagements/:engagementId` | `EngagementDetailPage` | Yes | Tabbed detail view — see *Engagement detail page composition*. |
| `/dashboard/engagements/:engagementId/bba` | `FileUploadPOCPage` | Yes | Engagement-scoped BBA builder. |
| `/dashboard/engagements/:engagementId/strategy-workbook` | `StrategyWorkbookPage` | Yes | |
| `/dashboard/engagements/:engagementId/strategic-business-plan` | `StrategicBusinessPlanPage` | Yes | |
| `/dashboard/engagements/:engagementId/roles-matrix` | `RolesMatrixPage` | Yes | |
| `/dashboard/engagements/:engagementId/pd-scorecard` | `PDScorecardPage` | Yes | |
| `/dashboard/ai-tools/bba` | `FileUploadPOCPage` | Yes | **Standalone twin** of the engagement-scoped route. |
| `/dashboard/ai-tools/strategy-workbook` | `StrategyWorkbookPage` | Yes | Standalone twin. |
| `/dashboard/ai-tools/strategic-business-plan` | `StrategicBusinessPlanPage` | Yes | Standalone twin. |
| `/dashboard/ai-tools/roles-matrix` | `RolesMatrixPage` | Yes | Standalone twin. |
| `/dashboard/ai-tools/pd-scorecard` | `PDScorecardPage` | Yes | Standalone twin; reachable from the `AIToolsPage` card grid. |
| `/dashboard/tasks` | `TasksPage` | Yes | |
| `/dashboard/documents` | `DocumentsPage` | Yes | Not present in the sidebar nav list. |
| `/dashboard/ai-tools` | `AIToolsPage` | Yes | Sidebar entry unconditionally suppressed (see *Layout, sidebar and navigation model*) — reachable only by typing the URL. |
| `/dashboard/settings` | `SettingsPage` | Yes | |
| `/dashboard/firms` | `FirmsPage` (`pages/dashboard/firm/Firms.tsx`) | Yes | `super_admin` only in nav. |
| `/dashboard/firms/:firmId` | `FirmDetailsLayout` | Yes | **No index child.** Renders the firm header and an empty `<Outlet context={{ firmId }}>`. Redirects away when `user.role !== 'super_admin'` (`FirmDetailsLayout.tsx:18-35`). |
| `/dashboard/firms/:firmId/clients` | `FirmDetailsClients` | Yes | Reads `firmId` via `useOutletContext`. |
| `/dashboard/firms/:firmId/advisors` | `FirmDetailsAdvisors` | Yes | |
| `/dashboard/firms/:firmId/engagements` | `FirmDetailsEngagements` | Yes | |
| `/dashboard/firms/:firmId/tasks` | `FirmDetailsTasks` | Yes | |
| `/dashboard/firms/:firmId/subscription` | `FirmDetailsSubscription` | Yes | |
| `/dashboard/subscriptions` | `SubscriptionsPage` (`pages/dashboard/Subscriptions.tsx`) | Yes | `super_admin` only in nav. |
| `/dashboard/ai-privacy` | `AIPrivacyPage` | Yes | Per-field "send to AI" toggles, one tab per questionnaire (`defaultValue="sale_ready"`). Performs no role check of its own. |
| `/dashboard/chat` | `DashboardHome` | Yes | **Silent placeholder** (`App.tsx:107`) — see below. |
| `/dashboard/analytics` | `DashboardHome` | Yes | **Silent placeholder** (`App.tsx:108`). |
| `/dashboard/firm` | `DashboardHome` | Yes | **Silent placeholder** (`App.tsx:109`). The "Firm Management" sidebar item points here and is filtered out unconditionally. |
| `/dashboard/security` | `DashboardHome` | Yes | **Silent placeholder** (`App.tsx:110`). |
| `*` | `NotFound` | No | Logs the path to `console.error`, links back to `/`. |

**The four placeholders are not 404s.** `frontend/src/App.tsx:105-110` maps `chat`, `analytics`, `firm` and `security` to `<DashboardHome />` under a `{/* Placeholder routes */}` comment. Navigating to any of them changes the URL and re-renders the role dashboard, giving the user no signal that the destination is unbuilt and giving a developer no error to trace. Treat a nav entry pointing at one of these as an unimplemented feature, not a routing bug.

> **Gotcha:** `Index` does not gate on `isLoading`. On a cold load of `/`, `isAuthenticated` is still `false` while `AuthProvider` is resolving, so `Index` navigates to `/login` — and `Login`'s mount effect (`frontend/src/pages/Login.tsx:39-48`) unconditionally does `localStorage.removeItem('auth_token')`. Landing on the bare root URL therefore logs a valid session out. Deep links to `/dashboard/*` are unaffected because `ProtectedRoute` blocks on `isLoading`.

**Twin routes.** Each tool page reads `engagementId` from `useParams`, so under `/dashboard/ai-tools/*` it is `undefined`, and the pages branch on that. `RolesMatrixPage` builds its list query as `` const query = engagementId ? `?engagement_id=${engagementId}` : '' `` (`frontend/src/pages/dashboard/RolesMatrixPage.tsx:66`) and points its back button at `/dashboard/ai-tools` instead of the engagement (`:182-186`). `FileUploadPOCPage` names the condition: `const isStandalone = !engagementId` (`frontend/src/pages/poc/FileUploadPOCPage.tsx:21`).

Tool pages are also entered with router `state`: `useToolLaunchers` navigates with `{ state: { bbaProjectId } }`, `{ state: { workbookId } }`, `{ state: { sbpPlanId } }`, `{ state: { matrixId } }`, `{ state: { buildId } }`, and each page reads the corresponding key off `useLocation().state`.

> **Gotcha:** Router `state` does not survive a hard refresh. `RolesMatrixPage` seeds `launchState` from `stateMatrixId ? 'ready' : 'checking'` (`:47`), so a direct load of `/dashboard/ai-tools/roles-matrix` with no `engagementId` and no `state.matrixId` starts in `'checking'` and falls back to listing or creating.

### State management

#### Store

`frontend/src/store/index.ts` registers **17** slices under `configureStore`. The only middleware customisation is `serializableCheck.ignoredActions: ['persist/PERSIST']` — a vestige, since no persistence library is installed. Typed hooks live in `frontend/src/store/hooks.ts` using the RTK 2.x `withTypes` form:

```ts
export const useAppDispatch = useDispatch.withTypes<AppDispatch>();
export const useAppSelector = useSelector.withTypes<RootState>();
```

The 17 registered keys are `engagement`, `tool`, `task`, `note`, `diagnostic`, `user`, `tag`, `advisorClient`, `firm`, `subscription`, `client`, `strategyWorkbook`, `strategicBusinessPlan`, `programGuide`, `deliverables`, `rolesMatrix`, `pdScorecard`. There is no `help` key — see *Dead and unreachable code*.

#### Slice registry

| Key | State shape | Key thunks | Consumed by |
|---|---|---|---|
| `engagement` | `engagements[]`, `selectedEngagement`, `isLoading`, `error`, `userRoleData`, `secondaryAdvisorCandidates[]`, `isLoadingCandidates`, `filters{status,clientId,search}` | `fetchUserRoleData`, `fetchEngagements`, `fetchEngagementById`, `createEngagement`, `updateEngagement`, `deleteEngagement`, `fetchSecondaryAdvisorCandidates`, `addClientsToEngagement`, `removeClientFromEngagement` | `EngagementsPage`, `SecondaryAdvisorDialog`, `AddClientsDialog`, `engagement/form.tsx`, `ClientsPage`, Admin/Advisor/FirmAdmin dashboards, `useGlobalDiagnosticPolling` |
| `tool` | `results[]`, `isLoading`, `isSaving`, `isSubmitting`, `error`, hard-coded `availableTools[]` | `saveToolProgress`, `submitTool`, `fetchToolResults` | **Nothing.** `store/slices/toolReducer.ts` is imported only by `store/index.ts`. |
| `task` | `tasks[]`, `selectedTask`, `isLoading`, `error`, `filters{engagementId,assignedToUserId,status,priority}` | `fetchTasks`, `fetchTaskById`, `createTask`, `updateTask`, `deleteTask` | `TasksPage`, `TasksList`, `AdminDashboard`, `AdvisorDashboard` |
| `note` | `notes[]`, `engagementNotes[]`, `isLoadingEngagementNotes`, `selectedNote`, `isLoading`, `error`, `filters{engagementId,taskId,noteType}` | `fetchNotes`, `createNote`, `updateNote`, `deleteNote`, `markNoteRead`, `fetchEngagementNotes` | `EngagementNotesModal`, `NotesList`, `ModuleSessionsPanel` |
| `diagnostic` | `diagnostic`, `isLoading`, `isSaving`, `isSubmitting`, `isPolling`, `isCancelling`, `error` | `fetchDiagnosticByEngagement`, `fetchDiagnosticById`, `updateDiagnosticResponses`, `submitDiagnostic`, `cancelDiagnosticProcessing`, `checkDiagnosticStatus`; plain reducers `updateLocalResponses`, `stopPolling`, `setDiagnosticCompleted`, `clearDiagnostic` | `ToolSurvey`, `EngagementDetailPage`, `useGlobalDiagnosticPolling` |
| `user` | `users[]`, `totalUsers`, `isLoading`, `isCreating`, `isUpdating`, `isDeleting`, `error` | `fetchUsers`, `createUser`, `updateUser`, `deleteUser` | `UsersPage`, `AdvisorClientDialog`, `AdminDashboard` |
| `tag` | `mediaTags: Record<mediaId,string>`, `diagnosticTags: Record<diagnosticId,string>`, `isLoading`, `error` | `fetchMediaTags`, `updateMediaTag`, `updateDiagnosticTag` | `EngagementDetailPage` |
| `advisorClient` | `associations[]`, `isLoading`, `isCreating`, `isDeleting`, `error` | `fetchAssociations`, `createAssociation`, `deleteAssociation` | `AdvisorClientDialog` |
| `firm` | `firms[]`, `firm`, `advisors[]`, `clients[]`, `stats`, `subscription`, `seats_used`, `seats_available`, `isLoading`, `error` | `fetchFirms`, `fetchFirm`, `fetchFirmById`, `fetchFirmAdvisors`, `addAdvisorToFirm`, `removeAdvisorFromFirm`, `getAdvisorEngagements`, `suspendAdvisor`, `reactivateAdvisor`, `fetchFirmStats`, `fetchFirmClients`, `fetchFirmClientsById`, `addClientToFirm`, `removeClientFromFirm`, `revokeFirm`, `reactivateFirm`, `createFirm` | `Firms`, `FirmDetailsLayout`, `FirmDetailsAdvisors`, `FirmDetailsSubscription`, `AdvisorsPage`, `ClientsPage`, `FirmAdminDashboard`, `AdvisorDashboard`, `AdvisorClientDialog` |
| `subscription` | `subscriptions[]`, `isLoading`, `isCreating`, `error` | `fetchSubscriptions`, `createSubscription` | `Subscriptions`, `CreateSubscriptionDialog` |
| `client` | `clients: ClientUser[]`, `isLoading`, `error` | `fetchClientUsers` | `ClientsPage` |
| `strategyWorkbook` | `currentWorkbook`, `uploadedFiles[]`, `clarificationNotes`, `clarificationAnswers: Record<number,string>`, `clarificationQuestions[]`, `isLoading`, `isExtracting`, `isGenerating`, `isPrechecking`, `error` | `uploadDocuments`, `precheckWorkbook`, `extractData`, `generateWorkbook`, `getWorkbook` | `StrategyWorkbookPage`, `ExtractStep`, `ClarifyStep` |
| `strategicBusinessPlan` | `currentPlan`, `employeePlan`, `uploadedFiles[]`, `isLoading`, `isAnalysing`, `isDraftingSection`, `isExporting`, `isGeneratingPresentation`, `isSavingEmployeePlan`, `error` | **23** thunks: `createPlan`, `createPlanFromDiagnostic`, `getPlan`, `uploadFiles`, `saveSetup`, `triggerCrossAnalysis`, `saveCrossAnalysisNotes`, `initialiseSections`, `draftSection`, `reviseSection`, `editSection`, `approveSection`, `surfaceThemes`, `assemblePlan`, `skipSection`, `skipAllPendingSections`, `reorderSections`, `resetPlanData`, `resetFromStep`, `updateStepProgress`, `fetchEmployeePlan`, `saveEmployeePlan`, `generatePresentation` | `StrategicBusinessPlanPage` and every `components/strategic-business-plan/*Step` plus `SectionEditor` |
| `programGuide` | `view`, `valueMovement`, `insights`, `isLoading`, `isReordering`, `error` | `fetchProgramGuide`, `reorderModules`, `resetModuleOrder`, `fetchValueMovement`, `fetchModuleInsights` | `ProgramGuideTab` |
| `deliverables` | `view`, `isLoading`, `pendingIds[]` (per-row spinners), `generatingModules[]` (per-module codes), `error` | `fetchDeliverables`, `setDeliverableComplete`, `setDeliverableScope`, `addAdvisorDeliverable`, `updateAdvisorDeliverable`, `removeAdvisorDeliverable`, `generateModuleTasks` | `ProgramGuideTab`, `ModuleDeliverablesPanel` |
| `rolesMatrix` | `currentMatrix`, `isLoading`, `isUploading`, `isExtracting`, `isGenerating`, `isSaving`, `isExporting`, `error` | `createMatrix`, `getMatrix`, `uploadDocuments`, `saveInputs`, `extractResponsibilities`, `generateMatrix`, `saveMatrixRows`, `updateStepProgress`, `exportMatrix` | `RolesMatrixPage` |
| `pdScorecard` | `currentBuild`, `suggestedRoles[]`, `activeRoleId`, `isLoading`, `isUploading`, `isExtracting`, `isGeneratingPD`, `isGeneratingScorecard`, `isSaving`, `isExporting`, `error` | `createBuild`, `getBuild`, `uploadDocuments`, `saveInputs`, `extractRoles`, `saveRoles`, `generatePD`, `savePD`, `approvePD`, `exportPD`, `generateScorecard`, `saveScorecard`, `approveScorecard`, `exportScorecard`, `updateStepProgress` | `PDScorecardPage` |

Every slice follows the same template: an `interface XState` with a bag of boolean loading flags plus `error: string | null`, thunks written with `createAsyncThunk` + `rejectWithValue`, and an `extraReducers` builder with pending/fulfilled/rejected per thunk.

**Camel/snake mapping is hand-written inside each thunk.** `engagementReducer` also remaps status values in both directions:

| Backend value | Frontend value |
|---|---|
| `draft` | `draft` |
| `active` | `active` |
| `paused` | `on-hold` |
| `completed` | `completed` |
| `archived` | `cancelled` |

`mapBackendStatusToFrontend` (`frontend/src/store/slices/engagementReducer.ts:180-190`) falls back to `'active'` for any unrecognised value; `mapFrontendStatusToBackend` (`:323-333`) is the inverse and has the same fallback. `Engagement.tool` is typed `'value_builder' | 'sale_ready' | 'diagnostic' | 'kpi_builder' | 'bba_builder'` (`:14`).

The diagnostic status enum is `'draft' | 'in_progress' | 'processing' | 'completed' | 'failed' | 'archived'` (`frontend/src/store/slices/diagnosticReducer.ts:9`), which matches the set the backend actually writes (see *Diagnostic Engine*). `DiagnosticResponseUpdate.status` (`:31`) omits `'failed'`.

Seven slices define their own `getAuthHeaders()` returning `{ Authorization, Content-Type }`: `firmReducer.ts:90`, `strategyWorkbookReducer.ts:51`, `strategicBusinessPlanReducer.ts:83` (takes a `json = true` flag so multipart uploads can drop the content type), `deliverablesReducer.ts:84`, `programGuideReducer.ts:225`, `pdScorecardReducer.ts:157`, `rolesMatrixReducer.ts:102`. `pdScorecardReducer` and `rolesMatrixReducer` additionally share a `readError(response, fallback)` helper, and `pdScorecardReducer` has `filenameFromResponse` / `downloadBlob` for its export endpoints.

#### Redux Toolkit vs TanStack Query — the actual division of labour

There is none. `@tanstack/react-query` is a dependency, a `QueryClient` is instantiated, and `QueryClientProvider` wraps the app — but a repo-wide grep for `useQuery`, `useMutation`, `useInfiniteQuery` and `useQueryClient` across `frontend/src` returns **zero hits**. The only four references to the library anywhere are the import and three JSX/constructor uses in `frontend/src/App.tsx:4`, `:45`, `:121`, `:131`.

All server state lives in Redux via `createAsyncThunk`, or in component-local `useState` + a bare `fetch` in a `useEffect` (`frontend/src/pages/dashboard/components/SuperAdminDashboard.tsx:64`, `:99`; `frontend/src/pages/dashboard/components/ClientDashboard.tsx:57`; `frontend/src/pages/dashboard/Engagement/EngagementDetailPage.tsx:75`, `:111`, `:192`). Treat TanStack Query as dead weight, not as a convention to follow.

### Data fetching conventions

The pattern, repeated near-verbatim across the codebase:

```ts
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
// ...
const token = localStorage.getItem('auth_token');
const response = await fetch(`${API_BASE_URL}/api/<resource>`, {
  headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
});
if (!response.ok) {
  const errorData = await response.json().catch(() => ({ detail: 'Failed to ...' }));
  throw new Error(errorData.detail || `HTTP ${response.status}: Failed to ...`);
}
```

That `API_BASE_URL` line appears **58 times across 56 files**:

| Location | Declarations |
|---|---|
| `frontend/src/components/**` | 21 |
| `frontend/src/store/slices/**` | 17 |
| `frontend/src/pages/**` | 16 |
| `frontend/src/lib/**` | 2 |
| `frontend/src/context/AuthContext.tsx` | 1 |
| `frontend/src/hooks/useToolLaunchers.ts` | 1 |

Two files declare it twice. `frontend/src/components/engagement/form.tsx` has no module-level declaration at all — only two function-local ones at `:262` and `:508`. `frontend/src/pages/dashboard/StrategyWorkbookPage.tsx` has a module-level one at `:23` shadowed by a function-local at `:139`.

> **Gotcha — the single most important thing to know about this frontend.** The 56 copies do not agree. `frontend/src/context/AuthContext.tsx:18` is `import.meta.env.VITE_API_BASE_URL || ''` — an empty-string fallback, i.e. same-origin. Every one of the other 55 falls back to `'http://localhost:8000'` (`frontend/src/pages/Login.tsx:7`, `frontend/src/lib/clientFetcher.ts:4`, and so on). With `VITE_API_BASE_URL` unset, **the two halves of the app talk to different origins**: `AuthContext`'s calls (`/api/auth/user`, `/api/auth/impersonation-status`, login, logout, impersonation start/stop) go same-origin and are the only traffic that ever reaches the Vite dev proxy, while every slice, page and component request goes direct to `localhost:8000`. Symptoms are asymmetric and confusing — a session that authenticates but whose data calls fail CORS, or the reverse. It is also the reason the `/api` and `/files` proxy entries in `frontend/vite.config.ts` look dead when you read them: they are exercised only by `AuthContext`. Any deployment where the base URL is not explicitly set is in this split state. Fix `AuthContext.tsx:18` to match the other 55 before changing anything else about deployment, and record the divergence as debt until all 56 collapse into one module.

Repo-wide there are ~239 `fetch(` call sites and 162 lines mentioning `Authorization`. `credentials: 'include'` is applied inconsistently — 52 occurrences in `components/`, 12 in `hooks/` (all of `useToolLaunchers.ts`), 8 in `pages/`, and 6 in `store/` (only `deliverablesReducer.ts` and `programGuideReducer.ts`). Every other slice omits it.

**Recommended consolidation.** Introduce a single `frontend/src/lib/api.ts` exporting the base URL once plus an `apiFetch(path, init)` that attaches the Bearer header, sets `Content-Type` for JSON bodies, applies `credentials: 'include'` uniformly, and normalises the `{detail}` error envelope into a thrown `Error`. The 58 `API_BASE_URL` declarations, the seven near-identical `getAuthHeaders()` definitions in `store/slices/` plus the three more inside `components/poc/` (`PresentationStep.tsx:120`, `TaskPlannerStep.tsx:188`, `TwelveMonthPlanStep.tsx:74`) and the one in `lib/aiPrivacyService.ts:12`, and the duplicated `.catch(() => ({ detail: ... }))` blocks all collapse into it. Do `store/slices/*.ts` first — densest cluster, most mechanical — then `pages/`, then components.

### Shared helpers in `frontend/src/lib/`

Five modules sit outside the slices and are easy to miss when tracing a data path, because nothing about their names suggests they issue network calls.

| File | Lines | Contents |
|---|---|---|
| `frontend/src/lib/clientFetcher.ts` | 174 | Role-branching client lookups (below) |
| `frontend/src/lib/userSortUtils.ts` | 90 | `sortUsersByLastEdited`, `sortAdvisorsBySurname` |
| `frontend/src/lib/utils.ts` | 84 | `cn`, `capitalizeFirstLetter`, `getUniqueClientIds`, `getPriorityBadgeClassName`, `isAdminRole`, `formatRoleForDisplay`, `getInitials` |
| `frontend/src/lib/aiPrivacyService.ts` | 41 | `getFieldConfigs(questionnaireType)` → `GET /api/ai-field-privacy/{type}`; `updateFieldConfigs(type, fields)` → `PUT /api/ai-field-privacy/{type}`. `QuestionnaireType = 'sale_ready' \| 'value_builder'`; items are `{ field_name, include_in_ai, updated_at?, updated_by_user_id? }` |
| `frontend/src/lib/taskUtils.ts` | 16 | `sortTasksByUpdatedAt` |

`clientFetcher.ts` exports three things:

- `fetchFirmAdvisorClientsFromEngagements(engagements, currentUserId)` — derives a `firm_advisor`'s client list **from engagement membership, not from the `adv_client` association table**. It filters `GET /api/engagements` down to rows where `String(engagement.primary_advisor_id) === String(currentUserId)` or `secondary_advisor_ids` includes it (`:56-57`), then collects those engagements' clients. The two sources can disagree: an advisor associated with a client but on no engagement with them, or on an engagement but with no association row, yields a different list depending on which function runs.
- `fetchAdvisorClientsFromAssociations()` — `GET /api/advisor-client?status_filter=active`.
- `getClientFetchingStrategy(user)` — pure, returns `{isAdvisor, isFirmAdvisor, isAdmin, isFirmAdmin, shouldUseEngagements, shouldUseAssociations, shouldUseFirmClients, shouldUseAdminClients}`.

> **Gotcha:** `getClientFetchingStrategy` hard-codes `shouldUseEngagements: false` (`clientFetcher.ts:168`, commented "Firm advisors now use associations instead of engagements"), so `fetchFirmAdvisorClientsFromEngagements` is exported but no strategy flag selects it. Both advisor roles route through associations. The engagement-derived path is live code with no caller — do not assume changing it changes behaviour.

### The dynamic survey renderer

Two SurveyJS-shaped JSON files drive the diagnostic. Both are `{ pages: [{ name, title, elements: [...] }] }` and are imported statically into the bundle:

| File | Size | Pages | Elements |
|---|---|---|---|
| `frontend/src/questions/questions_ValueBuilder.json` | ~136 KB | 10 | 306 |
| `frontend/src/questions/questions_sale_ready.json` | ~138 KB | 11 | 311 |

```ts
import valueBuilderSurveyData from '@/questions/questions_ValueBuilder.json';
import saleReadySurveyData from '@/questions/questions_sale_ready.json';
// ...
const surveyData = engagementType === 'sale_ready' ? saleReadySurveyData : valueBuilderSurveyData;
```
(`frontend/src/components/engagement/tools/ToolSurvey.tsx:37-38`, `:85`)

These are the client-side questionnaires; the backend's own copy and the scoring that consumes the answers are covered in *Diagnostic Engine*. A third file, `frontend/src/questions/diagnostic-survey.json` (~133 KB), is referenced by nothing.

**`ToolSurvey`** (`frontend/src/components/engagement/tools/ToolSurvey.tsx`, 1107 lines) owns one page at a time:

- Page state (`currentPage`, `completedPages`, `progress`), a page-number pill strip that auto-saves before jumping, and Previous / Save / Next-or-Submit buttons.
- `responses` is a `useMemo` merge of `diagnostic.userResponses` from Redux (source of truth) with a local `localResponses` map of unsaved edits, local winning (`:281-287`).
- `handleSaveProgress` (`:537-595`) PATCHes **only the current page's fields** plus any `<field>_other` companions with `status: 'in_progress'`, then deletes from `localResponses` exactly the keys the server echoed back.
- Advancing off page 0 for the first time also dispatches `updateEngagement({ id, updates: { status: 'active' } })`; failure is logged and swallowed so navigation still happens (`:688-701`).
- Submit is two-step: PATCH all responses, then `submitDiagnostic({ diagnosticId, completedByUserId })` (`:597-635`).
- While `status === 'processing'` and `isPolling`, it runs its own loop (`:140-260`): an immediate `checkDiagnosticStatus`, then `setInterval` every **10 s**, a `visibilitychange` listener to re-check on tab refocus (browsers throttle background intervals), and a **90-minute** safety timeout that stops polling and shows a warning toast.
- Fetches AI-privacy field configs for the questionnaire type and passes `isExcluded` down (`:129-137`); failures are silently swallowed since the badge is cosmetic.
- Renders a "Download Diagnostic Summary" button (`GET /api/diagnostics/{id}/download`) only when `hasExistingReport && status !== 'processing' && canAdminSeeThisReport`. `canAdminSeeThisReport` (`:97-109`) restricts `admin` and `firm_admin` to diagnostics whose `completed_by_user_id` matches their own id.

> **Gotcha:** The comment at `ToolSurvey.tsx:246` justifies the 90-minute timeout as a buffer over a 60-minute backend auto-fail. No such auto-fail runs in the deployed API — a stuck diagnostic stays `processing` indefinitely and must be reset through `POST /api/diagnostics/{id}/cancel`. Details in *Operations, Diagnostics & Troubleshooting*. The 90-minute timeout stops the client polling; it does not change server state.

**`ToolQuestion`** (`frontend/src/components/engagement/tools/ToolQuestion.tsx`) does two things: conditional visibility, then dispatch by `type`.

Visibility is a hand-rolled evaluator for SurveyJS `visibleIf` expressions. `evaluateCondition` (`:125-158`) replaces innermost parentheses with `true`/`false` recursively, then splits on ` and ` (checked first) then ` or `. `evaluateSingleCondition` (`:26-122`) regex-matches, in order: `{f} notempty`, `{f} == 'v'`, `{f} <> 'v'`, `{f} != 'v'`, `{f} >= n`, `{f} > n`, `{f} < n`, `{f} <= n`, `{f} allof ['a','b']`, `{f} contains 'text'`. An unrecognised expression returns `true` (fail-open, shows the question).

> **Gotcha:** `allof` is implemented as `expectedValues.includes(actualValue)` (`ToolQuestion.tsx:108`) — i.e. "any of", not SurveyJS's "all of". Numeric comparisons go through `parseInt`, so decimals truncate, and an empty/undefined field returns `false` rather than being skipped. Field names must match `\w+`. Because `>=` is tested before `>` and `<=` after `<`, a `{f} <= n` expression is matched by the `<` branch first and evaluated as a strict `<`.

Question type registry (`ToolQuestion.tsx:167-206`, barrel at `frontend/src/components/engagement/tools/question-types/index.ts`):

| JSON `type` | Component | JSON keys read | Stored value shape |
|---|---|---|---|
| `boolean` | `BooleanQuestion.tsx` | `name`, `title`, `description` | `true` / `false`; normalises legacy `"Yes"`/`"No"`/`"yes"`/`"no"` on read |
| `checkbox` | `CheckboxQuestion.tsx` | `choices` (string or `{value,text}`) | `string[]` |
| `comment` | `CommentQuestion.tsx` | `maxLength`, `placeholder` | `string`; shows a live `n / maxLength` counter when `maxLength` is set |
| `dropdown` | `DropdownQuestion.tsx` | `choices`, `choicesMin`/`choicesMax` (generates an inclusive numeric range that **replaces** `choices`), `showOtherItem`, `otherText`, `otherPlaceholder` | `string`; selecting the literal value `other` reveals a second input persisted to the sibling key `` `${name}_other` `` via `onFieldChange`, and is cleared when a non-other option is picked |
| `file` | `FileQuestion.tsx` | `allowMultiple`, `waitForUpload` | `FileMetadata[]` or a single `FileMetadata` — never raw `File` objects |
| `matrixdynamic` | `MatrixDynamicQuestion.tsx` | `columns[].name`, `columns[].title` | `Array<Record<columnName, string>>`, with add/remove row UI |
| `multipletext` | `MultipleTextQuestion.tsx` | `items[].name`, `items[].title` | `Record<itemName, string>` |
| `radiogroup` | `RadioGroupQuestions.tsx` (exported as `RadioGroupQuestion`) | `choices`, `showNoneItem` | `string` (`showNoneItem` appends a `none` option) |
| `text` | `TextQuestion.tsx` | `inputType`, `min`, `max`, `step`, `placeholder` | `string` |
| *anything else* | inline fallback | — | Renders a yellow box: `Unsupported question type: {type}` |

Type distribution:

| Type | `questions_ValueBuilder.json` | `questions_sale_ready.json` |
|---|---|---|
| `radiogroup` | 170 | 172 |
| `text` | 59 | 62 |
| `comment` | 24 | 23 |
| `checkbox` | 13 | 12 |
| `matrixdynamic` | 10 | 12 |
| `multipletext` | 10 | 10 |
| `dropdown` | 10 | 10 |
| `file` | 9 | 9 |
| `boolean` | 1 | 1 |

`FileQuestion` is the only type with side effects. When `waitForUpload` is set and a `diagnosticId` exists it:

1. POSTs each file to `/api/diagnostics/{id}/upload-file` as `multipart/form-data`;
2. stores the returned metadata (`file_name`, `file_type`, `file_size`, `relative_path`, `media_id`, `openai_file_id` (legacy), `llm_file_id`, `uploaded_by_user_id`, `uploaded_by_role`);
3. immediately `PATCH`es `/api/diagnostics/{id}/responses` with `{ user_responses: { [field]: metadata }, status: 'in_progress' }`;
4. dispatches `window` `CustomEvent('diagnostic-file-uploaded', { detail: { diagnosticId, engagementId } })` so `EngagementDetailPage` can refresh its file lists.

Removal calls `DELETE /api/diagnostics/{id}/delete-file?field_name=...&file_name=...` and rehydrates the field from the returned diagnostic. With `waitForUpload` unset, selecting a file does nothing at all — the handler has no else branch.

`ToolQuestion` also wraps excluded fields (`:208-225`): when `isExcluded` it renders the title plus an amber "Not sent to AI" badge and the description itself, then re-renders the inner control with `{...question, title: '', description: undefined}` so neither is duplicated.

### Engagement detail page composition

`frontend/src/pages/dashboard/Engagement/EngagementDetailPage.tsx` (857 lines) is a single component holding a shadcn `<Tabs>` with `activeTab` in local state (default `'overview'`). It fetches the engagement (`GET /api/engagements/{id}`), the diagnostics list (`GET /api/diagnostics/engagement/{id}`, then a `GET /api/diagnostics/{id}` per row in `Promise.all`), and `GET /api/engagements/{id}/generated-documents`. `fetchInFlightRef` (`:45`) guards against duplicate concurrent fetches, and the file fetches only re-run when `activeTab === 'overview'` (`:223-227`).

| Tab value | Label | Renders | Notes |
|---|---|---|---|
| `overview` | Overview | Two `card-trinity` panels, each a `GeneratedFilesList` (`components/engagement/overview/`) — "Generated Files" and "Uploaded Files", each with a count | Rows are `GeneratedFile`; tag edits go through the `tag` slice; `handleDownload` branches between `/api/diagnostics/{id}/download` and `${API_BASE_URL}${file.downloadUrl}` |
| `tasks` | Tasks | `TasksList` (`components/engagement/tasks/`) | Client-side filter by status/priority/search over the `task` slice, `TASKS_PER_PAGE = 10`, `TaskItem` rows and a `TaskForm` dialog |
| `diagnostic` | Diagnostic | `<ToolSurvey engagementId toolType="diagnostic" engagementType={engagement?.tool} />` | The survey renderer above |
| `program-guide` | **Value Builder** | `ProgramGuideTab` (`components/engagement/program-guide/`) | Rendered only when `canViewProgramGuide = engagement?.tool === 'value_builder' && !isClient` (`:61`). Its 11 sibling components, two-view swap and four mount-time thunks are described in *Value Builder Programme — Program Guide & Deliverables* |
| `tools` | Tools | `FollowUpToolsTab` | A flat list of five tool rows plus five `AlertDialog`s, driven entirely by `useToolLaunchers` |
| `chatbot` | Chat Bot | `EngagementChatbot` (`components/engagement/chatbot/`) | Conversation bootstrap against `/api/chat/conversations`, messages at `/api/chat/conversations/{id}/messages`, `ChatMessage` rows |

Notes are **not** a tab — a "Notes" button in the page header (`:721`) opens `EngagementNotesModal` (`components/engagement/notes/`), a dialog with a `PanelMode` of `'view' | 'add' | 'edit'` plus search and a mobile detail sheet, driven by the `note` slice.

The `TabsList` grid column count is hard-coded to `grid-cols-6` or `grid-cols-5` depending on `canViewProgramGuide` (`:740`).

#### `useToolLaunchers`

`frontend/src/hooks/useToolLaunchers.ts` (589 lines) centralises the "run this tool" flow for all five tools:

```ts
export type ToolKey = 'bba' | 'strategy_workbook' | 'strategic_business_plan' | 'roles_matrix' | 'pd_scorecard';
```

It is called as `useToolLaunchers(engagementId, diagnostics, currentUserId?, isAdmin?)` and returns `{ effectiveDiagnosticId, anyLoading, tools }` where `tools` is a `Record<ToolKey, { loading, run, dialog: {open,title,description,warning}, continueExisting, startFresh, cancelDialog }>`.

`run()` pre-flights the tool's list endpoint; if an existing project is found it opens a Continue-vs-Start-Fresh `AlertDialog` with tool-specific copy (BBA's, for example, names the step out of 9); otherwise it creates and navigates. "Start Fresh" for BBA / Strategy Workbook / SBP appends `&force_new=true` to the create URL, while Roles Matrix and PD Scorecard issue a `DELETE` of the prior record first. Every call sets `credentials: 'include'`.

`effectiveDiagnosticId` (`:100-112`) is the first `status === 'completed'` diagnostic, further filtered when `isAdmin` to ones whose normalised `created_by_user_id` **or** `completed_by_user_id` equals the current user id. This is looser than `ToolSurvey`'s `canAdminSeeThisReport`, which checks `completed_by_user_id` only.

`ModuleDetail` also calls `useToolLaunchers` independently, so an engagement page with the Value Builder tab open has two instances of this hook live at once.

### Role-specific dashboards

`frontend/src/pages/dashboard/DashboardHome.tsx` renders a title and delegates on `user?.role` (`:14-36`). All five components live in `frontend/src/pages/dashboard/components/`.

| `user.role` | Title | Component |
|---|---|---|
| `super_admin` | "Platform Overview" | `SuperAdminDashboard` |
| `admin` | "Administration Dashboard" | `AdminDashboard` |
| `advisor` | "Advisor Dashboard" | `AdvisorDashboard` |
| `firm_advisor` | "Advisor Dashboard" | `AdvisorDashboard` (shared) |
| `client` | "My Dashboard" | `ClientDashboard` |
| `firm_admin` | "Firm Dashboard" | `FirmAdminDashboard` |
| anything else | "Dashboard" | `null` |

| Component | Lines | Data source | Stat cards |
|---|---|---|---|
| `AdminDashboard.tsx` | 109 | Pure Redux: `fetchUsers({limit:1000})`, `fetchEngagements({})`, `fetchTasks({limit:1000})` on mount | Total Users, Total Engagements, Clients, Advisors |
| `AdvisorDashboard.tsx` | 344 | Hybrid — Redux (`engagement`, `task`, `firm`) plus a direct `fetch` of `/api/dashboard/stats` (`:86`) into local state | Total Clients, Engagements, Documents |
| `ClientDashboard.tsx` | 348 | No Redux; local `useState` + one `fetch` of `/api/dashboard/stats` (`:57`) | My Tasks, Documents, Diagnostics |
| `FirmAdminDashboard.tsx` | 274 | Pure Redux: `fetchFirm()`, then on `firm.id` → `fetchFirmAdvisors(firm.id)`, `fetchFirmClients()`, `fetchFirmStats(firm.id)`, `fetchEngagements({firm_id: firm.id})` | Firm Advisors, Total Clients, Active Engagements, Subscription Days |
| `SuperAdminDashboard.tsx` | 324 | No Redux; two local fetches — `/api/dashboard/stats` (`:64`) and `/api/dashboard/activity?days={timePeriod}` (`:99`, with a period selector) | Total Users, Active Engagements, Total Firms, AI Generations |

All five use the shared `StatCard` primitive from `frontend/src/components/ui/stat-card.tsx`, whose props are `{ title, value, change?, changeType?: 'positive'|'negative'|'neutral', icon: LucideIcon, iconColor?, className? }`. It renders the `.stat-card` class defined in `frontend/src/index.css`.

Because the four placeholder routes above all render `DashboardHome`, any of these five components can also appear at a URL that promises something else.

### Layout, sidebar and navigation model

`frontend/src/components/layout/DashboardLayout.tsx` is the layout route element. It holds `sidebarCollapsed` in local state, mounts the global diagnostic polling hook (`:17`), and renders `Sidebar` (fixed, `w-[260px]` / `w-[72px]` collapsed) beside a flex column of `TopBar` → `ImpersonationBanner` → `<main><Outlet/></main>`, with the main column offset by `ml-[260px]` / `ml-[72px]`. It returns `null` when `!isAuthenticated || !user`.

`TopBar` (`frontend/src/components/layout/TopBar.tsx`) shows a role badge from `roleLabels` / `roleColors` in `frontend/src/types/auth.ts:23-39`, a decorative bell with an always-on dot (no notification wiring), and a dropdown with the user's identity and Log out. The avatar `src` is `user.avatar.startsWith('http') ? user.avatar : ${API_BASE_URL}${user.avatar}` with an `onError` handler that hides the image and overwrites the parent's `textContent` with the first initial. `Sidebar.tsx:216-235` duplicates that avatar block verbatim.

`ImpersonationBanner` (`frontend/src/components/ImpersonationBanner.tsx:9`) renders only when `isImpersonating && user && originalUser`, naming both accounts and offering "Stop Impersonation". The backend side of that session is described in *Authentication, Authorization & Impersonation*.

#### Sidebar nav model

`frontend/src/components/layout/Sidebar.tsx:39-52` declares a flat `NavItem[]` of `{ label, href, icon, roles: UserRole[] }`. `UserRole` is the six-member union in `frontend/src/types/auth.ts:1`.

| Label | Href | `roles` |
|---|---|---|
| Dashboard | `/dashboard` | all six |
| Users | `/dashboard/users` | `super_admin`, `admin` |
| Firms | `/dashboard/firms` | `super_admin` |
| Subscriptions | `/dashboard/subscriptions` | `super_admin` |
| Clients | `/dashboard/clients` | `advisor`, `firm_admin`, `firm_advisor` |
| Advisors | `/dashboard/advisors` | `firm_admin` |
| Engagements | `/dashboard/engagements` | all six |
| Tasks | `/dashboard/tasks` | all six |
| AI Tools | `/dashboard/ai-tools` | `super_admin`, `admin`, `advisor`, `firm_admin`, `firm_advisor` |
| Firm Management | `/dashboard/firm` | `firm_admin` |
| AI Privacy | `/dashboard/ai-privacy` | `super_admin`, `admin` |
| Settings | `/dashboard/settings` | all six |

Filtering happens in two stages, and both have quirks worth knowing on day one:

1. **Declarative role filter plus one hard exclusion** (`:59-61`):
   ```ts
   const filteredItems = navItems.filter(item =>
     user && item.roles.includes(user.role) && item.href !== '/dashboard/firm' // Remove firm admin dashboard from superadmin
   );
   ```
   The `item.href !== '/dashboard/firm'` clause is unconditional, so **"Firm Management" is hidden from every role**. Since `firm_admin` is the only role listed for it, the item can never render. The comment does not match the behaviour — and the route behind it is one of the four silent placeholders, so the entry would go nowhere even if it did render.

2. **An imperative suppression inside the render loop** (`:185-186`): `// AI Tools hidden for now` / `if (item.href === '/dashboard/ai-tools') return null;`. The AI Tools entry is dead for all roles, so `/dashboard/ai-tools` and its five standalone tool routes are URL-only.

`AI Privacy` is visible to both `super_admin` and `admin`; `AIPrivacyPage` itself performs no role check.

**Firms sub-navigation.** For `super_admin` the Firms item is special-cased (`:119-183`): when the path matches `/^\/dashboard\/firms\/([^/]+)/` the `firmId` is extracted and five nested links (Clients, Advisors, Engagements, Tasks, Subscription) render indented behind a chevron toggle. `firmsExpanded` auto-opens via a `useEffect` (`:70-74`) when on the firms list or a firm detail page — but the chevron and the nested block only render when `isOnFirmDetails`, so on the plain list page the flag is set with nothing to show.

**Active-state logic** (`:189-192`) is prefix matching with two explicit carve-outs so `/dashboard/firms/...` and `/dashboard/ai-tools/...` do not light up their parents:
```ts
const isActive = location.pathname === item.href ||
  (item.href !== '/dashboard' && location.pathname.startsWith(item.href) &&
   !location.pathname.startsWith('/dashboard/firms/') &&
   !location.pathname.startsWith('/dashboard/ai-tools/'));
```

`frontend/src/components/NavLink.tsx` is a `forwardRef` wrapper over React Router's `NavLink` that accepts flat `className` / `activeClassName` / `pendingClassName` strings and merges them with `cn()`, restoring the v5-style API. The visual classes `sidebar-item` and `sidebar-item-active` are defined in `frontend/src/index.css` under `@layer components`.

### Global diagnostic polling

`frontend/src/hooks/useGlobalDiagnosticPolling.ts` (174 lines) is mounted exactly once, at `frontend/src/components/layout/DashboardLayout.tsx:17`, so it runs on every authenticated page. Its job is to raise a toast when a diagnostic submitted earlier finishes after the user has navigated away from the survey. `frontend/GLOBAL_DIAGNOSTIC_POLLING.md` is its design note.

**localStorage is the source of truth.** Key `processing_diagnostics`, value a JSON array of `{ id: string, engagementId: string, timestamp: number }` where `timestamp` is `Date.now()` at the moment the diagnostic was observed to be processing. There is no server-side queue behind this and no cross-device state.

| Operation | Where |
|---|---|
| Write (append if absent) | `frontend/src/store/slices/diagnosticReducer.ts:405-417` in `fetchDiagnosticByEngagement.fulfilled` when `status === 'processing'`, and `:467-479` in `submitDiagnostic.fulfilled` |
| Remove | `diagnosticReducer.ts:499-511` (`cancelDiagnosticProcessing.fulfilled`); `ToolSurvey.tsx:153-168` (poll-loop terminal states) and `:659-672` (cancel confirm); `useGlobalDiagnosticPolling.ts:66-79` and `:107-121` |
| Expire | A mount-only effect drops entries older than **30 minutes** (`30 * 60 * 1000`) and rewrites or removes the key (`:150-172`) |

**Behaviour.** The main effect reads the key, skips entries older than 30 minutes (`:32`) and entries already notified, then starts one `setInterval` per remaining diagnostic at **30 000 ms** (`:137`), keyed by `diagnosticId` in a `Map` ref, each dispatching `checkDiagnosticStatus(diagnosticId)`. A second `Set` ref (`notifiedDiagnosticsRef`) guarantees one toast per diagnostic per page session. The effect's cleanup clears every interval; its dependency array is `[dispatch, engagements]`.

| Terminal status | Toast (via `sonner`) |
|---|---|
| `completed` | `toast.success('✅ Diagnostic Processing Completed!')`, description "Your diagnostic report is ready for download.", `duration: 10000`, with a **View Report** action that sets `window.location.href = /dashboard/engagements/${engagementId}`. Also dispatches `fetchEngagements({})`. |
| `failed` | `toast.error('❌ Diagnostic Processing Failed')`, description "Please try submitting the diagnostic again.", `duration: 10000`. |

> **Gotcha:** The queue is per-browser-profile. A diagnostic submitted on a different machine, a different browser, or an incognito window never appears in this `localStorage` key, so no completion toast is raised there and the user has to reload the engagement page to see the result. Clearing site data has the same effect. The run itself is unaffected — it completes server-side regardless.

> **Gotcha:** This runs *in addition to* the per-page 10-second poll inside `ToolSurvey` (`ToolSurvey.tsx:228-238`), which raises its own differently-worded toasts. While the Diagnostic tab is open the same diagnostic is polled by two independent loops, both writing the same `processing_diagnostics` key.

> **Gotcha:** `engagements` is in the dependency array, so every change to that array's identity tears down and recreates all intervals. Because the interval fires no immediate check, a stream of engagement refetches (the `completed` branch dispatches `fetchEngagements({})` itself) can reset the 30-second timer before it ever elapses.

> **Gotcha:** The 30-minute expiry runs only in a mount-only effect. A long-lived session never re-prunes, and the polling effect's own filter skips stale entries without deleting them.

> **Gotcha:** "View Report" uses `window.location.href`, forcing a full page reload rather than a client-side navigation.

### Dead and unreachable code

The build compiles only what is reachable from `src/main.tsx` and it does not type-check (see *Build and tooling*), so broken modules can sit in the tree indefinitely. Inventory:

**`frontend/src/pages/dashboard/help/HelpPage.tsx` (109 lines) — a Help / video-guide feature whose every dependency is missing.** The page renders a `PlayCircle` header, a `super_admin`/`admin`-gated "Manage videos" button navigating to `/dashboard/help/manage`, and a per-category video list with an empty state. It:

- imports `fetchCategoriesWithVideos` from `@/store/slices/helpReducer` (`HelpPage.tsx:5`) — **no such file exists** in `frontend/src/store/slices/`;
- imports `YouTubePlayer` from `@/components/help/YouTubePlayer` (`:6`) — **`frontend/src/components/help/` does not exist**;
- reads `state.help` (`:15`) — **not a key** in `frontend/src/store/index.ts`, so the selector would throw at render;
- has no route: neither `/dashboard/help` nor `/dashboard/help/manage` appears in `frontend/src/App.tsx`, and nothing imports the page;
- has no backend: there is no help or video endpoint under `backend/app/api/`.

It survives only because `npm run build` is bare `vite build` with no `tsc` — an unreferenced module is never compiled, so three unresolvable imports produce no error. **Adding a route for this page, or ever wiring `tsc --noEmit` into the build, breaks the build immediately.** Either finish the feature (reducer, player component, backend CRUD, two routes) or delete the file; do not add the route first.

| Other dead surface | Where | Note |
|---|---|---|
| `@tanstack/react-query` | `frontend/src/App.tsx:4`, `:45`, `:121`, `:131` | Provider mounted, zero hook call sites — see *State management* |
| `tool` Redux slice | `frontend/src/store/slices/toolReducer.ts` | Registered in the store, imported by nothing else |
| "Generate Document from Template" panel | `ToolSurvey.tsx:843` | Whole panel behind `{false && hasResponses && ...}` — permanently dead UI covering upload/select/generate/delete of `.docx` templates. The effect that populates it was **not** disabled: `:298-335` still fires `GET /api/diagnostics/{id}/templates` on every mount once responses exist. `handleGenerateDocument`, `handleTemplateUpload` and `handleDeleteTemplate` (`POST /api/diagnostics/{id}/generate-document`, `POST /api/diagnostics/templates/upload`, `DELETE /api/diagnostics/templates/{name}`) are unreachable from the UI |
| `frontend/src/questions/diagnostic-survey.json` | ~133 KB | Referenced by nothing |
| `frontend/src/components/engagement/tools/ToolPage.tsx` | — | **0-byte file**, imported nowhere |
| `fetchFirmAdvisorClientsFromEngagements` | `clientFetcher.ts:28` | Exported, no strategy flag selects it — see *Shared helpers* |
| `.dark` CSS token block | `frontend/src/index.css:101-137` | No `ThemeProvider`, nothing sets a `dark` class |
| "Firm Management" nav item | `Sidebar.tsx:39-52` | Filtered out unconditionally; its route is a placeholder |
| "AI Tools" nav item | `Sidebar.tsx:185-186` | Suppressed for all roles; the six routes behind it are URL-only |

### Styling system

**Tailwind** (`frontend/tailwind.config.ts`): `darkMode: ["class"]`, no prefix, content globs `./pages`, `./components`, `./app`, `./src` (the first three do not exist at the project root — only `./src/**/*.{ts,tsx}` matches anything). `theme.container` is `{ center: true, padding: "2rem", screens: { "2xl": "1400px" } }`. Extensions:

| Area | Tokens |
|---|---|
| `fontFamily` | `sans` → `DM Sans, system-ui, sans-serif`; `heading` → `Plus Jakarta Sans, system-ui, sans-serif`. Both loaded via a Google Fonts `@import` at `frontend/src/index.css:1`. |
| `colors` | All `hsl(var(--token))` indirections: `border`, `input`, `ring`, `background`, `foreground`, and DEFAULT/foreground pairs for `primary`, `secondary`, `destructive`, `muted`, `accent`, `success`, `warning`, `info`, `popover`, `card`, plus a `sidebar.*` scale (`DEFAULT`, `foreground`, `primary`, `primary-foreground`, `accent`, `accent-foreground`, `border`, `ring`). |
| `borderRadius` | `lg`/`md`/`sm` derived from `var(--radius)`. |
| `boxShadow` | `trinity`, `trinity-md`, `trinity-lg`, `trinity-xl`, `glow` → `--shadow-card` / `--shadow-md` / `--shadow-lg` / `--shadow-xl` / `--shadow-glow`. |
| `keyframes` | `accordion-down`, `accordion-up` (Radix), `shimmer`, `pulse`. |
| `animation` | `accordion-down` / `accordion-up` (0.2s), `shimmer` (2s linear infinite), `pulse-slow` (`pulse` 3s ease-in-out infinite). |
| `plugins` | `[require("tailwindcss-animate")]` — **only**. |

The CSS variables live in `frontend/src/index.css` under `@layer base` (`:34-99` light `:root`, `:101-137` `.dark`), including gradient tokens (`--gradient-primary/accent/hero/card/glass`) and shadow tokens (`--shadow-sm/md/lg/xl/glow/card`). A second `@layer base` block (`:141-154`) applies `border-border` globally and sets the body/heading fonts. `@layer components` (`:156-266`) defines `.card-trinity`, `.stat-card`, `.glass-panel`, `.text-gradient`, `.btn-trinity`, `.btn-primary`, `.btn-secondary`, `.sidebar-item`, `.sidebar-item-active`, `.status-badge`, `.status-success/warning/info/error`, `.table-trinity`, `.input-trinity`, `.progress-trinity`, `.progress-trinity-bar`. A hand-written `.sbp-content` block (`:268-439`) styles LLM-generated HTML in the Strategic Business Plan. `@layer utilities` (`:441-500`) defines `.animate-fade-in`, `.animate-slide-up`, `.animate-slide-in-left`, `.animate-scale-in` with local `@keyframes`, plus `.stagger-1`…`.stagger-5` delay classes — hand-rolled CSS, not Tailwind config entries.

> **Gotcha:** `@tailwindcss/typography` is in `devDependencies` but is **not** in the `plugins` array. Ten call sites use `prose` / `prose-sm` — `components/poc/ExpandedFindingsStep.tsx:477`, `components/poc/ReviewEditStep.tsx:323,342,440`, `components/strategic-business-plan/PlanAssemblyStep.tsx:104,111`, `components/strategic-business-plan/SectionEditor.tsx:184,188,251,255` — and they generate no CSS. The SBP call sites also carry `sbp-content`, which does the real work; the two `poc/` files have no fallback.

**shadcn/ui** (`frontend/components.json`): `style: "default"`, `rsc: false`, `tsx: true`, `tailwind.baseColor: "slate"`, `cssVariables: true`, empty prefix, config `tailwind.config.ts`, css `src/index.css`. Aliases map `components → @/components`, `utils → @/lib/utils`, `ui → @/components/ui`, `lib → @/lib`, `hooks → @/hooks`. `frontend/src/components/ui/` holds **50 files** — the standard Radix-backed primitives (including `chart.tsx`, `sidebar.tsx` and a `use-toast.ts` re-export shim over `@/hooks/use-toast`) plus one local addition, `stat-card.tsx`. Adding a new primitive with the shadcn CLI lands in the right place and picks up the right import paths.

> **Gotcha:** `frontend/src/components/ui/sidebar.tsx` is shadcn's own sidebar primitive and is unrelated to the app's `frontend/src/components/layout/Sidebar.tsx`. Do not confuse the two when searching.

**The `@` alias** is declared in three places and must be kept in sync: `frontend/vite.config.ts` (`resolve.alias`), both `frontend/tsconfig.app.json` and `frontend/tsconfig.json` (`compilerOptions.paths`), and every alias in `frontend/components.json` depends on it resolving.

**`cn()`** (`frontend/src/lib/utils.ts:4-6`) is `twMerge(clsx(inputs))` — `clsx` resolves conditionals and arrays, `tailwind-merge` deduplicates conflicting Tailwind utilities so a caller's `className` prop can override a component's defaults. Use it for every composed `className`.

### Build and tooling

**Scripts** (`frontend/package.json`):

| Script | Command | Notes |
|---|---|---|
| `dev` | `vite` | Dev server |
| `build` | `vite build` | Production mode. **No type-check** — see below |
| `build:dev` | `vite build --mode development` | Production bundle built with `development` mode — loads `.env.development`, and the only build that activates `componentTagger` |
| `lint` | `eslint .` | |
| `preview` | `vite preview` | |

There is no test runner and no test file in `frontend/`; the testing position for the whole repo is in *Engineering Standards, Workflow & Testing*.

**Vite** (`frontend/vite.config.ts`): the config is a function of `{ mode }` and calls `loadEnv(mode, process.cwd(), "")`.

- `server.host: "::"`, `server.port: **8080**`, `server.allowedHosts: ["*"]`.
- Proxy: `/api` and `/files` both to `apiTarget = env.VITE_API_BASE_URL || "http://localhost:8000"`, with `changeOrigin: true, secure: false`.
- Plugins: `@vitejs/plugin-react-swc` (SWC, not Babel), plus `mode === "development" && componentTagger()` from `lovable-tagger`, `.filter(Boolean)`-ed out otherwise. `componentTagger` annotates JSX with source metadata for the Lovable visual editor; dev-only and irrelevant to the production bundle.
- `resolve.alias`: `"@" → path.resolve(__dirname, "./src")`.

> **Gotcha:** The two proxy entries are close to inert. `frontend/.env` is git-tracked and sets `VITE_API_BASE_URL=http://localhost:8000`, so every module prefixes its requests with that absolute origin and bypasses the proxy entirely. Unset the variable and the proxy starts serving exactly one caller — `AuthContext`, the only file whose fallback is the empty string — while the other 55 files still target `localhost:8000` directly. There is no configuration in which the proxy carries the whole app. Env-var provenance and deployment settings are in *Environments, Configuration & Deployment*.

**ESLint** (`frontend/eslint.config.js`) — flat config via `tseslint.config()`:

- Ignores `dist`.
- Extends `js.configs.recommended` and `...tseslint.configs.recommended` (the non-type-checked preset — no `parserOptions.project`, so no type-aware rules run).
- Applies to `**/*.{ts,tsx}`, `ecmaVersion: 2020`, `globals.browser`.
- Plugins `react-hooks` and `react-refresh`, with `reactHooks.configs.recommended.rules` spread in.
- Two rule overrides: `"react-refresh/only-export-components": ["warn", { allowConstantExport: true }]` and **`"@typescript-eslint/no-unused-vars": "off"`**.

**TypeScript** — the item most likely to surprise a new owner. `frontend/tsconfig.json` is a solution file referencing `tsconfig.app.json` (`include: ["src"]`) and `tsconfig.node.json` (`include: ["vite.config.ts"]`), but it *also* carries its own `compilerOptions`, where a second set of relaxations lives.

`frontend/tsconfig.app.json` — the config that governs all of `src/` — explicitly disables exactly five checks, all in a block commented `/* Linting */`:

```jsonc
"strict": false,
"noUnusedLocals": false,
"noUnusedParameters": false,
"noImplicitAny": false,
"noFallthroughCasesInSwitch": false,
```

`strictNullChecks` is not named; it is off as a consequence of `"strict": false`. Full comparison:

| Flag | `tsconfig.app.json` (all of `src/`) | `tsconfig.node.json` (`vite.config.ts`) | Root `tsconfig.json` |
|---|---|---|---|
| `strict` | **`false`** (explicit) | `true` | — |
| `strictNullChecks` | off (implied by `strict:false`) | on (implied by `strict:true`) | **`false`** (explicit) |
| `noImplicitAny` | **`false`** (explicit) | on (implied) | **`false`** (explicit) |
| `noUnusedLocals` | **`false`** (explicit) | `false` | **`false`** |
| `noUnusedParameters` | **`false`** (explicit) | `false` | **`false`** |
| `noFallthroughCasesInSwitch` | **`false`** (explicit) | `true` | — |
| `skipLibCheck` | `true` | `true` | `true` |
| `allowJs` | — | — | `true` |
| `isolatedModules` / `moduleDetection` | `true` / `force` | `true` / `force` | — |
| `moduleResolution` | `bundler` | `bundler` | — |
| `baseUrl` / `paths` | `.` / `@/* → ./src/*` | — | `.` / `@/* → ./src/*` |
| `target` / `module` / `jsx` | `ES2020` / `ESNext` / `react-jsx` | `ES2022` / `ESNext` / — | — |

For application code: **no strict mode, no null checks, implicit `any` allowed, unused locals and parameters allowed, switch fall-through allowed.** `undefined`/`null` are assignable everywhere and untyped function parameters silently become `any` — five question-type components rely on that (`CommentQuestion`, `TextQuestion`, `RadioGroupQuestion`, `MatrixDynamicQuestion`, `MultipleTextQuestion` all take fully untyped props).

**None of it is enforced anyway, because there is no type-check step.** `npm run build` is bare `vite build`, which uses SWC to strip types without checking them; `tsc` appears in no script, there is no `typecheck` target, and no CI runs one. Even the relaxed settings above are never evaluated against the code. Two consequences visible today: `frontend/src/lib/clientFetcher.ts:2` does `import { User } from '@/context/AuthContext'`, but that module exports only `AuthProvider` and `useAuth` (the type lives in `frontend/src/types/auth.ts`); and `HelpPage.tsx` imports two modules that do not exist at all (see *Dead and unreachable code*). Nothing complains about either.

Practical expectation for a new owner: treat the type system here as documentation, not enforcement. A realistic sequence is (1) add a `typecheck` script running `tsc -b --noEmit` and see what the *current* settings already reject — delete or fix `HelpPage.tsx` and the `clientFetcher` import first, since those break it immediately; (2) make that script pass and wire it into the build; (3) only then tighten `strictNullChecks` and `noImplicitAny` directory by directory. Turning on `"strict": true` at step one will produce an error count large enough to stall the effort.

---

## 16. Engineering Standards, Workflow & Testing

This section records the conventions the Trinity Platform codebase actually follows on `staging`, measured by reading code rather than by asking what the rules are meant to be. Where practice is uniform, the convention is stated as a rule. Where practice is split, both halves are given with counts and a normalisation is recommended.

**There is no CI.** `.github/` contains exactly one file — `.github/pull_request_template.md` — and no `workflows/` directory. Nothing in this repository lints, type-checks, tests or builds a change automatically. Every standard below is enforced by review alone.

---

### Backend code conventions

#### 1.1 Module docstrings

Every module under `backend/app/` opens with a triple-quoted docstring. Measured across `app/api/`, `app/services/`, `app/models/`, `app/schemas/`, `app/utils/` (excluding `__init__.py`): **102 of 106 modules** have one. The exceptions are `backend/app/api/settings.py`, `backend/app/services/activity_service.py`, `backend/app/services/dashboard_service.py`, `backend/app/schemas/dashboard.py`.

The strongest examples are decision records, not descriptions. `backend/app/services/deliverable_permissions.py:1-34` records which specification part settles the role matrix, what "owner" resolves to in code, and the one unmodelled column (`users.account_type`, present in the database but absent from the `User` model on this branch) that blocks a finer rule. `backend/app/models/program_deliverable.py:1-18` explains the template/instance split before declaring a column.

> **Rule:** every new module starts with a docstring — the module's job, then the non-obvious constraint a future reader would otherwise break.

#### 1.2 Router → service → model layering

Intended layering: the router translates HTTP to a service call and back; the service owns business rules and raises `ValueError`; the model is a passive SQLAlchemy declaration. `backend/app/api/program_deliverable.py` is the reference implementation and says so at `:1-8` — *"Thin translation over ProgramDeliverableService. No business logic lives here."* All seven of its routes are short and contain no `db.query`.

Adherence is partial. Direct `db.query(...)` calls inside the API layer:

| Router | `db.query(` calls |
|---|---|
| `backend/app/api/engagements.py` | 65 |
| `backend/app/api/firms.py` | 37 |
| `backend/app/api/users.py` | 26 |
| `backend/app/api/tasks.py` | 21 |
| `backend/app/api/note.py` | 14 |
| `backend/app/api/adv_client.py` | 13 |
| `backend/app/api/diagnostics.py` | 9 |
| `backend/app/api/subscriptions.py` | 6 |
| `upload_poc`, `strategic_business_plan` | 5 each |
| `strategy_workbook`, `files`, `auth` | 4 each |
| `ai_field_privacy` | 3 |
| `settings`, `roles_matrix`, `pd_scorecard` | 2 each |
| `program_guide` | 1 |
| `program_deliverable`, `chat`, `dashboard` | 0 |

Conversely, only two service modules import `HTTPException`: `backend/app/services/deliverable_permissions.py` (deliberate — it is a FastAPI dependency, not business logic) and `backend/app/services/file_service.py` (a genuine leak of the HTTP layer into a service, at `:64`, `:71` and `:123`).

> **Rule:** new endpoints go through a service. A router may hold a `db.query` only to load the entity a `Depends` guard already resolved. Services raise `ValueError` (or a domain subclass); they never raise `HTTPException`. The exception is a permission module written explicitly as a dependency.

#### 1.3 `get_<thing>_service(db)` factories

Twelve services expose a module-level factory returning a service bound to the request session:

```python
# backend/app/services/program_deliverable_service.py:658
def get_program_deliverable_service(db: Session) -> ProgramDeliverableService:
```

Present in: `bba_service.py:731`, `chat_service.py:806`, `diagnostic_service.py:1295`, `file_service.py:294`, `firm_service.py:749`, `pd_scorecard_service.py:475`, `program_deliverable_service.py:658`, `program_guide_service.py:463`, `roles_matrix_service.py:273`, `sbp_presentation_service.py:99`, `sbp_service.py:523`, `strategy_workbook_service.py:576`.

Note the call site: the factory is invoked **inside the handler body**, not as a `Depends`, e.g. `service = get_program_deliverable_service(db)` at `backend/app/api/program_deliverable.py:115`.

> **Rule:** every stateful service class ships a `get_<thing>_service(db: Session) -> <Thing>Service` factory at module bottom, with a return type annotation. Handlers call it after taking `db: Session = Depends(get_db)`.

#### 1.4 The dependency trio

The standard handler signature composes three dependencies:

```python
# backend/app/api/tasks.py:409-415
@router.patch("/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: UUID,
    task_data: TaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
```

`get_db` comes from `backend/app/database.py`; `get_current_user` from `backend/app/utils/auth.py:187`, which checks a bearer token first, falls back to the session cookie, 401s when neither resolves (`:228`), then 403s deleted and inactive users.

**Role enforcement is not uniform.** `require_role([...])` (`backend/app/utils/auth.py:252`) is used in only **two of twenty-one routers** — `backend/app/api/pd_scorecard.py` (18 uses) and `backend/app/api/roles_matrix.py` (11 uses). Each names its own role constants: `BUILD_SETUP_ROLES`, `ROLE_WORK_ROLES`, `READ_ROLES` in `pd_scorecard.py:67-73` (all three currently aliases of `_ADVISOR_ROLES`), and `ADVISOR_ROLES` in `roles_matrix.py:43`. Elsewhere, authorisation is done one of two other ways:

1. **A resource guard used as a dependency**, which loads the entity, 404s, 403s and returns it — `require_deliverable_read` / `require_deliverable_write` in `backend/app/services/deliverable_permissions.py:90,108`. The endpoint then takes `engagement: Engagement = Depends(require_deliverable_write)` and never refetches. The allowed set is declared once as a `frozenset` (`DELIVERABLE_ACCESS_ROLES`, `:57`): `ADVISOR`, `FIRM_ADVISOR`, `FIRM_ADMIN`, `ADMIN`, `SUPER_ADMIN` — every `CLIENT` is denied.
2. **Inline checks in the handler body** via `check_engagement_access(...)` (`backend/app/services/role_check.py:10`), used across eleven routers, or the `can_*` helpers in `backend/app/services/firm_permissions.py`. This is the majority pattern, and it is the one that scales worst — see `backend/app/api/tasks.py:444-465`, where a 20-line `can_update` ladder sits inside the handler.

The six roles are `advisor`, `client`, `admin`, `super_admin`, `firm_admin`, `firm_advisor` (`backend/app/models/user.py:16-21`).

> **Rule:** for a new resource, put the guard in a `Depends`. Prefer pattern (1) — a `require_<resource>_<read|write>` dependency in a dedicated `*_permissions.py` module that returns the loaded entity — because it makes the rule testable in one place and stops handlers refetching. Use `require_role([...])` only for endpoints whose access depends on role alone with no per-resource relationship.

#### 1.5 Pydantic schemas

One schema module per resource under `backend/app/schemas/`, named after the model. Across **187 schema classes**, the suffix distribution is: `Response` (45), `Request` (28), `Update` (16), `Create` (15), `Base` (10), `Item` (8), `ListItem` (6), `View` (4), `Detail` (3). The remaining 52 carry ad-hoc names.

The canonical family, `backend/app/schemas/task.py`:

| Class | Line | Role |
|---|---|---|
| `TaskBase` | 11 | Shared fields |
| `TaskCreate(TaskBase)` | 26 | Create payload |
| `TaskUpdate(BaseModel)` | 53 | Partial update, all fields `Optional` |
| `TaskResponse(TaskBase)` | 65 | Single-resource response |
| `TaskListItem(TaskResponse)` | 80 | Collection row, adds denormalised display fields |

The same module also holds two off-pattern classes — `TaskCreateFromDiagnostic` (`:35`) and `BulkTaskCreate` (`:92`) — for operations that are not plain CRUD. `backend/app/schemas/engagement.py` follows the same core shape and adds `EngagementDetail` for the expanded single read.

`Update` schemas deliberately do **not** inherit `Base` — they must be all-optional so `model_dump(exclude_unset=True)` distinguishes "omitted" from "sent as null" (`backend/app/api/program_deliverable.py:176-178`).

> **Rule:** `<Resource>Base` → `<Resource>Create` → `<Resource>Update` (standalone, all optional) → `<Resource>Response` → `<Resource>ListItem`. Add `Detail` only when the single read genuinely returns more than the list row. Name non-CRUD payloads explicitly rather than bending the family.

#### 1.6 Column comments

**289 of 405** `Column(...)` declarations carry an explicit `comment=`. Coverage is best in the newer and most business-critical models and worst in the oldest.

| Model file | Columns | With `comment=` |
|---|---|---|
| `models/user.py` | 19 | 19 |
| `models/firm.py` | 12 | 12 |
| `models/adv_client.py` | 7 | 7 |
| `models/subscription.py` | 7 | 7 |
| `models/impersonation.py` | 6 | 6 |
| `models/bba.py` | 41 | 34 |
| `models/strategic_business_plan.py` | 36 | 30 |
| `models/roles_matrix.py` | 21 | 17 |
| `models/pd_scorecard.py` | 36 | 25 |
| `models/program_deliverable.py` | 32 | 19 |
| `models/program_guide.py` | 40 | 20 |
| `models/document_template.py` | 8 | **0** |

Comments carry real semantics, not restatements of the name:

```python
# backend/app/models/program_deliverable.py:44
is_mandatory = Column(
    Boolean,
    nullable=False,
    server_default='true',
    comment="Mandatory/optional flag for this preset; the only source of truth - instances never override it",
)
```

Uncommented columns are almost always structural (`id`, `created_at`, `updated_at`).

> **Rule:** every column that carries business meaning gets `comment=`. Say what the value means and what depends on it. `id`, `created_at`, `updated_at` are exempt.

#### 1.7 Naming, typing, and UUIDs

- Python is `snake_case` throughout; classes are `PascalCase`.
- **Every id path parameter is typed `UUID`** — 205 declarations of the form `<name>_id: UUID` across `backend/app/api/`, and zero `str`-typed path ids. The single `str`-typed id (`backend/app/api/files.py:30`, `diagnostic_id: str = Form(None)`) is a multipart form field, not a path param. This gives free 422 validation on malformed ids.
- Primary keys are `Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False)`.
- JSON columns use `JSONB` from `sqlalchemy.dialects.postgresql`. The schema layer types them `Dict[str, Any]`, so **nothing validates their inner shape** — see *Testing* on the render-contract tests that exist specifically to close that gap.

#### 1.8 Logging

**54 modules** declare `logger = logging.getLogger(__name__)` immediately after imports. Root config is in `backend/app/main.py:35-43`: `level=INFO`, format `'%(asctime)s - %(name)s - %(levelname)s - %(message)s'`, with `sqlalchemy.engine`, `sqlalchemy.pool` and `sqlalchemy.dialects` forced to `WARNING`.

Long-running and cross-boundary work uses a bracketed subsystem prefix as the first token of the message:

| Prefix | Uses | Subsystem |
|---|---|---|
| `[Pipeline]` | 53 | Diagnostic processing pipeline |
| `[Claude]` / `[Claude API]` | 49 / 26 | Anthropic client |
| `[OpenAI API]` / `[OpenAI]` | 33 / 32 | Legacy provider, retained for rollback |
| `[BBA Engine]` | 29 | BBA conversation engine |
| `[Scoring]` / `[Scoring Data]` | 23 / 4 | Diagnostic scoring |
| `[Background Task]` | 20 | In-process background work |
| `[BBA Export]` | 19 | BBA document export |
| `[PD Scorecard]` | 11 | PD scorecard tool |
| `[BBA Presentation]` | 11 | BBA presentation export |
| `[File Sync]` | 9 | File synchronisation |
| `[Roles Matrix]` | 8 | Roles matrix tool |
| `[StrategyWorkbook]` | 7 | Strategy workbook |
| `[BBA Task Planner]` | 7 | BBA task planning |
| `[SBP Engine]` / `[SBP]` | 6 / 1 | Strategic business plan |
| `[Precheck]` | 3 | Strategy workbook precheck |
| `[BBA PPTX]` | 3 | BBA PPTX exporter |

**Gotcha:** `[StrategyWorkbook]` is the only prefix without internal spacing, and `[SBP]`/`[SBP Engine]`, `[Scoring]`/`[Scoring Data]`, `[Claude]`/`[Claude API]` and `[OpenAI]`/`[OpenAI API]` are unstable pairs. A log grep written against one form misses the other.

> **Rule:** `logger = logging.getLogger(__name__)` per module. Prefix any message from AI calls, exports, pipelines or background work with an existing `[Bracketed Subsystem]` tag, spelled exactly as the table above. Do not invent a new tag when one fits.

---

### Error-handling conventions

#### 2.1 Status codes in use

Constants from `fastapi.status` are the norm — **569 uses** across `backend/app/`, against **11 raw integer literals**.

| Constant | Uses | Meaning as used here |
|---|---|---|
| `HTTP_404_NOT_FOUND` | 143 | Resource id does not resolve, or is soft-deleted |
| `HTTP_400_BAD_REQUEST` | 131 | Request is well-formed but violates a business rule |
| `HTTP_403_FORBIDDEN` | 125 | Authenticated but not permitted; also deleted/inactive account |
| `HTTP_500_INTERNAL_SERVER_ERROR` | 66 | Unexpected failure, usually a re-raise after logging |
| `HTTP_200_OK` | 53 | Explicit `status_code=` on non-CRUD tool endpoints |
| `HTTP_201_CREATED` | 29 | Create |
| `HTTP_401_UNAUTHORIZED` | 14 | No credentials at all (`backend/app/utils/auth.py:228`) |
| `HTTP_204_NO_CONTENT` | 7 | Delete with no body |
| `HTTP_409_CONFLICT` | 1 | Sole use in the codebase |

The 11 raw literals are all accounted for: `status_code=302` ×4 (Auth0 redirects, `backend/app/api/auth.py:150,159,180,190`), `400` ×3 (`auth.py:109`, `services/file_service.py:64,71`), `401` ×2 (`auth.py:232,247`), `404` ×1 (`firms.py:317`), `500` ×1 (`file_service.py:123`).

**Gotcha:** 422 never appears explicitly — it comes only from Pydantic and `UUID` path validation. A `UUID`-typed path param therefore returns **422, not 404**, for a malformed id, and 404 only for a well-formed id that does not exist.

#### 2.2 The 404 → 403 → 400 ordering

Handlers resolve existence, then permission, then business validity, in that order. Canonically:

```python
# backend/app/services/deliverable_permissions.py:66-88
def _load_engagement(engagement_id: UUID, db: Session) -> Engagement:
    engagement = db.query(Engagement).filter(
        Engagement.id == engagement_id,
        Engagement.is_deleted == False,  # noqa: E712
    ).first()
    if not engagement:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Engagement not found")
    return engagement


def _authorize(engagement, current_user, db, require_advisor) -> Engagement:
    if not check_engagement_access(engagement, current_user, require_advisor=require_advisor, db=db):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="You do not have access to this engagement")
    if engagement.tool != DELIVERABLE_PROGRAM_TYPE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Deliverables are only available for Value Builder engagements")
    return engagement
```

The same order appears inline in the older routers: `backend/app/api/tasks.py:422-465` 404s the task, 404s its engagement, then 403s on `check_engagement_access`, then 403s again on the finer `can_update` ladder.

**Gotcha:** the ordering is deliberate but leaks existence. A caller with no access to an engagement can distinguish "does not exist" (404) from "exists, denied" (403). That is the accepted trade-off here — it is not an accident, but do not assume it is safe for a future public API.

#### 2.3 Service `ValueError` → HTTP

Services raise `ValueError`. Routers catch it and convert. The pattern that must be copied is the **two-tier catch**, because the not-found exception subclasses `ValueError`:

```python
# backend/app/api/program_deliverable.py:44-58
def _not_found(action: str, exc: Exception) -> HTTPException:
    """
    A deliverable id that does not resolve is a 404, not a 400.

    DeliverableNotFound subclasses ValueError, so it must be caught BEFORE the
    generic handler in every endpoint below - otherwise it falls through and a
    stale id is indistinguishable from a malformed body.
    """
    logger.info("%s: %s", action, exc)
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_FOUND)


def _invalid(action: str, exc: Exception) -> HTTPException:
    logger.warning("%s: %s", action, exc)
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=_INVALID_REQUEST)
```

Used as:

```python
try:
    service.set_deliverable_complete(engagement, deliverable_id, body.is_complete, current_user.id)
except DeliverableNotFound as e:
    raise _not_found("Failed to set deliverable completion", e)
except ValueError as e:
    raise _invalid("Failed to set deliverable completion", e)
```

Note two further details: the client-facing `detail` is a **constant** (`_INVALID_REQUEST = "Invalid request data"`, `_NOT_FOUND = "Deliverable not found"`, at `:40-41`) while the exception text goes to the log only; and the log level differs — 404 logs at `info`, 400 at `warning`. Creates have no `DeliverableNotFound` branch at all, with a comment saying why (`backend/app/api/program_deliverable.py:165` — *"a create resolves nothing"*).

> **Rule:** services raise `ValueError`, or a domain subclass of it for "not found". Routers catch the subclass first, then `ValueError`. Log the exception; return a constant `detail`. Never let raw exception text reach a client.

---

### API conventions

#### 3.1 What is uniform

- **Kebab-case multi-word paths**: `/api/advisor-client`, `/api/ai-field-privacy`, `/api/pd-scorecard`, `/api/roles-matrix`, `/api/program-guide`, `/api/strategy-workbook`, `/api/strategic-business-plan`.
- **Plural collection resources**: `/api/engagements`, `/api/tasks`, `/api/notes`, `/api/users`, `/api/firms`, `/api/subscriptions`, `/api/files`, `/api/diagnostics`, `/api/deliverables`. Singular names are reserved for non-collection routers — `/api/auth`, `/api/chat`, `/api/dashboard`, `/api/settings` — and for the per-tool routers, each of which addresses one build at a time.
- **Every router declares `tags=[...]`**, and in nineteen of twenty-one the tag matches the path segment. Two do not: `backend/app/api/upload_poc.py:97` is `APIRouter(prefix="/api/poc", tags=["bba"])`, and `backend/app/api/auth.py:28` is `prefix="/api/auth", tags=["authentication"]`. Both split the `/api/docs` grouping from the URL.
- **`PATCH` for partial update**: 31 `@router.patch` vs 5 `@router.put`. The five `PUT`s are full-state replacements: `program_deliverable.py:107,125` (`.../complete`, `.../scope` — the body is the whole state of one boolean), `program_guide.py:118` (`.../order`), `ai_field_privacy.py:62` (upsert by questionnaire type), `settings.py:33` (`/profile`).
- **`201` on create**: 29 uses of `status.HTTP_201_CREATED`, including the interesting case at `backend/app/api/program_deliverable.py:206-224`, which returns 201 even when zero tasks were generated and documents why (`created_count` tells the caller the difference).
- Verb distribution across all 212 routes: POST 90, GET 69, PATCH 31, DELETE 17, PUT 5.

#### 3.2 `204` on delete — partial

Of **17 `DELETE` routes, 7 return `204`**:

| 204 | Other |
|---|---|
| `adv_client.py:283`, `engagements.py:1297`, `firms.py:279`, `firms.py:495`, `note.py:360`, `subscriptions.py:167`, `tasks.py:508` | `diagnostics.py:261` (200 + `DiagnosticDetail`), `diagnostics.py:1147` (200), `engagements.py:1202` (200 + `EngagementResponse`), `files.py:146` (200, no model), `pd_scorecard.py:213` (200), `program_deliverable.py:190` (200 + `DeliverableView`), `roles_matrix.py:165` (200), `settings.py:140` (200), `upload_poc.py:1914` (200), `users.py:537` (200) |

Some of the non-204 cases are defensible: `program_deliverable.py:190`, `engagements.py:1202` and `diagnostics.py:261` remove a child and return the recomputed parent view, which is more useful than an empty body. Others (`files.py:146`, `settings.py:140`) simply return an untyped dict.

> **Rule:** `DELETE` returns 204 with no body when nothing useful remains to say. It may return 200 with a `response_model` when it returns the recomputed parent resource. It must never return 200 with an undeclared dict.

#### 3.3 `response_model` — the largest real gap

**83 of 212 route decorators (39%) declare `response_model`.** The split is not random: it tracks the age and type of the router.

| Router | Routes | With `response_model` |
|---|---|---|
| `program_deliverable.py` | 7 | 7 |
| `program_guide.py` | 7 | 7 |
| `ai_field_privacy.py` | 2 | 2 |
| `dashboard.py` | 2 | 2 |
| `firms.py` | 17 | 13 |
| `diagnostics.py` | 17 | 10 |
| `engagements.py` | 10 | 8 |
| `chat.py` | 7 | 5 |
| `note.py` | 6 | 5 |
| `tasks.py` | 6 | 5 |
| `strategy_workbook.py` | 9 | 5 |
| `adv_client.py` | 5 | 4 |
| `subscriptions.py` | 5 | 4 |
| `users.py` | 7 | 4 |
| `strategic_business_plan.py` | 28 | 2 |
| `upload_poc.py` | 32 | **0** |
| `pd_scorecard.py` | 18 | **0** |
| `roles_matrix.py` | 11 | **0** |
| `auth.py` | 8 | **0** |
| `files.py` | 5 | **0** |
| `settings.py` | 3 | **0** |

The five AI-tool routers (`upload_poc`, `pd_scorecard`, `roles_matrix`, `strategic_business_plan`, `strategy_workbook`) account for 98 routes and 7 response models between them. Their responses are hand-built dicts, so the OpenAPI schema at `/api/docs` describes them as untyped, and the frontend's TypeScript interfaces for those tools are unverified assertions.

> **Rule:** every new route declares `response_model`. When touching an existing untyped route in an AI-tool router, add the schema as part of the change — the schema modules already exist (`backend/app/schemas/pd_scorecard.py`, `roles_matrix.py`, `strategic_business_plan.py`, `bba.py`).

#### 3.4 The `/api` prefix inconsistency

Correcting a common misreading: **every router does end up under `/api`.** No router is served outside it. The only non-`/api` surfaces are `GET /` (`backend/app/main.py:136`), `GET /health` (`main.py:146`), the docs at `/api/docs` and `/api/redoc`, and the `StaticFiles` mount at `/files` (`main.py:115`).

The inconsistency is in **where the prefix is declared**. Six routers declare a bare prefix and are given `/api` at `include_router` time; fifteen bake `/api` into their own `APIRouter(prefix=...)`.

| Router module | `APIRouter(prefix=)` | `include_router(prefix=)` | Effective path |
|---|---|---|---|
| `diagnostics.py:44` | `/diagnostics` | `/api` (`main.py:88`) | `/api/diagnostics` |
| `files.py:22` | `/files` | `/api` (`main.py:89`) | `/api/files` |
| `strategy_workbook.py:38` | `/strategy-workbook` | `/api` (`main.py:101`) | `/api/strategy-workbook` |
| `strategic_business_plan.py:46` | `/strategic-business-plan` | `/api` (`main.py:102`) | `/api/strategic-business-plan` |
| `program_guide.py:27` | `/program-guide` | `/api` (`main.py:103`) | `/api/program-guide` |
| `program_deliverable.py:38` | `/deliverables` | `/api` (`main.py:104`) | `/api/deliverables` |
| all fifteen others | `/api/<name>` | — | `/api/<name>` |

**Gotcha:** `main.py:90,106,107` carry inline comments (`# already has /api prefix`, `# POC router (already has /api prefix)`) precisely because the two conventions coexist and someone has been bitten. A router moved between the two lists without editing both files silently produces `/api/api/...` or drops the prefix entirely — and because there is no test that walks `app.routes`, nothing catches it.

Second gotcha: `backend/app/api/files.py:22` declares `prefix="/files"` while `main.py:115` mounts `StaticFiles` at the top-level `/files`. They do not collide today only because the router's effective prefix is `/api/files`. Removing the `prefix="/api"` from `main.py:89` would shadow the static mount.

> **Recommended normalisation:** move `/api` into every `APIRouter(prefix=...)` declaration, so a router's full path is readable from its own file, and drop the `prefix=` argument from all `include_router` calls in `main.py`. Six files change (`diagnostics.py`, `files.py`, `strategy_workbook.py`, `strategic_business_plan.py`, `program_guide.py`, `program_deliverable.py`) plus four lines in `main.py`; no URL changes, so no frontend or Postman collection edits are needed. Add a smoke test that asserts every `app.routes` path starts with `/api`, `/files`, `/health` or `/`.

---

### Frontend conventions

Stack as configured (`frontend/package.json`): Vite 5.4 + `@vitejs/plugin-react-swc`, React 18.3, TypeScript 5.8, Redux Toolkit 2.11, React Router 6.30, Tailwind 3.4, shadcn/ui on Radix, `sonner` for toasts, `recharts` for charts, `react-hook-form` + `zod` for forms, and `@tanstack/react-query` 5.83 (present as a dependency alongside Redux).

**Functional components with a typed props interface.** Zero uses of `React.FC` anywhere in `src/`; one class component in the whole tree (`frontend/src/components/ui/sheet.tsx`, generated by shadcn). 102 `Props` type declarations. The shape is always:

```tsx
// frontend/src/components/engagement/program-guide/ModuleContentPanel.tsx:16
interface ModuleContentPanelProps {
  module: ProgramGuideModule;
}

export function ModuleContentPanel({ module }: ModuleContentPanelProps) {
```

Named `export function`, destructured props, interface named `<ComponentName>Props` and declared immediately above.

**One slice per domain, wired in one store.** `frontend/src/store/index.ts` composes **seventeen** reducers, matching the seventeen files in `frontend/src/store/slices/`. The file naming is `<domain>Reducer.ts` — *not* `Slice.ts` — and each default-exports `slice.reducer`.

| State key | File |
|---|---|
| `engagement`, `tool`, `task`, `note`, `diagnostic`, `user`, `tag` | `engagementReducer.ts`, `toolReducer.ts`, `tasksReducer.ts`, `notesReducer.ts`, `diagnosticReducer.ts`, `userReducer.ts`, `tagReducer.ts` |
| `advisorClient`, `firm`, `subscription`, `client` | `advisorClientReducer.ts`, `firmReducer.ts`, `subscriptionReducer.ts`, `clientReducer.ts` |
| `strategyWorkbook`, `strategicBusinessPlan`, `programGuide`, `deliverables`, `rolesMatrix`, `pdScorecard` | matching `*Reducer.ts` |

**Gotcha:** the state key does not always match the file stem — `tasksReducer.ts` mounts at `task`, `notesReducer.ts` at `note`, while `deliverablesReducer.ts` mounts at `deliverables`. `RootState` and `AppDispatch` are exported from `store/index.ts:53-54`; typed hooks live in `frontend/src/store/hooks.ts`.

**`createAsyncThunk` per API call** — 123 of them across the slices — with a shared `request<T>` helper per slice. `frontend/src/store/slices/deliverablesReducer.ts:94-105` is the model: it reads `VITE_API_BASE_URL` (the only `import.meta.env` variable used anywhere — 58 references across `src/`), attaches `Authorization: Bearer ${localStorage.getItem('auth_token')}` and `credentials: 'include'`, and unwraps FastAPI's `{ detail }` error body with a `.catch()` so a non-JSON 502 does not throw a parse error over the real status. Thunks are named `'<domain>/<verb>'` (`'deliverables/setComplete'`, `'diagnostic/cancelProcessing'`) and every one wraps its body in `try/catch` returning `rejectWithValue(...)`.

**The `@/` alias** resolves to `frontend/src/`, declared twice and required in both places: `frontend/vite.config.ts:30-33` for the bundler and `frontend/tsconfig.app.json:23-26` for the compiler (`tsconfig.json` repeats it a third time for the solution root). `frontend/components.json:13-19` maps shadcn's aliases onto it (`@/components`, `@/components/ui`, `@/lib/utils`, `@/lib`, `@/hooks`). Relative imports are reserved for siblings within a feature folder (`./ModulePrimitives`, `./moduleDisplay`).

**shadcn/ui primitives live in `frontend/src/components/ui/`** — 50 files, generated by the shadcn CLI against `components.json` (style `default`, base colour `slate`, CSS variables on). Treat them as generated output: regenerate rather than hand-edit, and put variations in a wrapper component elsewhere.

**Tailwind utility-first with `cn()`.** `cn` is `twMerge(clsx(...))` at `frontend/src/lib/utils.ts:4`. Conditional and merged classes go through it; raw template-literal class strings are the exception. Repeated class strings are hoisted to named constants inside the feature folder (`SECTION_LABEL_CLASS:26`, `SOURCE_LABEL_CLASS:30`, `STATUS_CONFIG:33`, `RAG_CLASS:61` in `frontend/src/components/engagement/program-guide/moduleDisplay.ts`), and there is a small set of project-level component classes in `frontend/src/index.css` (e.g. `.card-trinity` at `:157`).

**Pages vs components.** Routable screens live in `frontend/src/pages/` (`AuthCallback.tsx`, `Login.tsx`, `NotFound.tsx`, `Index.tsx`, `VerifyEmail.tsx`, plus `pages/dashboard/` and `pages/poc/`) and are mostly suffixed `Page` when nested (`AIToolsPage.tsx`, `TasksPage.tsx`, `PDScorecardPage.tsx`, `SettingsPage.tsx`). Reusable pieces live in `frontend/src/components/`, grouped by feature (`engagement/`, `firms/`, `users/`, `advisors/`, `poc/`, `roles-matrix/`, `pd-scorecard/`, `strategy-workbook/`, `strategic-business-plan/`, `subscriptions/`, `layout/`, `ui/`). Feature folders are kebab-case; component files are PascalCase.

**Gotcha:** the `Page` suffix is not universal — `pages/dashboard/DashboardHome.tsx` and `pages/dashboard/Subscriptions.tsx` are routable screens without it.

**Gotchas in the frontend toolchain:**
- `frontend/tsconfig.app.json:18-22` sets `strict: false`, `noUnusedLocals: false`, `noUnusedParameters: false`, `noImplicitAny: false`, `noFallthroughCasesInSwitch: false`; `frontend/tsconfig.json` adds `strictNullChecks: false`. `frontend/eslint.config.js:23` then turns `@typescript-eslint/no-unused-vars` off. The type system is close to advisory.
- `"build": "vite build"` (`frontend/package.json:8`) — **no `tsc` step**. `npm run build` does not type-check. `npx tsc -b` must be run separately.
- There is **no test tooling at all**: no vitest, jest, or testing-library in either dependency block.
- `lovable-tagger` is a devDependency and `componentTagger()` runs in development mode (`frontend/vite.config.ts:28`); `frontend/README.md` is the unedited Lovable scaffold README and documents nothing about this project.

---

### Naming conventions

| Thing | Convention | Example |
|---|---|---|
| Backend module file | `snake_case.py`, singular, named for the resource | `backend/app/api/program_deliverable.py` |
| Backend package layout | `api/` \| `services/` \| `models/` \| `schemas/` mirroring each other by name | `api/roles_matrix.py` ↔ `services/roles_matrix_service.py` ↔ `models/roles_matrix.py` ↔ `schemas/roles_matrix.py` |
| Service class / factory | `<Domain>Service` + `get_<domain>_service(db)` | `ProgramDeliverableService`, `get_program_deliverable_service` |
| Permission module | `<domain>_permissions.py`, functions `require_<resource>_<read\|write>` | `deliverable_permissions.py`, `require_deliverable_write` |
| SQLAlchemy model | `PascalCase` singular | `EngagementModuleDeliverable` |
| Database table | `snake_case` — **plural for CRUD entities, singular for the newer program/link tables** | `users`, `tasks`, `engagements`, `diagnostics`, `firms`, `notes`, `subscriptions`, `impersonation_sessions` vs `program_module_deliverable`, `engagement_module_deliverable`, `program_module_content`, `engagement_program_module_state`, `advisor_client`, `ai_field_privacy`, `bba` |
| Column | `snake_case`; booleans `is_*`; FKs `<entity>_id`; array FKs `<entity>_ids`; timestamps `created_at` / `updated_at` | `is_mandatory`, `primary_advisor_id`, `secondary_advisor_ids` |
| Constraint / index | `uq_<table>_<cols>` / `ix_<table>_<cols>` | `uq_program_module_deliverable_type_module_key`, `ix_engagement_module_deliverable_engagement_module` |
| Pydantic schema | `<Resource>` + `Base`/`Create`/`Update`/`Response`/`ListItem`/`Detail` | `TaskCreate`, `EngagementListItem` |
| Endpoint path | `/api/<kebab-case-resource>`; plural for collections; `{id}` segments typed `UUID` | `/api/deliverables/engagements/{engagement_id}/items/{deliverable_id}` |
| Router tag | Matches the path segment, kebab-case | `tags=["program-guide"]` |
| Log prefix | `[Title Case Subsystem]` as the first token | `[Background Task] ...` |
| Prompt file | `backend/files/prompts/`; root-level `<purpose>_prompt[_<variant>].md`, tool-scoped `<tool-kebab>/<name>.md` | `scoring_prompt_report.md`, `category_prompt_financial.md`, `roles-matrix/…`, `strategy-workbook/…` |
| Alembic revision | `<rev_hash>_<snake_case_slug>.py`; merges named `merge_<what>` or `<hash>_merge_<what>` | `0cfcd28150eb_merge_add_task_source_deliverable_and_.py`, `merge_deliverable_and_sale_ready.py` |
| Frontend component | `PascalCase.tsx`, one component per file, `export function` | `ModuleDeliverablesPanel.tsx` |
| Frontend feature folder | `kebab-case/` under `src/components/` | `components/pd-scorecard/` |
| Frontend page | `PascalCase.tsx` in `src/pages/`, `Page` suffix for nested screens | `pages/dashboard/TasksPage.tsx` |
| Redux slice file | `<domain>Reducer.ts` in `src/store/slices/`, default-exports the reducer | `deliverablesReducer.ts` |
| Redux thunk | `'<domain>/<verb>'` | `'deliverables/setComplete'` |
| Frontend env var | `VITE_` prefix, SCREAMING_SNAKE | `VITE_API_BASE_URL` |
| Branch | `<type>/<slug-or-ticket>` — see *Git workflow* | `feature/bench-92`, `fix/advisor-email` |
| Commit | Conventional Commits: `<type>: <imperative summary>` | `feat: add ProgramProgressCard component for displaying program-wide progress` |

---

### Git workflow

#### 6.1 Branch topology

`staging` is the integration branch. Measured on this checkout: `origin/staging` is **55 commits ahead of `origin/main`** and `origin/main` is **0 commits ahead of `origin/staging`** — `main` is a strict ancestor and lags a full release cycle behind. Feature branches are cut from and merged into `staging`; `main` is promoted from `staging` in batches.

The remote carries **232 branches** (455 refs in total once tags and local branches are counted). The prefix taxonomy actually in use:

| Prefix | Count | Notes |
|---|---|---|
| `fix/` | 159 | Dominant. Slug (`fix/advisor-email`) or ticket (`fix/BBA-tool-error`) |
| `feature/` | 35 | Slug (`feature/value-builder-program`) or ticket (`feature/bench-92`) |
| `fix-2/` | 8 | Second attempt at the same ticket — `fix-2/bench-103`, `fix-2/bba-tool` |
| `bba/` | 5 | Phase-scoped, two segments deep — `bba/phase2/excel-generator`, `bba/phase3/ppt-generator` |
| `fix-3/` | 3 | Third attempt — `fix-3/bench-103`, `fix-3/bench-93` |
| `feature-2/` | 3 | `feature-2/bench-81`, `feature-2/bench-92`, `feature-2/bench-93` |
| `feat/` | 2 | `feat/pd-role-scorecard`, `feat/roles-matrix` — a third spelling of `feature/` |
| `merge/`, `fixes/`, `fix-bba/`, `tool/` | 1 each | `merge/value-builder-into-staging`, `fixes/audit-fixes`, `fix-bba/continuation`, `tool/bba-tool/poc` |
| bare / personal / topic | ~10 | `ibtehaj`, `fox/existing-modal`, `claude`, `claude-implementation`, `deploy`, `BENCH-60`, `url-changes`, `pr-template`, `drive-implementation`, `strategy-workbook-issues`, `ai-audit-issues-fix` |

Ticket ids are `bench-NN` in branch names and `BENCH-NN` in one branch (`BENCH-60`) — the case is not stable.

**Gotcha:** `fix-2/`, `fix-3/` and `feature-2/` are not a category; they are re-cuts of an abandoned branch for the same ticket. `fix/bench-81`, `feature/bench-81` and `feature-2/bench-81` all exist. There is no way to tell from the names which is authoritative. 232 remote branches with almost no deletion means `git branch -r` is not a useful index of live work.

#### 6.2 Commit messages

Conventional-Commit prefixes are the intended style and recent practice is close to it. Across the **55 commits on `staging` not yet in `main`**: 41 use a conventional prefix, 8 are merge commits, 6 are free-form (`database fixes`, `fixed migrations errors`, `value builder program guide setup`, `Enhance dynamic column fitting and text wrapping`, `enhance Roles & Responsibilities matrix visibility for clients`, `Add program deliverable models and service for engagement tracking`).

Across the last 400 commits the picture is much worse: **249 are merge commits** and only **46 carry a conventional prefix**; the rest are free-form. Prefix frequency in the last 200: `feat:` 33, `fix:` 7, `refactor:` 2, `test:` 1, `chore(backend):` 1.

**Gotcha:** `feat:` is used for migration housekeeping and pure cleanups too — `feat: alembic output cleanup`, `feat: migration drift cleanup`, `feat: drop redundant unique constraints and add merge roles matrix revision`. The prefix is not a reliable signal of what a commit does. Scopes (`chore(backend)`) appear exactly once.

#### 6.3 The PR template

`.github/pull_request_template.md` defines seven sections, each with an HTML-comment prompt; the last two are conditional in practice:

| Section | Content required |
|---|---|
| `## Summary` | What the PR does, short and concrete |
| `## Issue it fixes` | Why the change is needed; link the issue |
| `## Changes` | Bulleted list (three empty bullets pre-seeded) |
| `## How to Test` | Numbered reproduction steps (three pre-seeded) |
| `## Impact` | Checkbox pair — `[ ] No breaking changes` / `[ ] Breaking changes (explain below)` |
| `## Checklist` | `[ ] Code builds and runs locally` / `[ ] Docs or comments updated (if needed)` |
| `## Screenshots / Logs (if applicable)` | UI screenshots, metrics, logs |
| `## Notes for Reviewer` | What to focus on |

Note what the checklist does **not** ask: nothing about tests, migrations, or the `staging` target. Given there is no CI, "Code builds and runs locally" is the only build signal that exists.

#### 6.4 Recommended standard

1. **Branches:** `<type>/<ticket>-<short-slug>`, types limited to `feat`, `fix`, `chore`, `docs`, `refactor`. Ticket ids lowercase (`bench-92`). Retire `feature/`, `fix-2/`, `fix-3/`, `feature-2/`, `fixes/`, `fix-bba/`, `bba/` and personal-name branches. Never re-cut a branch for the same ticket — force-push the original. Delete branches on merge.
2. **Commits:** Conventional Commits, mandatory. Use the type that describes the change (`chore:` for migration housekeeping, not `feat:`). Scope with the affected area when useful: `fix(diagnostics): ...`.
3. **Base branch:** always `staging`. Promote `staging` → `main` as a deliberate release merge, not a drive-by.
4. **Migrations:** because all branches share one development Postgres, two branches that each add a revision produce sibling heads that collide on the shared database. **Restore the database and create a proper merge revision (`alembic merge`); never `alembic stamp` your way out.** The repository already carries 15 merge revisions out of 80 in `backend/alembic/versions/` — this is a recurring, not a theoretical, event.
5. **PR template:** add three lines to `## Checklist` — `[ ] Tests added or updated`, `[ ] Migration included and merges cleanly onto staging`, `[ ] response_model declared on any new route`.

---

### Testing

#### 7.1 Layout and tooling

All tests live in `backend/tests/` — a flat directory, no `unit/` or `integration/` split, package-marked by an empty `backend/tests/__init__.py`. There is **no `pytest.ini`, `pyproject.toml`, `setup.cfg` or `tox.ini`** anywhere in `backend/`, so pytest runs on defaults: no registered markers, no `testpaths`, no coverage configuration.

`backend/requirements-dev.txt` is two effective lines: `-r requirements.txt` plus `pytest==8.3.4`. That is the entire test toolchain.

Eleven test files, 300 test functions:

| File | Tests | Needs DB | Notes |
|---|---|---|---|
| `test_program_deliverable_status.py` | 17 | no | Pure — `derive_module_status()` over hand-built deliverable-state tuples |
| `test_program_deliverable_validation.py` | 16 | no | Pure — deliverable invariant validators |
| `test_program_guide_render_contract.py` | 25 | no | Reads the real JSON fixture from disk (`backend/files/program_guide/value_builder_modules.json`); asserts stored shape matches what the UI renders |
| `test_program_deliverable_mutations.py` | 34 | yes | Service-level; lazy materialization, unique constraints, boolean server defaults |
| `test_program_deliverable_api.py` | 27 | yes | HTTP role-boundary matrix over `/api/deliverables/engagements` |
| `test_deliverable_task_generation.py` | 24 | yes | HTTP; the "must NOT happen" rules of task generation |
| `test_program_guide_api.py` | 26 | yes | HTTP role boundaries over `/api/program-guide/engagements` |
| `test_program_guide_insights.py` | 24 | yes | Per-module diagnostic insights; absent-must-stay-absent |
| `test_program_guide_seed.py` | 67 | yes | Seed script: in-place update, retire-not-delete |
| `test_claude_service.py` | 32 | no | Mocked Anthropic client; **16 are `async` and need `pytest-asyncio`** |
| `test_claude_integration.py` | 8 | no | Live API calls; all `async` |

#### 7.2 What `conftest.py` does

`backend/tests/conftest.py` has two jobs that must happen before any `from app...` import (`:1-15`).

1. **`sys.path` insertion** (`:19-22`): puts `backend/` on `sys.path` so `app` imports regardless of where pytest was invoked.
2. **Conditional `Settings` stubbing** (`:26-41`): `app.config.Settings` has ten required fields with no default, and importing anything under `app.services` pulls in `AuthService` → `Settings`, which would raise `ValidationError` at import time on a machine with no `.env`. The fixture stubs those ten names via `os.environ.setdefault` — **only when `backend/.env` does not exist**, so a normal dev checkout keeps its real configuration and nothing here can shadow it. The stubbed names are `DATABASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_AUDIENCE`, `AUTH0_MANAGEMENT_API_AUDIENCE`, `AUTH0_MANAGEMENT_CLIENT_ID`, `AUTH0_MANAGEMENT_CLIENT_SECRET`, `SECRET_KEY`, `ANTHROPIC_API_KEY`. The list is kept in sync with `backend/app/config.py` **by hand** — a new required field there surfaces as a `ValidationError` on import.

#### 7.3 The savepoint/rollback design

This is the part worth understanding properly, because it is what makes it safe to run DB tests against your own development database.

- **`engine` (session-scoped, `conftest.py:76`)** — builds a `create_engine` from `TEST_DATABASE_URL` if set, else `settings.DATABASE_URL`. It then probes with `SELECT 1 FROM engagement_module_deliverable LIMIT 0`. If that fails, it calls `pytest.skip(..., allow_module_level=True)` with instructions to run `alembic upgrade head` — so an unmigrated database produces one clear skip instead of thirty `UndefinedTable` errors.
- **`db_session` (function-scoped, `conftest.py:98`)** — the core of the design:

```python
connection = engine.connect()
outer = connection.begin()
session = Session(bind=connection, join_transaction_mode="create_savepoint")
try:
    yield session
finally:
    session.close()
    outer.rollback()
    connection.close()
```

  The connection holds an **outer transaction**; the `Session` joins it as a **savepoint** rather than starting its own transaction. A service calling `db.commit()` therefore only issues `RELEASE SAVEPOINT` — it never reaches a real `COMMIT`. Teardown rolls the outer transaction back and discards everything the test created. **Tests never commit.**
- **Why not SQLite** (`conftest.py:50-53`): the two deliverable tables do build on SQLite, but `server_default='false'` is stored as the literal string `'false'`, which SQLAlchemy reads back as Python `True` — every freshly materialized row would report complete and deleted. Tests run against real Postgres for this reason.
- **`test_user`** (`:119`) — a throwaway `User` with only `email` set, so its role falls back to the column default.
- **`make_user`** (`:174`) — a factory taking an explicit `role` (defaulting to `UserRole.ADVISOR`), because `test_user`'s default role is useless for role-boundary tests.
- **`clean_library`** (`:130`) — deactivates every active `ProgramModuleDeliverable` and deletes every `ProgramModuleContent` row for the duration of the test. Necessary because the guide and status reads are library-wide: a seeded environment would add unrelated mandatory items and change the answer, and authoring a V1 card would collide outright with the seeded one on `(program_type, module_code)`. Presets are **deactivated, not deleted**, to keep the FK from any engagement instance intact.
- **`test_engagement`** (`:159`) — a throwaway `value_builder` engagement owned by `test_user`, depending on `clean_library`.
- **`api`** (`:198`) — a `TestClient` with a swappable caller. It overrides `get_db` with the transactional session (so HTTP requests write inside the savepoint) and overrides `get_current_user` (which also means the session-cookie branch in `utils/auth.py` never runs, making `SessionMiddleware` irrelevant). `TestClient` is constructed bare, **not** as a context manager, because the `with` form runs the startup event and builds the Anthropic client for nothing. Teardown calls `app.dependency_overrides.clear()` — `app` is a module-level singleton, so a leaked override would poison every later test.

#### 7.4 How to write a new DB test

```python
# backend/tests/test_my_thing.py
"""
One-paragraph docstring: what behaviour this file pins, and why it can rot.

Run with: pytest tests/test_my_thing.py -v
"""
import uuid
import pytest

from app.models.user import UserRole
from app.services.my_service import get_my_service

BASE = "/api/my-resource"


@pytest.fixture
def advisor(db_session, test_engagement, make_user):
    user = make_user(UserRole.ADVISOR)
    test_engagement.primary_advisor_id = user.id
    db_session.flush()          # flush, never commit
    return user


class TestServiceLevel:
    def test_service_behaviour(self, db_session, test_engagement):
        service = get_my_service(db_session)
        ...                     # service.commit() is a no-op savepoint release


class TestRoleBoundary:
    def test_advisor_can_read(self, api, advisor, test_engagement):
        assert api.as_user(advisor).get(f"{BASE}/{test_engagement.id}").status_code == 200

    def test_client_is_denied(self, api, make_user, test_engagement):
        client = make_user(UserRole.CLIENT)
        assert api.as_user(client).get(f"{BASE}/{test_engagement.id}").status_code == 403

    def test_unknown_id_is_404(self, api, advisor):
        assert api.as_user(advisor).get(f"{BASE}/{uuid.uuid4()}").status_code == 404
```

Rules that fall out of the design:

1. **Never call `db_session.commit()`** — use `flush()`. Commit works, but only because it degrades to `RELEASE SAVEPOINT`; writing `commit()` in a test hides that from the next reader.
2. **Request `db_session` only when you need a database.** The engine is built lazily inside the fixture, so pure unit tests open no connection at all — keep them pure.
3. **Generate unique keys** (`f"key-{uuid.uuid4()}"`, `f"...-{uuid.uuid4()}@example.test"`). The suite runs against a shared development database with real data in it.
4. **Depend on `clean_library`** (directly or via `test_engagement`) if your assertion reads anything library-wide.
5. **Use `api.as_user(user)`** rather than constructing a `TestClient` — it is what wires the request to the rollback-only session.
6. **Class-group by concern** (`TestReadAccess`, `TestMutationRoleBoundary`) and give each class a docstring saying what it is pinning.

#### 7.5 Honest coverage

**What has tests:** the Value Builder program-deliverable subsystem (status derivation, invariant validators, service mutations, HTTP role boundaries, task generation), the program-guide subsystem (role boundaries, per-module diagnostic insights, seed script, seed↔UI render contract), and `ClaudeService` message conversion and response mapping.

At the HTTP level the tests touch exactly two path families — `/api/deliverables/*` and `/api/program-guide/*`. That is **14 of 212 routes (7%)**, out of twenty-one routers.

**What has no tests at all:**

| Subsystem | Surface |
|---|---|
| Diagnostics pipeline | `backend/app/api/diagnostics.py` (17 routes), `services/diagnostic_service.py` (1,295+ lines), `services/scoring_service.py`, the `[Pipeline]` background work |
| Authentication & authorisation | `backend/app/api/auth.py` (8 routes), `utils/auth.py`, `require_role`, `services/role_check.py`, impersonation (`models/impersonation.py`) |
| BBA / POC tool | `backend/app/api/upload_poc.py` (**32 routes**), `bba_service.py`, `bba_conversation_engine.py`, the BBA exporters |
| Strategic Business Plan | `backend/app/api/strategic_business_plan.py` (**28 routes**), `sbp_service.py`, `sbp_conversation_engine.py`, exporters |
| PD Scorecard | `backend/app/api/pd_scorecard.py` (18 routes), `pd_scorecard_service.py`, `pd_scorecard_engine.py` |
| Roles Matrix | `backend/app/api/roles_matrix.py` (11 routes), `roles_matrix_engine.py`, exporter |
| Strategy Workbook | `backend/app/api/strategy_workbook.py` (9 routes) |
| Core CRUD | `engagements` (10), `firms` (17), `users` (7), `tasks` (6), `notes` (6), `chat` (7), `files` (5), `subscriptions` (5), `dashboard` (2), `adv_client` (5), `ai_field_privacy` (2), `settings` (3) |
| Firm permission model | `services/firm_permissions.py` — four `can_*` functions (`can_manage_firm_users`, `can_view_firm_engagements`, `can_assign_advisors`, `can_modify_subscription`), none exercised |
| Email, audit, activity | `email_service.py`, `audit_service.py`, `activity_service.py` |
| **The entire frontend** | No test runner is installed |

The tested routers are the ones with a written specification behind them; the AI-tool routers, which are also the ones with no `response_model`, have neither.

#### 7.6 The collection trap

Documented at `backend/README.md:77-79`: a bare `pytest` also collects `tests/test_claude_service.py`, whose 16 async tests are marked `@pytest.mark.asyncio` (`test_claude_service.py:261,279,295,308,…`) — and **`pytest-asyncio` is not in `requirements-dev.txt`**. Without it, pytest emits `PytestUnknownMarkWarning` for every marker and the async coroutines are collected but never awaited, so they report without executing anything. Run specific test files until the dependency is added.

**Second, undocumented trap in the same area.** `tests/test_claude_integration.py:19-22` guards its 8 live-API tests with:

```python
pytestmark = pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set -- skipping live integration tests",
)
```

But `conftest.py:39-41` sets `ANTHROPIC_API_KEY` in `os.environ` **when there is no `.env` file**, and `app.config.Settings` reads `.env` through pydantic-settings (`class Config: env_file = ".env"`, `backend/app/config.py:96-98`) without exporting values into `os.environ`. The guard therefore behaves backwards:

- **No `.env`:** the stub sets the variable, the skip does not fire, and eight tests attempt real Anthropic calls with an invalid key.
- **With `.env`:** `os.getenv` returns `None` (the key is in the file, not the environment), so the live tests skip even on a fully configured machine.

The only way to actually run them is `ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_claude_integration.py -v -s`, exporting the key into the shell.

> **Rule:** until `pytest-asyncio` is added and the integration guard is fixed, always run pytest against named files, never bare.

---

### Commands reference

Run backend commands from `backend/`, frontend commands from `frontend/`.

| Task | Command |
|---|---|
| Create venv | `python -m venv venv` |
| Activate venv (Windows) | `venv\Scripts\activate` |
| Activate venv (macOS/Linux) | `source venv/bin/activate` |
| Install runtime deps | `pip install -r requirements.txt` |
| Install dev + test deps | `pip install -r requirements-dev.txt` |
| Configure env | copy `.env.example` → `.env`, fill in Auth0 + `DATABASE_URL` |
| Apply migrations | `alembic upgrade head` |
| Create a migration (autogenerate) | `alembic revision --autogenerate -m "add_<thing>"` |
| Create an empty migration | `alembic revision -m "<slug>"` |
| Inspect heads | `alembic heads` |
| Inspect current revision | `alembic current` |
| Merge divergent heads | `alembic merge -m "merge_<a>_and_<b>" <rev_a> <rev_b>` then `alembic upgrade head` |
| Roll back one revision | `alembic downgrade -1` |
| Run backend (reload) | `uvicorn app.main:app --reload --port 8000` |
| Run backend (VS Code) | `Python Debugger: FastAPI` in `.vscode/launch.json` |
| API docs | `http://localhost:8000/api/docs` (ReDoc at `/api/redoc`) |
| Health check | `curl http://localhost:8000/health` |
| Run pure tests (no DB) | `pytest tests/test_program_deliverable_status.py tests/test_program_deliverable_validation.py tests/test_program_guide_render_contract.py -v` |
| Run DB tests | `alembic upgrade head` then `pytest tests/test_program_deliverable_mutations.py tests/test_program_deliverable_api.py tests/test_deliverable_task_generation.py -v` |
| Run program-guide tests | `pytest tests/test_program_guide_api.py tests/test_program_guide_insights.py tests/test_program_guide_seed.py -v` |
| Run DB tests elsewhere | `TEST_DATABASE_URL=postgresql://... pytest tests/... -v` |
| Run Claude unit tests | `pip install pytest-asyncio` first, then `pytest tests/test_claude_service.py -v` |
| Run Claude live tests | `ANTHROPIC_API_KEY=sk-ant-... pytest tests/test_claude_integration.py -v -s` |
| Seed module card library | `python scripts/seed_program_guide_content.py` |
| Seed library — dry run | `python scripts/seed_program_guide_content.py --dry-run` |
| Seed library from a file | `python scripts/seed_program_guide_content.py --file <path>` |
| Create a super admin | `python seed/add_superadmin.py` |
| Seed a firm | `python seed/seed_firm.py` |
| Seed clients | `python seed/seed_clients.py` |
| Seed a subscription | `python seed/seed_subscription.py` |
| Fill a diagnostic | `python seed/fill_diagnostic.py --diagnostic-id <UUID>` (or `--engagement-id <UUID>`; also `--dry-run`, `--api`, `--token <jwt>`, `--base-url`, `--submit`, `--user-id`) |
| Install frontend deps | `npm install` |
| Run frontend | `npm run dev` → `http://localhost:8080` (proxies `/api` and `/files` to `VITE_API_BASE_URL`, default `http://localhost:8000`) |
| Lint frontend | `npm run lint` |
| Type-check frontend | `npx tsc -b` — **not run by the build** |
| Build frontend | `npm run build` (dev mode: `npm run build:dev`) |
| Preview a build | `npm run preview` |
| Add a shadcn primitive | `npx shadcn@latest add <component>` (writes to `src/components/ui/`) |

**Gotchas in this table:**
- `alembic upgrade head` **cannot build a database from empty** in this repo — an early revision runs `ALTER TABLE advisor_client` before the table is created (`backend/README.md:73-75`). Upgrading an existing database works. New developers must start from a dump.
- `backend/README.md:9` says the venv is `venv/`; `.vscode/launch.json` points at `${workspaceFolder}/backend/venv-trinity/Scripts/python.exe`. Pick one.
- The frontend dev server runs on **8080** (`frontend/vite.config.ts:14`), not Vite's default 5173, but `backend/README.md:90-92` documents Auth0 callback origins for **5173**.

---

### Definition of done

A change is done in this repository when all of the following hold.

**Code**
- [ ] New modules open with a docstring that states the job and the non-obvious constraint.
- [ ] Business logic is in a service, not a router. The service raises `ValueError` (or a domain subclass), never `HTTPException`.
- [ ] A new service exposes `get_<thing>_service(db: Session) -> <Thing>Service`.
- [ ] Handlers take `db: Session = Depends(get_db)` and `current_user: User = Depends(get_current_user)`; authorisation is a `Depends` guard, not an inline ladder.
- [ ] Not-found is caught before generic `ValueError`; client-facing `detail` is a constant; exception text goes to the log only.
- [ ] Status codes use `status.HTTP_*` constants, never integer literals.
- [ ] Any new log line from an AI call, export, pipeline or background task carries an existing `[Bracketed Subsystem]` prefix.

**API**
- [ ] Every new route declares `response_model`.
- [ ] Path is `/api/<kebab-plural>`; id params are typed `UUID`; `PATCH` for partial update; `201` on create; `204` on delete unless returning the recomputed parent.
- [ ] Router `prefix` and `tags` follow *API conventions*; if you add a router to `main.py`, verify the effective path — the `/api` prefix is declared in two different places.

**Data**
- [ ] Every business-meaningful column has `comment=`.
- [ ] Migration is autogenerated, reviewed by hand, and named `<hash>_<snake_case_slug>.py`.
- [ ] `alembic upgrade head` succeeds on a database already migrated to `staging`. If it produces sibling heads, restore and create a real merge revision — do not `stamp`.
- [ ] `alembic downgrade -1` is present and correct.

**Frontend**
- [ ] Functional component, `export function`, `<Name>Props` interface above it.
- [ ] Imports use `@/`; shadcn primitives are regenerated, not hand-edited.
- [ ] Redux additions go in `src/store/slices/<domain>Reducer.ts` with `createAsyncThunk` and a `rejectWithValue` catch, registered in `src/store/index.ts`.
- [ ] Classes composed with `cn()`; repeated strings hoisted to a named constant.
- [ ] `npm run lint` clean **and** `npx tsc -b` clean — the build alone does not type-check.

**Tests**
- [ ] Pure logic gets a pure test (no `db_session`).
- [ ] Any new role boundary gets an `api.as_user(...)` test proving allowed *and* denied, including 404 for an unknown id.
- [ ] Tests `flush()`, never `commit()`; unique values are `uuid4`-suffixed; library-wide reads depend on `clean_library`.
- [ ] The named test files pass: `pytest tests/<the files you touched> -v`. Do not run bare `pytest` and do not treat its output as a pass.

**Git & review**
- [ ] Branch is `<type>/<ticket>-<slug>` cut from `staging`; PR targets `staging`.
- [ ] Commits use a Conventional Commit prefix that matches what the commit does.
- [ ] PR fills in all seven template sections, including reproduction steps under *How to Test* and the breaking-change checkbox.
- [ ] Because there is no CI: the author has personally run the backend, the frontend build, the lint, and the relevant test files, and says so in the PR.

---

## 17. Operations, Diagnostics & Troubleshooting

This section is the runbook: what you can observe while the system runs, how to check it is alive, the scripts you will need, the state of the repository you inherit, and a symptom-driven troubleshooting table.

### Execution model — the operational recap

All AI work runs inside the API server process; there is no worker tier, no queue and no cache service. Exactly one endpoint defers work past the response — `POST /api/diagnostics/{diagnostic_id}/submit` (`backend/app/api/diagnostics.py:423-505`) hands `_run_pipeline` to FastAPI's `BackgroundTasks` — and every other AI surface awaits its model calls inline, so the client holds the connection for the whole generation. The dispatch mechanism, the list of inline-AI surfaces and the pipeline's step semantics belong to *System Architecture* and *Diagnostic Engine*; what follows is only what an operator sees and does.

Two facts drive most of the entries in the troubleshooting table below:

- **A restart kills in-flight work and leaves the row behind.** The task is an in-memory coroutine on the API process's event loop. The shutdown handler (`backend/app/main.py:155-160`) only logs. `completed` / `failed` / `draft` are written exclusively by handlers inside `_run_pipeline`; a process kill runs none of them, so the diagnostic stays `processing`.
- **Nothing sweeps those rows.** There is no automatic reset on startup and no periodic cleanup. A stranded diagnostic stays `processing` indefinitely unless one of three things happens: someone opens that specific diagnostic and the status endpoint's lazy auto-fail catches it (below), someone calls the cancel endpoint, or someone edits the row in SQL.

There is also **no application-level wall-clock ceiling and no retry**. A hung model call holds the row at `processing` until `ANTHROPIC_TIMEOUT` expires (default `1800.0` s — `backend/app/config.py:53`, applied at `backend/app/services/claude_service.py:33-42`), at which point the generic `except Exception` (`backend/app/tasks/diagnostic_tasks.py:248-263`) records `failed` and swallows. Nothing re-dispatches. The read timeout applies **per HTTP request**, not to the pipeline, so a pipeline making seven calls can exceed it seven times over.

**Gotcha — the background PDF is thrown away.** `pdf_bytes` (`backend/app/tasks/diagnostic_tasks.py:167`) is only logged (`:174`); nothing writes it to disk or to a column, and `diagnostics.report_url` (`backend/app/models/diagnostic.py:46`) is never assigned anywhere in `backend/app`. The real PDF renders on demand at `backend/app/api/diagnostics.py:919`. The background render is a smoke test: when it logs `PDF generation failed (non-critical)` nothing was lost, but the same failure recurs at download time for that diagnostic.

**Gotcha — submit has no access check.** Neither submit nor cancel calls `_require_diagnostic_access`; the read endpoints in the same module do (`:579`, `:634`, `:672`, `:846`, `:974`, `:1014`). Any authenticated user who knows the UUID can start a paid AI run or cancel someone else's.

#### Status values

`diagnostics.status` is a plain `VARCHAR(50)`, not a database enum, `server_default='draft'`, indexed (`backend/app/models/diagnostic.py:30-31`). The authoritative set is `draft | in_progress | processing | completed | failed | archived`.

| Value | Written by |
|---|---|
| `draft` | server default; cancel endpoint (`backend/app/api/diagnostics.py:541`); the `CancelledError` handler (`backend/app/tasks/diagnostic_tasks.py:243`) |
| `processing` | submit endpoint, before dispatch (`backend/app/api/diagnostics.py:494`) |
| `completed` | `backend/app/tasks/diagnostic_tasks.py:182` |
| `failed` | `backend/app/tasks/diagnostic_tasks.py:260` (generic error handler); the 60-minute lazy auto-fail at `backend/app/api/diagnostics.py:596`; `backend/app/services/diagnostic_service.py:285` |
| `in_progress`, `archived` | no backend code writes either. The frontend writes `in_progress` on *engagements*, not diagnostics. |

**Gotcha:** the column comment at `backend/app/models/diagnostic.py:31` reads `"draft, in_progress, processing, completed, archived"` — it omits `failed`, which the code writes constantly. Trust the code.

**Gotcha:** the second `failed` writer that a reader expects to find does not exist. A timeout branch at `backend/app/tasks/diagnostic_tasks.py:217-231` looks like a wall-clock guard, but nothing in this deployment can raise the exception it catches. It is dead code, not coverage.

#### Cancel

`POST /api/diagnostics/{diagnostic_id}/cancel` (`backend/app/api/diagnostics.py:508-548`) **cancels nothing directly**. It refuses any status other than `processing` (400), sets `status = "draft"`, clears `completed_at`, commits and returns. The running pipeline keeps going until its next `check_shutdown` poll re-reads the row, sees `draft` and raises `asyncio.CancelledError`; those poll points are described in *Diagnostic Engine*. `_run_pipeline` then catches it and re-asserts `draft` (`backend/app/tasks/diagnostic_tasks.py:232-246`).

Three things to know before you use it:

- The endpoint's own docstring claims it "Cancels the registered background task (if running)". That is false.
- The poll happens only *between* pipeline steps. Cancelling during the scoring or report call does nothing until that call returns — potentially many minutes — and the AI spend for the in-flight step is already incurred.
- There is no authorisation beyond authentication. `backend/app/api/diagnostics.py:535-536` carries the comment `# Optional: add role / access checks here if needed`, unactioned.

Cancel also does not roll back partial writes from earlier steps.

#### Observing progress

By polling `GET /api/diagnostics/{diagnostic_id}/status` (`backend/app/api/diagnostics.py:551-603`), which enforces access via `_require_diagnostic_access` (`:579`) and returns `{status, completed_at, error}` — `error` is hard-coded `None` (`:602`). This endpoint is also the only automatic recovery path in the system: a row `processing` for more than `STUCK_THRESHOLD_SECONDS = 3600` is marked `failed` on read (`:581-597`). It fires only for the row being requested, so a diagnostic nobody polls is never recovered.

Two independent pollers exist on the client, and the markdown note describing them is stale:

| | Page-level poller | Global poller |
|---|---|---|
| File | `frontend/src/components/engagement/tools/ToolSurvey.tsx:139-260` | `frontend/src/hooks/useGlobalDiagnosticPolling.ts` |
| Mounted in | The survey component itself | `frontend/src/components/layout/DashboardLayout.tsx` — survives navigation |
| Interval | 10 s (`:228-234`), plus an immediate check on mount and a re-check on `visibilitychange` | 30 s (`useGlobalDiagnosticPolling.ts:137`) |
| Safety timeout | 90 minutes, then a warning toast (`ToolSurvey.tsx:238-245`) | **None** |
| Staleness rule | — | Ignores and prunes `localStorage` entries older than 30 minutes (`:32`, `:158`) |
| Persistence | `localStorage` key `processing_diagnostics`, entries `{id, engagementId, timestamp}` | same key |

**Gotcha:** `frontend/GLOBAL_DIAGNOSTIC_POLLING.md` claims a 5-second interval and a 20-minute safety timeout. Neither exists in the code.

**Gotcha:** the global poller has no upper bound, but its 30-minute staleness filter means that after 30 minutes it stops picking the entry up on remount — the completion toast is simply never delivered. The row is correct; only the notification is lost. Because the queue lives in `localStorage`, a run submitted in one browser is invisible to another.

#### Recovering a stuck row

Find them:

```sql
SELECT id, engagement_id, status, updated_at, completed_at
FROM diagnostics
WHERE status = 'processing' AND is_deleted = false
ORDER BY updated_at;
```

Anything whose `updated_at` predates the last deploy, or is older than ~60 minutes with no `[Pipeline] PIPELINE COMPLETED SUCCESSFULLY` line in the logs, is orphaned. Either open the diagnostic in the UI once — the status endpoint will auto-fail it past 60 minutes — or reset it directly:

```sql
UPDATE diagnostics SET status = 'draft', completed_at = NULL
WHERE id = '<uuid>' AND status = 'processing';
```

Then resubmit through the UI or re-`POST /api/diagnostics/{id}/submit`, and clear the browser's `localStorage.processing_diagnostics` entry.

**Gotcha:** never reset a row that is genuinely still running. Because cancel is implemented as "status becomes `draft`", writing `draft` on a live run aborts the pipeline at its next checkpoint. Check the log stream first.

---

### Observability

#### What exists

**stdlib `logging` to stdout at `INFO`**, configured once at import:

```python
# backend/app/main.py:35-43
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.pool').setLevel(logging.WARNING)
logging.getLogger('sqlalchemy.dialects').setLevel(logging.WARNING)
```

Three SQLAlchemy loggers are pinned to `WARNING`; everything else inherits `INFO`. No file handler, no rotation — your host's log collector is the whole of log persistence.

**Bracketed prefixes** are the de facto namespacing convention (registry below). Grep the prefix, not the logger name; every module uses `logging.getLogger(__name__)`, so logger names are dotted module paths.

**Per-step elapsed times.** Each pipeline step records `time.time()` deltas and prints a breakdown on success (`backend/app/services/diagnostic_service.py:841-851`). `_run_pipeline` logs total wall time (`backend/app/tasks/diagnostic_tasks.py:211-215`). AI calls log their own duration on success and failure (`backend/app/services/claude_service.py:310, 317`).

**Token accounting**, in logs and in the database. Each call logs total/input/output tokens, prompt-cache creation and read counts (`backend/app/services/claude_service.py:378-380`) and `stop_reason` (`:381`). Persisted per artefact as `ai_tokens_used` / `ai_model_used` on `diagnostics` (`backend/app/models/diagnostic.py:54-55`), `bba` (`backend/app/models/bba.py:120-121`), `strategic_business_plans` (`backend/app/models/strategic_business_plan.py:98-99`), `roles_matrices` (`backend/app/models/roles_matrix.py:61-62`) and `pd_scorecards` (`backend/app/models/pd_scorecard.py:55-56`). These columns are the only durable cost signal in the system — query them for spend attribution. `strategy_workbooks` has no such columns.

#### Log prefix registry

Verified by grepping logger calls; the "emitted from" column is the only file that emits each prefix.

| Prefix | Emitted from | Signals |
|---|---|---|
| `[Pipeline]` | `backend/app/services/diagnostic_service.py` | Diagnostic pipeline step boundaries, cancellation checks, per-step elapsed times, final breakdown |
| `[Background Task]` | `backend/app/tasks/diagnostic_tasks.py` | Lifecycle of one background run: start, PDF, completion/cancel/failure, total elapsed |
| `[Claude API]` | `backend/app/services/claude_service.py` | One outbound AI HTTP call: model, duration, HTTP status on failure, token usage, stop reason |
| `[Claude]` | `backend/app/services/claude_service.py` | Response handling above the HTTP layer: JSON parse attempts, repair ladder, per-method timings, file uploads |
| `[Scoring]` | `backend/app/services/diagnostic_service.py` | File discovery and upload for the scoring step, re-upload retries |
| `[Scoring Data]` | `backend/app/services/diagnostic_service.py` | Post-scoring numeric processing (module averages, ranking, RAG, validation) |
| `[File Sync]` | `backend/app/services/diagnostic_service.py` | Reconciling local media rows with provider-side file ids |
| `[Status]` | `backend/app/api/diagnostics.py:592-594` | The 60-minute stuck-row auto-fail |
| `[BBA Engine]` | `backend/app/services/bba_conversation_engine.py` | BBA conversation engine |
| `[BBA Export]` | `backend/app/services/bba_report_export.py` | BBA document export |
| `[BBA Task Planner]` | `backend/app/services/bba_task_planner_service.py` | BBA task planning |
| `[BBA Presentation]` | `backend/app/services/bba_presentation_service.py` | BBA presentation generation |
| `[BBA PPTX]` | `backend/app/services/bba_pptx_export.py` | BBA PPTX export |
| `[SBP Engine]` | `backend/app/services/sbp_conversation_engine.py` | Strategic Business Plan generation |
| `[SBP]` | `backend/app/api/strategic_business_plan.py` | SBP API surface |
| `[StrategyWorkbook]`, `[Precheck]` | `backend/app/services/strategy_workbook_service.py` | Workbook generation; pre-run input validation |
| `[Roles Matrix]` | `backend/app/services/roles_matrix_engine.py` | Roles matrix extraction and build |
| `[PD Scorecard]` | `backend/app/services/pd_scorecard_engine.py` | PD scorecard generation |
| `[OpenAI]`, `[OpenAI API]` | `backend/app/services/openai_service.py` | **Dead.** That module is imported nowhere live. If you see these prefixes, someone re-enabled it. |

**Gotcha:** several live call sites use local variables literally named `openai_service` that hold a `ClaudeService` instance (`backend/app/api/upload_poc.py:239, 1544`; `backend/app/services/bba_conversation_engine.py:54`). The variable name is not evidence of provider.

#### What does not exist

| Missing | Impact on day-one debugging |
|---|---|
| Request IDs / correlation IDs | You cannot tie a user's failed action to its log lines. Correlate on timestamp plus diagnostic UUID — most pipeline lines carry it. |
| Structured / JSON logging | Plain `%`-formatted strings. Field-level querying needs regex. |
| Error tracker | Exceptions exist only as `exc_info=True` tracebacks in stdout. No grouping, no counts, no alert on a new exception type. |
| Metrics (latency, error rate, throughput, token spend over time) | No instrumentation. Token spend is per-row in the database only. |
| Alerting | Nothing pages anyone. A pipeline that fails at 2 a.m. is discovered by the advisor the next morning. |
| Audit log sink | `AuditService` (`backend/app/services/audit_service.py`) is log-only: `log_impersonation_start` and `log_impersonation_end` emit lines through `logging` and swallow their own exceptions, with the comment "In the future, this could write to a dedicated audit_log table" (`:38`, `:63`). Impersonation metadata is also stashed on `request.state` (`backend/app/utils/auth.py:156-158`) and never persisted. Impersonation history exists only in whatever the host retains of stdout. |

---

### Health checks

Two unauthenticated endpoints, both in `backend/app/main.py`.

| Endpoint | Definition | Response |
|---|---|---|
| `GET /` | `backend/app/main.py:136-143` | `{"message": "Trinity Platform API", "version": "1.0.0", "status": "running"}` |
| `GET /health` | `backend/app/main.py:146-152` | `{"status": "healthy", "environment": <APP_ENV>}` |

Both are static dictionaries. Neither touches the database, the AI provider, Auth0 or the filesystem. There is no `/api/health`.

**Gotcha — the important one:** `/health` returns `200 {"status":"healthy"}` while the database is unreachable, `ANTHROPIC_API_KEY` is invalid, Auth0's JWKS endpoint is down and the uploads directory is gone. It asserts one thing: a Python process is bound to the port and the event loop is turning. Do not treat a green health check as evidence the platform works, and do not let a deploy gate depend on it alone.

One thing it catches implicitly: `Settings` is instantiated at import (`backend/app/config.py:102`) and ten fields have no defaults — `DATABASE_URL`, `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_AUDIENCE`, `AUTH0_MANAGEMENT_API_AUDIENCE`, `AUTH0_MANAGEMENT_CLIENT_ID`, `AUTH0_MANAGEMENT_CLIENT_SECRET`, `SECRET_KEY`, `ANTHROPIC_API_KEY`. A missing one crashes the process at import, so it never answers `/health` at all. Misconfiguration shows up as "no process", not "unhealthy".

**What a real readiness check would assert:**

1. `SELECT 1` against the session from `get_db`, with a short timeout.
2. The database's `alembic_version` matches the code's head — catches "deployed but not migrated".
3. `ClaudeService._client is not None`, i.e. the startup event at `backend/app/main.py:118-132` ran.
4. `backend/files/uploads` (created at `backend/app/services/file_service.py:51-52`) exists and is writable.
5. The count of `diagnostics` rows in `processing` older than N minutes, exposed as a number so it can be alerted on.

Keep `/health` as the cheap liveness probe and add `/ready` for the above. A readiness probe that queries the database is fine; a liveness probe that does is a restart loop waiting to happen.

---

### API exploration tooling

| Tool | Where | Notes |
|---|---|---|
| Swagger UI | `GET /api/docs` | `backend/app/main.py:50`. Non-default path — `/docs` is a 404. |
| ReDoc | `GET /api/redoc` | `backend/app/main.py:51` |
| OpenAPI JSON | `GET /openapi.json` | Default location; not overridden. |
| Postman collection | `backend/Trinity_Platform_API.postman_collection.json` | Named "Trinity Platform - AI Diagnostic API" |

The collection defines variables `base_url`, `engagement_id`, `diagnostic_id`, `user_id`, `auth_token`, in five folders:

| Folder | Requests |
|---|---|
| 1. Authentication | `GET /api/auth/user`, `GET /api/auth/login` |
| 2. Engagements | `POST /api/engagements`, `GET /api/engagements/{{engagement_id}}`, `GET /api/engagements?skip=0&limit=100` |
| 3. AI Diagnostic | `POST /api/diagnostics/create`, `PATCH /api/diagnostics/{{diagnostic_id}}/responses`, `POST .../submit`, `GET /api/diagnostics/{{diagnostic_id}}`, `GET .../results`, `GET /api/diagnostics/engagement/{{engagement_id}}`, `POST .../regenerate-report` |
| 4. Tasks | `GET /api/tasks/diagnostic/{{diagnostic_id}}`, `GET /api/tasks/{task_id}`, `PATCH /api/tasks/{task_id}` |
| 5. Health Check | `GET /api/health` |

**Gotcha:** the Health Check request targets `{{base_url}}/api/health`, which does not exist — the endpoint is `/health` (`backend/app/main.py:146`). It will 404.

**Gotcha:** the two Tasks requests use a literal `{task_id}` in the path, not a collection variable. Substitute a real UUID by hand.

**Gotcha:** the collection covers the original diagnostic flow only. BBA/POC, strategy workbook, strategic business plan, program guide, program deliverables, roles matrix, PD scorecard, chat, firms, subscriptions and AI field privacy are absent — use `/api/docs`. Treat the collection as a point-in-time artefact and verify a request against the code before trusting it.

**Gotcha:** `Depends(get_current_user)` accepts either an `Authorization: Bearer` header or the session cookie (`backend/app/utils/auth.py:210-224`). Swagger UI's "Try it out" sends neither by default; paste a bearer token, or drive the API from Postman with `auth_token` set.

---

### Seed and maintenance scripts

All `sys.path.insert` the backend root and open a `SessionLocal()` directly — **they connect to whatever `DATABASE_URL` your `.env` points at, with no confirmation prompt.** Run them from `backend/` with the virtualenv active.

| Script | What it does | How to run | When you need it |
|---|---|---|---|
| `backend/seed/add_superadmin.py` | Looks up a user in Auth0 by email (via `Auth0Management.get_management_token()`), sets their `app_metadata` role to `super_admin`, creates or updates the local `users` row, and sends a fresh password-setup email. Email, first name, last name and role are module-level constants (`:27-30`). | `cd backend && python seed/add_superadmin.py` | Bootstrapping the first super admin, or repairing an account whose Auth0 record and local row disagree. |
| `backend/seed/seed_clients.py` | Inserts two demo client users (`client1@example.com`, `client2@example.com`) with `role = UserRole.CLIENT` and seeded `auth0_id` values `auth0\|seed_client_1` / `_2`. | `cd backend && python seed/seed_clients.py` | Populating a demo or test environment with clients to attach to engagements. |
| `backend/seed/seed_firm.py` | Creates a `Firm` via `FirmService.create_firm(...)` with `seat_count=10` (`:88-92`), using a **hard-coded admin user UUID** (`:29`) as firm admin; prints an error and returns if that user does not exist. Uses raw SQL in places to dodge columns that may not exist yet. | `cd backend && python seed/seed_firm.py` | Standing up the firm/multi-tenant path in a test environment. |
| `backend/seed/seed_subscription.py` | Creates a `Subscription` (`plan_name="professional"`, `monthly_price=299.00`, `status="active"`, 30-day period) for a firm — either the UUID passed as the **first positional argument**, or the first firm with `subscription_id IS NULL`. No-ops with a warning if one already exists. | `cd backend && python seed/seed_subscription.py`<br>`cd backend && python seed/seed_subscription.py <firm-uuid>` | A firm exists without a subscription and subscription-gated features are 403-ing. |
| `backend/seed/fill_diagnostic.py` | Auto-fills every question on a diagnostic with realistic test data, picking the `sale_ready` or `value_builder` set from the engagement. Two modes: direct DB (default) and API (`--api`). Flags (`:1167-1176`): `--diagnostic-id` \| `--engagement-id` (mutually exclusive, required), `--api`, `--base-url`, `--cookie`, `--token`, `--submit`, `--user-id`, `--dry-run`. | `cd backend && python seed/fill_diagnostic.py --diagnostic-id <UUID>`<br>`... --engagement-id <UUID> --api --token <jwt> --submit --user-id <UUID>` | Exercising the pipeline end to end without hand-filling a long survey. **`--submit` is API-mode only** and triggers a real AI run and real spend. |
| `backend/scripts/seed_program_guide_content.py` | Upserts the module card library from a JSON fixture into `program_module_content` and `program_module_deliverable`. Idempotent: cards upsert on `(program_type, module_code)`, deliverables on `(program_type, module_code, deliverable_key)`. Validates `input_source`, producer and note-section values against fixed sets (`:52-72`). Prints a `{created, updated, retired, reactivated}` tally. | `cd backend && python scripts/seed_program_guide_content.py`<br>`... --file files/program_guide/value_builder_modules.json`<br>`... --dry-run` | Whenever the fixture changes — notably when real copy replaces the placeholders. See *Value Builder Programme — Program Guide & Deliverables*. |

**Gotcha (`seed_program_guide_content.py`):** a deliverable dropped from the fixture is **retired** (`is_active = False`, `:627`), never deleted, and upserts preserve the row id. `EngagementModuleDeliverable.library_deliverable_id` cascades on delete, so deleting a preset row would destroy every engagement's completion and scope history for it. Never delete-and-recreate a deliverable to apply an edit; edit the fixture and re-run. Putting a retired key back reactivates the same row.

**Gotcha:** `seed_firm.py` and `add_superadmin.py` contain hard-coded identifiers — a UUID, an email address, a person's name. They are one-shot scripts written for one environment, not parameterised tooling. Read them before running them.

---

### Repository hygiene

The working tree carries artefacts that are not part of the running system. Know them so you do not mistake one for a component.

| Path | What it is | Tracked? |
|---|---|---|
| `backend/=0.52.0` | Debris from a shell-quoting mistake in a `pip install` — a redirect created a file named after the version constraint. Delete it. | Yes |
| `backend/fix_userrole_enum.sql` | Hand-written SQL patch for the mixed-case `users.role` enum, run out of band. **Not a migration** — it is not in `backend/alembic/versions/`, so nothing guarantees it has been applied to any given database. | Yes |
| `backend/test_diagnostic_responses.json` | Diagnostic answer fixture sitting at the package root rather than under `tests/`. | Yes |
| `backend/Trinity_Platform_API.postman_collection.json` | The Postman collection above. Verify freshness before trusting it. | Yes |
| `backend/files/exports/sbp/*.pptx` | Generated Strategic Business Plan artefacts left in the tree. `backend/.gitignore` ignores `*.docx`, so the `.pptx` is the one still committed. | Yes |
| `backend/uploads/` | A `bba/` subdirectory plus engagement-UUID directories holding **real client uploads**. Present locally, gitignored. Not backed up, not replicated — see the debt register. | No |
| `frontend/dist/` | A stale production build. Rebuild rather than trusting it. | No |

**Gotcha — `/files` has no authentication.** `backend/app/main.py:110-115` mounts `backend/files` with `StaticFiles`, unauthenticated. Anything written under `backend/files/` is readable by anyone who can guess the path, including the committed sample SBP exports above and every uploaded diagnostic, workbook and profile document. Delete the sample exports and treat the mount as a public directory until it is put behind a permission check.

**Gotcha:** grepping `backend/app/` for the orphan table names (see the debt register) returns hits only inside `__pycache__`. Compiled modules from another branch — `owner_team_member`, `sale_ready`, `sale_ready_service` — survive in the tree with no corresponding source. Restrict greps to tracked source, or clear `__pycache__` before concluding a module exists.

---

### Troubleshooting

| Symptom | Likely cause | How to confirm | Fix |
|---|---|---|---|
| `alembic upgrade` fails: *"Multiple head revisions are present for given argument 'head'"* | Two branches each added a revision with the same `down_revision`. `backend/alembic/versions/` already holds 81 revisions of which **14 are merge revisions** (a tuple `down_revision`), so this recurs constantly. | `cd backend && alembic heads` prints more than one. `alembic history --verbose` shows where they diverge. | `alembic merge -m "merge <a> and <b>" <rev1> <rev2>`, commit the generated merge revision, then `alembic upgrade head`. **Standing rule: never `alembic stamp` past a sibling revision.** Stamping marks the database as having applied schema changes it has not, and the next autogenerate will try to re-create objects that already exist. |
| A colleague's migration ran and now *your* branch 500s on a column that should not exist yet, or vice versa | Development points at a **shared hosted database** (`backend/alembic/env.py:24` overrides `alembic.ini:56`'s placeholder with `settings.DATABASE_URL`). Migrations are global; branches are not. | `SELECT version_num FROM alembic_version;` compared against your branch's `alembic heads`. | Restore the branch relationship and merge — do not stamp. If the applied revision is genuinely wrong, `alembic downgrade <rev>` deliberately after telling the other engineers, then re-apply the merged chain. Longer term: give each developer their own database. |
| `alembic revision --autogenerate` emits a huge diff full of tables you never touched | Pre-existing drift between the models and the shared database — dead columns on `users`, `subscriptions`, `strategy_workbooks`, plus comment and constraint noise. Documented at `docs/ROLES_MATRIX_TOOL.md:119-125`. `backend/alembic/env.py:34-40` already exempts the redundant `UNIQUE (id)` constraints. | Read the generated file. `drop_column` / `drop_constraint` on tables unrelated to your change is drift. | **Hand-trim the revision to your change only**, exactly as the roles-matrix note prescribes ("Trim the generated revision down to the `create_table('roles_matrices')` call and its three `create_index` calls before applying it"). Never apply an untrimmed autogenerate in this repo. |
| `alembic upgrade head` on an empty database fails partway | `backend/README.md` states a bare upgrade cannot build from empty because an early revision runs `ALTER TABLE advisor_client` before that table is created. `backend/alembic/versions/create_orphan_tables.py` was added to fix exactly this: it creates `advisor_client` and `bba` behind an existence check, with `down_revision = 'remove_unique_sub_id'`, positioned before the first revision that references `bba`. | Try it on a throwaway database and read the failure; note the revision id in the traceback. | If it now succeeds, the README note is stale — update it. If it still fails, the failing revision needs the same existence-guard treatment: inspect first, then act. Upgrading an *existing* database works either way. |
| `ValueError: Invalid role: ...`, or Postgres `invalid input value for enum userrole` after adding a role | The `userrole` type is **mixed case**: legacy labels uppercase (`ADVISOR`, `CLIENT`, `ADMIN`, `SUPER_ADMIN`), newer ones lowercase (`firm_admin`, `firm_advisor`). `UserRoleType` (`backend/app/models/user.py:24-99`) hand-maps Python↔DB both ways. A role missing from either dictionary, or absent as a database label, fails. | `SELECT enumlabel FROM pg_enum WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname='userrole') ORDER BY enumsortorder;` compared against `UserRole` (`backend/app/models/user.py:14-21`) and both maps. | Add the label with the idempotent pattern in `backend/fix_userrole_enum.sql` (`DO $$ ... IF NOT EXISTS (SELECT 1 FROM pg_enum ...) THEN ALTER TYPE userrole ADD VALUE '<role>'; END IF; END $$;`), **and** add the value to `UserRole`, to `process_bind_param`'s `db_value_map` **twice** (the enum branch at `:46-53` and the string branch at `:58-65`), and to `process_result_value`'s `lowercase_map` (`:82-91`). Match the case convention of the half you extend. |
| Diagnostic shows "processing" forever in the UI | The process that owned the run restarted, was redeployed or crashed. Nothing sweeps the row afterwards. | `SELECT id, status, updated_at FROM diagnostics WHERE status='processing' AND is_deleted=false ORDER BY updated_at;` — anything older than the last deploy is orphaned. Cross-check the logs for `[Background Task] Background processing completed` for that UUID. | Open the diagnostic once so the status endpoint's 60-minute auto-fail catches it (`backend/app/api/diagnostics.py:581-597`), or `UPDATE diagnostics SET status='draft', completed_at=NULL WHERE id='<uuid>' AND status='processing';` then resubmit. Clear the browser's `localStorage.processing_diagnostics` entry. Verify the run is genuinely dead first — writing `draft` on a live run cancels it. |
| Background run fails immediately with an event-loop or "client has been closed" error on the first AI call | The `AsyncAnthropic` client is a **class attribute** (`ClaudeService._client`, `backend/app/services/claude_service.py:23`) initialised once at startup and bound to that event loop. Anything on a different loop inherits a stale client. | The traceback originates in the httpx/anyio layer under `ClaudeService.generate_completion`, not in the SDK's API error classes. | Already mitigated for the diagnostic pipeline: `_run_pipeline` recreates the client per run before anything else — `ClaudeService._client = None; ClaudeService.initialize_client()` (`backend/app/tasks/diagnostic_tasks.py:84-85`). **Copy those two lines into any new background entry point**; if you removed them, put them back. |
| Claude call fails with 429, 529 or a 5xx | Rate limit, provider overload, or provider server error. | Grep `[Claude API] API call failed after`. The next lines print `Error type`, `Error message` and `HTTP Status Code`, with an explicit branch per code (`backend/app/services/claude_service.py:326-333`). | The SDK retries internally, but only **once** — `max_retries=1` (`backend/app/services/claude_service.py:42`). After that the exception propagates, `_run_pipeline` marks the diagnostic `failed`, and there is no application-level retry. Resubmit. Raising `max_retries` is a one-line change; do it deliberately, since each attempt costs a full multi-minute request. |
| Claude call fails with a timeout | The HTTP read timeout elapsed. Timeouts are `connect=10.0`, `read=timeout_seconds`, `write=10.0`, `pool=10.0` (`backend/app/services/claude_service.py:33-42`), where `timeout_seconds = settings.ANTHROPIC_TIMEOUT or 600.0` (`:33`) and `ANTHROPIC_TIMEOUT` defaults to `1800.0` (`backend/app/config.py:53`). | The wrapper logs elapsed seconds and, past 600 s, adds `"likely a timeout"` (`:321-322`). The outer handler re-raises with the configured timeout in the message (`:412-418`). | Reduce the payload — the report step logs a full character-count breakdown of its inputs at `:786-793`, use it to find what grew — lower `ANTHROPIC_MAX_TOKENS`, or raise `ANTHROPIC_TIMEOUT`. `read` applies **per HTTP request**, not to the whole pipeline. |
| `Failed to parse JSON response after repair attempts` | The model emitted prose, fences, trailing text or malformed JSON despite the instruction injected at `backend/app/services/claude_service.py:247-251`. | Grep `[Claude] Direct JSON parse failed` and follow the ladder. On final failure the code logs the error line and column plus surrounding context, or the first 1000 characters of the payload (`:601-606`). | The ladder in `generate_json_completion` (`:498-646`) runs in order: direct `json.loads` (`:533`) → strip ```` ```json ````/```` ``` ```` fences (`:538-552`) → `raw_decode`, ignoring trailing text (`:555-560`) → seek the first `{`/`[` to skip a preamble (`:566-575`) → `_repair_json` (`:445-486`: fences, `raw_decode`, the `json-repair` library, then structural regex fixes) → a follow-up turn at `temperature=0.0` demanding raw JSON (`:608-641`). If all six fail the run is marked `failed`. Manual next steps: capture the logged payload, tighten the prompt for the failing step, or reduce input size — truncation from `max_tokens` produces genuinely incomplete JSON that cannot be repaired, so check the logged `stop_reason`. |
| PDF generation crashes, or tables come out broken or overlapping | `xhtml2pdf` (`pisa`) is fragile with LLM-generated markdown tables; the classic failure is a negative `availWidth` crash on a table with too many narrow columns. | `[Background Task] PDF generation failed (non-critical)` in the logs, or `ReportService _html_to_pdf: first render failed`. | `ReportService` (`backend/app/services/report_service.py`) already applies a stack of workarounds: `_wrap_cell_text` (`:1820`) and `_pre_wrap_advisor_table_cells` (`:1908`) insert hard wraps; the Pre-Listing Readiness Checklist (`:474-561`), Diagnostic Triggers (`:563-622`) and Section 1 / Roadmap Summary (`:624-662`) tables are each rewritten with `table-layout:fixed`, an explicit `<colgroup>` and `border-collapse:collapse`; a catch-all rewrites any remaining class-less table to `table-layout:auto` (`:664-672`); and `_html_to_pdf` (`:2345-2387`) catches a failed first render, runs `_strip_markdown_tables` (`:2296-2342`) and retries. When a *new* table breaks, add it to the per-table fix-up list with a fixed layout and a colgroup. **Note:** the background render is non-fatal and its bytes are discarded anyway (`backend/app/tasks/diagnostic_tasks.py:167-179`) — the failure that matters is the same one recurring at `GET /api/diagnostics/{id}/download`. |
| Browser console: CORS policy blocked the request from a new origin | `CORSMiddleware` uses an explicit allow-list, and `allow_credentials=True` forbids `"*"` (`backend/app/main.py:67-83`). The list is `settings.FRONTEND_URL` plus hard-coded `localhost` / `127.0.0.1` on ports 5173, 3000, 8080, 8000. | The blocked origin is in the browser error. Compare against the list and the deployed `FRONTEND_URL`. | Set `FRONTEND_URL` to the new origin (injected at `backend/app/main.py:70`) and restart. For more than one non-localhost origin you must edit `main.py` — there is no multi-origin env var. Match scheme and port exactly. |
| Frontend loops back to login, or every request 401s | Three candidates. (a) `localStorage.auth_token` missing or expired — `frontend/src/main.tsx:29-48` monkey-patches `window.fetch` to short-circuit an expired token into a synthetic 401 and dispatch `auth:token-expired`, and to clear the token reactively on any server 401; a capture-phase click listener (`:53-59`) does the same for UI-only interactions. (b) The token decodes by neither path: `decode_and_resolve_user` tries **HS256 with `SECRET_KEY` first** (`backend/app/utils/auth.py:112`), then falls back to Auth0 RS256 via JWKS (`:119-127`). A rotated `SECRET_KEY` invalidates every locally-issued token at once. (c) Cookie session expired — `SessionMiddleware` uses `trinity_session`, `max_age=3600*24*7`, `same_site="lax"`, `https_only` whenever `APP_ENV != "development"` (`backend/app/main.py:56-63`). | DevTools: is `auth_token` present and is its `exp` in the future? Does the request carry `Authorization: Bearer`? Server-side, a JWKS failure logs `Auth0 token verification failed:` (`backend/app/utils/auth.py:123`). | Log out and back in. Server-side: confirm `SECRET_KEY` is stable across restarts and replicas, that `AUTH0_DOMAIN` / `AUTH0_AUDIENCE` / `AUTH0_CLIENT_ID` match the tenant, and that the backend can reach `https://<AUTH0_DOMAIN>/.well-known/jwks.json` (cached in-process at `backend/app/utils/auth.py:21`). **Gotcha:** over plain HTTP outside development, `https_only=True` means the session cookie is never sent — cookie auth silently fails while bearer auth still works. |
| Advisor gets 403 on something they should be able to see | Three independent gates, detailed in *Authentication, Authorization & Impersonation*. (1) `require_role([...])` (`backend/app/utils/auth.py:252-269`) is a flat membership test on `user.role`; if the endpoint's list omits `FIRM_ADVISOR` or `FIRM_ADMIN`, that role is refused regardless of relationship. (2) `check_engagement_access` (`backend/app/services/role_check.py:10-106`) then checks the relationship. (3) `get_current_user` returns **403, not 401**, for `is_deleted` or inactive users (`backend/app/utils/auth.py:235-245`). | The detail string distinguishes them: `"Access denied. Required roles: [...]"` vs `"User account has been deleted"` / `"User account is inactive"` vs whatever the endpoint raises. | For (2): `ADVISOR` / `FIRM_ADVISOR` passes if they are `engagement.primary_advisor_id`, are in `engagement.secondary_advisor_ids`, **or** have a live `AdvisorClient` row (`advisor_id`, `client_id`, `status='active'`, `is_deleted=false`) matching `engagement.client_id`. **Gotcha:** the association branch is evaluated only when a `db` session is passed *and* `engagement.client_id` is not null (`backend/app/services/role_check.py:54, 78`) — a call site that omits `db=` silently loses it, and a multi-client engagement carrying only `client_ids` has a null `client_id` and bypasses it too. Fix by creating the `AdvisorClient` row, adding the advisor to `secondary_advisor_ids`, or correcting the endpoint's role list. |
| File upload rejected with 400 | Extension not on the allow-list, or over the size cap. Diagnostic uploads go through `FileService`: `ALLOWED_EXTENSIONS = {pdf, doc, docx, txt, rtf, xls, xlsx, csv, jpg, jpeg, png, gif, webp, zip}` (`backend/app/services/file_service.py:28-38`) and `MAX_FILE_SIZE = 10 * 1024 * 1024` (`:40`), enforced at `:58-72`. | The 400 detail names the rejected extension or the size limit. | Convert the file, or widen the list deliberately. **Gotcha — limits are per-surface:** profile-image upload allows only `.jpg/.jpeg/.png` (`backend/app/api/settings.py:97`), while the strategic-business-plan surface allows `{.pdf, .docx, .xlsx, .xls, .pptx, .txt, .csv, .png, .jpg, .jpeg}` at **100 MB** (`backend/app/api/strategic_business_plan.py:52-53`). Change the one you mean. **Gotcha:** the size check is `if hasattr(file, 'size') and file.size and ...` — when the client sends no length, `file.size` is falsy and the cap is skipped. |
| Files uploaded before a deploy are gone (broken links, 404 on `/files/...`) | Storage is the container's local disk. `backend/app/main.py:110-115` mounts `backend/files` at `/files`; `FileService` writes to `backend/files/uploads/...` (`backend/app/services/file_service.py:49-52`). Separately, `UPLOAD_DIR` (default `"uploads"`, `backend/app/config.py:62`) roots `backend/uploads/` for BBA, Roles Matrix and PD Scorecard — that root has **no mount at all**. | The `media` row exists; the file on disk does not. Reproduce by restarting the container and re-requesting the URL. | No fix after the fact — the bytes are gone. Attach a persistent volume, or move to object storage. Until then treat every uploaded file as ephemeral. Files sent to the AI provider carry a provider-side id on `media.llm_file_id` (legacy `media.openai_file_id`, `backend/app/models/media.py:43, 50`) with its own lifetime — provider files expire independently, which is why the scoring step has a re-upload-and-retry path (`backend/app/services/diagnostic_service.py:501-612`, `max_retries = 1` at `:513`). |
| Frontend hits the wrong backend (404s, CORS, or `localhost:8000` in production) | `VITE_API_BASE_URL` is re-read with a hand-copied constant in **56 separate files**, and **one disagrees**: `frontend/src/context/AuthContext.tsx:18` falls back to `''` (same-origin) while the rest fall back to `'http://localhost:8000'` (e.g. `frontend/src/lib/clientFetcher.ts:4`, `frontend/src/pages/Login.tsx:7`). Separately the **dev server** proxies `/api` and `/files` to `env.VITE_API_BASE_URL \|\| "http://localhost:8000"` (`frontend/vite.config.ts:8-27`); that proxy exists only under `vite dev`. | Check the Network tab's request origin, `frontend/.env` (it sets `VITE_API_BASE_URL`), and the build-time env of your deploy. | Set `VITE_API_BASE_URL` **at build time** — Vite inlines `import.meta.env` into the bundle, so changing it afterwards does nothing. **Gotcha:** with the variable unset, auth calls go same-origin through the proxy while every other call goes straight to `localhost:8000` — the two halves of the app talk to different origins, which is why "works in dev" and "404s in prod" happen together. See *Frontend Architecture*. |

---

### If you break glass

**Standing warning: local development points at a shared hosted database.** `DATABASE_URL` in `backend/.env` targets a hosted Postgres on `render.com`, and `backend/alembic/env.py:24` overrides `alembic.ini`'s placeholder with that same value. So:

- Every developer's `alembic upgrade head` migrates the environment everyone uses.
- Every seed script writes rows everyone sees.
- A `DELETE`, `TRUNCATE`, `alembic downgrade`, or any "let me just try this locally" destructive statement has real consequences for other people's work — and, if that database also backs anything customer-facing, for customers.
- Running the database-backed tests is safe: `tests/conftest.py`'s `db_session` fixture binds the session to an outer connection with `join_transaction_mode="create_savepoint"` (`:110`), so a service's own `db.commit()` only releases a savepoint and teardown rolls everything back (`:115`). Set `TEST_DATABASE_URL` (`:86`) to point them elsewhere anyway. See *Engineering Standards, Workflow & Testing*.

**Inspecting production data safely:**

1. Connect with a **read-only** role. If one does not exist, create it — the single highest-value operational change available in an afternoon.
2. Open an explicit read-only transaction and stay inside it: `BEGIN; SET TRANSACTION READ ONLY;` … `ROLLBACK;`. The server refuses writes, which no amount of client-side care can guarantee.
3. Always `SELECT` before you `UPDATE`. Write the `WHERE`, run it as a `SELECT`, count the rows, then convert it — keeping the same predicate.
4. Scope every mutation by primary key **and** expected state (`... WHERE id = '<uuid>' AND status = 'processing'`). If the row moved on, the update hits zero rows instead of the wrong thing.
5. Never `UPDATE` or `DELETE` without a `WHERE`. Never run a migration by hand; run the revision.
6. Take a snapshot before any manual data repair and know how to restore it. `alembic downgrade` is not a backup.
7. Do not print secrets into shared channels.

**Reading logs:** logs go to stdout only, so use the host's log viewer. Useful greps: the diagnostic UUID, `[Pipeline]`, `[Background Task]`, `[Status]`, `[Claude API] API call failed`, `PDF generation failed`.

---

### Technical debt and risk register

Ordered by blast radius × likelihood.

| # | Item | Impact | Effort | Recommendation |
|---|---|---|---|---|
| 1 | **Secrets in the working tree.** `backend/.env` holds live values for `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `AUTH0_CLIENT_SECRET`, `AUTH0_MANAGEMENT_CLIENT_SECRET`, `SMTP_PASSWORD` and `RESEND_API_KEY`; a Google service-account key sits beside it at `backend/trinity-platform-b690f5c862c7.json` with no code consuming it. Both are gitignored (`backend/.gitignore:27`, `:28-35`) but sit in a cloud-synced user folder, one `git add -f` from being committed. `frontend/.env` **is** tracked. | Critical — full database and AI-account compromise | Medium | Move backend secrets to the host's secret store and rotate every key on the assumption the current set is exposed. Revoke the service-account key unless someone claims it. `frontend/.env` holds only `VITE_API_BASE_URL` today; keep it that way and consider untracking it, since Vite inlines it into the public bundle. Both files are out-of-band handover artefacts — see *Environments, Configuration & Deployment*. |
| 2 | **One shared hosted database for all development.** No per-developer isolation; migrations and seeds are global. | Critical — sibling-revision collisions, cross-branch breakage, destructive local commands with real consequences | Medium | Give each developer a local Postgres; keep the shared instance as staging behind a read-only role for inspection. |
| 3 | **Long-running work in the API process.** No durability, no retry, no cross-process visibility, no horizontal scaling; a restart strands the row in `processing` and nothing sweeps it. The only recovery is a per-row auto-fail that fires when someone happens to poll that row. | High — silent data-state corruption on every deploy | High | Move long-running work out of the request process. Until then, add a startup routine that resets `processing` rows older than a threshold, and expose a stuck-count gauge on a readiness endpoint. |
| 4 | **Submit and cancel have no engagement-access check.** `POST /api/diagnostics/{id}/submit` (`:423`) and `.../cancel` (`:508`) depend only on `get_current_user`; sibling endpoints call `_require_diagnostic_access`. Any authenticated user with a UUID can start a paid AI run or cancel someone else's. | High — cross-tenant action and uncontrolled AI spend | Low | Add `_require_diagnostic_access(db=db, diagnostic=diagnostic, current_user=current_user)` to both, matching `:579`. |
| 5 | **`/files` is served unauthenticated.** `StaticFiles` at `backend/app/main.py:110-115` exposes every client upload, generated report and sample export under `backend/files/` to anyone who can guess a path. | High — client-confidential document disclosure | Medium | Replace the mount with an authenticated download endpoint that resolves the `media` row and runs the same access check as the rest of the API. Delete the committed sample SBP exports now. |
| 6 | **Near-zero automated coverage on critical paths.** `backend/tests/` covers program-guide and deliverable behaviour, deliverable task generation, and some of the Claude service surface. Nothing covers the diagnostic pipeline, auth/JWT resolution, `check_engagement_access`, `UserRoleType`, PDF generation or the JSON repair ladder. No frontend tests at all. | High — no safety net on the code most likely to break | High | Start with the cheapest units: a `check_engagement_access` truth table, `UserRoleType` round-trip both ways, `_repair_json` against captured bad payloads. Detail in *Engineering Standards, Workflow & Testing*. |
| 7 | **No CI and no deployment configuration in the repo.** `.github/` contains only `pull_request_template.md`; there is no Dockerfile, Procfile or platform manifest. Nothing runs tests, lint or type-check on push, and how the service is built and run is knowledge held outside the codebase. | High — every regression reaches the shared environment; deploys are undocumented | Low (CI) / Medium (deploy docs) | Add a workflow that installs `requirements-dev.txt`, runs the pure tests and builds the frontend. Separately, commit the deploy definition or document it in *Environments, Configuration & Deployment*. |
| 8 | **No error tracking.** Exceptions live only as tracebacks in stdout, with no grouping, counts or alerts. | High — failures are discovered by users, not engineers | Low | Wire an error tracker and alert on new exception groups. The fastest single improvement to operational awareness available here. |
| 9 | **No queryable audit trail.** `AuditService` writes impersonation start and end to the log stream only and swallows its own exceptions; nothing persists who acted as whom, or when. | High — impersonation is unaccountable beyond log retention | Low | Add the `audit_log` table the service's own comment anticipates and write through it. See *Authentication, Authorization & Impersonation*. |
| 10 | **A bare `pytest` does not pass.** `tests/test_claude_service.py` and `test_claude_integration.py` use `@pytest.mark.asyncio` but `pytest-asyncio` is not a dependency — `backend/requirements-dev.txt` adds only `pytest==8.3.4`, and there is no `pytest.ini`, `setup.cfg` or `pyproject.toml`. Developers run individual files. | Medium — discourages running tests at all | Low | Add `pytest-asyncio` and configure `asyncio_mode` so `pytest` from `backend/` is one green command. Prerequisite for CI. |
| 11 | **Local-disk file storage.** `backend/files` (served at `/files`) and the unmounted `backend/uploads` are ephemeral on most hosts; `media` rows outlive the bytes, and `backend/uploads/` currently holds real client uploads that are not backed up. | Medium–High — silent data loss on redeploy | Medium | Attach a persistent volume as a stopgap; move to object storage properly. Back up `backend/uploads/` before the next deploy. |
| 12 | **The background PDF render is discarded and `report_url` is never written.** `diagnostic_tasks.py:167` generates bytes and logs their length; nothing persists them. `diagnostics.report_url` (`models/diagnostic.py:46`) is read by `api/users.py:364` and two schemas but assigned nowhere. Every download re-renders from scratch inside the request (`api/diagnostics.py:919`). | Medium — wasted CPU on every run, a permanently null column that looks meaningful, slow downloads | Medium | Either persist the rendered PDF and populate `report_url`, or delete the background render and the column. |
| 13 | **Nine database tables exist with no models and no code.** `owner_team_members` and `signup_intents` from the self-service SaaS migration; `program_stage`, `program_task_template`, `program_dd_template`, `engagement_stage_state`, `engagement_dd_item` and `engagement_document_register_entry` from the Sale Ready programme migration; plus `engagement_module_checklist_item`, whose own docstring says "Schema only for now". Grepping `backend/app/` for any of them hits only `__pycache__`. `users.account_type` exists in the database but not on the `User` model, so a self-service owner and an advisor-provisioned client cannot be told apart in code (`backend/app/services/deliverable_permissions.py:20-30`). | Medium — schema no one can reason about; autogenerate noise; a permission rule that cannot be written | Medium | Decide per group: adopt with models, or drop with a migration. Adding `account_type` to `User` is the prerequisite for any self-service rule. Detail in *Data Model & Database*. |
| 14 | **`/api/poc` route prefix for a production tool.** The BBA tool is served under `APIRouter(prefix="/api/poc", tags=["bba"])` (`backend/app/api/upload_poc.py:97`), in a module named `upload_poc.py`, with a `frontend/src/components/poc/` directory. The prefix disagrees with its own tag. | Medium — misleads every new engineer; renaming later is a breaking API change plus a frontend sweep | Medium | Introduce `/api/bba`, serve both for one release, migrate the frontend, retire `/api/poc`, and rename the module and component directory in the same change. |
| 15 | **56 hand-copied API base URL constants, one of which disagrees.** `VITE_API_BASE_URL` is re-read in 56 files; `frontend/src/context/AuthContext.tsx:18` falls back to `''` while the other 55 fall back to `'http://localhost:8000'`. `localStorage.getItem('auth_token')` appears 136 times. The only shared behaviour is the `window.fetch` monkey-patch in `frontend/src/main.tsx`. | Medium — auth and the rest of the app can address different origins; no single place to change base URL, auth handling, retries or error handling | Medium | Extract one `apiFetch(path, init)` helper owning base URL, bearer header and 401 handling; migrate call sites incrementally and retire the monkey-patch. |
| 16 | **Disabled TypeScript strictness with no type-check in the build.** `frontend/tsconfig.json` sets `strictNullChecks: false`, `noImplicitAny: false`, `noUnusedLocals: false`, `noUnusedParameters: false`, `allowJs: true`, and `npm run build` is bare `vite build` with no `tsc`. Type errors never fail a build. | Medium — whole classes of null/undefined bugs invisible, and nothing enforces even the weakened settings | High | Add `tsc --noEmit` to the build (expect it to fail first — see the Help page below), then enable `strictNullChecks` per directory, starting with `src/lib` and `src/store`. |
| 17 | **A broken Help feature is committed.** `frontend/src/pages/dashboard/help/HelpPage.tsx` imports `@/store/slices/helpReducer` and `@/components/help/YouTubePlayer` — neither file exists — and reads a `state.help` slice that is not registered. There is no `/dashboard/help` route and no backend endpoint. Nothing imports the page, so it compiles only because the build skips `tsc`. | Medium — adding a route, or wiring type-checking, breaks the build immediately | Low | Delete the file, or finish the feature (reducer, player component, backend CRUD, route). Resolve before item 16. |
| 18 | **PLACEHOLDER programme content.** `backend/files/program_guide/value_builder_modules.json` contains 6 `PLACEHOLDER` occurrences; `backend/app/services/document_template_service.py` also references placeholders. | Medium — placeholder text can reach a client-facing deliverable | Low (rerun) / blocked on content | Track the outstanding copy, add a guard that refuses to render a client-facing document containing `PLACEHOLDER`, and re-run `backend/scripts/seed_program_guide_content.py` when real copy lands. |
| 19 | **Inconsistent route prefixes.** Fifteen routers declare `/api/...` themselves; six declare a bare prefix and rely on `main.py` adding `prefix="/api"`. `main.py` carries comments to keep it straight (`:90, 106, 107`). | Medium — a new router mounted the wrong way lands at the wrong path or double-prefixed | Low | Pick one convention — full prefix on the router, no prefix in `main.py` — and convert all of them in one change. |
| 20 | **Health check asserts nothing.** `/health` returns a static dict. | Low–Medium — deploy gates and uptime monitors report green on a broken app | Low | Add `/ready` asserting database, migration head, AI client init and uploads-dir writability, per *Health checks* above. |
| 21 | **Dead OpenAI code path retained.** `backend/app/services/openai_service.py` (910 lines) is imported nowhere; nine modules carry commented "Preserved for rollback" imports (`backend/app/main.py:30`, `api/upload_poc.py:43`, `services/bba_conversation_engine.py:12`, `bba_presentation_service.py:22`, `bba_task_planner_service.py:28`, `chat_service.py:17`, `diagnostic_service.py:19`, `file_service.py:19`, `strategy_workbook_service.py:14`). `OPENAI_*` settings remain (`config.py:40-44`), `openai==2.9.0` is still pinned, `media.openai_file_id` persists alongside `llm_file_id`, and live variables named `openai_service` hold `ClaudeService`. `LLM_PROVIDER` (`config.py:55`) is read by no live code. | Low–Medium — misleads readers, doubles the surface to reason about | Low | Delete the module, the commented blocks and the dependency; rename the misleading variables; keep `media.openai_file_id` as a data column, documented as legacy. See *Technology Stack & Dependencies*. |
| 22 | **Task-queue packages are load-bearing for the wrong reason.** They are pinned **and imported at module scope** by `backend/app/tasks/diagnostic_tasks.py:14-18`, and `backend/app/api/diagnostics.py:500` imports `_run_pipeline` from that module — so the API cannot serve a diagnostic submit without them installed. Removing them requires moving `_run_pipeline` out of that module first. The same module holds a stale-row reset (`:34-50`) bound to a worker-lifecycle signal the API process never emits, and a timeout handler (`:217-231`) nothing can trigger; both look like coverage that does not exist. `backend/app/celery_app.py`, `docker-compose.yml`, `backend/app/config.py:57-59` and the never-written `diagnostics.celery_task_id` column (`backend/app/models/diagnostic.py:61`) are dead alongside them. | Low–Medium | Low | Move `_run_pipeline` to its own module, then delete the rest — re-homing the stale-row reset into the FastAPI startup event, where it would actually fire. |
| 23 | **Repository strays.** `backend/=0.52.0`, `backend/fix_userrole_enum.sql`, `backend/test_diagnostic_responses.json` and a generated `.pptx` under `backend/files/exports/sbp/` are all tracked; `frontend/dist/` and `backend/uploads/` sit untracked in the tree. Stale `__pycache__` files reference models that do not exist on this branch. | Low — confuses greps and code reading; one file is publicly served | Low | Delete the strays, add `dist/` and `__pycache__/` coverage, and convert `fix_userrole_enum.sql` into a real migration so its application is tracked. Detail in *Repository hygiene* above. |
| 24 | **Stale documentation.** `frontend/GLOBAL_DIAGNOSTIC_POLLING.md` states a 5-second poll and a 20-minute safety timeout; the code uses 30 s (global) and 10 s / 90 min (page-level). `backend/README.md` still says a from-empty `alembic upgrade head` fails, though `create_orphan_tables.py` was added to fix it. `backend/NON_BLOCKING_FIX.md` documents an OpenAI-era fix in a Claude-only codebase. `backend/app/models/diagnostic.py:31` lists status values the code neither writes nor recognises. The Postman collection's health check hits a non-existent `/api/health`. The cancel endpoint's docstring claims it cancels a running task. | Low — sends new engineers down wrong paths | Low | Verify and correct each; delete `NON_BLOCKING_FIX.md` or retitle it as historical context. |
| 25 | **Unmerged work on other branches is undecided.** Feature work exists outside `staging` that has not been adopted or abandoned, and every day it sits there widens the diff against a shared database that all branches migrate. | Medium — merge cost grows; migration collisions recur | Medium | Take an explicit adopt-or-abandon decision per branch. Inventory and current state in *Unmerged Work on Other Branches*. |

---

## 18. Unmerged Work on Other Branches

The remote carries **233 branches**. Most are merged history, but four hold substantial work that exists nowhere on `staging` and that a new owner would otherwise never find. Between them they account for roughly **9,000 lines of written, unmerged code** — including a complete deployment, and one feature whose *database schema is already live in production while its code is not*.

Read this section before scoping any new work. Two of these branches represent weeks of effort that is already written, and together they explain eight otherwise-inexplicable tables in the database.

> **How this was determined:** `git for-each-ref --sort=-committerdate refs/remotes/origin` for recency, `git rev-list --left-right --count origin/staging...<branch>` for divergence, and `git diff --shortstat origin/staging...<branch>` for size. Every claim below is reproducible with those commands.

### Summary

| Branch | Ahead | Behind | Size | What it is | Schema already on `staging`? |
|---|---:|---:|---|---|---|
| `feature/sale-ready-management` | 1 | 65 | 29 files, 3,146 lines | The Sale Ready programme — the Sale Ready twin of Value Builder | **Yes — 6 tables, live and orphaned** |
| `feature/self-service` | 1 | 59 | 44 files, 4,203 lines | Self-service signup, checkout, billing, team management | **Yes — 2 tables + 5 columns, live and orphaned** |
| `feature/azure-deployment` | 2 | 59 | 28 files, 1,049 lines | A complete Azure deployment: IaC, Dockerfile, CI, blob storage | No |
| `fix/google-drive-imp` | — | — | `google_drive_service.py` | Google Drive integration | Partial — one column |

**The pattern is the same in the first two cases and it is the most important thing in this section: the migration was merged so the Alembic graph would stay consistent, and the feature code was not.** That is why the database contains eight tables that no model, service or router references.

---

### `feature/sale-ready-management` — a live schema with no code

**Status:** 1 commit ahead of `staging` (`ca4c700`, "sale ready management"), 65 behind. Last touched 14 July 2026. 29 files, 3,146 insertions.

This is the Sale Ready analogue of the Value Builder programme documented in *Value Builder Programme — Program Guide & Deliverables* — stages instead of modules, task templates, a due-diligence checklist and a document register. It is complete on the branch:

| Layer | Files |
|---|---|
| Backend | `app/models/sale_ready.py` (297 lines), `app/services/sale_ready_service.py` (445 lines), `app/api/sale_ready.py` (240 lines), `app/schemas/sale_ready.py` (160 lines) |
| Content | `files/sale_ready/stages.json`, `task_templates.json`, `dd_templates.json`, and `scripts/seed_sale_ready_content.py` (140 lines) |
| Frontend | 8 components under `components/engagement/sale-ready/` — `SaleReadyProgramTab`, `StageDetailView`, `StageTasksSection`, `DDItemsTable`, `MasterDDView`, `DocumentRegisterTable`, `RoadmapView`, `saleReadyUi` |
| Wiring | `app/main.py`, `app/models/__init__.py`, `tool_service/tool_selector.py`, `app/api/tasks.py`, `app/models/task.py` |

> **Gotcha — this is the one to understand.** The migration `backend/alembic/versions/add_sale_ready_program_tables.py` **is on `staging`** (it arrived in commit `3ad9abe`, and a dedicated merge revision `merge_deliverable_and_sale_ready.py` exists to splice it into the graph). Its six tables — `program_stage`, `program_task_template`, `program_dd_template`, `engagement_stage_state`, `engagement_dd_item`, `engagement_document_register_entry` — plus the added column `tasks.section` are **applied in every environment right now**. But `grep sale_ready backend/app/main.py` on `staging` returns zero: no model, no service, no router, no frontend. The tables exist and nothing can read or write them.

**Recommendation:** decide, and then act on the decision in the schema. Either merge the feature — the code is written and only needs a rebase — or write a migration that drops the six tables and the column. Leaving live tables with no owning code is how a schema becomes unmaintainable: the next engineer cannot tell orphaned scaffolding from something load-bearing they have not found yet.

---

### `feature/self-service` — a second live schema with no code

**Status:** 1 commit ahead of `staging` (`00e840f`), 59 behind. Last touched 24 July 2026. 44 files, 4,203 insertions.

A complete self-service tier — a business owner signing up, paying, and running their own programme without an advisory firm — built in one commit and never merged.

| Area | Files |
|---|---|
| Backend | `app/api/self_service.py`, `app/services/self_service.py` (353 lines), `app/services/team_service.py` (324 lines), and an `app/services/billing/` package (`base.py`, `catalogue.py`, `manual.py`) |
| Frontend — signup funnel | `pages/signup/SignUpPage.tsx`, `CheckoutPage.tsx`, `OnboardingCompletePage.tsx` |
| Frontend — in-app | `pages/dashboard/BillingPage.tsx`, `TeamPage.tsx`, `components/OwnerProgramCard.tsx`, `lib/selfServiceApi.ts` |
| Modified | `app/utils/auth.py`, `app/services/role_check.py`, `frontend/src/App.tsx`, `Sidebar.tsx`, `AuthContext.tsx`, `types/auth.ts` |

Again the migration shipped without the code. `backend/alembic/versions/f7a1b2c3d4e5_self_service_saas.py` is on `staging` and has already added `users.account_type`, made `engagements.primary_advisor_id` nullable, added `subscriptions.user_id` / `.program` / `.provider`, and created `owner_team_members` and `signup_intents` — none of which any model declares.

The consequence is written down in the codebase itself, at `backend/app/services/deliverable_permissions.py:20-30`: a genuine self-service owner is `CLIENT` **and** `account_type == 'self_service'`, while an advisor-provisioned client is `CLIENT` + `'advisory'` — but "account_type exists in the database but is not on the User model on this branch, so the two cannot be told apart in code". **Adding `account_type` to the `User` model is the prerequisite for any authorisation rule that needs to distinguish them.**

The migration is written defensively with `inspector` guards (`:31-41`) "because several environments have drifted from the migration history" — read that as contemporaneous evidence for the shared-database risk in *Environments, Configuration & Deployment*.

> **Gotcha:** `backend/app/services/billing/` **exists as a directory in the working tree on `staging` containing only a stale `__pycache__`** from a previous checkout of this branch. If you find it and conclude billing is implemented, it is not — nothing there is tracked or importable. The same is true of `backend/app/api/self_service.py`. Delete the orphaned `__pycache__` directories so they stop misleading readers.

The billing package's `manual.py` suggests a manual rather than provider-integrated payment flow, consistent with the finding in *Core Domain Modules* that no payment provider appears anywhere in the tree.

**Recommendation:** this is a product decision before it is an engineering one. Establish whether self-service is still on the roadmap before anyone invests in rebasing 4,200 lines across 59 commits of drift — including changes to `auth.py` and `role_check.py`, the two files most likely to conflict. Whatever is decided, resolve the orphaned schema either way.

---

### `feature/azure-deployment` — a complete, unmerged deployment

**Status:** 2 commits ahead of `staging`, 59 behind. Last touched 28 July 2026. 28 files, 1,049 insertions.

This branch answers most of the deployment questions in *Handover Checklist & Open Questions*: **`staging` has no deployment infrastructure, but a full Azure deployment was designed, written and documented here and never merged.**

| File | Purpose |
|---|---|
| `infra/main.bicep` (296 lines) | Infrastructure as code: Log Analytics, Application Insights, Azure Container Registry (Basic), Key Vault, Storage Account with a `files` blob container, PostgreSQL Flexible Server (`Standard_B1ms`, database `trinity`), Container Apps environment |
| `infra/README.md` (145 lines) | Step-by-step runbook — prerequisites, parameters, first deploy, image build, migrations, frontend, CI secrets |
| `infra/main.parameters.json` | Parameter template, values intentionally blank; the runbook directs you to copy it to a gitignored `.local.json` |
| `backend/Dockerfile`, `backend/.dockerignore` | Container build for the API |
| `backend/gunicorn_conf.py`, `backend/supervisord.conf` | In-container process management |
| `.github/workflows/deploy-backend.yml` | On push to `main` touching `backend/**` or `infra/**`: `az acr build`, then `az containerapp update` |
| `.github/workflows/deploy-frontend.yml` | Build and publish the SPA to Azure Static Web Apps |
| `frontend/staticwebapp.config.json` | SPA fallback routing |
| `backend/app/services/storage_service.py` (164 lines) | **The most valuable file on the branch** — see below |

**`storage_service.py` is worth merging on its own merits, whatever is decided about Azure.** It puts every file read and write behind a `StorageService` interface with two implementations chosen by a `STORAGE_BACKEND` setting: `local` (today's behaviour, `backend/files/<key>`) and `azure_blob`. It also solves the migration problem — rows written before the abstraction hold absolute local paths, and the blob backend falls back to reading those off disk so existing data keeps working. This directly retires the "uploads vanish on redeploy" risk in *Operations, Diagnostics & Troubleshooting*, and the interface is generic enough to retarget at any object store. The branch already threads it through `file_service.py`, `upload_poc.py`, `strategy_workbook.py`, `users.py` and the SBP exporters.

The branch's own README independently flags something this document also found: the CORS `allow_origins` list in `backend/app/main.py` is hardcoded to localhost origins, so any deployed frontend must be added to it.

**Cost shape:** the design is explicitly optimised to stay under roughly USD $100/month — burstable Postgres, Basic-tier registry, a single small Container App at 0.5 vCPU / 1 GiB with `minReplicas: 1`, `maxReplicas: 3`, and Free-tier Static Web Apps.

**Three things must change before reviving it:**

1. **Rebase.** It is 59 commits behind. Everything built since — the Roles Matrix, PD & Scorecard, the Value Builder programme and the deliverables system — postdates it, and several files it touches have moved underneath it.
2. **Drop the second process.** The container runs two processes under `supervisord`, and the template provisions an extra managed cache service, purely to serve the dead task-queue scaffolding described in *Operations, Diagnostics & Troubleshooting*. Neither is needed. Run one process, delete the cache resource from the Bicep template, and the cost falls further.
3. **Replace admin-credential registry auth with a managed identity** and an `AcrPull` role assignment. The branch's own notes call this out as a start-simple shortcut that should not survive real traffic.

**Recommendation:** treat `storage_service.py` and the `Dockerfile` as immediately mergeable, and the infrastructure template as a strong starting point needing a rebase and the three changes above. Whichever platform is ultimately chosen, this is the closest thing to a deployment design that exists — do not start from scratch without reading it.

---

### `fix/google-drive-imp` — an unmerged Google Drive integration

**Status:** holds `backend/app/services/google_drive_service.py`, which does not exist on `staging`.

This explains a set of loose ends found independently elsewhere in this document: the `GOOGLE_DRIVE_ENABLED` / `GOOGLE_DRIVE_CREDENTIALS_FILE` / `GOOGLE_DRIVE_FOLDER_ID` settings declared at `backend/app/config.py:77-80` that no `staging` code reads; the `strategy_workbooks.drive_file_id` column that is declared and serialised but never written; `GOOGLE_DRIVE_ENABLED=true` in the local `.env`; a service-account key sitting in `backend/`; and a stale `google_drive_service.cpython-312.pyc` in `__pycache__`. No Google client library is pinned in `backend/requirements.txt`, so the integration could not run on `staging` even if something called it.

**Recommendation:** the integration is not live. Either merge it deliberately, or **revoke the service-account key and delete the three dead settings and the dead column**. A live private key on developer machines, for a feature that does not run, is pure downside.

---

### Branch hygiene

233 remote branches — of which the ten most recent are all either merged or stale — is itself a maintenance problem. It is precisely why the four branches above were nearly invisible, and why two of them managed to land schema changes without anyone noticing the code never followed.

**Recommendations:**

1. **Resolve the four decisions above first**, so nothing of value is lost in the cleanup.
2. **Prune.** Delete merged branches; tag anything kept for the record; adopt the rule that a branch is deleted when its pull request merges.
3. **Adopt one naming convention.** Current practice mixes `feature/*`, `feature-2/*`, `feat/*`, `fix/*`, `merge/*`, personal-name branches and ticket-style `bench-NN` suffixes — see *Engineering Standards, Workflow & Testing*.
4. **Add a merge rule that prevents a repeat of the schema/code split**: a pull request that adds an Alembic revision must also add the model that owns the tables, or must not be merged. This single rule would have prevented all eight orphan tables.

---

## 19. Handover Checklist & Open Questions

### Accounts and access to transfer

Nothing in this list can be recovered from the codebase. Each item needs a named owner on the receiving side before the outgoing team disengages.

| # | Item | Why it is needed | Owner | Done |
|---|---|---|---|---|
| 1 | **GitHub organisation `46-Bytes`** — admin on `Trinity-Platform` | Source of truth; branch protection; future CI | | ☐ |
| 2 | **Auth0 tenant** (`dev-i35a4hkouf6bs25n.au.auth0.com`) — tenant admin | Every login depends on it. Note the `dev-` prefix: confirm whether a separate production tenant exists. | | ☐ |
| 3 | Auth0 **application** credentials (client ID/secret) and **Management API** credentials | Backend cannot start without them | | ☐ |
| 4 | **Render** account owning the PostgreSQL instance | The database. Backups, credentials, plan. | | ☐ |
| 5 | **Anthropic** console — API key, billing, usage limits | All AI features | | ☐ |
| 6 | **Resend** account — API key and the verified sending domain `benchmarkbusinessadvisory.com.au` | Password-setup and notification email | | ☐ |
| 7 | **Google Cloud** project behind the service-account key `trinity-platform-*.json` | No code on `staging` reads it (see Q5 below). Revoke unless the integration is being merged. | | ☐ |
| 8 | **Lovable** project `48e3eaf7-28c5-4a8d-99a0-61f6b3c0c01a` | The frontend's origin; confirm whether it still round-trips commits | | ☐ |
| 9 | Wherever the **backend and frontend are actually hosted** | See Q1 below — this is not determinable from the repository | | ☐ |
| 10 | DNS / domain registrar for any production hostname | | ☐ |

### First-week actions for the receiving team

**Day 1 — get it running**
1. Obtain `backend/.env` from the outgoing team over a secure channel. Do not accept it by email or chat.
2. Stand up a local backend and frontend against a **restored copy** of the database, not the shared instance (*Operations, Diagnostics & Troubleshooting*).
3. Confirm login works on both paths — Auth0 and email/password.

**Week 1 — make it safe**
4. **Rotate every credential** now that they have been shared: Auth0 client secret, Auth0 Management client secret, `SECRET_KEY`, Anthropic key, Resend key, database password. Rotating `SECRET_KEY` invalidates all existing sessions and locally-issued tokens — announce it.
5. **Write `backend/.env.example`** — every variable name, no values, with a one-line comment each. The README already tells people to copy it; the file does not exist.
6. **Give each developer their own database.** This is the single change that most reduces day-to-day risk (*Operations, Diagnostics & Troubleshooting*).
7. **Take and verify a database backup**, and document the restore procedure by actually performing a restore.
8. **Capture the current schema as a baseline.** `pg_dump --schema-only` from a known-good database, committed to the repo, so a new environment can be built without replaying migrations that cannot replay (*Data Model & Database*).

**Week 2–4 — make it maintainable**
9. Add CI: run the backend test suite and `npm run build` on every pull request. There is none today.
10. Add an error tracker to the backend. Today a failed AI pipeline is visible only in stdout (*Operations, Diagnostics & Troubleshooting*).
11. Move long-running AI work out of the request process (*System Architecture*).
12. **Resolve the eight orphan tables.** Two merged migrations created schema for features whose code was never merged (*Unmerged Work on Other Branches*). Either merge the code or drop the tables — and add the merge rule that prevents a repeat: a pull request adding an Alembic revision must also add the model that owns the tables.
13. Work the technical-debt register in *Operations, Diagnostics & Troubleshooting* in priority order.

### Open questions for the outgoing team

These could not be answered from the code. Each one should be answered in writing before this document is considered final.

| # | Question | Why it matters |
|---|---|---|
| Q1 | **Where are the backend and frontend deployed?** The `staging` branch contains no Dockerfile, no CI workflow and no platform manifest; only the database's Render hostname is discoverable. A complete Azure deployment exists but is unmerged (*Unmerged Work on Other Branches*). Is anything running today, and if so, where and how was it put there? | Nobody can deploy a fix without this. |
| Q2 | **Was the Azure deployment ever executed?** Does the resource group `trinity-platform-rg` exist? If it does, its outputs are the missing production configuration. | Determines whether *Unmerged Work on Other Branches* is a revival or a first deploy. |
| Q3 | **Is there a production environment distinct from this one?** The Auth0 tenant is `dev-`-prefixed and the checked-in config is entirely local. If production exists, what are its URLs, its database, and its Auth0 tenant? | Determines whether the shared-database risk is a development-only problem or a live one. |
| Q4 | **Which branch deploys?** `main`, `staging`, or something else? The history shows active `main` and `staging` branches merging in both directions. | Release process. |
| Q5 | **Is the Google Drive integration wanted?** It is not live — the implementation sits unmerged on `fix/google-drive-imp` (*Unmerged Work on Other Branches*) while its settings and a live service-account key remain on `staging` and on disk. Merge it or revoke the key. | A live private key for a feature that does not run is pure downside. |
| Q5b | **Is self-service signup and billing still on the roadmap?** 4,200 lines of it are built and unmerged (*Unmerged Work on Other Branches*). | Decides whether to rebase it or delete it. |
| Q6 | **Is there a payment provider?** Subscriptions carry a `monthly_price` but no payment integration was found. How are firms actually billed? | Revenue path. |
| Q6b | **Is the Sale Ready programme wanted?** Its six tables are live in the database and its 3,146 lines of code sit unmerged (*Unmerged Work on Other Branches*). Merge it, or write a migration that drops the tables. | Live tables with no owning code make the schema unreadable to the next engineer. |
| Q7 | **When does the Value Builder programme content get replaced?** `backend/files/program_guide/value_builder_modules.json` is still PLACEHOLDER copy. Who owns the real advisory text? | The programme cannot be shown to a client until this is done. |
| Q8 | **Are there users in production today, and how many?** | Determines the blast radius of every item above. |
| Q9 | **Is the Lovable project still connected**, and does editing there still commit to this repository? | If yes, changes can arrive in the repo from outside the team's git workflow. |
| Q10 | **Which of the seven unbuilt AI Tool cards are committed roadmap** versus aspirational? (*AI Tools — Roles Matrix, PD & Scorecard*) | Scoping the next phase. |
| Q11 | **What is the intended retention policy for uploaded client files and AI outputs?** Files are on local disk with no lifecycle rules. | Privacy obligation, and it affects the storage decision in the technical-debt register in *Operations, Diagnostics & Troubleshooting*. |
| Q12 | **Is there any existing agreement on data residency?** The Auth0 tenant is `au.auth0.com` and the sending domain is `.com.au`, which suggests Australian clients and possibly Australian Privacy Principles obligations, but the database region and the AI provider region were not verified. | Compliance. |

### Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Outgoing engineering owner | | | |
| Receiving engineering owner | | | |
| Product / business owner | | | |
