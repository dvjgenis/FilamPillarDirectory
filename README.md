# Church Directory

A Streamlit **admin-only** directory for **Filam** and **Pillar** churches. The full app is behind login — there is no public portal.

## Features

**Staff directory** (login required)

- Searchable people directory with table, card, and household views
- Household map with geocoding
- Full calendar including children's birthdays from parent records
- Leadership insights and data quality reporting

## Login

1. Open the app — you will see the login screen only.
2. Select one of the three authorized church emails and enter the **shared staff password**.
3. Click **Send verification code** — a 6-digit code is emailed **only to that address**.
4. Enter the code to sign in. The session ends when you close the browser or click **Log out**.

### Credentials setup

Copy `admin_credentials.sample.toml` to `admin_credentials.toml` (gitignored), or run:

```bash
python scripts/setup_admin.py
```

Configure:

- **email1–email3** — allowlisted addresses that may sign in
- **password** — shared staff password (plaintext in the local file)
- **smtp.user** — Gmail sender (`dvjgenis@gmail.com` or your church Gmail)
- **smtp.app_password** — [Google App Password](https://myaccount.google.com/apppasswords) (2-Step Verification required)

Legacy layout is also supported: `email1`–`email3` under `[credentials.usernames.filpilchurch]` and `app_password` under `[Gmail App Password]` or `[smtp]`.

## Quick start

```bash
make dev
```

Opens the app at `http://localhost:8501`.

### Using sample data for development

```bash
export CHURCH_CSV_PATH=data/sample_directory.csv
make dev
```

If SMTP is not configured locally, the app shows the OTP on screen in dev mode only (not on Streamlit Cloud).

## Data

The app reads from **local CSV** (default) or **Google Sheets** (recommended for deployment).

- **Production CSV:** `Filam_Pillar Church Directory - Main.csv` (gitignored — contains real PII)
- **Sample CSV:** `data/sample_directory.csv` (safe fake records for dev)
- **Geocode cache:** `geocode_cache.json` (gitignored)

### Google Sheets (live updates — recommended for deployment)

Use a **private Google Sheet** as the source of truth. The app refetches every 5 minutes (configurable) and when staff click **Refresh data**. Member data stays out of GitHub.

#### Sheet format

Row 1 must use the same 15 column headers as the CSV (see `data/sample_directory.csv`). Boolean columns accept `TRUE`/`FALSE`, `Yes`/`No`, etc.

Copy the **Sheet ID** from the URL: `https://docs.google.com/spreadsheets/d/SHEET_ID/edit`

#### Share the sheet

| Who | Permission | Why |
|-----|------------|-----|
| Trusted staff who edit the directory | Editor | Maintain records |
| `filampillardirectory-sa@filampillardirectory.iam.gserviceaccount.com` | **Viewer** | App reads via service account |

#### Local development & secrets

1. Place the service account JSON at `.streamlit/filampillardirectory-cb6db0de17be.json` (gitignored).
2. Enable **Google Sheets API** on the `filampillardirectory` GCP project.
3. Sync secrets from the JSON key:

```bash
make sync-secrets   # writes .streamlit/secrets.toml
make dev-sheets
```

`make dev-sheets` runs `sync-secrets` automatically.

#### Streamlit Cloud deployment

1. Run `make sync-secrets` locally.
2. Copy the entire contents of `.streamlit/secrets.toml` into **Streamlit Cloud → App settings → Secrets**.
3. Reboot the app.

**Environment variables (alternative to secrets):**

| Variable | Purpose |
|----------|---------|
| `CHURCH_DATA_SOURCE` | `csv` or `sheets` (auto-detects sheets if `CHURCH_SHEET_ID` is set) |
| `CHURCH_SHEET_ID` | Google Sheet ID |
| `CHURCH_SHEET_WORKSHEET` | Tab name (optional; defaults to first tab) |
| `CHURCH_SHEET_CACHE_TTL` | Seconds between auto-refresh (default `300`) |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON (optional override) |
| `CHURCH_GCP_SERVICE_ACCOUNT_JSON` | Inline service account JSON string |

### Clean the CSV

Remove blank padding rows and print a data quality report:

```bash
python scripts/clean_csv.py
python scripts/clean_csv.py --dry-run
```

### Geocoding workflow

1. Sign in
2. Open **Household Map**
3. Click **Geocode all missing** (runs once, cached locally)

Church building markers are geocoded automatically on startup.

## Configuration

| Variable | Default |
|----------|---------|
| `CHURCH_CSV_PATH` | `Filam_Pillar Church Directory - Main.csv` |
| `CHURCH_GEOCODE_CACHE_PATH` | `geocode_cache.json` |

Streamlit secrets (see `.streamlit/secrets.toml.example`):

```toml
[auth]
email1 = "..."
email2 = "..."
email3 = "..."
password = "shared-staff-password"

[smtp]
user = "sender@gmail.com"
app_password = "xxxx xxxx xxxx xxxx"
```

## Tests

```bash
make test
```

## Deployment checklist

1. Push code to GitHub — **do not** commit the real CSV, geocode cache, or credentials
2. Connect the repo to [Streamlit Community Cloud](https://streamlit.io/cloud) (or your host)
3. Run `make sync-secrets` locally and paste the full generated `.streamlit/secrets.toml` into Streamlit Cloud → App settings → Secrets (includes `google_sheets`, `gcp_service_account`, `[auth]`, and `[smtp]`)
4. Bootstrap geocoding for Cloud (optional but recommended):
   - `make pregeocode` — builds `geocode_cache.json` locally
   - `make pregeocode-secrets` — prints a `[geocode_cache]` block to paste into secrets so maps work immediately after deploy
5. Share the Google Sheet only with trusted staff + the service account
6. Host behind HTTPS (Streamlit Cloud does this automatically)

**Note:** Without a secrets geocode cache, the first visit to a Map page geocodes missing addresses (~1 sec each) with a visible progress bar. Other pages load immediately.

## Project layout

```
app.py              Entry point (login gate + admin routing)
auth.py             Email + password + OTP authentication
data_source.py      CSV / Google Sheets loader
helpers.py          Cleaning, geocoding, events, filters
views/
  admin_views.py    Staff pages
  shared.py         CSS, calendar, charts
scripts/
  setup_admin.py    Credential generator
  pregeocode.py     Build geocode cache for local dev or Streamlit secrets
  clean_csv.py      CSV cleanup and audit
data/
  sample_directory.csv
```
