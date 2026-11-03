#!/usr/bin/env python3
"""Download and validate Warsaw Baza Zieleni tree points without writing to the database."""

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from warsaw_data import (  # noqa: E402
    BASE_URL,
    BBOX,
    FULL_LAYER_VERIFICATION,
    PARTITION_VERIFICATION,
    SOURCE,
    TERMS_URL,
    THEMES,
    digest,
    validate_archive,
    validate_response,
)


def now():
    return datetime.now(timezone.utc).isoformat()


def request_url(theme, bbox):
    """Build the exact public MapViewer request URL."""
    return BASE_URL + "?" + urlencode({
        "t": theme,
        "bbox": ",".join(str(value) for value in bbox),
        "bbox_srid": 4326,
        "to_srid": 4326,
        "include_label_box": "false",
    })


def decode_response(stream):
    """Decode MapViewer JSON, including its occasional unescaped label controls."""
    return json.load(stream, strict=False)


def fetch(theme, bbox, cache_dir):
    """Cache an exact request and return validated records plus acquisition provenance."""
    url = request_url(theme, bbox)
    cache_path = cache_dir / f"{digest(url)}.json"
    if cache_path.exists():
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("url") != url or cached.get("sha256") != digest(cached.get("payload")):
            raise ValueError(f"Invalid cached response: {cache_path}")
    else:
        for attempt in range(3):
            try:
                request = Request(url, headers={"User-Agent": "TreeSeek-Warsaw-download/1.0"})
                with urlopen(request, timeout=120) as response:
                    payload = decode_response(response)
                validate_response(payload, theme, bbox)
                cached = {
                    "url": url,
                    "retrieved_at": now(),
                    "payload": payload,
                    "sha256": digest(payload),
                }
                cache_dir.mkdir(parents=True, exist_ok=True)
                temporary = cache_path.with_suffix(".tmp")
                temporary.write_text(json.dumps(cached, ensure_ascii=False), encoding="utf-8")
                temporary.replace(cache_path)
                time.sleep(0.5)
                break
            except (OSError, ValueError):
                if attempt == 2:
                    raise
                time.sleep(2 ** attempt)
    records = validate_response(cached["payload"], theme, bbox)
    provenance = {key: cached[key] for key in ("url", "retrieved_at", "sha256")}
    provenance["count"] = len(records)
    return records, provenance


def verified_layer(theme, cache_dir, fetcher=fetch):
    """Require a whole extent to equal the union of independent geographic halves."""
    try:
        whole, audit = fetcher(theme, BBOX, cache_dir)
    except json.JSONDecodeError:
        return verified_partitions(theme, cache_dir, fetcher)
    mid_longitude = (BBOX[0] + BBOX[2]) / 2
    halves = (
        (BBOX[0], BBOX[1], mid_longitude, BBOX[3]),
        (mid_longitude, BBOX[1], BBOX[2], BBOX[3]),
    )
    combined = {}
    requests = [audit]
    for bbox in halves:
        records, audit = fetcher(theme, bbox, cache_dir)
        requests.append(audit)
        for objectid, feature in records.items():
            if objectid in combined and combined[objectid] != feature:
                raise ValueError(f"Conflicting boundary record in {theme}: {objectid}")
            combined[objectid] = feature
    if whole != combined:
        raise ValueError(f"Whole/half mismatch for {theme}; possible truncation or source change")
    return whole, requests, FULL_LAYER_VERIFICATION


def combined_partition(theme, cache_dir, boxes, fetcher):
    """Fetch overlapping tiles and return their deduplicated records and audit trail."""
    combined, requests = {}, []
    for bbox in boxes:
        records, audits = complete_tile(theme, bbox, cache_dir, fetcher)
        requests.extend(audits)
        for objectid, feature in records.items():
            if objectid in combined and combined[objectid] != feature:
                raise ValueError(f"Conflicting boundary record in {theme}: {objectid}")
            combined[objectid] = feature
    return combined, requests


def complete_tile(theme, bbox, cache_dir, fetcher, depth=0):
    """Recursively split a tile when MapViewer truncates its response body."""
    try:
        records, audit = fetcher(theme, bbox, cache_dir)
        return records, [audit]
    except json.JSONDecodeError:
        if depth >= 8:
            raise ValueError(f"MapViewer repeatedly truncated {theme} at {bbox}") from None
        if bbox[2] - bbox[0] >= bbox[3] - bbox[1]:
            midpoint = (bbox[0] + bbox[2]) / 2
            children = ((bbox[0], bbox[1], midpoint, bbox[3]),
                        (midpoint, bbox[1], bbox[2], bbox[3]))
        else:
            midpoint = (bbox[1] + bbox[3]) / 2
            children = ((bbox[0], bbox[1], bbox[2], midpoint),
                        (bbox[0], midpoint, bbox[2], bbox[3]))
        return combined_partition(theme, cache_dir, children, fetcher)


def verified_partitions(theme, cache_dir, fetcher):
    """Compare orthogonal split queries when a complete response is too large to transport."""
    mid_longitude = (BBOX[0] + BBOX[2]) / 2
    mid_latitude = (BBOX[1] + BBOX[3]) / 2
    vertical, vertical_requests = combined_partition(
        theme,
        cache_dir,
        ((BBOX[0], BBOX[1], mid_longitude, BBOX[3]),
         (mid_longitude, BBOX[1], BBOX[2], BBOX[3])),
        fetcher,
    )
    horizontal, horizontal_requests = combined_partition(
        theme,
        cache_dir,
        ((BBOX[0], BBOX[1], BBOX[2], mid_latitude),
         (BBOX[0], mid_latitude, BBOX[2], BBOX[3])),
        fetcher,
    )
    if vertical != horizontal:
        raise ValueError(f"Partition mismatch for {theme}; possible truncation or source change")
    return vertical, vertical_requests + horizontal_requests, PARTITION_VERIFICATION


def download(output, overwrite=False, cache_dir=None, fetcher=fetch):
    """Write a fully audited raw archive only after every theme validates."""
    if output.exists() and not overwrite:
        raise ValueError(f"Output exists: {output}; use --overwrite")
    cache_dir = cache_dir or output.parent / ".warsaw-responses"
    started_at = now()
    features, objectids, inventory_numbers, requests, theme_counts, theme_verification = (
        [], set(), set(), [], {}, {}
    )
    for theme in THEMES:
        records, audit, verification = verified_layer(theme, cache_dir, fetcher)
        requests.extend(audit)
        theme_counts[theme] = len(records)
        theme_verification[theme] = verification
        for objectid, feature in sorted(records.items()):
            inventory_number = feature["properties"]["NAZWA_SERWIS"]
            if objectid in objectids or inventory_number in inventory_numbers:
                raise ValueError("Cross-theme duplicate; review city identity before importing")
            objectids.add(objectid)
            inventory_numbers.add(inventory_number)
            features.append({**feature, "properties": {
                **feature["properties"],
                "_treeseek_theme": theme,
            }})
        print(f"{theme}: {len(records)} verified points", flush=True)
    for objectid, feature in enumerate(sorted(features, key=lambda item: item["_id"]), start=1):
        feature["properties"]["_treeseek_objectid"] = objectid
    archive = {
        "type": "FeatureCollection",
        "srs": 4326,
        "treeseek": {
            "format_version": 1,
            "source": SOURCE,
            "source_url": BASE_URL,
            "attribution": "Urząd m.st. Warszawy",
            "terms_url": TERMS_URL,
            "started_at": started_at,
            "finished_at": now(),
            "bbox": list(BBOX),
            "themes": list(THEMES),
            "count": len(features),
            "theme_counts": theme_counts,
            "features_sha256": digest(features),
            "requests": requests,
            "verification": "independent-geographic-partitions",
            "theme_verification": theme_verification,
            "coverage_note": "No authoritative total is exposed; partition agreement is not proof "
            "of all Warsaw trees.",
            "modifications": "Coordinates requested in EPSG:4326; acquisition theme and "
            "archive-local integer objectid added. "
            "Original identifiers, properties and labels retained.",
        },
        "features": features,
    }
    validate_archive(archive)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    try:
        temporary.write_text(json.dumps(archive, ensure_ascii=False, allow_nan=False),
                             encoding="utf-8")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    print(f"Wrote {len(features)} points to {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/raw/warsaw") / date.today().isoformat() / "warsaw-trees.geojson",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--cache-dir", type=Path)
    args = parser.parse_args()
    download(args.output, args.overwrite, args.cache_dir)


if __name__ == "__main__":
    main()
