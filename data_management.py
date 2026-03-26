from datetime import datetime
from pathlib import Path


def dataset_date_for_path(path):
    """Derive a YYYY-MM-DD date from filesystem metadata."""
    file_path = Path(path)
    stat_result = file_path.stat()
    timestamp = getattr(stat_result, "st_birthtime", stat_result.st_mtime)
    return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")


def archive_destination(path, city, base_dir="data/raw", date_str=None):
    """Return the canonical destination for a raw dataset file."""
    source_path = Path(path)
    archive_date = date_str or dataset_date_for_path(source_path)
    return Path(base_dir) / city / archive_date / source_path.name


def latest_archived_dataset(city, base_dir="data/raw"):
    """Return the newest archived dataset file for a city."""
    city_dir = Path(base_dir) / city
    if not city_dir.exists() or not city_dir.is_dir():
        raise FileNotFoundError(
            f"No archived dataset directory found for city '{city}': {city_dir}"
        )

    dated_dirs = sorted(path for path in city_dir.iterdir() if path.is_dir())
    if not dated_dirs:
        raise FileNotFoundError(
            f"No dated archive directories found for city '{city}' under {city_dir}"
        )

    latest_dir = dated_dirs[-1]
    files = sorted(
        path
        for path in latest_dir.iterdir()
        if path.is_file() and not path.name.startswith(".")
    )
    if not files:
        raise FileNotFoundError(
            f"No dataset files found in latest archive directory for city '{city}': {latest_dir}"
        )

    return files[-1]
