#!/usr/bin/env python3

import argparse
import json
from datetime import date
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

BASE_URL = (
    "https://vector.sitg.ge.ch/arcgis/rest/services/Hosted/"
    "SIPV_ICA_WEB_PUBLIC_TOT/FeatureServer/0/query"
)
DEFAULT_PAGE_SIZE = 2000


def fetch_json(params):
    """Fetch one ArcGIS REST JSON response."""
    url = f"{BASE_URL}?{urlencode(params)}"
    with urlopen(url, timeout=120) as response:
        return json.load(response)


def remote_feature_count():
    """Return the number of features currently exposed by the Geneva service."""
    payload = fetch_json(
        {
            "where": "1=1",
            "returnCountOnly": "true",
            "f": "json",
        }
    )
    return int(payload["count"])


def default_output_path():
    """Use the repository's raw archive layout."""
    return Path("data") / "raw" / "geneva" / date.today().isoformat() / "geneva-trees-full.geojson"


def write_feature_collection(output_path, page_size, overwrite):
    """Download all Geneva tree pages and write one GeoJSON FeatureCollection."""
    if output_path.exists() and not overwrite:
        raise SystemExit(f"Output already exists: {output_path}. Use --overwrite to replace it.")

    total = remote_feature_count()
    print(f"Remote feature count: {total}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    downloaded = 0
    first_feature = True
    with temp_path.open("w", encoding="utf-8") as output:
        output.write('{"type":"FeatureCollection","features":[')
        for offset in range(0, total, page_size):
            payload = fetch_json(
                {
                    "where": "1=1",
                    "outFields": "*",
                    "f": "geojson",
                    "resultOffset": offset,
                    "resultRecordCount": page_size,
                    "orderByFields": "objectid",
                }
            )
            features = payload.get("features", [])
            if not features:
                break

            for feature in features:
                if not first_feature:
                    output.write(",")
                json.dump(feature, output, separators=(",", ":"))
                first_feature = False

            downloaded += len(features)
            print(f"Downloaded {downloaded} / {total}")

        output.write("]}")

    if downloaded != total:
        temp_path.unlink(missing_ok=True)
        raise SystemExit(f"Expected {total} features, downloaded {downloaded}")

    temp_path.replace(output_path)
    print(f"Wrote {downloaded} features to {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Download the full Geneva SITG tree inventory as paged GeoJSON."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output_path(),
        help="Output GeoJSON path (default: data/raw/geneva/<today>/geneva-trees-full.geojson)",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="FeatureServer page size (default: 2000)",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output file",
    )

    args = parser.parse_args()
    write_feature_collection(args.output, max(1, args.page_size), args.overwrite)


if __name__ == "__main__":
    main()
