# REMINDNET Monitoring Tool

Streamlit web app scaffold for creating Landsat RGB timelapses with Google Earth
Engine and geemap.

The app is based on the existing Google Colab prototype, but the Colab-specific
authentication, widgets, and notebook output are replaced with Streamlit UI
controls, a web map drawing workflow, and reusable Python modules.

## Project structure

```text
app.py              Streamlit user interface
gee_utils.py        Earth Engine setup and ROI/map helpers
timelapse.py        Landsat timelapse options and GIF generation
requirements.txt    Python dependencies
.env.example        Environment variable template
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

For local development, authenticate Earth Engine once:

```bash
earthengine authenticate
```

Then set your Earth Engine project in `.env`:

```text
GEE_PROJECT_ID=your-earth-engine-project-id
```

Run the app:

```bash
streamlit run app.py
```

## Credentials

Do not commit real credentials. The current code supports local Earth Engine
authentication and is prepared for future service account configuration through:

- `GEE_PROJECT_ID`
- `GEE_SERVICE_ACCOUNT_EMAIL`
- `GEE_SERVICE_ACCOUNT_KEY_PATH`
- `GEE_SERVICE_ACCOUNT_KEY_JSON`

Use `.env.example` as the template and keep any real `.env` or key files out of
version control.

## Current workflow

1. Draw a polygon or rectangle ROI on the map.
2. Choose year/month range, RGB band combination, cloud masking, GIF size, and
   label styling.
3. Click **Create timelapse**.
4. Preview and download the generated GIF from the Streamlit page.

Generated GIFs are written to the local `outputs/` folder.

## Opening a Mine Location from Web GIS

The app accepts mine coordinates from URL parameters. A Web GIS popup can link
directly to a mine like this:

```text
http://localhost:8501/?lat=41.559&lon=21.009&mine=Oslomej&zoom=14
```

Supported parameters:

- `lat` or `latitude`
- `lon`, `lng`, or `longitude`
- `mine` or `mine_name`
- `zoom`

For the online version, replace `http://localhost:8501/` with the deployed app
URL, for example:

```text
https://monitoring.remindnet.eu/?lat=41.559&lon=21.009&mine=Oslomej&zoom=14
```

## Free-first deployment approach

To keep the online version practical without extra hosting charges:

- Use noncommercial Google Earth Engine access for REMINDNET research/education
  use.
- Deploy first to a free Streamlit-compatible host, such as Streamlit Community
  Cloud, if its resource limits are sufficient.
- Embed the deployed app in WordPress with an iframe or link.
- Use server-side Earth Engine credentials so visitors do not need to log in.
- Keep usage guardrails enabled for public access.

The app currently enforces conservative defaults:

```text
MAX_ROI_AREA_KM2=2500
GIF widths: 512 or 768 px
```

These limits reduce accidental high-compute requests. They do not replace Google
Cloud billing controls, so keep the Earth Engine project registered for the
correct noncommercial use case and avoid attaching paid services unless needed.
