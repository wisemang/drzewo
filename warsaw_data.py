"""Validation for TreeSeek's Warsaw Baza Zieleni raw archive."""

import hashlib
import json
import math
from datetime import datetime

SOURCE = "Warsaw Baza Zieleni Tree Inventory"
BASE_URL = "https://mapa.um.warszawa.pl/mapviewer/dataserver/DANE_WAWA"
TERMS_URL = (
    "https://mapa.um.warszawa.pl/api/modul-mapowy/open/cms/"
    "Warunki-ponownego-wykorzystania-informacji-publicznej"
)
BBOX = (20.75, 52.05, 21.35, 52.40)
# MapViewer returns points slightly over a requested split boundary (observed 0.00018°).
# Keep this narrow enough to detect a wrong CRS or axis order.
BBOX_EDGE_OVERLAP = 0.001
FULL_LAYER_VERIFICATION = "whole-layer-equals-geographic-halves"
PARTITION_VERIFICATION = "vertical-halves-equal-horizontal-halves"
THEMES = tuple(
    f"BOS_ZIELEN_DRZEWA_{index}_{'WA' if index in (11, 12) else 'MOD_BOS'}"
    for index in range(1, 21)
)
LABEL_KEYS = (
    "Numer inwentaryzacyjny",
    "Nazwa polska",
    "Nazwa łacińska",
    "Obwód pnia w cm",
    "Jednostka zarządzająca",
    "Aktualność danych na dzień",
)


def digest(value):
    """Return a stable checksum for JSON-compatible source content."""
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def label_fields(label):
    """Parse the city's source label without discarding its original text."""
    if not isinstance(label, str):
        raise ValueError("Warsaw record has no original label")
    fields = {}
    for line in label.splitlines():
        if not line.strip():
            continue
        key, separator, value = line.partition(":")
        if not separator or key.strip() in fields:
            raise ValueError("Malformed or duplicate Warsaw label field")
        fields[key.strip()] = value.strip()
    if not set(LABEL_KEYS).issubset(fields):
        raise ValueError("Warsaw label schema changed; required fields missing")
    return fields


def known_text(value):
    """Normalize Warsaw's no-data markers to None."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    return None if text.casefold() in ("", "brak danych", "brak", "null") else text


def validate_feature(feature, bbox=BBOX):
    """Validate one returned MapViewer tree point and return its identity fields."""
    if feature.get("type") != "Feature":
        raise ValueError("Expected Warsaw feature")
    identifier = feature.get("_id")
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("Invalid Warsaw OBJECTID")
    geometry = feature.get("geometry") or {}
    coordinates = geometry.get("coordinates", [])
    if geometry.get("type") != "Point" or len(coordinates) != 2:
        raise ValueError("Warsaw requires two-dimensional Point geometry")
    if any(type(value) not in (int, float) or not math.isfinite(value) for value in coordinates):
        raise ValueError("Invalid Warsaw coordinates")
    longitude, latitude = coordinates
    # MapViewer rounds WGS84 coordinates and includes a small overlap at split boundaries.
    if not (bbox[0] - BBOX_EDGE_OVERLAP <= longitude <= bbox[2] + BBOX_EDGE_OVERLAP
            and bbox[1] - BBOX_EDGE_OVERLAP <= latitude <= bbox[3] + BBOX_EDGE_OVERLAP):
        raise ValueError("Warsaw coordinates outside requested extent; check CRS/axis order")
    properties = feature.get("properties") or {}
    inventory_number = properties.get("NAZWA_SERWIS")
    fields = label_fields(properties.get("_label_"))
    if not isinstance(inventory_number, str) or not inventory_number.strip():
        raise ValueError("Missing Warsaw inventory number")
    if fields["Numer inwentaryzacyjny"] != inventory_number:
        raise ValueError("Conflicting Warsaw inventory numbers")
    return identifier, inventory_number, fields


def validate_response(payload, theme, bbox):
    """Validate one MapViewer response before it is cached."""
    if (payload.get("type") != "FeatureCollection" or payload.get("srs") != 4326
            or payload.get("collectionName") != theme
            or not isinstance(payload.get("features"), list) or "mds_error" in payload):
        raise ValueError("Unexpected Warsaw response, service error or CRS")
    records = {}
    for feature in payload["features"]:
        objectid, _, _ = validate_feature(feature, bbox)
        if objectid in records:
            raise ValueError("Duplicate OBJECTID within Warsaw response")
        records[objectid] = feature
    return records


def validate_archive(data):
    """Fail closed on partial, corrupted, or incompatible Warsaw archives."""
    if data.get("type") != "FeatureCollection" or data.get("srs") != 4326:
        raise ValueError("Warsaw archive must declare WGS84 / srs 4326")
    features = data.get("features")
    metadata = data.get("treeseek", {})
    if not isinstance(features, list) or not features:
        raise ValueError("Empty or missing Warsaw features")
    if (metadata.get("format_version") != 1 or metadata.get("source_url") != BASE_URL
            or metadata.get("source") != SOURCE or metadata.get("bbox") != list(BBOX)
            or metadata.get("themes") != list(THEMES)
            or metadata.get("verification") != "independent-geographic-partitions"):
        raise ValueError("Unverified or partial Warsaw archive; use download-warsaw-data")
    theme_verification = metadata.get("theme_verification")
    if (not isinstance(theme_verification, dict) or set(theme_verification) != set(THEMES)
            or not set(theme_verification.values()).issubset(
                {FULL_LAYER_VERIFICATION, PARTITION_VERIFICATION}
            )):
        raise ValueError("Warsaw archive has invalid theme verification metadata")
    if (
        metadata.get("count") != len(features)
        or metadata.get("features_sha256") != digest(features)
    ):
        raise ValueError("Warsaw archive count/checksum mismatch")
    for key in ("started_at", "finished_at"):
        timestamp = datetime.fromisoformat(metadata.get(key, ""))
        if timestamp.tzinfo is None:
            raise ValueError("Warsaw provenance timestamps require a timezone")
    source_ids, inventory_numbers, import_objectids = set(), set(), set()
    counts = dict.fromkeys(THEMES, 0)
    for feature in features:
        source_id, inventory_number, _ = validate_feature(feature)
        objectid = feature.get("properties", {}).get("_treeseek_objectid")
        if not isinstance(objectid, int) or objectid < 1:
            raise ValueError("Warsaw archive lacks a valid TreeSeek objectid")
        if (source_id in source_ids or inventory_number in inventory_numbers
                or objectid in import_objectids):
            raise ValueError("Duplicate Warsaw object or inventory number")
        source_ids.add(source_id)
        inventory_numbers.add(inventory_number)
        import_objectids.add(objectid)
        theme = feature.get("properties", {}).get("_treeseek_theme")
        if theme not in counts:
            raise ValueError("Unexpected Warsaw source theme")
        counts[theme] += 1
    if metadata.get("theme_counts") != counts:
        raise ValueError("Warsaw theme counts do not match records")
    return features


def read_archive(filename):
    """Read and validate a full local Warsaw archive."""
    with open(filename, encoding="utf-8") as stream:
        data = json.load(stream)
    validate_archive(data)
    return data
