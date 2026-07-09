# Church Directory

A Streamlit community portal for **Filam** and **Pillar** churches — public pages for celebrations and lookup, plus a staff area with full directory access.

## Features

**Public portal**
- Community overview charts (no contact details)
- First-name-only celebrations calendar
- Privacy-safe community map (heatmap, not household pins)
- Name lookup (name + church only)

**Staff portal** (login required)
- Searchable people directory with table, card, and household views
- Household map with geocoding
- Full calendar including children's birthdays from parent records
- Leadership insights and data quality reporting

## Quick start

```bash
make dev
```

Opens the app at `http://localhost:8501`.

### First-time staff login setup

```bash
python scripts/setup_admin.py
```

Or copy `admin_credentials.sample.toml` to `admin_credentials.toml` and set a bcrypt password hash.

### Using sample data for development

```bash
export CHURCH_CSV_PATH=data/sample_directory.csv
make dev
```

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

1. Sign in as staff
2. Open **Household Map**
3. Click **Geocode all missing** (runs once, cached locally)
4. Public community map heatmap uses the same cache

Church building markers are geocoded automatically on startup.

## Privacy model

| Data | Public | Staff |
|------|--------|-------|
| Name + church | Yes | Yes |
| City (aggregates) | Yes | Yes |
| Phone, email, address | No | Yes |
| Children's data on parent records | No | Yes |
| Exact household map pins | No | Yes |

Public map aggregates households into ~8–10 mile neighborhood cells and caps zoom so street-level homes can't be matched to heat.

## Configuration

| Variable | Default |
|----------|---------|
| `CHURCH_CSV_PATH` | `Filam_Pillar Church Directory - Main.csv` |
| `CHURCH_GEOCODE_CACHE_PATH` | `geocode_cache.json` |

Streamlit secrets (see `.streamlit/secrets.toml.example`):

```toml
[google_sheets]
sheet_id = "your-sheet-id"

[cookie]
key = "your-random-signing-key"
```

## Tests

```bash
make test
```

## Deployment checklist

1. Push code to GitHub — **do not** commit the real CSV, geocode cache, or credentials
2. Connect the repo to [Streamlit Community Cloud](https://streamlit.io/cloud) (or your host)
3. Add secrets: `google_sheets`, `gcp_service_account`, admin `cookie` key
4. Run `python scripts/setup_admin.py` locally and copy the generated `admin_credentials.toml` fields into secrets, or configure credentials separately
5. Share the Google Sheet only with trusted staff + the service account
6. Host behind HTTPS (Streamlit Cloud does this automatically)

## Project layout

```
app.py              Entry point and routing
auth.py             Staff authentication
data_source.py      CSV / Google Sheets loader
helpers.py          Cleaning, geocoding, events, filters
views/
  public_views.py   Public pages
  admin_views.py    Staff pages
  shared.py         CSS, calendar, charts
scripts/
  setup_admin.py    Credential generator
  clean_csv.py      CSV cleanup and audit
data/
  sample_directory.csv
```
