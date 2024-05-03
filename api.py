#!/usr/bin/env python3

from os import environ
from flask import Flask, render_template, request, jsonify
import psycopg2

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/nearest', methods=['GET'])
def nearest():
    lat = request.args.get('lat', type=float)
    lng = request.args.get('lng', type=float)
    limit = request.args.get('limit', type=int) or 10

    db_params = {
        "database": environ.get('DRZEWO_DB', 'drzewo'),
        "user": environ.get('DRZEWO_DB_USER', 'greg'),
        "password": environ.get('DRZEWO_DB_PW', None),
        "host": environ.get('DRZEWO_DB_HOST', 'localhost'),
        "port": environ.get('DRZEWO_DB_PORT', '5432')
    }


    conn = psycopg2.connect(**db_params)
    cur = conn.cursor()
    cur.execute("""
        SELECT source, common_name, botanical_name, address, streetname, 
        ST_Distance(geom, ST_MakePoint(%s, %s)::geography) AS distance,
        ST_X(ST_GeometryN(geom, 1)) AS longitude, ST_Y(ST_GeometryN(geom, 1)) AS latitude
        FROM street_trees
        ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
        LIMIT %s;
    """, (lng, lat, lng, lat, limit))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify([{'source': row[0], 'common_name': row[1], 'botanical_name':row[2], 'address':row[3], 'streetname': row[4], 'distance': row[5], 'longitude': row[6], 'latitude': row[7]} for row in results])




if __name__ == '__main__':
    app.run(debug=True)
