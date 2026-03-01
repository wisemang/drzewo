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
