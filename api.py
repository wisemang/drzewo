#!/usr/bin/env python3

from os import environ

import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
DEFAULT_LIMIT = 10
MAX_LIMIT = 100
MIN_RADIUS_M = 1.0
MAX_RADIUS_M = 5000.0

@app.route('/')
def home():
    return render_template('index.html')

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

    db_params = {
        "database": environ.get('DRZEWO_DB', 'drzewo'),
        "user": environ.get('DRZEWO_DB_USER'),
        "password": environ.get('DRZEWO_DB_PW'),
        "host": environ.get('DRZEWO_DB_HOST', 'localhost'),
        "port": environ.get('DRZEWO_DB_PORT', '5432')
    }


    conn = psycopg2.connect(**db_params)
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
            "distance": row[8],
            "longitude": row[9],
            "latitude": row[10],
        }
        for row in results
    ]
    return jsonify(response)




if __name__ == '__main__':
    app.run(debug=True)
