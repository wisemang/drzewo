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
