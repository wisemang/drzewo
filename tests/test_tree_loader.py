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


def test_calgary_row_tuple_uses_shared_schema_fields():
    row = {
        "TREE_ASSET_CD": "123",
        "COMMON_NAME": "Honey Locust",
        "GENUS": "Gleditsia",
        "SPECIES": "triacanthos",
        "CULTIVAR": "",
        "DBH_CM": "22",
        "LOCATION_DETAIL": "123 Example St",
        "COMM_CODE": "DOWNTOWN",
        "ASSET_TYPE": "Tree",
        "ASSET_SUBTYPE": "Boulevard",
        "WAM_ID": "T-32114228",
        "POINT": "POINT (-114.0719 51.0447)",
    }

    result = tree_loader.calgary_row_tuple(row)

    assert result[0] == "Calgary Open Data Tree Inventory"
    assert result[1] == 32114228
    assert result[2] == "123"
    assert result[3] == "Honey Locust"
    assert result[4] == "Gleditsia triacanthos"
    assert result[8] == "Boulevard"
    assert result[9] == "POINT (-114.0719 51.0447)"


def test_toronto_row_tuple_normalizes_point_geometry():
    feature = {
        "properties": {
            "OBJECTID": 1,
            "STRUCTID": "abc",
            "ADDRESS": "10",
            "STREETNAME": "King",
            "CROSSSTREET1": "Bay",
            "CROSSSTREET2": "Yonge",
            "SUFFIX": "St",
            "UNIT_NUMBER": None,
            "TREE_POSITION_NUMBER": 2,
            "SITE": "Boulevard",
            "WARD": "1",
            "BOTANICAL_NAME": "Acer saccharum",
            "COMMON_NAME": "Sugar Maple",
            "DBH_TRUNK": 20,
        },
        "geometry": {"type": "Point", "coordinates": [-79.38, 43.65]},
    }

    result = tree_loader.toronto_row_tuple(feature)

    assert result[0] == "Toronto Open Data Street Trees"
    assert '"type": "MultiPoint"' in result[-1]
