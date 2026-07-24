# Deploying Trinity Platform to Azure

Architecture: a single Azure Container App running both the FastAPI API
(gunicorn) and the Celery worker together, under supervisord (see
`backend/Dockerfile`, `backend/supervisord.conf`), backed by Azure Database
for PostgreSQL, Azure Cache for Redis, and Azure Blob Storage; the React/Vite
frontend ships to Azure Static Web Apps.

This trades away independent scaling and fault isolation between the API and
the worker (a stuck Celery task or memory spike can now affect API
responsiveness, and vice versa) for roughly half the always-on Container
Apps compute cost of running them as two separate apps — chosen to keep
monthly spend under ~$100. If the worker later needs to scale independently
(e.g. under heavy background-job load), split it back into its own Container
App and reintroduce a `workerImage`/`workerApp` resource in `main.bicep`.

## 0. File storage

All uploads/exports (diagnostic files, profile pictures, BBA/SBP project
files, generated Strategy Workbooks) go through `app/services/storage_service.py`,
which supports two backends selected by `STORAGE_BACKEND`:

- `local` (default) — reads/writes `backend/files` on disk. Used automatically
  in dev and anywhere `STORAGE_BACKEND` isn't set, so local behavior is
  unchanged.
- `azure_blob` — reads/writes blobs in the storage account this template
  provisions. `main.bicep` already sets `STORAGE_BACKEND=azure_blob` and
  `AZURE_STORAGE_CONNECTION_STRING` on the container app, so this is wired
  up automatically — no manual step needed.

Docx/pptx exports for the BBA tool and Strategic Business Plan tool
(Word/Excel/PowerPoint downloads) were already generated in-memory and
streamed straight to the response, so those needed no change either way.

## 1. Prerequisites

```bash
az login
az account set --subscription <subscription-id>
az group create -n trinity-platform-rg -l australiaeast
```

## 2. Fill in secrets

Copy the parameters file and fill in real values — **do not** edit
`infra/main.parameters.json` in place with secrets, it's checked into git:

```bash
cp infra/main.parameters.json infra/main.parameters.local.json
# edit infra/main.parameters.local.json (gitignored) with real values:
#   - postgresAdminPassword: generate a strong password
#   - secretKey: `openssl rand -hex 32`
#   - auth0ClientSecret / auth0ManagementClientSecret / anthropicApiKey / resendApiKey: from your existing .env
#   - auth0Domain / auth0ClientId / auth0Audience / auth0ManagementApiAudience / auth0ManagementClientId: from Auth0 dashboard
#   - frontendUrl: fill in after step 4 creates the Static Web App (or leave a placeholder and `az containerapp update` it later)
```

## 3. First deploy (infra + a placeholder image)

The first run deploys everything with a placeholder container image so the
Container Apps Environment, registry, database, cache, and storage account
all exist before you've built anything:

```bash
az deployment group create \
  -g trinity-platform-rg \
  -f infra/main.bicep \
  -p infra/main.parameters.local.json
```

Note the outputs — `acrLoginServer`, `apiFqdn`, `storageAccountName`,
`postgresHost`, `redisHost`.

## 4. Build and push the real image, point the app at it

```bash
ACR_NAME=$(az deployment group show -g trinity-platform-rg -n main --query properties.outputs.acrLoginServer.value -o tsv | cut -d. -f1)

az acr build --registry "$ACR_NAME" --image trinity-backend:latest ./backend

az containerapp update -g trinity-platform-rg -n <apiApp name from output> \
  --image "$ACR_NAME.azurecr.io/trinity-backend:latest"
```

## 5. Run database migrations

Run once against the new Postgres instance (from a machine that can reach
it, or as a one-off `az containerapp exec` / job using the same image):

```bash
DATABASE_URL=postgresql://trinityadmin:<password>@<postgresHost>:5432/trinity \
  alembic upgrade head
```

## 6. Frontend — Azure Static Web Apps

```bash
az staticwebapp create \
  -g trinity-platform-rg \
  -n trinity-frontend \
  -l eastasia \
  --sku Free
```

Set `frontend/.env` (or the build-time env var) to the API's public FQDN
before building:

```
VITE_API_BASE_URL=https://<apiFqdn from step 3 output>
```

Then either `npm run build` and deploy `frontend/dist` with the SWA CLI, or
let `.github/workflows/deploy-frontend.yml` do it — set these repo secrets:
`AZURE_STATIC_WEB_APPS_API_TOKEN` (from `az staticwebapp secrets list`),
`VITE_API_BASE_URL`.

Update the `FRONTEND_URL` app setting on the API container app (and
`frontendUrl` in your params file) to the Static Web App's URL, and add it
to the CORS `allow_origins` list in `backend/app/main.py:66` — right now
that list is hardcoded to localhost origins only.

## 7. CI/CD

`.github/workflows/deploy-backend.yml` rebuilds and redeploys the container
app on every push to `backend/**`. It needs these repo secrets:
`AZURE_CREDENTIALS` (a service principal — `az ad sp create-for-rbac --sdk-auth`
scoped to the resource group), `AZURE_ACR_NAME`, `AZURE_RESOURCE_GROUP`,
`AZURE_API_APP_NAME`.

## Notes on choices baked into `main.bicep`

- **API + worker share one Container App**: gunicorn and the Celery worker
  run as two processes under supervisord in the same container
  (`backend/supervisord.conf`), sized at 0.5 vCPU / 1Gi with `minReplicas: 1`,
  `maxReplicas: 3`. This is a deliberate cost trade-off (see the top of this
  file) — not the default recommendation if the worker needs to scale
  independently of API traffic or if AI/PDF-generation jobs are heavy enough
  to risk starving API request handling.
- **Redis**: Basic C0 tier — fine for Celery broker/result-backend traffic at
  low volume; bump to Standard for HA once this is load-bearing.
- **Postgres**: Burstable `Standard_B1ms` — cheapest tier, resize once you
  know real load.
- **ACR admin credentials** are used for registry auth for simplicity: fine
  to start, but switch the container app to a managed identity + ACR
  `AcrPull` role assignment before this is handling real traffic.
