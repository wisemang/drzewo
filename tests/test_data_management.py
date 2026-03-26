import pytest

import data_management


def test_archive_destination_uses_explicit_date(tmp_path):
    source = tmp_path / "oakville.geojson"
    source.write_text("{}", encoding="utf-8")

    destination = data_management.archive_destination(
        source,
        "oakville",
        base_dir=tmp_path / "raw",
        date_str="2026-02-18",
    )

    assert destination == tmp_path / "raw" / "oakville" / "2026-02-18" / "oakville.geojson"


def test_dataset_date_for_path_uses_filesystem_metadata(tmp_path):
    source = tmp_path / "peterborough.geojson"
    source.write_text("{}", encoding="utf-8")

    date_value = data_management.dataset_date_for_path(source)

    assert len(date_value) == 10
    assert date_value.count("-") == 2


def test_latest_archived_dataset_returns_file_from_latest_date_dir(tmp_path):
    (tmp_path / "raw" / "toronto" / "2024-11-30").mkdir(parents=True)
    (tmp_path / "raw" / "toronto" / "2026-03-26").mkdir(parents=True)
    (tmp_path / "raw" / "toronto" / "2024-11-30" / "old.geojson").write_text("{}")
    newest = tmp_path / "raw" / "toronto" / "2026-03-26" / "Street Tree Data - 4326.geojson"
    newest.write_text("{}")

    result = data_management.latest_archived_dataset("toronto", base_dir=tmp_path / "raw")

    assert result == newest


def test_latest_archived_dataset_raises_when_city_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="No archived dataset directory found"):
        data_management.latest_archived_dataset("toronto", base_dir=tmp_path / "raw")
