#!/usr/bin/env python3

from math import isfinite
from os import environ

import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

load_dotenv()

app = Flask(__name__)
DEFAULT_LIMIT = 60
MAX_LIMIT = 150
MIN_RADIUS_M = 1.0
MAX_RADIUS_M = 5000.0


def db_params():
    """Return database connection parameters from the environment."""
    return {
        "database": environ.get('DRZEWO_DB', 'drzewo'),
        "user": environ.get('DRZEWO_DB_USER'),
        "password": environ.get('DRZEWO_DB_PW'),
        "host": environ.get('DRZEWO_DB_HOST', 'localhost'),
        "port": environ.get('DRZEWO_DB_PORT', '5432')
    }

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/manifest.webmanifest')
def manifest():
    return send_from_directory("static", "manifest.webmanifest")


@app.route('/sw.js')
def service_worker():
    response = send_from_directory("static", "sw.js")
    response.headers["Service-Worker-Allowed"] = "/"
    return response


@app.route('/offline')
def offline():
    return send_from_directory("static", "offline.html")

@app.route('/nearest', methods=['GET'])
def nearest():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    limit = request.args.get('limit', type=int) or DEFAULT_LIMIT

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng query parameters are required"}), 400

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return jsonify({"error": "lat/lng are out of bounds"}), 400

    # Keep request size bounded for predictable query cost.
    limit = max(1, min(limit, MAX_LIMIT))

    max_distance_m_raw = request.args.get('max_distance_m')
    max_distance_m = None
    if max_distance_m_raw is not None:
        try:
            max_distance_m = float(max_distance_m_raw)
        except ValueError:
            return jsonify({"error": "max_distance_m must be a number"}), 400
        max_distance_m = max(MIN_RADIUS_M, min(max_distance_m, MAX_RADIUS_M))

    conn = psycopg2.connect(**db_params())
    try:
        cur = conn.cursor()
        where_clause = ""
        query_params = [lng, lat]

        if max_distance_m is not None:
            where_clause = """
            WHERE ST_DWithin(
                geom::geography,
                ST_MakePoint(%s, %s)::geography,
                %s
            )
            """
            query_params.extend([lng, lat, max_distance_m])

        query_params.extend([lng, lat, limit])

        cur.execute(f"""
            SELECT source, objectid, common_name, botanical_name, address, streetname,
            dbh_trunk, tree_position_number,
            to_jsonb(street_trees)->>'original_common_name' AS original_common_name,
            street_trees.species_id,
            ST_Distance(geom::geography, ST_MakePoint(%s, %s)::geography) AS distance,
            ST_X(ST_GeometryN(geom, 1)) AS longitude, ST_Y(ST_GeometryN(geom, 1)) AS latitude
            FROM street_trees
            {where_clause}
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT %s;
        """, query_params)
        results = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    response = [
        {
            "source": row[0],
            "objectid": row[1],
            "common_name": row[2],
            "botanical_name": row[3],
            "address": row[4],
            "streetname": row[5],
            "dbh": row[6],
            "pos": row[7],
            "original_common_name": row[8],
            "species_id": int(row[9]) if row[9] is not None else None,
            "distance": row[10],
            "longitude": row[11],
            "latitude": row[12],
        }
        for row in results
    ]
    return jsonify(response)


@app.route('/species/<int:species_id>/profile', methods=['GET'])
def species_profile(species_id):
    local_stats_context, local_stats_error = parse_local_stats_context()
    if local_stats_error is not None:
        return local_stats_error

    conn = psycopg2.connect(**db_params())
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                species.id,
                species.species_key,
                species.canonical_botanical_name,
                species.display_common_name,
                species.wikipedia_url,
                profile.summary,
                profile.taxonomy,
                profile.canonical_url,
                profile.source_system,
                profile.source_url,
                profile.retrieved_at,
                profile.method_version,
                profile.confidence,
                profile.license_name,
                profile.license_url,
                profile.attribution
            FROM species
            LEFT JOIN species_profile AS profile
                ON profile.species_id = species.id
                AND profile.source_system = 'wikipedia'
            WHERE species.id = %s
            ORDER BY profile.retrieved_at DESC NULLS LAST
            LIMIT 1;
            """,
            (species_id,),
        )
        row = cur.fetchone()

        local_stats = None
        if row is not None and local_stats_context is not None:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS same_species_count,
                    MAX(dbh_trunk) AS largest_dbh
                FROM street_trees
                WHERE species_id = %s
                AND ST_DWithin(
                    geom::geography,
                    ST_MakePoint(%s, %s)::geography,
                    %s
                );
                """,
                (
                    species_id,
                    local_stats_context["lng"],
                    local_stats_context["lat"],
                    local_stats_context["radius_m"],
                ),
            )
            stats_row = cur.fetchone()
            same_species_count = stats_row[0] if stats_row and stats_row[0] is not None else 0
            local_stats = {
                "radius_m": local_stats_context["radius_m"],
                "same_species_count": same_species_count,
                "largest_dbh": stats_row[1] if stats_row else None,
            }
        benefits = None
        if row is not None:
            cur.execute(
                """
                SELECT
                    metric_type,
                    scope,
                    label,
                    text,
                    value,
                    unit,
                    min_value,
                    max_value,
                    currency,
                    region,
                    method_version,
                    assumptions,
                    confidence,
                    source_system,
                    source_url,
                    retrieved_at,
                    calculated_at,
                    license_name,
                    license_url,
                    attribution,
                    caveat
                FROM species_benefit
                WHERE species_id = %s
                  AND scope = 'species'
                ORDER BY
                    metric_type,
                    retrieved_at DESC NULLS LAST,
                    calculated_at DESC NULLS LAST,
                    id;
                """,
                (species_id,),
            )
            benefits = serialize_species_benefits(cur.fetchall())
        cur.close()
    finally:
        conn.close()

    if row is None:
        return jsonify({"error": "species not found"}), 404

    summary = None
    if row[8] is not None and row[5] is not None:
        summary = {
            "available": True,
            "text": row[5],
            "source_system": row[8],
            "source_url": row[9] or row[7],
            "source_title": (row[6] or {}).get("canonical_botanical_name") or row[2],
            "license": row[13],
            "license_url": row[14],
            "attribution": row[15],
            "confidence": row[12],
            "retrieved_at": serialize_datetime(row[10]),
            "method_version": row[11],
        }

    return jsonify(
        {
            "species_id": row[0],
            "species_key": row[1],
            "common_name": row[3],
            "botanical_name": row[2],
            "sections": {
                "summary": summary,
                "benefits": benefits,
                "risk": None,
                "media": None,
                "local_stats": local_stats,
            },
        }
    )


def parse_local_stats_context():
    """Return nearby local-stats context when all required query params are present."""
    lat_raw = request.args.get("lat")
    lng_raw = request.args.get("lng")
    radius_raw = request.args.get("radius_m")

    if lat_raw is None or lng_raw is None or radius_raw is None:
        return None, None

    try:
        lat = float(lat_raw)
        lng = float(lng_raw)
        radius_m = float(radius_raw)
    except ValueError:
        return None, (jsonify({"error": "lat, lng, and radius_m must be numbers"}), 400)

    if not isfinite(lat) or not isfinite(lng) or not isfinite(radius_m):
        return None, (jsonify({"error": "lat, lng, and radius_m must be finite numbers"}), 400)

    if not (-90 <= lat <= 90) or not (-180 <= lng <= 180):
        return None, (jsonify({"error": "lat/lng are out of bounds"}), 400)

    radius_m = max(MIN_RADIUS_M, min(radius_m, MAX_RADIUS_M))
    if radius_m.is_integer():
        radius_m = int(radius_m)

    return {"lat": lat, "lng": lng, "radius_m": radius_m}, None


def serialize_datetime(value):
    """Return an ISO string for DB datetimes, preserving test strings as-is."""
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()


def serialize_species_benefits(rows):
    """Return the API benefits section or null when no valid items exist."""
    items = []
    for row in rows:
        item = serialize_species_benefit_item(row)
        if item is not None:
            items.append(item)
    if not items:
        return None
    return {"available": True, "items": items}


def serialize_species_benefit_item(row):
    """Return a single benefit item when it has enough data to be trustworthy."""
    (
        metric_type,
        scope,
        label,
        text,
        value,
        unit,
        min_value,
        max_value,
        currency,
        region,
        method_version,
        assumptions,
        confidence,
        source_system,
        source_url,
        retrieved_at,
        calculated_at,
        license_name,
        license_url,
        attribution,
        caveat,
    ) = row

    if not all([metric_type, scope, method_version, confidence, source_system, source_url]):
        return None

    has_qualitative_text = bool(text)
    has_estimate_values = any(number is not None for number in (value, min_value, max_value))
    if not has_qualitative_text and not has_estimate_values:
        return None

    item = {
        "metric_type": metric_type,
        "scope": scope,
        "confidence": confidence,
        "source_system": source_system,
        "source_url": source_url,
        "method_version": method_version,
    }
    optional_fields = {
        "label": label,
        "text": text,
        "value": value,
        "unit": unit,
        "min_value": min_value,
        "max_value": max_value,
        "currency": currency,
        "region": region,
        "assumptions": assumptions,
        "retrieved_at": serialize_datetime(retrieved_at),
        "calculated_at": serialize_datetime(calculated_at),
        "license": license_name,
        "license_url": license_url,
        "attribution": attribution,
        "caveat": caveat,
    }
    for key, field_value in optional_fields.items():
        if field_value is not None:
            item[key] = field_value
    return item




if __name__ == '__main__':
    app.run(debug=True)
