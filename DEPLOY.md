# Meridian — Deployment Walkthrough

**Repository:** [https://github.com/RichardCByrne/meridian-financial-planning](https://github.com/RichardCByrne/meridian-financial-planning)

End-to-end, copy-pasteable steps to take Meridian from a local checkout to a live deployment:

- **Backend** (FastAPI + Alembic) → Cloud Run, image stored in Artifact Registry, built by Cloud Build.
- **Database** → **Neon** (managed serverless Postgres, free tier, autosuspends on idle). Cloud SQL remains a viable alternative — see Appendix A.
- **Secrets** → Secret Manager (`DATABASE_URL`, `FIREBASE_SERVICE_ACCOUNT_JSON`, `ALLOWED_ORIGINS`).
- **Frontend** (Vite static build) → Firebase Hosting.
- **Auth** → Firebase Authentication (Google + Email/Password).

> **Why Neon over Cloud SQL.** Neon's free tier covers Meridian's projected scale indefinitely (0.5 GB storage, autosuspend) versus ~€8/month for the cheapest Cloud SQL instance. Zero code change either way — both speak Postgres and the existing `psycopg` driver works. Trade-offs: Neon adds a ~1-3 s cold-start lag on the first request after the database has been idle, and the DB now sits outside GCP (network egress, separate vendor). For a personal-scale deployment that's the right call. If you later need always-on low-latency reads or analytical workloads, follow Appendix A to switch to Cloud SQL — only the `DATABASE_URL` secret and one `cloudbuild.yaml` flag change.

Follow the sections in order on a first-time setup. Skip ahead to **§9 Redeploys** for routine updates.

---

## 0. Prerequisites

Install once on your local machine:


| Tool                                                             | Install                                                                                            | Verify                |
| ---------------------------------------------------------------- | -------------------------------------------------------------------------------------------------- | --------------------- |
| `gcloud` SDK                                                     | [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)             | `gcloud --version`    |
| `firebase` CLI                                                   | `npm install -g firebase-tools`                                                                    | `firebase --version`  |
| Docker (optional, only if you want `make build-backend` locally) | [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/) | `docker --version`    |
| Node 18.x + npm                                                  | [https://nodejs.org/](https://nodejs.org/) or `fnm install 18`                                     | `node -v` → `v18.x.x` |
| Python 3.11+                                                     | [https://www.python.org/downloads/](https://www.python.org/downloads/)                             | `python --version`    |


Authenticate the CLIs (one-time, opens a browser):

```powershell
gcloud auth login
gcloud auth application-default login
firebase login
```

You also need:

- **A GCP billing account** for Cloud Run + Artifact Registry + Secret Manager. All three have generous free tiers; Cloud Run idles at €0 with `--min-instances=0`.
- **A Neon account** (free) — sign up at [https://neon.tech](https://neon.tech) with the same Google account for simplicity. No credit card required on the free tier.

---

## 1. Choose names and write them down

Pick these values up front and substitute them throughout the rest of the guide. Pick once and don't change later — re-running with different names creates orphan resources.


| Variable          | Example                         | What it is                                                                 |
| ----------------- | ------------------------------- | -------------------------------------------------------------------------- |
| `PROJECT_ID`      | `meridian-financial-planner`    | GCP / Firebase project id (must be globally unique)                        |
| `REGION`          | `europe-west1`                  | Cloud Run region                                                           |
| `REPO`            | `meridian`                      | Artifact Registry repo name                                                |
| `SERVICE`         | `meridian-api`                  | Cloud Run service name                                                     |
| `NEON_PROJECT`    | `meridian`                      | Neon project name (display only)                                           |
| `NEON_REGION`     | `aws-eu-west-1`                 | Neon region — pick the closest to `REGION` to minimise cross-cloud latency |
| `FRONTEND_ORIGIN` | `https://meridian-prod.web.app` | Final hosting URL (Firebase auto-issues `<project>.web.app`)               |


You will also generate a **Neon connection string** in §4 — looks like `postgresql://USER:PASSWORD@ep-xxxx.aws-eu-west-1.aws.neon.tech/meridian?sslmode=require`. Keep it in a password manager.

> **PowerShell tip.** Export these as session variables so the rest of the commands paste cleanly:
>
> ```powershell
> $PROJECT_ID       = "meridian-financial-planner"
> $REGION           = "europe-west1"
> $REPO             = "meridian"
> $SERVICE          = "meridian-api"
> $FRONTEND_ORIGIN  = "https://meridian-financial-planner.web.app"
> # Filled in after §4:
> $NEON_URL         = "postgresql://USER:PASS@ep-xxxx.aws-eu-west-1.aws.neon.tech/meridian?sslmode=require"
> ```

---

## 2. Create the Firebase + GCP project

A Firebase project is a GCP project with Firebase services enabled. Creating it via the Firebase console keeps both in sync.

1. Go to [https://console.firebase.google.com](https://console.firebase.google.com) → **Add project**.
2. Project name → `meridian-financial-planner` (or whatever you chose). Project id → confirm it matches `$PROJECT_ID`.
3. Disable Google Analytics (not needed). Click **Create project**.
4. Link the Firebase project to a **billing account** (Project settings → Usage and billing → Modify plan → **Blaze**). Required for Cloud Run / Cloud SQL.
5. Verify on the CLI:
  ```powershell
   gcloud projects describe $PROJECT_ID
   gcloud config set project $PROJECT_ID
  ```

Enable the APIs the rest of the guide depends on:

```powershell
gcloud services enable `
  run.googleapis.com `
  cloudbuild.googleapis.com `
  artifactregistry.googleapis.com `
  secretmanager.googleapis.com `
  iam.googleapis.com `
  firebase.googleapis.com
```

> `sqladmin.googleapis.com` is **not** enabled on the Neon path. Re-enable it only if you switch to Cloud SQL via Appendix A.

---

## 3. Configure Firebase Authentication

1. Firebase console → **Build → Authentication → Get started**.
2. **Sign-in method** tab → enable:
  - **Google** (set support email to your address).
  - **Email/Password**.
3. **Settings → Authorized domains** → ensure `<project>.web.app` and `<project>.firebaseapp.com` are present (added automatically). Add any custom domain you intend to use.
4. **Project settings (gear icon) → Service accounts** → **Generate new private key** → download the JSON file (e.g. `meridian-firebase-admin.json`). **Treat this like a password** — store it outside the repo and never commit it.
5. **Project settings → General → Your apps → Add app → Web (`</>`)**. Register the app (no Hosting checkbox here — we set Hosting up separately). After registration Firebase shows a config object:
  ```js
   const firebaseConfig = {
     apiKey: "AIza…",
     authDomain: "meridian-prod.firebaseapp.com",
     projectId: "meridian-financial-planner",
     appId: "1:1234:web:abcdef",
     // …
   };
  ```
   Copy these four values — you need them for the frontend `.env.production` in §7.

---

## 4. Provision Neon (Postgres)

1. Sign in at [https://console.neon.tech](https://console.neon.tech) with the Google account you want to own the project.
2. **Create project**:
  - Name: `meridian` (matches `$NEON_PROJECT`).
  - Postgres version: **15** (matches the Cloud SQL alternative for parity).
  - Cloud / region: **AWS → `eu-west-1`** (Dublin) — closest to `europe-west1` (St. Ghislain). Cross-cloud round-trip is ~10-20 ms, dominated by Neon's compute cold-start when autosuspended.
  - Database name: `meridian`.
3. After creation, Neon shows a **connection string** — copy the **pooled** variant (host contains `-pooler`). Cloud Run scales to many short-lived workers; the pooler endpoint avoids exhausting Postgres connections during traffic bursts. Format:
  ```
   postgresql://USER:PASSWORD@ep-xxxx-pooler.aws-eu-west-1.aws.neon.tech/meridian?sslmode=require
  ```
4. Convert to SQLAlchemy / `psycopg` form (the only edit is the driver prefix):
  ```powershell
   $NEON_URL = "postgresql+psycopg://USER:PASSWORD@ep-xxxx-pooler.aws-eu-west-1.aws.neon.tech/meridian?sslmode=require"
  ```
   The `+psycopg` selector tells SQLAlchemy to use `psycopg` (v3, already pinned in `pyproject.toml`) rather than the legacy `psycopg2` driver.
5. **Autosuspend.** Neon's free-tier compute suspends after 5 minutes of inactivity. The first request after suspension waits ~1-3 s while the compute spins back up — visible only on cold cache. No action needed; this is the trade-off for the free tier.
6. **Backups.** Free tier gets 7 days of point-in-time recovery automatically — no scheduling required.

> **No IP allowlist.** Neon accepts connections from anywhere over TLS. Authentication is purely via the username/password in the connection string. Keep `$NEON_URL` secret — anyone with it can read/write the DB.

> **Smoke-test the connection** from your local machine before wiring it into Cloud Run:
>
> ```powershell
> .\backend\.venv\Scripts\python -c "import psycopg; psycopg.connect('postgresql://USER:PASS@ep-xxxx-pooler.aws-eu-west-1.aws.neon.tech/meridian?sslmode=require').close(); print('ok')"
> ```
>
> If you see `ok`, the credentials and TLS chain work.

---

## 5. Create the Artifact Registry repo and Secret Manager entries

### 5a. Artifact Registry

```powershell
gcloud artifacts repositories create $REPO `
  --repository-format=docker `
  --location=$REGION `
  --description="Meridian Docker images"
```

### 5b. Secret Manager — three secrets

The `cloudbuild.yaml` deploy step expects exactly these names. The Cloud Run revision pulls them at startup, so changing a secret value redeploys (a no-op revision is enough to pick up the new value).

```powershell
# 1. DATABASE_URL — the Neon pooled connection string from §4 step 4.
$NEON_URL | gcloud secrets create DATABASE_URL --data-file=-

# 2. FIREBASE_SERVICE_ACCOUNT_JSON — full JSON from §3 step 4.
gcloud secrets create FIREBASE_SERVICE_ACCOUNT_JSON `
  --data-file="C:\path\to\meridian-firebase-admin.json"

# 3. ALLOWED_ORIGINS — comma-separated CORS allowlist.
"$FRONTEND_ORIGIN" | gcloud secrets create ALLOWED_ORIGINS --data-file=-
```

### 5c. Grant the Cloud Run runtime service account read access

Cloud Run defaults to using the **Compute Engine default service account** (`PROJECT_NUMBER-compute@developer.gserviceaccount.com`). Each secret needs `roles/secretmanager.secretAccessor`:

```powershell
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$RUNTIME_SA = "$PROJECT_NUMBER-compute@developer.gserviceaccount.com"

foreach ($s in @("DATABASE_URL", "FIREBASE_SERVICE_ACCOUNT_JSON", "ALLOWED_ORIGINS")) {
  gcloud secrets add-iam-policy-binding $s `
    --member="serviceAccount:$RUNTIME_SA" `
    --role="roles/secretmanager.secretAccessor"
}
```

> **No `roles/cloudsql.client` grant needed** — Neon is reached as a plain Postgres TCP host over TLS, not via the Cloud SQL Auth Proxy. If you later switch to Cloud SQL (Appendix A), add that role then.

The **Cloud Build** service account (`$PROJECT_NUMBER@cloudbuild.gserviceaccount.com`) needs deploy permissions:

```powershell
$CB_SA = "$PROJECT_NUMBER@cloudbuild.gserviceaccount.com"
foreach ($r in @("roles/run.admin", "roles/iam.serviceAccountUser", "roles/artifactregistry.writer")) {
  gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$CB_SA" --role=$r
}
```

---

## 6. Deploy the backend

The pipeline is described in `cloudbuild.yaml`: a Kaniko build-and-push (with Artifact Registry layer caching) → `gcloud run deploy` with secrets mounted. Kaniko caches every image layer — including the multi-stage pip-install layer, keyed only on `pyproject.toml` — in a `<image>/cache` repo, so an app-code-only deploy reuses the cached dependencies and skips `pip install` entirely. The first build after this change is cold (it populates the cache); subsequent app-only deploys are markedly faster. The committed file is already wired for Neon (no `--add-cloudsql-instances` flag). If you later switch to Cloud SQL, see Appendix A for the one-line restore.

Run the build:

```powershell
gcloud builds submit --config cloudbuild.yaml `
  --substitutions "_REGION=$REGION,_REPO=$REPO,_SERVICE=$SERVICE"
```

What happens, in order:

1. Docker image built from `backend/Dockerfile` (multi-stage; runtime layer has no pip cache).
2. Image pushed to `${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPO}/${SERVICE}` with two tags (`$BUILD_ID` and `latest`). `BUILD_ID` is auto-populated by Cloud Build for both manual `gcloud builds submit` and trigger-based builds; `SHORT_SHA` only populates for triggers connected to a git repo.
3. Cloud Run service deployed/updated with:
  - `--set-env-vars=MERIDIAN_DEV_AUTH=false,FIREBASE_SERVICE_ACCOUNT_PATH=/secrets/firebase.json`.
  - `--set-secrets=DATABASE_URL=…,ALLOWED_ORIGINS=…,/secrets/firebase.json=FIREBASE_SERVICE_ACCOUNT_JSON:latest`.
4. The container's entrypoint runs `alembic upgrade head` **before** starting uvicorn — a deploy never serves traffic against a half-migrated DB. The first migration run on a fresh Neon DB creates the full schema.

When the build finishes, grab the service URL:

```powershell
$API_URL = gcloud run services describe $SERVICE --region=$REGION --format="value(status.url)"
$API_URL
# https://meridian-api-XXXX-ew.a.run.app
```

Smoke-test:

```powershell
curl "$API_URL/api/health"
# {"status":"ok","db":"ok"}
```

If `db` reports anything other than `ok`, jump to §10 Troubleshooting.

---

## 7. Build and deploy the frontend

### 7a. Point `.firebaserc` at your project

The committed `.firebaserc` already targets `meridian-financial-planner`. If you fork the repo and use a different `$PROJECT_ID`, update it:

```powershell
firebase use --add $PROJECT_ID
```

Or edit `.firebaserc` directly:

```json
{
  "projects": {
    "default": "$PROJECT_ID"
  }
}
```

### 7b. Write `frontend/.env.production`

```powershell
@"
VITE_DEV_AUTH=false
VITE_API_URL=$API_URL/api
VITE_FIREBASE_API_KEY=AIza…
VITE_FIREBASE_AUTH_DOMAIN=$PROJECT_ID.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=$PROJECT_ID
VITE_FIREBASE_APP_ID=1:1234:web:abcdef
"@ | Out-File -Encoding utf8 frontend\.env.production
```

Fill in the four `VITE_FIREBASE_*` values from §3 step 5. The file is gitignored.

### 7c. Build and deploy

```powershell
cd frontend
npm install            # only if you haven't yet
npm run build          # tsc -b && vite build → frontend/dist
firebase deploy --only hosting
cd ..
```

The CLI prints the **Hosting URL** when it finishes — that's your live frontend (`https://$PROJECT_ID.web.app`). It should match `$FRONTEND_ORIGIN` from §1; if it doesn't, update the `ALLOWED_ORIGINS` secret (see §9) and redeploy the backend.

---

## 8. Verify end-to-end

1. Open the Hosting URL in a private window.
2. Sign in with Google. You should land on `/plans` with the chip in the sidebar showing your real name + email.
3. Create a plan ("Murphy household", base year 2026, 30 years). Add a person and an income source. Switch to **Let's See** — projection should render with the deterministic line.
4. In the Cloud Run logs (Cloud Console → Cloud Run → `$SERVICE` → Logs), look for:
  - `Phase 8 migration: assigned 0 orphan plan(s)` on first start.
  - `alembic upgrade head` finishing without errors before uvicorn boots.
  - No `MERIDIAN_DEV_AUTH` warnings.

API smoke checks from your terminal:

```powershell
curl "$API_URL/api/health"             # {"status":"ok","db":"ok"}
curl "$API_URL/docs"                   # OpenAPI UI loads
```

---

## 9. Redeploys

Once the one-time setup is done, day-to-day deploys are short.

**Backend (code change):**

```powershell
gcloud builds submit --config cloudbuild.yaml `
  --substitutions "_REGION=$REGION,_REPO=$REPO,_SERVICE=$SERVICE"
```

**Frontend (code change):**

```powershell
cd frontend; npm run build; firebase deploy --only hosting; cd ..
```

**Updating a secret** (e.g. rotating the DB password or changing allowed origins):

```powershell
# 1. Add a new version of the secret.
"new value" | gcloud secrets versions add DATABASE_URL --data-file=-

# 2. Force a new Cloud Run revision so it picks up the new version.
gcloud run services update $SERVICE --region=$REGION --update-env-vars=ROTATE=$(Get-Date -Format o)
```

**New Alembic migration:**

1. Commit the migration under `backend/alembic/versions/`.
2. Redeploy backend (above). The container runs `alembic upgrade head` before serving — no separate migration step.

**Rollback to the previous revision:**

```powershell
gcloud run revisions list --service=$SERVICE --region=$REGION
gcloud run services update-traffic $SERVICE --region=$REGION --to-revisions=<PREVIOUS-REVISION>=100
```

---

## 10. Troubleshooting


| Symptom                                                                 | Likely cause                                                       | Fix                                                                                                                                                                                                                           |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `curl /api/health` returns `{"db":"error"}` or `503`                    | Wrong `DATABASE_URL` shape, expired Neon password, or DB suspended | (1) Confirm secret uses `postgresql+psycopg://…` prefix and ends in `?sslmode=require`. (2) Re-test connection locally with the smoke-test command in §4. (3) Wait 5 s and retry — autosuspended compute may still be waking. |
| First request after idle period takes 1-3 s                             | Neon free-tier autosuspend cold-start                              | Expected behaviour. Either accept it, upgrade to Neon's paid tier (no autosuspend), or hit `/api/health` from a scheduled job every 4 minutes to keep the compute warm.                                                       |
| `psycopg.OperationalError: SSL connection has been closed unexpectedly` | Connection picked from pool after Neon idle-suspended the compute  | Already mitigated by `pool_pre_ping=True` in `app/db.py:51`. If still seen, set `pool_recycle=300` on the engine to drop connections older than 5 minutes.                                                                    |
| Cloud Build fails at `deploy` step with `permission denied`             | Cloud Build SA missing roles                                       | Re-run the `roles/run.admin` / `roles/iam.serviceAccountUser` / `roles/artifactregistry.writer` bindings in §5c.                                                                                                              |
| Frontend loads but login throws `auth/unauthorized-domain`              | Firebase Auth doesn't recognise the origin                         | Firebase console → Auth → Settings → Authorized domains → add the Hosting URL / custom domain.                                                                                                                                |
| Frontend loads but API calls fail with CORS error                       | `ALLOWED_ORIGINS` doesn't include the Hosting URL                  | Update the `ALLOWED_ORIGINS` secret (§9) and force a new revision.                                                                                                                                                            |
| Cloud Run logs show `firebase_admin… could not be loaded`               | `FIREBASE_SERVICE_ACCOUNT_JSON` malformed or missing               | Re-upload via `gcloud secrets versions add FIREBASE_SERVICE_ACCOUNT_JSON --data-file=…` with the original downloaded JSON.                                                                                                    |
| `alembic upgrade head` fails on first deploy                            | Pre-existing schema drift or stale `alembic_version`               | Open the Neon SQL console (Neon dashboard → SQL Editor) and run `SELECT * FROM alembic_version;` — if empty on a fresh DB, drop the row and redeploy.                                                                         |
| Cloud Run image deployed but old code still served                      | Service pinned to old revision                                     | `gcloud run services update-traffic $SERVICE --region=$REGION --to-latest`.                                                                                                                                                   |
| Neon free-tier compute-hour limit hit                                   | Excess traffic for a free project                                  | Neon dashboard → upgrade to paid (no monthly cap) or wait until next billing cycle. Free tier covers ~191 hours/month of compute time — autosuspend keeps usage well under this for personal scale.                           |


---

## 11. Optional next steps

- **Custom domain.** Firebase Hosting → Add custom domain. Add the domain to Firebase Auth → Authorized domains and to the `ALLOWED_ORIGINS` secret. No backend change required — Cloud Run keeps its `.run.app` URL.
- **Cloud Build trigger on push.** Cloud Console → Cloud Build → Triggers → connect the GitHub repo and point a trigger at `cloudbuild.yaml`. Pass the same `_REGION` / `_REPO` / `_SERVICE` substitutions.
- **Separate staging project.** Repeat §2–§7 with a `meridian-staging` project + a separate Neon project (free tier allows multiple). Same code, two `.firebaserc` aliases (`firebase use --add` for both).
- **Backups.** Neon free tier ships 7 days of point-in-time recovery automatically — no scheduling required. Add a calendar reminder to test a restore once per quarter (Neon dashboard → Branches → "Restore" creates a new branch at a chosen timestamp).

---

## 12. CI/CD via GitHub Actions

`.github/workflows/deploy.yml` ships both sides on every successful `Tests + audits` run on `main`, with a manual `workflow_dispatch` button (target = `both` | `backend` | `frontend`) for re-deploys.

Auth uses **Workload Identity Federation** — no JSON keys in GitHub Secrets.

### 12.1. One-time GCP setup

```powershell
$PROJECT_ID     = "meridian-financial-planner"
$PROJECT_NUMBER = gcloud projects describe $PROJECT_ID --format="value(projectNumber)"
$REPO           = "RichardCByrne/meridian-financial-planning"
$SA             = "gh-actions-deploy@$PROJECT_ID.iam.gserviceaccount.com"

# 1. Service account
gcloud iam service-accounts create gh-actions-deploy --display-name="GitHub Actions deploy"

# 2. Roles (least-privilege for Cloud Build + Cloud Run + Firebase Hosting)
foreach ($role in @(
  "roles/run.admin",
  "roles/cloudbuild.builds.editor",
  "roles/iam.serviceAccountUser",
  "roles/storage.admin",
  "roles/artifactregistry.writer",
  "roles/firebasehosting.admin",
  "roles/firebase.viewer"
)) {
  gcloud projects add-iam-policy-binding $PROJECT_ID --member="serviceAccount:$SA" --role=$role
}

# 3. Workload Identity Pool + Provider
gcloud iam workload-identity-pools create github-pool --location=global --display-name="GitHub Actions"
gcloud iam workload-identity-pools providers create-oidc github-provider `
  --location=global --workload-identity-pool=github-pool `
  --display-name="GitHub OIDC" `
  --attribute-mapping="google.subject=assertion.sub,attribute.repository=assertion.repository,attribute.ref=assertion.ref" `
  --attribute-condition="assertion.repository == '$REPO'" `
  --issuer-uri="https://token.actions.githubusercontent.com"

# 4. Bind GH repo → SA impersonation
$POOL = "projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool"
gcloud iam service-accounts add-iam-policy-binding $SA `
  --role=roles/iam.workloadIdentityUser `
  --member="principalSet://iam.googleapis.com/$POOL/attribute.repository/$REPO"

# 5. Print the values to paste into GitHub
"WIF_PROVIDER = projects/$PROJECT_NUMBER/locations/global/workloadIdentityPools/github-pool/providers/github-provider"
"WIF_SERVICE_ACCOUNT = $SA"
```

### 12.2. GitHub configuration

Repo → **Settings → Secrets and variables → Actions**.

**Secrets** (sensitive):

| Name                  | Value                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------- |
| `WIF_PROVIDER`        | The full `projects/.../providers/github-provider` string from §12.1 step 5                         |
| `WIF_SERVICE_ACCOUNT` | `gh-actions-deploy@meridian-financial-planner.iam.gserviceaccount.com`                             |

**Variables** (build-time, public — `VITE_*` end up in the JS bundle):

| Name                          | Value                                                                |
| ----------------------------- | -------------------------------------------------------------------- |
| `GCP_PROJECT_ID`              | `meridian-financial-planner`                                         |
| `VITE_API_URL`                | `https://meridian-api-XXXX-ew.a.run.app/api` (your Cloud Run URL)    |
| `VITE_FIREBASE_API_KEY`       | from Firebase console → Project settings → Web app config            |
| `VITE_FIREBASE_AUTH_DOMAIN`   | `meridian-financial-planner.firebaseapp.com`                         |
| `VITE_FIREBASE_PROJECT_ID`    | `meridian-financial-planner`                                         |
| `VITE_FIREBASE_APP_ID`        | from Firebase console → Project settings → Web app config            |

### 12.3. Trigger model

- **Auto**: push to `main` → `Tests + audits` runs → on success, `Deploy` fires both jobs in parallel.
- **Manual**: Actions tab → Deploy → Run workflow → pick `target`.
- **Negative**: failed tests do not deploy (gate job's `if:` requires `workflow_run.conclusion == 'success'`).

### 12.4. Verifying

After §12.1 + §12.2:

1. Actions tab → Deploy → Run workflow → target=`backend`. Expect a green run + new Cloud Run revision in `gcloud run revisions list`.
2. Same for target=`frontend`. Expect a green run + new bundle hash on `https://meridian-financial-planner.web.app`.
3. Push a no-op commit to `main`. Watch `Tests + audits` → `Deploy` chain in the Actions UI.

---

## Appendix A. Cloud SQL as an alternative to Neon

If you later need always-on low-latency reads, larger storage, or VPC-only networking, swap Neon for Cloud SQL. Only three things change.

### A.1. Provision Cloud SQL

```powershell
gcloud services enable sqladmin.googleapis.com

$SQL_INSTANCE = "meridian-db"
$SQL_DB       = "meridian"
$SQL_USER     = "meridian"
$SQL_PASSWORD = "REPLACE-ME-WITH-STRONG-PASSWORD"

gcloud sql instances create $SQL_INSTANCE `
  --database-version=POSTGRES_15 `
  --tier=db-f1-micro `
  --region=$REGION `
  --storage-size=10GB --storage-type=SSD `
  --backup --backup-start-time=02:00

gcloud sql users set-password postgres --instance=$SQL_INSTANCE --password=$SQL_PASSWORD
gcloud sql users create $SQL_USER --instance=$SQL_INSTANCE --password=$SQL_PASSWORD
gcloud sql databases create $SQL_DB --instance=$SQL_INSTANCE

$SQL_CONN = "$PROJECT_ID`:$REGION`:$SQL_INSTANCE"
```

Cost: ~€8/month (`db-f1-micro`). Bump to `db-g1-small` for real traffic.

### A.2. Swap the `DATABASE_URL` secret

```powershell
$DB_URL = "postgresql+psycopg://$SQL_USER`:$SQL_PASSWORD@/$SQL_DB`?host=/cloudsql/$SQL_CONN"
$DB_URL | gcloud secrets versions add DATABASE_URL --data-file=-
```

Note the `host=/cloudsql/<conn-name>` form — Cloud Run reaches the instance over a Unix socket via the Cloud SQL Auth Proxy.

### A.3. Grant Cloud SQL Client + re-add the cloudbuild flag

```powershell
gcloud projects add-iam-policy-binding $PROJECT_ID `
  --member="serviceAccount:$RUNTIME_SA" `
  --role="roles/cloudsql.client"
```

In `cloudbuild.yaml`, restore the deploy-step flag:

```yaml
- --add-cloudsql-instances=${_CLOUD_SQL_INSTANCE}
```

And include the substitution on the submit call:

```powershell
gcloud builds submit --config cloudbuild.yaml `
  --substitutions "_REGION=$REGION,_REPO=$REPO,_SERVICE=$SERVICE,_CLOUD_SQL_INSTANCE=$SQL_CONN"
```

### A.4. Decommission Neon (optional)

Once Cloud SQL serves traffic and you're confident, delete the Neon project from its dashboard. There's no GCP-side cleanup.

---

## Appendix B. Supply-chain policy

Meridian pulls from `registry.npmjs.org` and `pypi.org`. The threat model is registry-side compromise: a maintainer account hijack, a typosquat, or a malicious release of a dep you already trust. The controls below limit the blast radius.

### B.1. Direct deps are pinned exactly

- `frontend/package.json` — no `^`/`~` on direct deps. Every entry is an exact version.
- `backend/pyproject.toml` — every direct dep uses `==`, not `>=`.

Why: with `^1.2.3`, a fresh `npm install` (or `pip install` without a lockfile) can pull `1.99.0` published 30 seconds before the install ran. Exact pins make every install reproducible and force compromised releases to wait for an explicit human PR.

Transitive deps are still resolved by the lockfile (`package-lock.json` SRI hashes; Python's resolver picks the latest matching). The lockfile is the second line of defence — CI runs `npm ci` (fails on drift) and `pip install` uses pinned direct deps.

### B.2. Dependabot is grouped and weekly

`.github/dependabot.yml` opens one PR per ecosystem per week, grouped:

- **patches** — auto-mergeable after CI passes; review-only for the changelog
- **minors** — review carefully, especially for `firebase`, `recharts`, `vite`
- **majors** — manual, never grouped, expect codemods

Four ecosystems are watched: `npm` (frontend), `pip` (backend), `github-actions` (CI workflows), `docker` (backend image base).

### B.3. CI auditing

- `npm audit --omit=dev` — already in `.github/workflows/test.yml`
- `pip-audit` — already in the same workflow
- Add **Socket** or **Snyk** if you want faster signal on newly-compromised packages (they flag in minutes; `npm audit` waits for an NVD CVE).

### B.4. Upgrade workflow

1. Bump the pin in `package.json` or `pyproject.toml`.
2. Run the language's install (`npm install` regenerates lockfile; `pip install -e .[dev]` updates the venv).
3. Run the full test suite: `pytest` (backend) and `npm run lint && npm run build` (frontend).
4. Run `pip-audit` / `npm audit` — fail the PR if a new high-severity finding appears.
5. PR with the pin diff + lockfile diff. Squash-merge.

### B.5. Release-age cooldown

`frontend/.npmrc` sets `min-release-age=7`, refusing any package version published less than 7 days ago. Rationale: most compromised npm releases (e.g. Shai-Hulud, axios) are flagged and unpublished within a week, so a one-week cooldown automatically blocks freshly-uploaded malicious versions without slowing down considered upgrades.

- Requires npm `>=11.10.0`. CI installs latest npm via `npm install -g npm@latest` before `npm ci` because Node 22 LTS still bundles npm 10.9.x. Local dev: fnm `lts-latest` (Node 24+) bundles npm 11.
- Exceptions go in `.npmrc` as `min-release-age-exclude=<glob>` if a legitimate same-week patch is needed.
- pip has no config-level equivalent yet. pip 26 added `--uploaded-prior-to` but it only accepts absolute timestamps, not a relative duration. The `==` pin + manual upgrade workflow in §B.4 fills the same role: a fresh malicious upload can't enter without an explicit human pin bump in a PR.

### B.6. Things deliberately not done

- **No `--ignore-scripts`** as a global default. Some deps need their postinstall (e.g. native binaries for `@vitejs/plugin-react`'s esbuild). The trade-off lives in the lockfile audit; switching to a global `ignore-scripts=true` would silently break the dev workflow.
- **No package-manager swap (yarn/pnpm/bun).** The registry is the supply chain, not the install client; all three managers fetch from the same place and run the same lifecycle hooks. Bun specifically gains perf, not security.
- **No private npm/pypi mirror.** Setting one up is real ops work and only meaningful if combined with an allow-list curated by hand. Not justified for a one-engineer project; revisit if Meridian ever takes on a second maintainer.
