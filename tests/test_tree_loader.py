from datetime import datetime, timezone

import tree_loader


def warsaw_feature():
    return {
        "type": "Feature",
        "_id": "1232965",
        "geometry": {"type": "Point", "coordinates": [20.99627, 52.22483]},
        "properties": {
            "NAZWA_SERWIS": "D1007155",
            "_treeseek_objectid": 1007155,
            "_label_": "\n".join(
                (
                    "Numer inwentaryzacyjny: D1007155",
                    "Nazwa polska: brzoza",
                    "Nazwa łacińska: Betula sp.",
                    "Obwód pnia w cm: 42",
                    "Jednostka zarządzająca: Dzielnica Ochota",
                    "Aktualność danych na dzień: 18.11.2025",
                )
            ),
        },
    }


class FakeCursor:
    def __init__(
        self,
        fetchone_result=(0,),
        fetchone_results=None,
        fetchall_result=None,
        rowcount=0,
    ):
        self.fetchone_result = fetchone_result
        self.fetchone_results = list(fetchone_results) if fetchone_results is not None else None
        self.fetchall_result = fetchall_result or []
        self.rowcount = rowcount
        self.calls = []

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        if self.fetchone_results is not None:
            if not self.fetchone_results:
                return None
            return self.fetchone_results.pop(0)
        return self.fetchone_result

    def fetchall(self):
        return self.fetchall_result


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


def test_warsaw_row_keeps_source_identifiers_and_derives_diameter_from_circumference():
    row = tree_loader.warsaw_row_tuple(warsaw_feature())

    assert row[0] == "Warsaw Baza Zieleni Tree Inventory"
    assert row[1] == 1007155
    assert row[2] == "D1007155"
    assert row[3] == "Dzielnica Ochota"
    assert row[4] == "Betula sp."
    assert row[6] == "brzoza"
    assert row[8] == 13
    assert '"coordinates": [[20.99627, 52.22483]]' in row[-1]


def test_resolved_species_values_ignores_botanical_author_citations():
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        "klon pospolity", "Acer platanoides L.", "Warsaw Baza Zieleni Tree Inventory"
    )

    assert common_name == "Norway Maple"
    assert original_common_name == "klon pospolity"
    assert species_key == "acer_platanoides"


def test_resolved_species_values_handles_reviewed_warsaw_names_and_generic_taxa():
    cases = (
        ("topola szara", "Populus ×canescens (Aiton) Sm.", "populus_x_canescens"),
        ("wiąz szypułkowy", "Ulmus laevis Pall.", "ulmus_laevis"),
        ("śliwa", "Prunus sp. (śliwa)", "prunus"),
    )

    for common_name, botanical_name, species_key in cases:
        _common, original_common_name, resolved_key = tree_loader.resolved_species_values(
            common_name, botanical_name, "Warsaw Baza Zieleni Tree Inventory"
        )
        assert original_common_name == common_name
        assert resolved_key == species_key


def test_parse_diameter_cm_falls_back_from_circumference():
    assert tree_loader.parse_diameter_cm(None, "42") == 13


def test_warsaw_is_registered_as_a_file_first_city_loader():
    config = tree_loader.CITY_HANDLERS["warsaw"]

    assert config["source_name"] == "Warsaw Baza Zieleni Tree Inventory"
    assert config["loader"] == "load_warsaw_data"


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


def test_ensure_species_enrichment_tables_creates_profile_schema():
    cursor = FakeCursor(
        fetchone_results=[
            (None,),
            (None,),
            (None,),
            (None,),
            (None,),
            (None,),
            (None,),
            (None,),
        ]
    )

    tree_loader.ensure_species_enrichment_tables(cursor)

    assert len(cursor.calls) == 16
    assert "to_regclass('public.species_profile')" in cursor.calls[0][0]
    profile_sql = cursor.calls[1][0]
    assert "CREATE TABLE species_profile" in profile_sql
    assert "source_system TEXT NOT NULL" in profile_sql
    assert "source_url TEXT NOT NULL" in profile_sql
    assert "retrieved_at TIMESTAMPTZ NOT NULL" in profile_sql
    assert "method_version TEXT NOT NULL" in profile_sql
    assert "confidence TEXT NOT NULL DEFAULT 'unreviewed'" in profile_sql
    assert "UNIQUE (species_id, source_system)" in profile_sql
    assert "to_regclass('public.idx_species_profile_species_id')" in cursor.calls[2][0]
    assert "CREATE INDEX idx_species_profile_species_id" in cursor.calls[3][0]
    assert "to_regclass('public.species_benefit')" in cursor.calls[4][0]
    benefit_sql = cursor.calls[5][0]
    assert "CREATE TABLE species_benefit" in benefit_sql
    assert "metric_type TEXT NOT NULL" in benefit_sql
    assert "scope TEXT NOT NULL" in benefit_sql
    assert "method_version TEXT NOT NULL" in benefit_sql
    assert "source_system TEXT NOT NULL" in benefit_sql
    assert "source_url TEXT NOT NULL" in benefit_sql
    assert "CHECK (retrieved_at IS NOT NULL OR calculated_at IS NOT NULL)" in benefit_sql
    assert "scope <> 'tree_instance'" in benefit_sql
    assert "to_regclass('public.idx_species_benefit_species_id')" in cursor.calls[6][0]
    assert "CREATE INDEX idx_species_benefit_species_id" in cursor.calls[7][0]
    assert "to_regclass('public.species_risk')" in cursor.calls[8][0]
    risk_sql = cursor.calls[9][0]
    assert "CREATE TABLE species_risk" in risk_sql
    assert "risk_type TEXT NOT NULL" in risk_sql
    assert "status TEXT NOT NULL" in risk_sql
    assert "region TEXT NOT NULL" in risk_sql
    assert "region_type TEXT NOT NULL" in risk_sql
    assert "method_version TEXT NOT NULL" in risk_sql
    assert "source_system TEXT NOT NULL" in risk_sql
    assert "source_url TEXT NOT NULL" in risk_sql
    assert "CHECK (retrieved_at IS NOT NULL OR observed_at IS NOT NULL)" in risk_sql
    assert "to_regclass('public.idx_species_risk_species_id')" in cursor.calls[10][0]
    assert "CREATE INDEX idx_species_risk_species_id" in cursor.calls[11][0]
    assert "to_regclass('public.species_risk_observation')" in cursor.calls[12][0]
    observation_sql = cursor.calls[13][0]
    assert "CREATE TABLE species_risk_observation" in observation_sql
    assert "species_risk_id BIGINT REFERENCES species_risk(id) ON DELETE CASCADE" in observation_sql
    assert "species_id BIGINT NOT NULL REFERENCES species(id) ON DELETE CASCADE" in observation_sql
    assert "risk_type TEXT NOT NULL" in observation_sql
    assert "source_system TEXT NOT NULL" in observation_sql
    assert "latitude IS NULL AND longitude IS NULL" in observation_sql
    assert "to_regclass('public.idx_species_risk_observation_species_id')" in cursor.calls[14][0]
    assert "CREATE INDEX idx_species_risk_observation_species_id" in cursor.calls[15][0]


def test_ensure_species_enrichment_tables_skips_existing_profile_schema():
    cursor = FakeCursor(
        fetchone_results=[
            ("species_profile",),
            ("idx_species_profile_species_id",),
            ("species_benefit",),
            ("idx_species_benefit_species_id",),
            ("species_risk",),
            ("idx_species_risk_species_id",),
            ("species_risk_observation",),
            ("idx_species_risk_observation_species_id",),
        ]
    )

    tree_loader.ensure_species_enrichment_tables(cursor)

    assert len(cursor.calls) == 8
    assert "to_regclass('public.species_profile')" in cursor.calls[0][0]
    assert "to_regclass('public.idx_species_profile_species_id')" in cursor.calls[1][0]
    assert "to_regclass('public.species_benefit')" in cursor.calls[2][0]
    assert "to_regclass('public.idx_species_benefit_species_id')" in cursor.calls[3][0]
    assert "to_regclass('public.species_risk')" in cursor.calls[4][0]
    assert "to_regclass('public.idx_species_risk_species_id')" in cursor.calls[5][0]
    assert "to_regclass('public.species_risk_observation')" in cursor.calls[6][0]
    assert "to_regclass('public.idx_species_risk_observation_species_id')" in cursor.calls[7][0]


def test_apply_species_catalog_to_source_updates_resolved_rows(monkeypatch):
    cursor = FakeCursor(
        fetchall_result=[
            ("Quercus robur", "Chêne pédonculé"),
            ("Unknown botanical", "Mystery tree"),
        ],
        rowcount=42,
    )
    inserted_rows = []

    def fake_execute_values(_cursor, _query, rows, **_kwargs):
        inserted_rows.extend(rows)

    monkeypatch.setattr(tree_loader, "execute_values", fake_execute_values)

    updated = tree_loader.apply_species_catalog_to_source(
        cursor, "Geneva Cantonal Tree Inventory"
    )

    assert updated == 42
    assert inserted_rows == [
        (
            "Geneva Cantonal Tree Inventory",
            "Quercus robur",
            "Chêne pédonculé",
            "English Oak",
            "quercus_robur",
        )
    ]
    assert cursor.calls[0][1] == ("Geneva Cantonal Tree Inventory",)
    assert "IS NOT DISTINCT FROM resolved.botanical_name" in cursor.calls[3][0]
    assert "tree.species_id IS DISTINCT FROM species.id" in cursor.calls[3][0]


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


def test_resolved_species_values_handles_ottawa_reversed_common_names():
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        "Maple Sugar", "Maple Sugar", "Ottawa Open Data Tree Inventory"
    )

    assert common_name == "Sugar Maple"
    assert original_common_name == "Maple Sugar"
    assert species_key == "acer_saccharum"


def test_resolved_species_values_handles_canonical_common_names_without_botanical_name():
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        "Norway Maple", None, "Mississauga City-Owned Tree Inventory"
    )

    assert common_name == "Norway Maple"
    assert original_common_name == "Norway Maple"
    assert species_key == "acer_platanoides"


def test_resolved_species_values_handles_san_francisco_packed_species_text():
    source_name = "Platanus x hispanica :: Sycamore: London Plane"
    common_name, original_common_name, species_key = tree_loader.resolved_species_values(
        source_name, source_name, "San Francisco Street Tree Inventory"
    )

    assert common_name == "London Plane"
    assert original_common_name == source_name
    assert species_key == "platanus_x_acerifolia"


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
        "qSpecies": "Platanus x hispanica :: Sycamore: London Plane",
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
    assert result[5] == "Platanus x hispanica"
    assert result[6] == "London Plane"
    assert result[7] == "Platanus x hispanica :: Sycamore: London Plane"
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
