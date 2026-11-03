import copy
import io
import json

import pytest

from scripts import download_warsaw_trees
from warsaw_data import (
    BBOX,
    BBOX_EDGE_OVERLAP,
    THEMES,
    digest,
    label_fields,
    validate_archive,
    validate_response,
)


def feature(objectid=123, inventory_number="D1007155", longitude=21.0):
    return {
        "type": "Feature",
        "_id": str(objectid),
        "geometry": {"type": "Point", "coordinates": [longitude, 52.2]},
        "properties": {
            "NAZWA_SERWIS": inventory_number,
            "_label_": "\n".join(
                (
                    f"Numer inwentaryzacyjny: {inventory_number}",
                    "Nazwa polska: brzoza",
                    "Nazwa łacińska: Betula sp.",
                    "Obwód pnia w cm: 42",
                    "Jednostka zarządzająca: Dzielnica Ochota",
                    "Aktualność danych na dzień: 18.11.2025",
                )
            ),
        },
    }


def payload(theme, records):
    return {
        "type": "FeatureCollection",
        "srs": 4326,
        "collectionName": theme,
        "features": records,
    }


def test_validate_response_accepts_verified_city_shape():
    records = validate_response(payload(THEMES[0], [feature()]), THEMES[0], BBOX)

    assert list(records) == ["123"]


def test_validate_response_accepts_opaque_city_feature_id():
    opaque_id = "ACjqIrAAAAAAJA7AAC"
    records = validate_response(
        payload(THEMES[11], [feature(objectid=opaque_id)]), THEMES[11], BBOX
    )

    assert list(records) == [opaque_id]


def test_decoder_accepts_unescaped_control_characters_in_city_labels():
    stream = io.StringIO('{"label": "first line\nsecond line"}')

    assert download_warsaw_trees.decode_response(stream) == {
        "label": "first line\nsecond line"
    }


def test_validate_response_allows_small_query_edge_overlap_only():
    split_bbox = (BBOX[0], BBOX[1], 21.05, BBOX[3])
    accepted = feature(longitude=split_bbox[2] + BBOX_EDGE_OVERLAP)
    assert validate_response(payload(THEMES[0], [accepted]), THEMES[0], split_bbox)

    rejected = feature(longitude=split_bbox[2] + BBOX_EDGE_OVERLAP + 0.00001)
    with pytest.raises(ValueError, match="outside requested extent"):
        validate_response(payload(THEMES[0], [rejected]), THEMES[0], split_bbox)


def test_label_fields_rejects_source_schema_drift():
    with pytest.raises(ValueError, match="required fields"):
        label_fields("Numer inwentaryzacyjny: D1007155")


def test_verified_layer_rejects_incomplete_whole_response(tmp_path):
    def fetcher(_theme, bbox, _cache_dir):
        response = {1: feature(1, "D1")}
        if bbox != BBOX:
            response[2] = feature(2, "D2")
        return response, {
            "url": "https://example.test",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "sha256": "a",
            "count": len(response),
        }

    with pytest.raises(ValueError, match="Whole/half mismatch"):
        download_warsaw_trees.verified_layer(THEMES[0], tmp_path, fetcher=fetcher)


def test_verified_layer_uses_orthogonal_partitions_when_full_response_is_truncated(tmp_path):
    def fetcher(_theme, bbox, _cache_dir):
        if bbox == BBOX:
            raise json.JSONDecodeError("truncated", "{", 1)
        response = {"opaque-source-id": feature("opaque-source-id", "D1")}
        return response, {
            "url": "https://example.test",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "sha256": "a",
            "count": 1,
        }

    records, requests, verification = download_warsaw_trees.verified_layer(
        THEMES[0], tmp_path, fetcher=fetcher
    )

    assert list(records) == ["opaque-source-id"]
    assert len(requests) == 4
    assert verification == "vertical-halves-equal-horizontal-halves"


def test_complete_tile_recursively_splits_truncated_partition(tmp_path):
    calls = []

    def fetcher(_theme, bbox, _cache_dir):
        calls.append(bbox)
        if bbox[2] - bbox[0] >= 0.3:
            raise json.JSONDecodeError("truncated", "{", 1)
        return {"opaque-source-id": feature("opaque-source-id", "D1")}, {
            "url": "https://example.test",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "sha256": "a",
            "count": 1,
        }

    records, requests = download_warsaw_trees.complete_tile(
        THEMES[0], (20.75, 52.05, 21.35, 52.4), tmp_path, fetcher
    )

    assert list(records) == ["opaque-source-id"]
    assert len(requests) == 8
    assert len(calls) == 15


def test_download_writes_validated_archive(tmp_path, monkeypatch):
    def fetcher(theme, _bbox, _cache_dir):
        position = THEMES.index(theme) + 1
        source_feature = feature(position, f"D{position}")
        return {position: source_feature}, {
            "url": f"https://example.test/{theme}",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "sha256": digest(source_feature),
            "count": 1,
        }

    monkeypatch.setattr(download_warsaw_trees, "now", lambda: "2026-01-01T00:00:00+00:00")
    output = tmp_path / "warsaw-trees.geojson"
    download_warsaw_trees.download(output, fetcher=fetcher)

    archive = json.loads(output.read_text(encoding="utf-8"))
    assert len(validate_archive(archive)) == len(THEMES)
    assert archive["features"][0]["properties"]["_treeseek_theme"] == THEMES[0]


def test_validate_archive_rejects_changed_feature_checksum(tmp_path, monkeypatch):
    def fetcher(theme, _bbox, _cache_dir):
        position = THEMES.index(theme) + 1
        source_feature = feature(position, f"D{position}")
        return {position: source_feature}, {
            "url": f"https://example.test/{theme}",
            "retrieved_at": "2026-01-01T00:00:00+00:00",
            "sha256": digest(source_feature),
            "count": 1,
        }

    monkeypatch.setattr(download_warsaw_trees, "now", lambda: "2026-01-01T00:00:00+00:00")
    output = tmp_path / "warsaw-trees.geojson"
    download_warsaw_trees.download(output, fetcher=fetcher)
    archive = json.loads(output.read_text(encoding="utf-8"))
    altered = copy.deepcopy(archive)
    altered["features"][0]["properties"]["NAZWA_SERWIS"] = "modified"

    with pytest.raises(ValueError, match="checksum"):
        validate_archive(altered)
