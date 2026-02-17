import api


class FakeCursor:
    def __init__(self, rows):
        self.rows = rows
        self.executed = None
        self.params = None
        self.calls = []

    def execute(self, query, params):
        self.executed = query
        self.params = params
        self.calls.append((query, params))

    def fetchall(self):
        return self.rows

    def close(self):
        return None


class FakeConnection:
    def __init__(self, rows):
        self.cursor_instance = FakeCursor(rows)
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
