from __future__ import annotations

import calendar
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import ee
from geemap.timelapse import landsat_timelapse

from gee_utils import ensure_output_dir


BAND_COMBINATIONS: dict[str, list[str]] = {
    "Red/Green/Blue": ["Red", "Green", "Blue"],
    "NIR/Red/Green": ["NIR", "Red", "Green"],
    "SWIR2/SWIR1/NIR": ["SWIR2", "SWIR1", "NIR"],
}


@dataclass(frozen=True)
class TimelapseOptions:
    title: str
    bands: list[str]
    start_year: int
    end_year: int
    start_month: int
    end_month: int
    frames_per_second: int = 8
    apply_fmask: bool = True
    font_size: int = 30
    font_color: str = "#ffffff"
    progress_bar_color: str = "#0000ff"
    dimensions: int = 768


def _safe_filename(value: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.-]+", "-", value.strip()).strip("-")
    return name.lower() or "landsat-timelapse"


def _month_day(month: int, year: int, start: bool) -> str:
    day = 1 if start else calendar.monthrange(year, month)[1]
    return f"{month:02d}-{day:02d}"


def validate_options(options: TimelapseOptions) -> None:
    if options.start_year > options.end_year:
        raise ValueError("The end year must be greater than or equal to the start year.")
    if options.start_month > options.end_month:
        raise ValueError("The end month must be greater than or equal to the start month.")
    if options.frames_per_second < 1:
        raise ValueError("Frames per second must be at least 1.")
    if not options.bands:
        raise ValueError("At least one RGB band combination is required.")


def generate_landsat_timelapse(
    roi: ee.Geometry,
    options: TimelapseOptions,
    output_dir: str | Path = "outputs",
) -> str:
    """Generate a Landsat GIF from an Earth Engine ROI and Streamlit options."""
    validate_options(options)

    start_date = _month_day(options.start_month, options.start_year, start=True)
    end_date = _month_day(options.end_month, options.end_year, start=False)
    add_progress_bar = options.start_year != options.end_year

    output_path = ensure_output_dir(output_dir) / (
        f"{_safe_filename(options.title)}-{datetime.utcnow():%Y%m%d-%H%M%S}.gif"
    )

    result = landsat_timelapse(
        roi=roi,
        title=options.title,
        start_year=options.start_year,
        end_year=options.end_year,
        start_date=start_date,
        end_date=end_date,
        bands=options.bands,
        dimensions=options.dimensions,
        frames_per_second=options.frames_per_second,
        font_size=options.font_size,
        font_color=options.font_color,
        add_progress_bar=add_progress_bar,
        progress_bar_color=options.progress_bar_color,
        out_gif=str(output_path),
        apply_fmask=options.apply_fmask,
    )

    generated_path = Path(result) if result else output_path
    if not generated_path.exists():
        raise FileNotFoundError(f"Expected GIF was not created at {generated_path}")

    return str(generated_path)
