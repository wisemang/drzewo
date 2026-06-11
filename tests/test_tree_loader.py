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


def test_species_seed_files_load():
    catalog = tree_loader.load_species_catalog()

    assert "quercus_robur" in catalog["species_by_key"]
    assert catalog["species_by_key"]["quercus_robur"]["display_common_name"] == "English Oak"


def test_resolved_species_values_uses_canadian_english_aliases():
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        "Birch, Grey", "Betula populifolia", "Toronto Open Data Street Trees"
    )

    assert common_name == "Grey Birch"
    assert original_common_name == "Birch, Grey"
    assert species_key == "betula_populifolia"


def test_resolved_species_values_handles_toronto_white_mulberry():
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        "Mulberry, white", "Morus alba", "Toronto Open Data Street Trees"
    )

    assert common_name == "White Mulberry"
    assert original_common_name == "Mulberry, white"
    assert species_key == "morus_alba"


def test_resolved_species_values_translates_known_geneva_species():
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        "Chêne pédonculé", "Quercus robur", "Geneva Cantonal Tree Inventory"
    )

    assert common_name == "English Oak"
    assert original_common_name == "Chêne pédonculé"
    assert species_key == "quercus_robur"


def test_standardize_common_name_does_not_invert_unknown_comma_names():
    assert tree_loader.standardize_common_name("Something, Cultivar") == "Something, Cultivar"


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
    assert result[4] == "Honey Locust"
    assert result[5] == "Gleditsia triacanthos"
    assert result[9] == "Boulevard"
    assert result[10] == "POINT (-114.0719 51.0447)"


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
            "BOTANICAL_NAME": "Acer platanoides",
            "COMMON_NAME": "Maple, Norway",
            "DBH_TRUNK": 20,
        },
        "geometry": {"type": "Point", "coordinates": [-79.38, 43.65]},
    }

    result = tree_loader.toronto_row_tuple(feature)

    assert result[0] == "Toronto Open Data Street Trees"
    assert result[12] == "Acer platanoides"
    assert result[13] == "Norway Maple"
    assert result[14] == "Maple, Norway"
    assert result[15] == "acer_platanoides"
    assert '"type": "MultiPoint"' in result[-1]


def test_mississauga_city_is_registered():
    config = tree_loader.CITY_HANDLERS["mississauga"]

    assert config["source_name"] == "Mississauga City-Owned Tree Inventory"
    assert config["loader"] == "load_mississauga_data"


def test_mississauga_row_tuple_maps_shared_fields():
    feature = {
        "properties": {
            "OBJECTID": 1001,
            "UNITID": "748543",
            "ADDRKEY": 38791,
            "LOC": "SIDE",
            "SPACETYPE": "BLVD",
            "SERVSTAT": "TREE MAINTAINED BY OPERATIONS",
            "ZAREA": "Z03",
            "BOTNAME": "APCRFL",
            "BOTDESC": "APPLE CRAB FLOWERING",
            "DIAM": 22.0,
        },
        "geometry": {"type": "Point", "coordinates": [-79.64, 43.58]},
    }

    result = tree_loader.mississauga_row_tuple(feature)

    assert result[0] == "Mississauga City-Owned Tree Inventory"
    assert result[1] == 1001
    assert result[2] == "748543"
    assert result[3] is None
    assert result[4] == "SIDE | BLVD | TREE MAINTAINED BY OPERATIONS"
    assert result[5] == "Z03"
    assert result[6] is None
    assert result[7] == "Apple Crab Flowering"
    assert result[8] == "Apple Crab Flowering"
    assert result[9] == 22
    assert '"type": "MultiPoint"' in result[10]


def test_mississauga_row_tuple_falls_back_to_botname():
    feature = {
        "properties": {
            "OBJECTID": 1002,
            "UNITID": "748544",
            "LOC": "FRONT",
            "SERVSTAT": "TO BE PLANTED",
            "ZAREA": "Z30",
            "BOTNAME": "COKEES",
            "BOTDESC": None,
            "DIAM": 5.0,
        },
        "geometry": {"type": "Point", "coordinates": [-79.60, 43.60]},
    }

    result = tree_loader.mississauga_row_tuple(feature)

    assert result[7] == "Cokees"
    assert result[8] == "Cokees"


def test_san_francisco_city_is_registered():
    config = tree_loader.CITY_HANDLERS["san_francisco"]

    assert config["source_name"] == "San Francisco Street Tree Inventory"
    assert config["loader"] == "load_san_francisco_data"


def test_san_francisco_row_tuple_maps_shared_fields():
    row = {
        "TreeID": "123456",
        "qLegalStatus": "Permitted",
        "qSpecies": "London Plane",
        "qAddress": "123 Market St",
        "SiteOrder": "7",
        "qSiteInfo": "Sidewalk",
        "qCaretaker": "Public Works",
        "qCareAssistant": "Urban Forestry",
        "XCoord": "551234.5",
        "YCoord": "4182345.8",
        "DBH": "18.4",
        "longitude": "-122.4464023",
        "latitude": "37.7760911",
    }

    result = tree_loader.san_francisco_row_tuple(row)

    assert result[0] == "San Francisco Street Tree Inventory"
    assert result[1] == 123456
    assert result[2] == "123 Market St"
    assert result[3] == "Sidewalk"
    assert result[4] == "Public Works"
    assert result[5] == "London Plane"
    assert result[6] == "London Plane"
    assert result[7] == "London Plane"
    assert result[8] == 18
    assert result[9] == 7
    assert result[10] == -122.4464023
    assert result[11] == 37.7760911


def test_madison_city_is_registered():
    config = tree_loader.CITY_HANDLERS["madison_wi"]

    assert config["source_name"] == "Madison Urban Forestry Street Trees"
    assert config["loader"] == "load_madison_data"


def test_madison_row_tuple_maps_shared_fields():
    feature = {
        "properties": {
            "OBJECTID": 794615,
            "INSPECT_DT": "2024-03-20T06:00:00Z",
            "INV_DATE": "2022-03-28T06:00:00Z",
            "SPP_COM": "Honeylocust 'Skyline'",
            "SPP_BOT": "Gleditsia triacanthos 'Skyline'",
            "GSSIZE": "7'-8'",
            "DIAMETER": 6.0,
            "STATUS": "Active",
            "site_id": 403144,
        },
        "geometry": {"type": "Point", "coordinates": [-89.385608133859975, 43.056392160247363]},
    }

    result = tree_loader.madison_row_tuple(feature)

    assert result[0] == "Madison Urban Forestry Street Trees"
    assert result[1] == 794615
    assert result[2] == "403144"
    assert result[3] == "Active"
    assert result[4] == "Gleditsia triacanthos 'Skyline'"
    assert result[5] == "Skyline Honey Locust"
    assert result[6] == "Honeylocust 'Skyline'"
    assert result[7] == 6
    assert '"type": "MultiPoint"' in result[8]


def test_geneva_city_is_registered():
    config = tree_loader.CITY_HANDLERS["geneva"]

    assert config["source_name"] == "Geneva Cantonal Tree Inventory"
    assert config["loader"] == "load_geneva_data"


def test_geneva_geojson_row_tuple_maps_shared_fields():
    feature = {
        "properties": {
            "classe": "Feuillus",
            "commune": "Collonge-Bellerive",
            "globalid": "{F402AD3D-C386-41B1-8D89-E543541AE71C}",
            "circonference": 201,
            "diam_1m": 64,
            "id_arbre": 42769,
            "no_postal": 1222,
            "nom_commun": "Peuplier",
            "nom_latin": "Populus",
            "objectid": 1,
            "statut": "Historique",
        },
        "geometry": {"type": "Point", "coordinates": [6.199525696665598, 46.24506941115345]},
    }

    result = tree_loader.geneva_geojson_row_tuple(feature)

    assert result[0] == "Geneva Cantonal Tree Inventory"
    assert result[1] == 42769
    assert result[2] == "{F402AD3D-C386-41B1-8D89-E543541AE71C}"
    assert result[3] == "1222 Collonge-Bellerive"
    assert result[4] == "Feuillus | Historique"
    assert result[5] == "Collonge-Bellerive"
    assert result[6] == "Populus"
    assert result[7] == "Poplar"
    assert result[8] == "Peuplier"
    assert result[9] == "populus"
    assert result[10] == 64
    assert '"type": "MultiPoint"' in result[11]


def test_geneva_arcgis_json_row_tuple_maps_lv95_coordinates():
    feature = {
        "attributes": {
            "CLASSE": "Feuillus",
            "COMMUNE": "Collonge-Bellerive",
            "GLOBALID": "{F402AD3D-C386-41B1-8D89-E543541AE71C}",
            "CIRCONFERENCE": 201,
            "DIAM_1M": None,
            "ID_ARBRE": 42769,
            "NO_POSTAL": 1222,
            "NOM_COMMUN": "Peuplier",
            "NOM_LATIN": "Populus",
            "OBJECTID": 1,
            "STATUT": "Historique",
        },
        "geometry": {"x": 2504434.43, "y": 1122271.21},
    }

    result = tree_loader.geneva_arcgis_json_row_tuple(feature)

    assert result[0] == "Geneva Cantonal Tree Inventory"
    assert result[1] == 42769
    assert result[3] == "1222 Collonge-Bellerive"
    assert result[4] == "Feuillus | Historique"
    assert result[9] == "populus"
    assert result[10] == 64
    assert result[11] == 2504434.43
    assert result[12] == 1122271.21
