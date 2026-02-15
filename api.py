#!/usr/bin/env python3

from os import environ
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
import psycopg2

load_dotenv()

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/nearest', methods=['GET'])
def nearest():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    limit = request.args.get('limit', type=int) or 10

    if lat is None or lng is None:
        return jsonify({"error": "lat and lng query parameters are required"}), 400

    # Keep request size bounded for predictable query cost.
    limit = max(1, min(limit, 100))

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
        cur.execute("""
            SELECT source, objectid, common_name, botanical_name, address, streetname,
            dbh_trunk, tree_position_number,
            ST_Distance(geom, ST_MakePoint(%s, %s)::geography) AS distance,
            ST_X(ST_GeometryN(geom, 1)) AS longitude, ST_Y(ST_GeometryN(geom, 1)) AS latitude
            FROM street_trees
            ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
            LIMIT %s;
        """, (lng, lat, lng, lat, limit))
        results = cur.fetchall()
        cur.close()
    finally:
        conn.close()

    return jsonify([{'source': row[0], 'objectid': row[1], 'common_name': row[2], 'botanical_name':row[3], 'address':row[4], 'streetname': row[5], 'dbh':row[6], 'pos':row[7], 'distance': row[8], 'longitude': row[9], 'latitude': row[10]} for row in results])




if __name__ == '__main__':
    app.run(debug=True)
