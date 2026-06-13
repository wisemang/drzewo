from datetime import datetime, timezone

import api


class FakeCursor:
    def __init__(self, rows, fetchone_results=None):
        self.rows = rows
        self.fetchone_results = list(fetchone_results) if fetchone_results is not None else None
        self.executed = None
        self.params = None
        self.calls = []

    def execute(self, query, params):
        self.executed = query
        self.params = params
        self.calls.append((query, params))

    def fetchall(self):
        return self.rows

    def fetchone(self):
        if self.fetchone_results is not None:
            if not self.fetchone_results:
                return None
            return self.fetchone_results.pop(0)
        if not self.rows:
            return None
        return self.rows[0]

    def close(self):
        return None


class FakeConnection:
    def __init__(self, rows, fetchone_results=None):
        self.cursor_instance = FakeCursor(rows, fetchone_results=fetchone_results)
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


def test_home_page_loads():
    client = api.app.test_client()
    response = client.get("/")
    assert response.status_code == 200


def test_nearest_requires_coordinates():
    client = api.app.test_client()
    response = client.get("/nearest")
    assert response.status_code == 400
    assert response.get_json() == {"error": "lat and lng query parameters are required"}


def test_nearest_returns_rows(monkeypatch):
    rows = [
        (
            "Toronto Open Data Street Trees",
            1,
            "Maple",
            "Acer",
            "10",
            "King St",
            25,
            1,
            "Maple",
            "12",
            9.3,
            -79.3832,
            43.6532,
        )
    ]
    fake_conn = FakeConnection(rows)

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/nearest?lat=43.65&lng=-79.38&limit=5")

    assert response.status_code == 200
    payload = response.get_json()
    assert len(payload) == 1
    assert payload[0]["common_name"] == "Maple"
    assert payload[0]["original_common_name"] == "Maple"
    assert payload[0]["species_id"] == 12
    assert fake_conn.closed is True


def test_nearest_rejects_out_of_bounds_coordinates():
    client = api.app.test_client()
    response = client.get("/nearest?lat=120&lng=-79.38")
    assert response.status_code == 400
    assert response.get_json() == {"error": "lat/lng are out of bounds"}


def test_nearest_rejects_non_numeric_radius():
    client = api.app.test_client()
    response = client.get("/nearest?lat=43.65&lng=-79.38&max_distance_m=abc")
    assert response.status_code == 400
    assert response.get_json() == {"error": "max_distance_m must be a number"}


def test_nearest_clamps_limit_and_radius(monkeypatch):
    fake_conn = FakeConnection([])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/nearest?lat=43.65&lng=-79.38&limit=999&max_distance_m=99999")

    assert response.status_code == 200
    assert "ST_DWithin" in fake_conn.cursor_instance.executed
    params = fake_conn.cursor_instance.params
    assert params[-1] == api.MAX_LIMIT
    assert api.MAX_RADIUS_M in params


def test_nearest_uses_default_limit_when_missing(monkeypatch):
    fake_conn = FakeConnection([])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/nearest?lat=43.65&lng=-79.38")

    assert response.status_code == 200
    params = fake_conn.cursor_instance.params
    assert params[-1] == api.DEFAULT_LIMIT


def test_species_profile_returns_sourced_profile(monkeypatch):
    rows = [
        (
            12,
            "acer_rubrum",
            "Acer rubrum",
            "Red Maple",
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            "Acer rubrum is a deciduous tree.",
            {"canonical_botanical_name": "Acer rubrum"},
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            "wikipedia",
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            datetime(2026, 6, 12, tzinfo=timezone.utc),
            "wikipedia-summary-v1",
            "source-derived",
            "Creative Commons Attribution-ShareAlike 4.0 International",
            "https://creativecommons.org/licenses/by-sa/4.0/",
            "Wikipedia contributors",
        )
    ]
    fake_conn = FakeConnection(rows)

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["species_key"] == "acer_rubrum"
    assert payload["common_name"] == "Red Maple"
    assert payload["botanical_name"] == "Acer rubrum"
    assert payload["sections"]["benefits"] is None
    assert payload["sections"]["risk"] is None
    summary = payload["sections"]["summary"]
    assert summary["available"] is True
    assert summary["text"] == "Acer rubrum is a deciduous tree."
    assert summary["source_system"] == "wikipedia"
    assert summary["source_url"] == "https://en.wikipedia.org/wiki/Acer_rubrum"
    assert summary["license"] == "Creative Commons Attribution-ShareAlike 4.0 International"
    assert summary["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert summary["attribution"] == "Wikipedia contributors"
    assert summary["retrieved_at"] == "2026-06-12T00:00:00+00:00"
    assert "profile" not in payload
    assert "LEFT JOIN species_profile" in fake_conn.cursor_instance.executed


def test_species_profile_contract_keeps_facts_separate_from_estimates_and_risk(monkeypatch):
    rows = [
        (
            12,
            "acer_rubrum",
            "Acer rubrum",
            "Red Maple",
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            "Acer rubrum is a deciduous tree.",
            {"canonical_botanical_name": "Acer rubrum"},
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            "wikipedia",
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            "2026-06-12T00:00:00+00:00",
            "wikipedia-summary-v1",
            "source-derived",
            "Creative Commons Attribution-ShareAlike 4.0 International",
            "https://creativecommons.org/licenses/by-sa/4.0/",
            "Wikipedia contributors",
        )
    ]
    fake_conn = FakeConnection(rows)

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile")

    assert response.status_code == 200
    payload = response.get_json()
    sections = payload["sections"]
    assert sections["summary"]["confidence"] == "source-derived"
    assert sections["summary"]["method_version"] == "wikipedia-summary-v1"
    assert "estimate" not in sections["summary"]
    assert "risk" not in sections["summary"]
    assert sections["benefits"] is None
    assert sections["risk"] is None
    assert sections["media"] is None
    assert sections["local_stats"] is None


def test_species_profile_returns_null_profile_for_unenriched_species(monkeypatch):
    rows = [
        (
            12,
            "acer_rubrum",
            "Acer rubrum",
            "Red Maple",
            "https://en.wikipedia.org/wiki/Acer_rubrum",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            None,
        )
    ]
    fake_conn = FakeConnection(rows)

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["common_name"] == "Red Maple"
    assert payload["botanical_name"] == "Acer rubrum"
    assert payload["sections"]["summary"] is None
    assert payload["sections"]["benefits"] is None
    assert payload["sections"]["risk"] is None
    assert payload["sections"]["media"] is None
    assert payload["sections"]["local_stats"] is None


def test_species_profile_returns_local_stats_when_context_is_present(monkeypatch):
    profile_row = (
        12,
        "acer_rubrum",
        "Acer rubrum",
        "Red Maple",
        "https://en.wikipedia.org/wiki/Acer_rubrum",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    fake_conn = FakeConnection(None, fetchone_results=[profile_row, (3, 47)])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile?lat=43.65&lng=-79.38&radius_m=1000")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["sections"]["local_stats"] == {
        "radius_m": 1000,
        "same_species_count": 3,
        "largest_dbh": 47,
    }
    stats_query, stats_params = fake_conn.cursor_instance.calls[1]
    assert "FROM street_trees" in stats_query
    assert "WHERE species_id = %s" in stats_query
    assert "ST_DWithin" in stats_query
    assert stats_params == (12, -79.38, 43.65, 1000)


def test_species_profile_coerces_missing_local_stats_count_to_zero(monkeypatch):
    profile_row = (
        12,
        "acer_rubrum",
        "Acer rubrum",
        "Red Maple",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    fake_conn = FakeConnection(None, fetchone_results=[profile_row, (None, None)])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile?lat=43.65&lng=-79.38&radius_m=1000")

    assert response.status_code == 200
    assert response.get_json()["sections"]["local_stats"] == {
        "radius_m": 1000,
        "same_species_count": 0,
        "largest_dbh": None,
    }


def test_species_profile_omits_local_stats_when_context_is_partial(monkeypatch):
    profile_row = (
        12,
        "acer_rubrum",
        "Acer rubrum",
        "Red Maple",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    fake_conn = FakeConnection(None, fetchone_results=[profile_row])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile?lat=43.65&lng=-79.38")

    assert response.status_code == 200
    assert response.get_json()["sections"]["local_stats"] is None
    assert len(fake_conn.cursor_instance.calls) == 1


def test_species_profile_clamps_local_stats_radius(monkeypatch):
    profile_row = (
        12,
        "acer_rubrum",
        "Acer rubrum",
        "Red Maple",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    fake_conn = FakeConnection(None, fetchone_results=[profile_row, (0, None)])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/12/profile?lat=43.65&lng=-79.38&radius_m=99999")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["sections"]["local_stats"]["radius_m"] == api.MAX_RADIUS_M
    assert fake_conn.cursor_instance.calls[1][1][-1] == api.MAX_RADIUS_M


def test_species_profile_rejects_invalid_local_stats_context():
    client = api.app.test_client()
    response = client.get("/species/12/profile?lat=43.65&lng=-79.38&radius_m=abc")

    assert response.status_code == 400
    assert response.get_json() == {"error": "lat, lng, and radius_m must be numbers"}


def test_species_profile_rejects_non_finite_local_stats_context():
    client = api.app.test_client()
    response = client.get("/species/12/profile?lat=43.65&lng=-79.38&radius_m=nan")

    assert response.status_code == 400
    assert response.get_json() == {"error": "lat, lng, and radius_m must be finite numbers"}


def test_species_profile_returns_404_for_unknown_species(monkeypatch):
    fake_conn = FakeConnection([])

    def fake_connect(**_kwargs):
        return fake_conn

    monkeypatch.setattr(api.psycopg2, "connect", fake_connect)

    client = api.app.test_client()
    response = client.get("/species/999/profile")

    assert response.status_code == 404
    assert response.get_json() == {"error": "species not found"}
