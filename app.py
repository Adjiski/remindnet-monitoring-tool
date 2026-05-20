from __future__ import annotations

from pathlib import Path
import os

import streamlit as st
from dotenv import load_dotenv
from streamlit_folium import st_folium

from gee_utils import (
    DEFAULT_CENTER,
    DEFAULT_ZOOM,
    build_draw_map,
    drawn_feature_to_ee_geometry,
    estimate_geojson_area_km2,
    initialize_earth_engine,
)
from timelapse import BAND_COMBINATIONS, TimelapseOptions, generate_landsat_timelapse


st.set_page_config(
    page_title="REMINDNET Monitoring Tool",
    layout="wide",
)

load_dotenv(override=True)

MAX_ROI_AREA_KM2 = float(os.getenv("MAX_ROI_AREA_KM2", "2500"))
GIF_WIDTH_OPTIONS = [512, 768]
DEFAULT_YEAR_RANGE = (1984, 2020)


def _query_value(name: str) -> str | None:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def _query_float(*names: str, default: float) -> float:
    for name in names:
        value = _query_value(name)
        if value not in (None, ""):
            try:
                return float(value)
            except ValueError:
                pass
    return default


def _query_int(name: str, default: int) -> int:
    value = _query_value(name)
    if value in (None, ""):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _query_text(name: str, default: str = "") -> str:
    value = _query_value(name)
    return value if value is not None else default


def _get_drawn_feature(map_state: dict) -> dict | None:
    """Return the latest geometry drawn with the Folium draw control."""
    if not map_state:
        return None

    latest = map_state.get("last_active_drawing")
    if latest:
        return latest

    drawings = map_state.get("all_drawings") or []
    if drawings:
        return drawings[-1]

    return None


def _render_credentials_help(error: Exception) -> None:
    with st.expander("Earth Engine configuration help", expanded=True):
        st.warning(
            "Google Earth Engine is not initialized yet. Configure credentials before "
            "creating timelapses."
        )
        st.code(str(error), language="text")
        st.markdown(
            """
            For local development, run `earthengine authenticate` once, then set
            `GEE_PROJECT_ID` in `.env`.

            For deployment, configure a service account later with environment
            variables such as `GEE_SERVICE_ACCOUNT_EMAIL` and
            `GEE_SERVICE_ACCOUNT_KEY_PATH`. Do not commit credential files.
            """
        )


st.title("REMINDNET Monitoring Tool")
st.caption("Landsat RGB composites and timelapse generation with Google Earth Engine")

try:
    initialize_earth_engine()
    gee_ready = True
except Exception as exc:  # noqa: BLE001 - show actionable auth state in the UI.
    gee_ready = False
    gee_error = exc
else:
    gee_error = None

if not gee_ready and gee_error is not None:
    _render_credentials_help(gee_error)

initial_latitude = _query_float("lat", "latitude", default=float(DEFAULT_CENTER[0]))
initial_longitude = _query_float("lon", "lng", "longitude", default=float(DEFAULT_CENTER[1]))
has_location_query = any(
    _query_value(name) not in (None, "")
    for name in ("lat", "latitude", "lon", "lng", "longitude")
)
initial_zoom = _query_int("zoom", 14 if has_location_query else DEFAULT_ZOOM)
initial_mine_name = _query_text("mine", _query_text("mine_name", ""))

with st.sidebar:
    st.header("Mine location")
    mine_name = st.text_input("Mine name", value=initial_mine_name)
    latitude = st.number_input(
        "Latitude",
        min_value=-90.0,
        max_value=90.0,
        value=initial_latitude,
        format="%.6f",
    )
    longitude = st.number_input(
        "Longitude",
        min_value=-180.0,
        max_value=180.0,
        value=initial_longitude,
        format="%.6f",
    )
    map_zoom = st.slider("Map zoom", min_value=6, max_value=18, value=initial_zoom)

    st.divider()
    st.header("Timelapse settings")

    title = st.text_input("Title", value="Landsat Timelapse")
    band_label = st.selectbox(
        "RGB band combination",
        options=list(BAND_COMBINATIONS.keys()),
        index=0,
    )
    frames_per_second = st.slider("Frames per second", min_value=1, max_value=20, value=8)
    apply_fmask = st.checkbox(
        "Apply fmask (remove clouds, shadows, snow)",
        value=True,
    )

    st.divider()
    start_year, end_year = st.slider(
        "Year range",
        min_value=1984,
        max_value=2026,
        value=DEFAULT_YEAR_RANGE,
    )
    start_month, end_month = st.slider(
        "Month range",
        min_value=1,
        max_value=12,
        value=(5, 10),
    )

    st.divider()
    font_size = st.slider("Font size", min_value=10, max_value=50, value=30)
    font_color = st.color_picker("Font color", value="#ffffff")
    progress_bar_color = st.color_picker("Progress bar color", value="#0000ff")
    dimensions = st.select_slider(
        "GIF width",
        options=GIF_WIDTH_OPTIONS,
        value=768,
    )

left, right = st.columns([3, 2], gap="large")

with left:
    st.subheader("Region of interest")
    st.write("Draw a polygon or rectangle on the map before creating the timelapse.")
    marker_label = mine_name or f"{latitude:.6f}, {longitude:.6f}"
    map_obj = build_draw_map(
        center=[latitude, longitude],
        zoom=map_zoom,
        marker_location=[latitude, longitude],
        marker_label=marker_label,
    )
    map_state = st_folium(
        map_obj,
        height=620,
        use_container_width=True,
        returned_objects=["last_active_drawing", "all_drawings"],
    )

with right:
    st.subheader("Output")
    drawn_feature = _get_drawn_feature(map_state)
    validation_errors = []
    roi_area_km2 = None

    if drawn_feature:
        st.success("ROI selected")
        roi_area_km2 = estimate_geojson_area_km2(drawn_feature)
        st.caption(f"Approximate ROI area: {roi_area_km2:,.0f} km²")
    else:
        st.info("No ROI selected yet.")

    if roi_area_km2 is not None and roi_area_km2 > MAX_ROI_AREA_KM2:
        validation_errors.append(
            f"ROI is too large for free-use mode. Maximum: {MAX_ROI_AREA_KM2:,.0f} km²."
        )

    can_generate = gee_ready and drawn_feature is not None and not validation_errors

    if drawn_feature is not None and not gee_ready:
        st.warning("GIF generation is disabled until Google Earth Engine is configured.")
    elif gee_ready and drawn_feature is None:
        st.info("Draw an ROI to enable GIF generation.")
    elif validation_errors:
        for validation_error in validation_errors:
            st.warning(validation_error)

    if st.button(
        "Create timelapse",
        type="primary",
        disabled=not can_generate,
        use_container_width=True,
    ):
        if start_year > end_year:
            st.error("The end year must be greater than or equal to the start year.")
        elif start_month > end_month:
            st.error("The end month must be greater than or equal to the start month.")
        else:
            options = TimelapseOptions(
                title=title,
                bands=BAND_COMBINATIONS[band_label],
                start_year=start_year,
                end_year=end_year,
                start_month=start_month,
                end_month=end_month,
                frames_per_second=frames_per_second,
                apply_fmask=apply_fmask,
                font_size=font_size,
                font_color=font_color,
                progress_bar_color=progress_bar_color,
                dimensions=dimensions,
            )

            try:
                roi = drawn_feature_to_ee_geometry(drawn_feature)
                with st.spinner("Computing Landsat timelapse in Earth Engine..."):
                    gif_path = Path(generate_landsat_timelapse(roi, options))
            except Exception as exc:  # noqa: BLE001 - surface GEE/geemap errors to user.
                st.error(f"Timelapse generation failed: {exc}")
            else:
                st.session_state["latest_gif_path"] = str(gif_path)
                st.success(f"GIF created: {gif_path.name}")

    latest_gif = st.session_state.get("latest_gif_path")
    if latest_gif:
        gif_path = Path(latest_gif)
        if gif_path.exists():
            st.image(str(gif_path), caption=gif_path.name)
            st.download_button(
                "Download GIF",
                data=gif_path.read_bytes(),
                file_name=gif_path.name,
                mime="image/gif",
                use_container_width=True,
            )
            st.caption(f"Saved locally: {gif_path.resolve()}")
