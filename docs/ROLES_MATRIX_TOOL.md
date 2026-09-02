# Roles & Responsibilities Matrix Tool

Advisor-facing tool that turns position descriptions and notes into a matrix
matching the "Job Roles" tab of the HR Planning Tool workbook.

---

## Workflow

| Step | What the advisor does | Endpoint |
|------|----------------------|----------|
| 1. Inputs | Uploads PDs/notes, lists key staff, pastes responsibilities lists, confirms which roles to include | `POST /{id}/upload`, `PATCH /{id}/inputs` |
| 2. Extract | Runs AI extraction of responsibilities per person | `POST /{id}/extract` |
| 3. Matrix | Builds the rows, edits them in a grid, exports | `POST /{id}/matrix/generate`, `PATCH /{id}/matrix`, `POST /{id}/export/excel` |

Nothing is estimated. Where the source material is silent, the cell stays blank.

---

## Matrix layout

The exported sheet keeps the template exactly:

- Row 1 — `HR MANAGEMENT PLAN` (A1:J1 merged)
- Row 2 — `Role Analysis` (A2:J2 merged)
- Row 3 — headings
- Row 4+ — one row per responsibility

| Name | Role Descriptions | Time | Priorities | Retain | Gain | Lose | Action | Resp | When |
|------|-------------------|------|------------|--------|------|------|--------|------|------|

- `Name` appears on the first row of each person's block only.
- `Retain` / `Gain` / `Lose` hold `Y` or nothing.
- The sample workbook merges `Time` down one person's block (C38:C43). The
  exporter unmerges everything in the data region and writes one value per row.

---

## Files

### Backend

| File | Purpose |
|------|---------|
| `app/api/roles_matrix.py` | All endpoints, prefix `/api/roles-matrix` |
| `app/services/roles_matrix_service.py` | CRUD and per-step updates |
| `app/services/roles_matrix_engine.py` | Claude orchestration for extract and build |
| `app/services/roles_matrix_export.py` | Writes rows into a copy of the template |
| `app/models/roles_matrix.py` | `RolesMatrix` entity, table `roles_matrices` |
| `app/schemas/roles_matrix.py` | Request/response schemas |
| `files/prompts/roles-matrix/*.md` | System prompt plus one prompt per AI step |
| `files/templates/roles-matrix/HR Planning Tool.xlsx` | The template the export is built from |

### Frontend

| File | Purpose |
|------|---------|
| `pages/dashboard/RolesMatrixPage.tsx` | Page shell, stepper, launch pre-flight |
| `components/roles-matrix/InputsStep.tsx` | Step 1 — the four required inputs |
| `components/roles-matrix/ExtractStep.tsx` | Step 2 — extraction and review |
| `components/roles-matrix/MatrixStep.tsx` | Step 3 — editable grid, copy for Excel, export |
| `store/slices/rolesMatrixReducer.ts` | Redux thunks and state |

Routes: `/dashboard/engagements/:engagementId/roles-matrix` and
`/dashboard/ai-tools/roles-matrix`. Launch points are the engagement's AI Tools
tab (`FollowUpToolsTab`) and the AI Tools grid.

---

## Access control

Every endpoint requires one of `advisor`, `admin`, `super_admin`, `firm_admin`,
`firm_advisor`. A matrix is reachable by its creator, or by anyone with access to
the linked engagement via `check_engagement_access`. Soft-deleted rows are
filtered out of every read.

---

## AI calls

Both AI steps go through `ClaudeService`:

- PDFs attach as document blocks.
- Word, Excel and text files go through the Code Interpreter container.
- The system prompt and the step prompt are sent as two separately cached
  system blocks.
- Responses are JSON; token usage accumulates on `ai_tokens_used`.

---

## Schema

Table `roles_matrices`:

| Column | Type | Null | Notes |
|--------|------|------|-------|
| `id` | UUID | no | PK |
| `engagement_id` | UUID | yes | FK `engagements.id` ON DELETE SET NULL, indexed |
| `created_by_user_id` | UUID | no | FK `users.id` ON DELETE CASCADE, indexed |
| `status` | VARCHAR(50) | no | `inputs`, `extracted`, `matrix_built`, `completed`; indexed |
| `current_step` / `max_step_reached` | INTEGER | yes | UI step persistence |
| `file_ids` | JSONB | yes | Claude file ids |
| `file_mappings` | JSONB | yes | filename → file_id |
| `stored_files` | JSONB | yes | filename → relative disk path |
| `staff` | JSONB | yes | `[{name, role_title}]` |
| `included_roles` | JSONB | yes | Roles confirmed for the matrix |
| `pasted_notes` | TEXT | yes | Pasted responsibilities/org chart text |
| `extracted_responsibilities` | JSONB | yes | Extraction output |
| `matrix_rows` | JSONB | yes | Ordered rows, one key per template column |
| `matrix_edited` | BOOLEAN | no | default false |
| `ai_model_used` | VARCHAR(100) | yes | |
| `ai_tokens_used` | INTEGER | yes | |
| `is_deleted` | BOOLEAN | no | default false |
| `created_at` / `updated_at` | TIMESTAMP | no | |
| `completed_at` | TIMESTAMP | yes | Set on first export |

Uploaded copies are persisted under `<UPLOAD_DIR>/roles-matrix/<matrix_id>/`.

### Migration note

`alembic revision --autogenerate` in this repo picks up a large amount of
pre-existing drift unrelated to this table (dead columns on `users`,
`subscriptions`, `strategy_workbooks`, plus comment and constraint noise). Trim
the generated revision down to the `create_table('roles_matrices')` call and its
three `create_index` calls before applying it.
