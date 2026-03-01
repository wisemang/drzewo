from datetime import datetime, timezone

import tree_loader


class FakeCursor:
    def __init__(self, fetchone_result=(0,)):
        self.fetchone_result = fetchone_result
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.fetchone_result


def test_delete_city_rows_uses_source_name():
    cursor = FakeCursor()

    tree_loader.delete_city_rows(cursor, "Oakville Parks Tree Forestry")

    assert "DELETE FROM street_trees WHERE source = %s" in cursor.calls[0][0]
    assert cursor.calls[0][1] == ("Oakville Parks Tree Forestry",)


def test_count_city_rows_returns_count():
    cursor = FakeCursor(fetchone_result=(29455,))

    count = tree_loader.count_city_rows(cursor, "Peterborough Open Data Tree Inventory")

    assert count == 29455
    assert "SELECT COUNT(*) FROM street_trees WHERE source = %s" in cursor.calls[0][0]


def test_record_import_run_writes_expected_values():
    cursor = FakeCursor()
    started_at = datetime(2026, 2, 18, tzinfo=timezone.utc)
    finished_at = datetime(2026, 2, 18, 1, tzinfo=timezone.utc)

    tree_loader.record_import_run(
        cursor,
        city="peterborough",
        source_name="Peterborough Open Data Tree Inventory",
        source_file="/tmp/Tree_Inventory.geojson",
        refresh_mode=True,
        row_count=29455,
        status="completed",
        started_at=started_at,
        finished_at=finished_at,
    )

    params = cursor.calls[0][1]
    assert params[0] == "peterborough"
    assert params[3] is True
    assert params[4] == 29455
    assert params[5] == "completed"
