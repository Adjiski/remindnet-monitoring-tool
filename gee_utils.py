from __future__ import annotations

import os
import math
from pathlib import Path
from typing import Any

import ee
import folium
import google.auth
from dotenv import load_dotenv
from folium.plugins import Draw


DEFAULT_CENTER = [41.6086, 21.7453]
DEFAULT_ZOOM = 8
GEE_SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/drive",
]


def initialize_earth_engine() -> None:
    """Initialize Earth Engine from local auth or later deployment credentials."""
    load_dotenv(override=True)

    project_id = os.getenv("GEE_PROJECT_ID") or os.getenv("EE_PROJECT_ID")
    service_account = os.getenv("GEE_SERVICE_ACCOUNT_EMAIL")
    key_path = os.getenv("GEE_SERVICE_ACCOUNT_KEY_PATH")
    key_json = os.getenv("GEE_SERVICE_ACCOUNT_KEY_JSON")

    credentials = None
    if service_account and key_path:
        credentials = ee.ServiceAccountCredentials(service_account, key_path)
    elif service_account and key_json:
        credentials = ee.ServiceAccountCredentials(
            service_account,
            key_data=key_json,
        )

    if credentials is not None:
        ee.Initialize(credentials, project=project_id)
        return

    try:
        credentials, adc_project = google.auth.default(scopes=GEE_SCOPES)
    except google.auth.exceptions.DefaultCredentialsError:
        credentials = None
        adc_project = None

    if credentials is not None:
        ee.Initialize(credentials, project=project_id or adc_project)
        return

    ee.Initialize(project=project_id)


def build_draw_map(
    center: list[float] | None = None,
    zoom: int = DEFAULT_ZOOM,
    marker_location: list[float] | None = None,
    marker_label: str | None = None,
) -> folium.Map:
    """Create a Folium map with hybrid basemap and drawing tools."""
    map_obj = folium.Map(
        location=center or DEFAULT_CENTER,
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
    )
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Esri World Imagery",
        overlay=False,
        control=True,
        max_zoom=30,
    ).add_to(map_obj)

    if marker_location is not None:
        folium.Marker(
            location=marker_location,
            tooltip=marker_label or "Selected mine location",
            popup=marker_label or "Selected mine location",
            icon=folium.Icon(color="red", icon="info-sign"),
        ).add_to(map_obj)

    draw_options = {
        "polyline": False,
        "circle": False,
        "circlemarker": False,
        "marker": False,
        "polygon": {
            "allowIntersection": False,
            "showArea": True,
            "shapeOptions": {"color": "#1f77b4", "weight": 2},
        },
        "rectangle": {
            "shapeOptions": {"color": "#1f77b4", "weight": 2},
        },
    }
    edit_options = {"edit": True, "remove": True}
    Draw(export=False, draw_options=draw_options, edit_options=edit_options).add_to(map_obj)
    folium.LayerControl().add_to(map_obj)

    return map_obj


def drawn_feature_to_ee_geometry(feature: dict[str, Any]) -> ee.Geometry:
    """Convert a Streamlit-Folium drawn GeoJSON feature into an EE geometry."""
    geometry = feature.get("geometry", feature)
    geometry_type = geometry.get("type")

    if geometry_type == "Feature":
        geometry = geometry.get("geometry", {})
        geometry_type = geometry.get("type")

    if geometry_type not in {"Polygon", "MultiPolygon"}:
        raise ValueError("Please draw a polygon or rectangle ROI.")

    return ee.Geometry(geometry)


def get_drawn_geometry(feature: dict[str, Any]) -> dict[str, Any]:
    """Extract a GeoJSON geometry object from a drawn Folium feature."""
    geometry = feature.get("geometry", feature)

    if geometry.get("type") == "Feature":
        geometry = geometry.get("geometry", {})

    return geometry


def estimate_geojson_area_km2(feature: dict[str, Any]) -> float:
    """Estimate GeoJSON polygon area in square kilometers for preflight limits."""
    geometry = get_drawn_geometry(feature)
    geometry_type = geometry.get("type")
    coordinates = geometry.get("coordinates", [])

    if geometry_type == "Polygon":
        return _polygon_area_km2(coordinates)
    if geometry_type == "MultiPolygon":
        return sum(_polygon_area_km2(polygon) for polygon in coordinates)

    return 0.0


def _polygon_area_km2(rings: list) -> float:
    if not rings:
        return 0.0

    exterior = abs(_ring_area_m2(rings[0]))
    holes = sum(abs(_ring_area_m2(ring)) for ring in rings[1:])
    return max(exterior - holes, 0.0) / 1_000_000


def _ring_area_m2(ring: list) -> float:
    if len(ring) < 4:
        return 0.0

    valid_points = [(float(lon), float(lat)) for lon, lat, *_ in ring]
    mean_lat = math.radians(sum(lat for _, lat in valid_points) / len(valid_points))
    meters_per_degree_lat = 111_320
    meters_per_degree_lon = 111_320 * math.cos(mean_lat)
    projected = [
        (lon * meters_per_degree_lon, lat * meters_per_degree_lat)
        for lon, lat in valid_points
    ]

    area = 0.0
    for index, (x1, y1) in enumerate(projected):
        x2, y2 = projected[(index + 1) % len(projected)]
        area += x1 * y2 - x2 * y1

    return area / 2


def ensure_output_dir(path: str | Path = "outputs") -> Path:
    output_dir = Path(path)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir
